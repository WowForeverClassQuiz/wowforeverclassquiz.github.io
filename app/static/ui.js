// Small DOM and presentation helpers shared by every view. Nothing here knows about scoring.

/** Create an element. Children may be strings, nodes, arrays or null. Never uses innerHTML. */
export function h(tag, props, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k === "value" || k === "checked" || k === "disabled" || k === "selected" || k === "hidden") el[k] = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  append(el, kids);
  return el;
}

export function append(el, kids) {
  for (const k of kids.flat(Infinity)) {
    if (k === null || k === undefined || k === false) continue;
    el.append(k instanceof Node ? k : document.createTextNode(String(k)));
  }
  return el;
}

export function clear(el) { el.replaceChildren(); return el; }
export const $ = (sel, root = document) => root.querySelector(sel);

export const fmt = (n, d = 2) => (n === null || n === undefined || Number.isNaN(n) ? "-" : Number(n).toFixed(d));
export const signed = (n, d = 2) => {
  if (n === null || n === undefined) return "-";
  const v = Number(n);
  const s = Math.abs(v) < 5e-10 ? (0).toFixed(d) : v.toFixed(d);
  return v > 0 && Number(s) !== 0 ? `+${s}` : Number(s) < 0 ? s.replace("-", "−") : s;
};
export const pct = (f, d = 1) => `${(f * 100).toFixed(d)}%`;
export const roleLabel = (r) => String(r).split("_or_").map((x) => x.replace(/_/g, " ")).join(" or ").replace(/\b\w/g, (c) => c.toUpperCase()).replace(/ Or /g, " or ");
const PURPOSES = {
  leveling_pve: "Leveling & general PvE", solo_leveling: "Solo leveling", dungeon_healing: "Dungeon healing",
  dungeon_tanking: "Dungeon tanking", dungeon_damage: "Dungeon damage", raid_60: "Level-60 raiding", pvp: "PvP", hybrid: "Hybrid",
};
export const purposeLabel = (p) => PURPOSES[p] || titleCase(p);
export const titleCase = (s) => String(s).replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

export function badge(text, kind = "") { return h("span", { class: `pill ${kind}` }, text); }

// ---- toasts -------------------------------------------------------------------------------
export function toast(message, kind = "ok", ms = 4200) {
  const box = document.getElementById("toasts");
  const t = h("div", { class: `toast ${kind}` }, message);
  box.append(t);
  setTimeout(() => t.remove(), ms);
}

// ---- dialogs ------------------------------------------------------------------------------
function dialog(build) {
  return new Promise((resolve) => {
    const dlg = h("dialog");
    const done = (value) => { dlg.close(); dlg.remove(); resolve(value); };
    build(dlg, done);
    dlg.addEventListener("cancel", () => done(null));
    document.body.append(dlg);
    dlg.showModal();
  });
}

export function confirmDialog(message, { title = "Please confirm", confirmText = "Confirm", danger = false, typed = null } = {}) {
  return dialog((dlg, done) => {
    const input = typed ? h("input", { type: "text", "aria-label": `Type ${typed} to confirm`, placeholder: typed }) : null;
    const ok = h("button", { class: `btn ${danger ? "danger" : "primary"}`, type: "button", disabled: !!typed, onclick: () => done(true) }, confirmText);
    if (input) input.addEventListener("input", () => { ok.disabled = input.value !== typed; });
    dlg.append(
      h("h3", {}, title),
      h("p", {}, message),
      typed ? h("p", {}, "Type ", h("b", {}, typed), " to continue:") : null,
      input,
      h("div", { class: "row end", style: { marginTop: "16px" } }, h("button", { class: "btn", type: "button", onclick: () => done(false) }, "Cancel"), ok),
    );
  }).then((v) => v === true);
}

export function askToken() {
  return dialog((dlg, done) => {
    const input = h("input", { type: "password", autocomplete: "off", "aria-label": "Administrator token" });
    dlg.append(
      h("h3", {}, "Administrator token required"),
      h("p", {}, "This server was started with ORACLE_ADMIN_TOKEN set. Enter the token to use the administrative interface."),
      input,
      h("div", { class: "row end", style: { marginTop: "16px" } },
        h("button", { class: "btn", type: "button", onclick: () => done("") }, "Cancel"),
        h("button", { class: "btn primary", type: "button", onclick: () => done(input.value) }, "Continue")),
    );
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") done(input.value); });
  }).then((v) => v || "");
}

