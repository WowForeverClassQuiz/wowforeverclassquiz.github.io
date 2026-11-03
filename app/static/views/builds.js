// Build Editor: talent catalog import, build records per specialization, talent allocation with live validation.
// Builds never affect personality scoring. A build can only be "verified" if the server validates it
// against imported talent data.
import { h, clear, append, toast, badge, confirmDialog, errorList, roleLabel, purposeLabel, debounce } from "../ui.js";
import { get, post, patch, put, del } from "../api.js";
import { state, ensureConfig } from "../state.js";

let root, cfg, catalog;           // catalog = full TalentCatalog or null
let clsId = "druid", specId = "balance";
let list = [];                    // BuildDetail[] for the selected specialization
let draft = null, isNew = false, editorHost, listHost, catalogHost, validationHost, counters;
let dirty = false;

const PURPOSES = ["leveling_pve", "solo_leveling", "dungeon_healing", "dungeon_tanking", "dungeon_damage", "raid_60", "pvp", "hybrid"];
const lines = (t) => t.split("\n").map((s) => s.trim()).filter(Boolean);
const slug = (s) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

export async function render(container) {
  root = container;
  cfg = await ensureConfig(true);
  const cat = await get("/talents/catalog", { full: true });
  catalog = cat.available ? cat.catalog : null;
  if (!cfg.classes.some((c) => c.id === clsId)) clsId = cfg.classes[0].id;
  if (!cfg.classes.find((c) => c.id === clsId).specializations.some((s) => s.id === specId)) specId = cfg.classes.find((c) => c.id === clsId).specializations[0].id;
  draft = null; dirty = false;
  state.dirtyGuard = (silent) => !dirty || (silent ? false : confirm("The build editor has unsaved changes. Discard them?"));
  await draw();
}

const specOf = () => cfg.classes.find((c) => c.id === clsId).specializations.find((s) => s.id === specId);
const catClass = () => (catalog ? catalog.classes.find((c) => c.id === clsId) : null);

async function loadList() {
  list = (await get("/builds", { class_id: clsId, specialization_id: specId })).builds;
}

async function draw() {
  await loadList();
  clear(root);
  catalogHost = h("div");
  listHost = h("div");
  editorHost = h("div");
  root.append(
    h("div", { class: "page-head" }, h("div", {}, h("h1", {}, "Build Editor"),
      h("p", {}, "Talent builds are chosen after the quiz picks a specialization. They never change personality scores."))),
    catalogHost, listHost, editorHost);
  drawCatalog();
  drawList();
  drawEditor();
}

// ---------------------------------------------------------------------------- catalog
function drawCatalog() {
  const fileInput = h("input", { type: "file", accept: "application/json,.json", "aria-label": "Talent catalog JSON file", onchange: importCatalog });
  clear(catalogHost).append(h("div", { class: "card" },
    h("h3", {}, "Talent data"),
    catalog
      ? h("div", { class: "stack" },
          h("div", { class: "row" }, badge(catalog.data_status === "draft" ? "draft data" : "imported", catalog.data_status === "draft" ? "warn" : "ok"),
            h("span", {}, `${catalog.game} · client ${catalog.client_version} · `, catalog.classes.length, " class(es) · source: ", catalog.source),
            h("button", { class: "btn small danger", type: "button", onclick: removeCatalog }, "Remove")),
          catalog.data_status === "draft"
            ? h("div", { class: "note warn" }, "This talent data is a draft and was not read from the game client. Allocations are checked against it, but builds cannot be marked verified. ", catalog.notes || "")
            : null)
      : h("div", { class: "note warn" }, "No talent data has been imported. Builds can be stored as drafts, but none can be marked verified, and no talent allocation can be checked."),
    h("div", { class: "row", style: { marginTop: "12px" } }, h("label", { class: "field" }, catalog ? "Replace talent catalog (JSON)" : "Import talent catalog (JSON)", fileInput)),
    h("details", { style: { marginTop: "12px" } }, h("summary", {}, "Catalog file format"),
      h("p", {}, "Use real talent data for the current World of Warcraft: Forever client. The application ships none and never invents talents."),
      h("pre", { class: "mono", style: { overflow: "auto", background: "var(--surface-2)", padding: "10px", borderRadius: "8px", fontSize: "0.8rem" } },
        JSON.stringify({ game: "World of Warcraft: Forever", client_version: "<build number>", source: "<where the data came from>", retrieved_at: "YYYY-MM-DD", points_per_tier: 5,
          classes: [{ id: "druid", trees: [{ id: "balance", name: "Balance", talents: [{ id: "<talent-id>", name: "<Talent name>", tier: 0, column: 0, max_rank: 5, requires: [{ talent_id: "<other-talent-id>", rank: 5 }] }] }] }] }, null, 2)),
      h("p", { class: "muted", style: { fontSize: "0.85rem" } }, "tier is the zero-based row. points_per_tier is the number of points that must be spent in earlier rows of the same tree for each row of depth. Tree ids must match this app's specialization ids."))));
}

