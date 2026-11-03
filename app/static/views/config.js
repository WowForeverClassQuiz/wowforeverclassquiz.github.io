// Configuration management: export, import, reset to the seed data, and revision history with restore.
import { h, clear, toast, badge, confirmDialog, errorList, download } from "../ui.js";
import { get, post } from "../api.js";
import { state, ensureConfig } from "../state.js";

let root, cfg, historyLimit = 25;

export async function render(container) {
  root = container;
  cfg = await ensureConfig(true);
  const history = await get("/config/history", { limit: historyLimit });
  const specCount = cfg.classes.reduce((s, c) => s + c.specializations.length, 0);
  const importHost = h("div");

  clear(root).append(
    h("div", { class: "page-head" }, h("div", {}, h("h1", {}, "Configuration"),
      h("p", {}, "Every change is a numbered revision. Import and reset write a backup file first, and the original seed configuration can always be restored."))),
    h("div", { class: "card" },
      h("div", { class: "stats" },
        stat(`r${cfg.revision}`, "current revision"), stat(String(cfg.questions.length), "questions"), stat(String(cfg.classes.length), "classes"),
        stat(String(specCount), "specializations"), stat(String(cfg.traits.length), "traits"), stat(String(cfg.builds.length), "builds"),
        stat(cfg.talent_catalog ? cfg.talent_catalog.client_version : "none", "talent data"), stat(cfg.scoring.algorithm_version, "algorithm")),
      h("div", { class: "row", style: { marginTop: "16px" } },
        h("button", { class: "btn primary", type: "button", onclick: exportConfig }, "Export configuration"),
        h("label", { class: "btn", style: { cursor: "pointer" } }, "Import configuration…", h("input", { type: "file", accept: "application/json,.json", hidden: true, onchange: (e) => pickImport(e, importHost) })),
        h("button", { class: "btn danger", type: "button", onclick: resetConfig }, "Reset to original"))),
    importHost,
    h("div", { class: "card" }, h("h3", {}, "Revision history"),
      h("div", { class: "table-wrap" }, h("table", {},
        h("thead", {}, h("tr", {}, ["Revision", "When (UTC)", "Type", "Change", ""].map((t) => h("th", {}, t)))),
        h("tbody", {}, history.map((e) => h("tr", {},
          h("td", {}, h("b", {}, `r${e.revision}`), e.revision === cfg.revision ? " " : "", e.revision === cfg.revision ? badge("current", "ok") : null),
          h("td", {}, e.created_at.replace("T", " ").replace("+00:00", "")), h("td", {}, badge(e.change_type, "")),
          h("td", { class: "wrap" }, e.change_description,
            e.change_detail && e.change_detail.before ? h("details", { style: { marginTop: "6px" } }, h("summary", {}, "Before / after"), diff(e.change_detail)) : null),
          h("td", {}, e.revision === cfg.revision ? null : h("button", { class: "btn small", type: "button", onclick: () => restore(e.revision) }, "Restore"))))))),
      history.length >= historyLimit ? h("div", { class: "row", style: { marginTop: "10px" } }, h("button", { class: "btn small", type: "button", onclick: () => { historyLimit += 50; render(root); } }, "Show older revisions")) : null),
  );
}

const stat = (v, l) => h("div", { class: "stat" }, h("b", {}, v), h("span", {}, l));

function diff(detail) {
  const fmtv = (o) => (o === undefined ? "(none)" : JSON.stringify(o, null, 2));
  return h("div", { class: "grid two" },
    h("div", {}, h("h4", {}, "Before"), h("pre", { class: "mono", style: { whiteSpace: "pre-wrap", fontSize: "0.78rem", margin: 0 } }, fmtv(detail.before))),
    h("div", {}, h("h4", {}, "After"), h("pre", { class: "mono", style: { whiteSpace: "pre-wrap", fontSize: "0.78rem", margin: 0 } }, fmtv(detail.after))));
}

async function exportConfig() {
  try {
    const c = await get("/config/export");
    download(`wow-oracle-config-r${c.revision}.json`, JSON.stringify(c, null, 2));
    toast("Configuration exported.", "ok");
  } catch (e) { toast(e.message, "bad", 7000); }
}

async function pickImport(e, host) {
  const file = e.target.files[0];
  e.target.value = "";
  if (!file) return;
  let data;
  try { data = JSON.parse(await file.text()); } catch (err) { clear(host).append(h("div", { class: "card" }, h("h3", {}, "Not a JSON file"), h("p", {}, err.message))); return; }
  const c = data.config && data.questions === undefined ? data.config : data;   // accept an import wrapper too
  const desc = h("input", { type: "text", value: `Imported ${file.name}`, "aria-label": "Description of this import" });
  const result = h("div");
  clear(host).append(h("div", { class: "card" },
    h("h3", {}, `Import ${file.name}`),
    h("p", {}, `${(c.questions || []).length} questions · ${(c.classes || []).length} classes · ${(c.traits || []).length} traits · ${(c.builds || []).length} builds · talent data: ${c.talent_catalog ? c.talent_catalog.client_version : "none"}`),
    h("p", { class: "note" }, "The server validates the file before changing anything and saves a backup of the current configuration first. The imported file's own revision number is ignored."),
    h("label", { class: "field", style: { margin: "12px 0" } }, "Description", desc),
    h("div", { class: "row" },
      h("button", { class: "btn primary", type: "button", onclick: async () => {
        if (!(await confirmDialog("This replaces the whole current configuration (a backup is saved).", { title: "Import configuration?", confirmText: "Import" }))) return;
        try {
          const r = await post("/config/import", { expected_revision: cfg.revision, config: c, description: desc.value || null });
          toast(`Imported as revision ${r.revision}. Backup: ${r.backup_path}`, "ok", 9000);
          state.adminEval = null;
          render(root);
        } catch (err) { clear(result).append(h("p", {}, h("b", {}, "Import rejected. Nothing was changed.")), errorList(err)); }
      } }, "Validate and import"),
      h("button", { class: "btn", type: "button", onclick: () => clear(host) }, "Cancel")),
    result));
}

async function resetConfig() {
  if (!(await confirmDialog("This replaces every question, weight, profile, build and talent catalog with the original seed configuration. A backup file is written first and the history keeps every earlier revision.", { title: "Reset to the original configuration?", confirmText: "Reset", danger: true, typed: "RESET" }))) return;
  try {
    const r = await post("/config/reset", { expected_revision: cfg.revision, confirm: true });
    toast(`Reset complete (revision ${r.revision}). Backup: ${r.backup_path}`, "ok", 9000);
    state.adminEval = null;
    render(root);
  } catch (e) { toast(e.message, "bad", 8000); }
}

async function restore(revision) {
  if (!(await confirmDialog(`Make revision ${revision} current again? This creates a new revision (and a backup); nothing is deleted.`, { title: `Restore revision ${revision}`, confirmText: "Restore" }))) return;
  try {
    const r = await post(`/config/history/${revision}/restore`, { expected_revision: cfg.revision });
    toast(`Restored revision ${revision} as revision ${r.revision}.`, "ok", 7000);
    render(root);
  } catch (e) { toast(e.message, "bad", 8000); }
}