// ---- tooltip ------------------------------------------------------------------------------
const tipEl = () => document.getElementById("tip");
export function showTip(evt, content) {
  const t = tipEl();
  t.replaceChildren(content);
  t.hidden = false;
  const pad = 14, r = t.getBoundingClientRect();
  let x = evt.clientX + pad, y = evt.clientY + pad;
  if (x + r.width > window.innerWidth - 8) x = evt.clientX - r.width - pad;
  if (y + r.height > window.innerHeight - 8) y = evt.clientY - r.height - pad;
  t.style.left = `${Math.max(8, x)}px`;
  t.style.top = `${Math.max(8, y)}px`;
}
export function hideTip() { tipEl().hidden = true; }
export function tipRows(title, rows) {
  return h("div", {}, h("b", {}, title), rows.map(([k, v]) => h("div", { class: "kv" }, h("span", {}, k), h("span", {}, v))));
}
export function attachTip(el, makeContent) {
  el.addEventListener("mousemove", (e) => showTip(e, makeContent()));
  el.addEventListener("mouseleave", hideTip);
  el.addEventListener("focus", () => { const r = el.getBoundingClientRect(); showTip({ clientX: r.left + 20, clientY: r.bottom }, makeContent()); });
  el.addEventListener("blur", hideTip);
}

// ---- diverging bar chart ----------------------------------------------------------------------
/**
 * Ranked horizontal bars around a zero line. Positive = blue (right), negative = red (left); the
 * value label always carries an explicit sign so colour is never the only cue.
 * rows: [{id, label, value, ghost?, tip?: [[k,v],...]}]; ghost draws an outline for a comparison value.
 */
export function barChart(rows, { selectedId = null, onSelect = null, decimals = 2, leadId = null, format = null } = {}) {
  const vals = rows.flatMap((r) => [r.value, r.ghost].filter((v) => v !== undefined && v !== null));
  const maxAbs = Math.max(1e-9, ...vals.map((v) => Math.abs(v)));
  const hasNeg = vals.some((v) => v < 0), hasPos = vals.some((v) => v > 0);
  // zero position (percent of track) so that both arms get room proportional to their extent
  const negExtent = hasNeg ? Math.max(...vals.map((v) => Math.max(0, -v))) : 0;
  const posExtent = hasPos ? Math.max(...vals.map((v) => Math.max(0, v))) : 0;
  const total = negExtent + posExtent || maxAbs;
  const zero = (negExtent / total) * 100;
  const scale = 100 / total;
  const out = h("div", { class: "bars", role: "list" });
  for (const r of rows) {
    const mk = (v, extra = "") => v === undefined || v === null ? null : h("i", {
      class: `bar-fill ${v >= 0 ? "pos" : "neg"} ${extra}`,
      style: v >= 0 ? { width: `${v * scale}%` } : { width: `${-v * scale}%`, left: `${zero + v * scale}%` },
    });
    const row = h("div", {
      class: `bar-row${onSelect ? " clickable" : ""}${r.id === selectedId ? " sel" : ""}${r.id === leadId ? " lead" : ""}`,
      role: "listitem", tabindex: onSelect ? 0 : null,
      onclick: onSelect ? () => onSelect(r.id) : null,
      onkeydown: onSelect ? (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(r.id); } } : null,
      "aria-label": `${r.label}: ${format ? format(r.value) : signed(r.value, decimals)}`,
    },
      h("span", { class: "bar-label", title: r.label }, r.icon || null, h("span", { class: "bar-label-text" }, r.label)),
      h("span", { class: "bar-track", style: { "--zero": `${zero}%` } }, mk(r.ghost, "ghost"), mk(r.value)),
      h("span", { class: "bar-val" }, format ? format(r.value) : signed(r.value, decimals)),
    );
    if (r.tip) attachTip(row, () => tipRows(r.label, r.tip));
    out.append(row);
  }
  return out;
}

export function chartLegend(extra = []) {
  return h("div", { class: "legend" },
    h("span", {}, h("i", { class: "pos" }), "above the question's average (+)"),
    h("span", {}, h("i", { class: "neg" }), "below it (−)"),
    ...extra);
}

// ---- misc -----------------------------------------------------------------------------------
export function download(filename, text, type = "application/json") {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = h("a", { href: url, download: filename });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function copyText(text) {
  try { await navigator.clipboard.writeText(text); return true; } catch {
    const ta = h("textarea", { style: { position: "fixed", opacity: "0" } });
    ta.value = text;
    document.body.append(ta);
    ta.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch { /* ignore */ }
    ta.remove();
    return ok;
  }
}

export function debounce(fn, ms = 200) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

export const errorList = (err) => {
  const items = err && err.errors && err.errors.length ? err.errors : [err && err.message ? err.message : String(err)];
  return h("ul", { class: "errors" }, items.slice(0, 12).map((e) => h("li", {}, e)));
};

/** Class accent colours, used only as a decorative accent; every value is also labelled in text. */
export const CLASS_COLORS = {
  druid: "#ff7d0a", hunter: "#abd473", mage: "#69ccf0", paladin: "#f58cba", priest: "#d8d8d8",
  rogue: "#f0e050", shaman: "#0070de", warlock: "#9482c9", warrior: "#c79c6e",
};