async function importCatalog(e) {
  const file = e.target.files[0];
  if (!file) return;
  try {
    const data = JSON.parse(await file.text());
    if (catalog && !(await confirmDialog("Replacing the catalog re-checks every verified build; any that no longer validate are downgraded to 'unverified'.", { title: "Replace talent data?", confirmText: "Replace" }))) { e.target.value = ""; return; }
    const r = await put("/talents/catalog", { expected_revision: cfg.revision, catalog: data });
    toast(`Talent data imported.${r.downgraded_builds.length ? ` Downgraded: ${r.downgraded_builds.join(", ")}.` : ""}`, r.downgraded_builds.length ? "warn" : "ok", 7000);
    await render(root);
  } catch (err) {
    clear(catalogHost.querySelector(".card")).append(h("h3", {}, "Import failed"), errorList(err), h("button", { class: "btn small", type: "button", onclick: drawCatalog }, "Dismiss"));
    e.target.value = "";
  }
}

async function removeCatalog() {
  if (!(await confirmDialog("Verified builds will be downgraded to 'unverified'.", { title: "Remove talent data?", confirmText: "Remove", danger: true }))) return;
  try { await put("/talents/catalog", { expected_revision: cfg.revision, catalog: null }); toast("Talent data removed.", "ok"); await render(root); } catch (err) { toast(err.message, "bad", 7000); }
}

// ---------------------------------------------------------------------------- list
function statusBadge(b) {
  const kind = { verified: "ok", draft: "warn", unverified: "warn", pending: "info" }[b.status];
  return badge(b.status, kind);
}

function drawList() {
  const classSel = h("select", { "aria-label": "Class", onchange: async () => { if (!guard()) { classSel.value = clsId; return; } clsId = classSel.value; specId = cfg.classes.find((c) => c.id === clsId).specializations[0].id; draft = null; dirty = false; await draw(); } },
    cfg.classes.map((c) => h("option", { value: c.id, selected: c.id === clsId }, c.name)));
  const specSel = h("select", { "aria-label": "Specialization", onchange: async () => { if (!guard()) { specSel.value = specId; return; } specId = specSel.value; draft = null; dirty = false; await draw(); } },
    cfg.classes.find((c) => c.id === clsId).specializations.map((s) => h("option", { value: s.id, selected: s.id === specId }, s.name)));
  const spec = specOf();
  clear(listHost).append(h("div", { class: "card" },
    h("div", { class: "row between" }, h("h3", { style: { margin: 0 } }, "Builds"),
      h("div", { class: "row" }, classSel, specSel, h("button", { class: "btn primary small", type: "button", onclick: newBuild }, "New build"))),
    h("p", { class: "muted", style: { fontSize: "0.88rem" } }, `${spec.name} · ${roleLabel(spec.role)}. The default build is what the participant sees after the quiz.`),
    h("div", { class: "table-wrap" }, h("table", {},
      h("thead", {}, h("tr", {}, ["Name", "Purpose", "Status", "Points", "Default", ""].map((t) => h("th", {}, t)))),
      h("tbody", {}, list.length ? list.map((b) => h("tr", { class: draft && !isNew && draft.id === b.id ? "sel" : "" },
        h("td", {}, b.name), h("td", {}, purposeLabel(b.purpose)), h("td", {}, statusBadge(b)),
        h("td", { class: "num" }, `${b.points_spent}/${b.total_points}${b.tree_distribution_text ? ` (${b.tree_distribution_text})` : ""}`),
        h("td", {}, b.is_default ? "★ default" : h("button", { class: "btn small", type: "button", onclick: () => setDefault(b) }, "Make default")),
        h("td", {}, h("div", { class: "row" }, h("button", { class: "btn small", type: "button", onclick: () => editBuild(b) }, "Edit"),
          h("button", { class: "btn small danger", type: "button", onclick: () => deleteBuild(b) }, "Delete")))))
        : [h("tr", {}, h("td", { colspan: 6, class: "muted" }, "No builds for this specialization yet."))])))));
}

const guard = () => !dirty || confirm("The build editor has unsaved changes. Discard them?");

async function setDefault(b) {
  try { await post(`/builds/${b.id}/default`, { expected_revision: cfg.revision }); toast(`${b.name} is now the default.`, "ok"); cfg = await ensureConfig(true); await draw(); } catch (e) { toast(e.message, "bad", 7000); }
}
async function deleteBuild(b) {
  if (!(await confirmDialog(`Delete "${b.name}"?`, { title: "Delete build", confirmText: "Delete", danger: true }))) return;
  try { await del(`/builds/${b.id}`, { expected_revision: cfg.revision }); toast("Build deleted.", "ok"); cfg = await ensureConfig(true); if (draft && draft.id === b.id) { draft = null; dirty = false; } await draw(); } catch (e) { toast(e.message, "bad", 7000); }
}

// ---------------------------------------------------------------------------- editor
function toDraft(b) {
  return {
    id: b.id, class_id: b.class_id, specialization_id: b.specialization_id, name: b.name, role: b.role, purpose: b.purpose, level: b.level,
    total_points: b.total_points, allocations: { ...b.allocations }, leveling_order: [...b.leveling_order],
    combat_priorities: [...b.combat_priorities], equipment_notes: [...b.equipment_notes], professions: [...b.professions],
    source: b.source, source_url: b.source_url, calculator_url: b.calculator_url, verified_at: b.verified_at || null,
    client_version: b.client_version, status: b.status, is_default: b.is_default, notes: b.notes,
  };
}

function newBuild() {
  if (!guard()) return;
  const spec = specOf();
  const taken = new Set(cfg.builds.map((b) => b.id));
  let id = slug(`${clsId}-${specId}-new`), n = 1;
  while (taken.has(id)) id = slug(`${clsId}-${specId}-new-${++n}`);
  draft = toDraft({ id, class_id: clsId, specialization_id: specId, name: `${spec.name} — new build`, role: spec.role.split("_or_")[0], purpose: "leveling_pve", level: 60, total_points: 51,
    allocations: {}, leveling_order: [], combat_priorities: [], equipment_notes: [], professions: [], source: "", source_url: "", calculator_url: "", verified_at: null,
    client_version: catalog ? catalog.client_version : "", status: "draft", is_default: list.length === 0, notes: "" });
  isNew = true; dirty = true;
  drawList(); drawEditor();
  editorHost.scrollIntoView({ behavior: "smooth" });
}

function editBuild(b) {
  if (!guard()) return;
  draft = toDraft(b); isNew = false; dirty = false;
  drawList(); drawEditor();
  editorHost.scrollIntoView({ behavior: "smooth" });
}

function touch() { dirty = true; validate(); }
const validate = debounce(async () => {
  if (!draft || !validationHost) return;
  try { paintValidation(await post("/builds/validate", { build: apiBuild() })); } catch (e) { clear(validationHost).append(errorList(e)); }
}, 250);

function apiBuild() {
  return { ...draft, allocations: Object.fromEntries(Object.entries(draft.allocations).filter(([, r]) => r > 0)), total_points: draft.level - 9 };
}

function paintValidation(v) {
  const spent = h("b", {}, `${v.points_spent} / ${draft.level - 9}`);
  append(clear(validationHost), [
    h("div", { class: "row" },
      h("span", {}, "Points spent ", spent), h("span", {}, `· remaining ${v.points_remaining}`),
      Object.keys(v.tree_distribution).length ? h("span", {}, "· distribution ", h("b", {}, Object.values(v.tree_distribution).join(" / "))) : null,
      badge(v.valid ? "allocation valid" : "has errors", v.valid ? "ok" : "bad"), badge(v.can_verify ? "can be verified" : "cannot be verified yet", v.can_verify ? "ok" : "warn")),
    v.errors.length ? h("ul", { class: "errors" }, v.errors.map((e) => h("li", {}, e))) : null,
    v.warnings.length ? h("ul", { class: "warnings" }, v.warnings.map((e) => h("li", {}, e))) : null,
    !v.can_verify ? h("details", { style: { marginTop: "8px" } }, h("summary", {}, "What verification still needs"), h("ul", {}, v.verification_problems.map((p) => h("li", {}, p)))) : null
  ]);
  const per = counters;
  if (per) for (const [tree, pts] of Object.entries(v.tree_distribution)) { const el = per[tree]; if (el) el.textContent = `${pts} pts`; }
}

function drawEditor() {
  clear(editorHost);
  if (!draft) return;
  const spec = specOf(), d = draft;
  const roles = [...new Set([...spec.role.split("_or_"), d.role])];
  const bind = (key, extra = {}) => ({ value: d[key] ?? "", oninput: (e) => { d[key] = e.target.value; touch(); }, ...extra });
  const pointsLabel = h("span", { class: "muted" }, `${d.level - 9} talent points at level ${d.level}`);
  validationHost = h("div", { class: "stack" });

  const statusSel = h("select", { "aria-label": "Status", onchange: (e) => { d.status = e.target.value; touch(); } },
    ["pending", "draft", "unverified", "verified"].map((s) => h("option", { value: s, selected: d.status === s }, s)));

  const card = h("section", { class: "card" },
    h("h3", {}, isNew ? "New build" : `Edit: ${d.name}`),
    h("div", { class: "grid three" },
      h("label", { class: "field" }, "Name", h("input", { type: "text", ...bind("name") })),
      h("label", { class: "field" }, "Intended role", h("select", { onchange: (e) => { d.role = e.target.value; touch(); } }, roles.map((r) => h("option", { value: r, selected: r === d.role }, roleLabel(r))))),
      h("label", { class: "field" }, "Intended activity", h("input", { type: "text", list: "purposes", ...bind("purpose") }), h("datalist", { id: "purposes" }, PURPOSES.map((p) => h("option", { value: p })))),
      h("label", { class: "field" }, "Character level", h("input", { type: "number", min: "10", max: "60", value: String(d.level), oninput: (e) => { d.level = Math.max(10, Math.min(60, Number(e.target.value) || 60)); pointsLabel.textContent = `${d.level - 9} talent points at level ${d.level}`; touch(); } }), pointsLabel),
      h("label", { class: "field" }, "Status", statusSel),
      isNew ? h("label", { class: "field" }, "Build id", h("input", { type: "text", ...bind("id") })) : null),
    h("h4", { style: { margin: "18px 0 6px" } }, "Talent allocation"),
    allocationEditor(),
    h("div", { style: { marginTop: "12px" } }, validationHost),
    h("h4", { style: { margin: "18px 0 6px" } }, "Leveling order"),
    levelingEditor(),
    h("h4", { style: { margin: "18px 0 6px" } }, "Guidance"),
    h("div", { class: "grid two" },
      h("label", { class: "field" }, "Combat priorities (one per line)", h("textarea", { rows: 4, oninput: (e) => { d.combat_priorities = lines(e.target.value); touch(); } }, d.combat_priorities.join("\n"))),
      h("label", { class: "field" }, "Attributes and equipment (one per line)", h("textarea", { rows: 4, oninput: (e) => { d.equipment_notes = lines(e.target.value); touch(); } }, d.equipment_notes.join("\n"))),
      h("label", { class: "field" }, "Professions (one per line)", h("textarea", { rows: 3, oninput: (e) => { d.professions = lines(e.target.value); touch(); } }, d.professions.join("\n"))),
      h("label", { class: "field" }, "Notes", h("textarea", { rows: 3, ...bind("notes") }, d.notes))),
    h("h4", { style: { margin: "18px 0 6px" } }, "Provenance"),
    h("div", { class: "grid three" },
      h("label", { class: "field" }, "Source", h("input", { type: "text", ...bind("source") })),
      h("label", { class: "field" }, "Source URL", h("input", { type: "url", ...bind("source_url") })),
      h("label", { class: "field" }, "Talent calculator link", h("input", { type: "url", ...bind("calculator_url") })),
      h("label", { class: "field" }, "Verification date", h("input", { type: "date", value: d.verified_at || "", oninput: (e) => { d.verified_at = e.target.value || null; touch(); } })),
      h("label", { class: "field" }, "Game client version", h("input", { type: "text", ...bind("client_version") }),
        catalog ? h("button", { class: "btn small ghost", type: "button", onclick: () => { d.client_version = catalog.client_version; drawEditor(); touch(); } }, `Use ${catalog.client_version}`) : null)),
    h("div", { class: "row", style: { marginTop: "20px" } },
      h("button", { class: "btn primary", type: "button", onclick: saveBuild }, isNew ? "Create build" : "Save build"),
      h("button", { class: "btn", type: "button", onclick: () => { draft = null; dirty = false; drawList(); drawEditor(); } }, "Cancel"),
      h("span", { id: "build-save-error", style: { flex: 1 } })));
  editorHost.append(card);
  validate();
}

function allocationEditor() {
  const d = draft, cc = catClass();
  counters = {};
  if (!cc) {
    return h("div", {},
      h("div", { class: "note warn" }, `No imported talent data for ${cfg.classes.find((c) => c.id === clsId).name}. Allocations cannot be checked and the build cannot be marked verified. You may still enter ids from your own source as a draft.`),
      h("label", { class: "field", style: { marginTop: "8px" } }, "Allocation (talent_id=rank, one per line)",
        h("textarea", { rows: 4, oninput: (e) => {
          const out = {};
          for (const l of lines(e.target.value)) { const [k, v] = l.split(/\s*=\s*/); if (k && Number(v) > 0) out[k] = Math.floor(Number(v)); }
          d.allocations = out; touch();
        } }, Object.entries(d.allocations).map(([k, v]) => `${k}=${v}`).join("\n"))));
  }
  const order = cfg.classes.find((c) => c.id === clsId).specializations.map((s) => s.id);
  const trees = [...cc.trees].sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id));
  return h("div", { class: "grid tree-grid" }, trees.map((tree) => {
    const counter = h("span", { class: "pill" }, "0 pts");
    counters[tree.id] = counter;
    const talents = [...tree.talents].sort((a, b) => a.tier - b.tier || a.column - b.column);
    const names = Object.fromEntries(tree.talents.map((t) => [t.id, t.name]));
    return h("div", {}, h("div", { class: "row between" }, h("h4", { style: { margin: 0 } }, tree.name), counter),
      h("div", { class: "table-wrap talent-table", style: { marginTop: "6px", maxHeight: "460px", overflowY: "auto" } }, h("table", {},
        h("thead", {}, h("tr", {}, h("th", {}, "Row"), h("th", {}, "Talent"), h("th", { class: "num" }, "Rank"))),
        h("tbody", {}, talents.map((t) => h("tr", {},
          h("td", {}, String(t.tier + 1)),
          h("td", { class: "wrap", title: t.description || "" }, t.name, t.requires.length ? h("div", { class: "muted", style: { fontSize: "0.75rem" } }, "needs " + t.requires.map((r) => `${names[r.talent_id] || r.talent_id} ×${r.rank}`).join(", ")) : null),
          h("td", { class: "num" }, h("input", { type: "number", min: "0", max: String(t.max_rank), step: "1", value: String(d.allocations[t.id] || 0), "aria-label": `${t.name} rank (max ${t.max_rank})`,
            oninput: (e) => { const v = Math.max(0, Math.floor(Number(e.target.value) || 0)); if (v > 0) d.allocations[t.id] = v; else delete d.allocations[t.id]; touch(); } }), ` / ${t.max_rank}`)))))));
  }));
}

function levelingEditor() {
  const d = draft, cc = catClass();
  const ta = h("textarea", { rows: 4, "aria-label": "Leveling order, one talent id per line", placeholder: "one talent id per line, first = level 10", oninput: () => { d.leveling_order = lines(ta.value); info.textContent = `${d.leveling_order.length} step(s)`; touch(); } }, d.leveling_order.join("\n"));
  const info = h("span", { class: "muted" }, `${d.leveling_order.length} step(s)`);
  const gen = h("button", { class: "btn small", type: "button", disabled: !cc, title: cc ? "" : "Needs imported talent data", onclick: () => {
    const order = generateOrder(apiBuild(), cc);
    if (!order) { toast("The allocation cannot be ordered legally. Fix the validation errors first.", "warn"); return; }
    d.leveling_order = order; ta.value = order.join("\n"); info.textContent = `${order.length} step(s)`; touch();
  } }, "Generate a legal order");
  return h("div", {}, ta, h("div", { class: "row", style: { marginTop: "6px" } }, gen, info,
    h("span", { class: "muted", style: { fontSize: "0.82rem" } }, "One entry per talent point. The server checks that every step is legal and that the order spends exactly the allocation.")));
}

/** Greedy legal ordering: always take the shallowest available talent. Returns null if stuck. */
function generateOrder(b, cc) {
  const ppt = catalog.points_per_tier;
  const info = {};
  cc.trees.forEach((tree, ti) => tree.talents.forEach((t) => { info[t.id] = { ...t, tree: tree.id, ti }; }));
  const remaining = { ...b.allocations }, have = {}, order = [];
  const total = Object.values(remaining).reduce((s, v) => s + v, 0);
  const above = (tree, tier) => Object.entries(have).reduce((s, [id, n]) => s + (info[id].tree === tree && info[id].tier < tier ? n : 0), 0);
  while (order.length < total) {
    const options = Object.keys(remaining).filter((id) => remaining[id] > 0 && info[id]
      && above(info[id].tree, info[id].tier) >= info[id].tier * ppt && info[id].requires.every((r) => (have[r.talent_id] || 0) >= r.rank));
    if (!options.length) return null;
    options.sort((a, c) => info[a].tier - info[c].tier || info[a].ti - info[c].ti || info[a].column - info[c].column);
    const id = options[0];
    have[id] = (have[id] || 0) + 1; remaining[id]--; order.push(id);
  }
  return order;
}

async function saveBuild() {
  const box = document.getElementById("build-save-error");
  clear(box);
  try {
    const b = apiBuild();
    let r;
    if (isNew) {
      r = await post("/builds", { expected_revision: cfg.revision, build: b });
    } else {
      const { id, class_id, specialization_id, is_default, ...fields } = b;
      r = await patch(`/builds/${id}`, { expected_revision: cfg.revision, ...fields });
    }
    toast(`Build saved (revision ${r.revision}).`, "ok");
    cfg = await ensureConfig(true);
    draft = null; dirty = false;
    await draw();
  } catch (e) {
    if (e.status === 409) { toast("The configuration changed elsewhere. Reload and reapply your edit.", "bad", 8000); }
    box.append(errorList(e));
  }
}
