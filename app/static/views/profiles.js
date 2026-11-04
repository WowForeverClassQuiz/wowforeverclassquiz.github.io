// Profiles: personality trait names, specialization trait profiles (any number of weighted traits),
// class descriptions, and scoring settings. Every card has explicit Save / Discard.
import { h, clear, toast, badge, errorList, roleLabel } from "../ui.js";
import { get, patch } from "../api.js";
import { state, ensureConfig } from "../state.js";
import { DEFAULT_SHARE_TEMPLATE, SAMPLE_RESULT, SHARE_FIELDS, renderShare, shareValues } from "../share.js";

let root, cfg, defaults;
const drafts = new Map();   // key -> draft object; removed when saved or discarded

const clone = (x) => JSON.parse(JSON.stringify(x));
const eq = (a, b) => JSON.stringify(a) === JSON.stringify(b);

export async function render(container) {
  root = container;
  cfg = await ensureConfig(true);
  if (!defaults) defaults = await get("/config/default");
  drafts.clear();
  state.dirtyGuard = (silent) => ![...drafts].some(([k, d]) => !eq(d, savedForm(k))) || (silent ? false : confirm("You have unsaved edits. Discard them?"));
  draw();
}

function savedForm(key) {
  const [kind, id] = key.split(":");
  if (kind === "trait") { const t = cfg.traits.find((x) => x.id === id); return { name: t.name, description: t.description, interpretation: t.interpretation }; }
  if (kind === "class") { const c = cfg.classes.find((x) => x.id === id); return { name: c.name, description: c.description, overview: c.overview || "" }; }
  if (kind === "spec") { const [cid, sid] = id.split("/"); const s = cfg.classes.find((c) => c.id === cid).specializations.find((x) => x.id === sid); return specForm(s); }
  if (kind === "share") return { template: cfg.quiz.share_template };
  const ad = cfg.scoring.adaptive;
  return {
    strong: cfg.scoring.confidence_margins.strong, moderate: cfg.scoring.confidence_margins.moderate, order: [...cfg.scoring.class_tie_break_order],
    adaptive: { enabled: ad.enabled, min: ad.min_questions, max: ad.max_questions, confidence: Math.round(ad.confidence * 10000) / 100, lc: ad.sharpness_class, ls: ad.sharpness_spec, cc: ad.class_credit, rc: ad.role_credit, tm: ad.tiebreak_mass, qs: ad.question_scaling, ro: ad.random_opening },
  };
}
const specForm = (s) => ({ description: s.description, overview: s.overview || "", rows: Object.entries(s.trait_multipliers).map(([t, m]) => [t, m]) });
const draftFor = (key) => { if (!drafts.has(key)) drafts.set(key, clone(savedForm(key))); return drafts.get(key); };

async function save(key, request, okMessage) {
  try {
    const r = await request();
    drafts.delete(key);
    toast(`${okMessage} (revision ${r.revision}).`, "ok");
    cfg = await ensureConfig(true);
    draw();
  } catch (e) {
    if (e.status === 409) { toast("The configuration changed elsewhere. Reloaded the latest values.", "bad", 7000); drafts.clear(); cfg = await ensureConfig(true); draw(); }
    else toast(e.message, "bad", 8000);
  }
}

/** Standard footer for a draft card: Save and Discard (plus optional extras) with live dirty state. */
function actions(key, card, onSave, extra = []) {
  const saveBtn = h("button", { class: "btn small primary", type: "button", onclick: onSave }, "Save");
  const discard = h("button", { class: "btn small", type: "button", onclick: () => { drafts.delete(key); draw(); } }, "Discard");
  const flag = h("span");
  const refresh = () => {
    const dirty = !eq(draftFor(key), savedForm(key));
    saveBtn.disabled = !dirty; discard.disabled = !dirty;
    card.classList.toggle("is-dirty", dirty);
    flag.replaceChildren(...(dirty ? [badge("unsaved changes", "info")] : []));
  };
  card.refresh = refresh;
  setTimeout(refresh, 0);
  return h("div", { class: "row", style: { marginTop: "12px" } }, saveBtn, discard, ...extra, flag);
}

const field = (label, input) => h("label", { class: "field" }, label, input);
const textArea = (value, onInput, label) => { const t = h("textarea", { rows: 3, "aria-label": label, oninput: () => onInput(t.value) }, value); return t; };
const textInput = (value, onInput, label) => { const i = h("input", { type: "text", value, "aria-label": label, oninput: () => onInput(i.value) }); return i; };

function draw() {
  clear(root).append(
    h("div", { class: "page-head" }, h("div", {}, h("h1", {}, "Profiles & Settings"),
      h("p", {}, "Edit trait names, specialization trait profiles, class descriptions and scoring settings. Changes take effect for the next evaluation and create a new revision."))),
    shareCard(),
    scoringCard(),
    traitsCard(),
    ...cfg.classes.map(classCard),
  );
}

// ---- share format ----------------------------------------------------------------------------------
/** The text a participant copies from "Share your result": a template with {placeholders}, previewed on a sample result. */
function shareCard() {
  const key = "share", d = draftFor(key);
  const card = h("section", { class: "card answer-card" });
  const preview = h("pre", { class: "share-preview", "aria-label": "Preview with a sample result" });
  const paint = () => { preview.textContent = renderShare(d.template, shareValues(SAMPLE_RESULT, { link: "https://example.com/oracle/", title: cfg.quiz.title })); };
  const area = h("textarea", { rows: 6, "aria-label": "Share format", oninput: () => { d.template = area.value; paint(); card.refresh(); } }, d.template);
  const insert = (name) => {
    const at = area.selectionStart ?? area.value.length, end = area.selectionEnd ?? at;
    area.setRangeText(`{${name}}`, at, end, "end");
    d.template = area.value; area.focus(); paint(); card.refresh();
  };
  paint();
  card.append(h("h3", {}, "Share format"),
    h("p", { class: "muted", style: { fontSize: "0.88rem" } }, "The text a participant copies from “Share your result”. Write it as you like and put a {placeholder} wherever a detail of their result should go. Click a placeholder to insert it at the cursor."),
    area,
    h("div", { class: "share-fields" }, SHARE_FIELDS.map(([name, text]) => h("button", { class: "btn small ghost", type: "button", title: text, onclick: () => insert(name) }, `{${name}}`))),
    h("h4", {}, "Preview"), preview,
    actions(key, card, () => save(key, () => patch("/quiz", { expected_revision: cfg.revision, share_template: d.template }), "Share format saved"),
      [h("button", { class: "btn small", type: "button", onclick: () => { d.template = DEFAULT_SHARE_TEMPLATE; area.value = d.template; paint(); card.refresh(); } }, "Restore the original")]));
  return card;
}

// ---- scoring settings ----------------------------------------------------------------------------
function scoringCard() {
  const key = "scoring", d = draftFor(key);
  const card = h("section", { class: "card answer-card" });
  const strong = h("input", { type: "number", step: "0.25", min: "0", value: String(d.strong), "aria-label": "Strong margin", oninput: () => { d.strong = Number(strong.value); card.refresh(); } });
  const moderate = h("input", { type: "number", step: "0.25", min: "0", value: String(d.moderate), "aria-label": "Moderate margin", oninput: () => { d.moderate = Number(moderate.value); card.refresh(); } });
  const list = h("ol", { style: { paddingLeft: "1.4em" } });
  const paintOrder = () => {
    clear(list).append(...d.order.map((id, i) => h("li", {}, h("span", { class: "row" }, cfg.classes.find((c) => c.id === id).name,
      h("button", { class: "btn small ghost", type: "button", disabled: i === 0, "aria-label": "Move up", onclick: () => { [d.order[i - 1], d.order[i]] = [d.order[i], d.order[i - 1]]; paintOrder(); card.refresh(); } }, "↑"),
      h("button", { class: "btn small ghost", type: "button", disabled: i === d.order.length - 1, "aria-label": "Move down", onclick: () => { [d.order[i + 1], d.order[i]] = [d.order[i], d.order[i + 1]]; paintOrder(); card.refresh(); } }, "↓")))));
  };
  paintOrder();
  const a = d.adaptive;
  const num = (label, key, props = {}) => {
    const input = h("input", { type: "number", value: String(a[key]), "aria-label": label, ...props, oninput: () => { a[key] = Number(input.value); card.refresh(); } });
    return field(label, input);
  };
  const enabled = h("input", { type: "checkbox", checked: a.enabled, "aria-label": "Confidence mode on", onchange: () => { a.enabled = enabled.checked; card.refresh(); } });
  card.append(h("h3", {}, "Scoring settings"),
    h("div", { class: "stack", style: { marginBottom: "16px" } },
      h("h4", {}, "Confidence mode (the default way to take the quiz)"),
      h("p", { class: "muted", style: { fontSize: "0.88rem" } }, "The Oracle asks the most informative question each time and stops once its confidence reaches the threshold, or at the maximum. The confidence is the model's probability for the recommended specialization plus partial credit for probability on other specializations of the same class and with a similar role; set both credits to 0 for the specialization's probability alone. A minimum of 1 means it may stop after any answer. The sharpness values say how consistently people are assumed to answer as their type: higher means fewer questions. See docs/oracle-math.pdf."),
      h("label", { class: "row" }, enabled, "Offer confidence mode"),
      h("div", { class: "row", style: { flexWrap: "wrap" } },
        num("Minimum questions (1 means none)", "min", { min: "1", step: "1" }), num("Maximum questions", "max", { min: "1", step: "1" }),
        num("Stop at confidence (%)", "confidence", { min: "1", max: "99", step: "1" }),
        num("Class sharpness", "lc", { min: "0.05", step: "0.05" }), num("Specialization sharpness", "ls", { min: "0.05", step: "0.05" }),
        num("Credit for the same class (0 to 1)", "cc", { min: "0", max: "1", step: "0.05" }), num("Credit for a similar role (0 to 1)", "rc", { min: "0", max: "1", step: "0.05" }),
        num("Probability the finalists must hold for a tiebreaker (0 to 1)", "tm", { min: "0.05", max: "1", step: "0.05" }),
        num("Question scaling k (confidence is scaled by n / (n + k); 0 turns it off)", "qs", { min: "0", max: "10", step: "0.1" })),
      h("label", { class: "row" }, h("input", { type: "checkbox", checked: a.ro, "aria-label": "Open with a random personality question", onchange: (e) => { a.ro = e.target.checked; card.refresh(); } }), "Open with a random personality question")),
    h("div", { class: "grid two" },
      h("div", { class: "stack" }, h("h4", {}, "Confidence descriptor margins"),
        h("p", { class: "muted", style: { fontSize: "0.88rem" } }, "Heuristic wording based on the gap between the top two class scores."),
        h("div", { class: "row" }, field("“Strong lean” at gap ≥", strong), field("“Clear lean” at gap ≥", moderate))),
      h("div", {}, h("h4", {}, "Class tie-break order"), h("p", { class: "muted", style: { fontSize: "0.88rem" } }, "Equal class scores resolve in this order (top wins)."), list)),
    actions(key, card, () => save(key, () => patch("/scoring", { expected_revision: cfg.revision, confidence_margins: { strong: d.strong, moderate: d.moderate }, class_tie_break_order: d.order,
      adaptive: { enabled: d.adaptive.enabled, min_questions: d.adaptive.min, max_questions: d.adaptive.max, confidence: d.adaptive.confidence / 100,
        sharpness_class: d.adaptive.lc, sharpness_spec: d.adaptive.ls, class_credit: d.adaptive.cc, role_credit: d.adaptive.rc, tiebreak_mass: d.adaptive.tm, question_scaling: d.adaptive.qs, random_opening: d.adaptive.ro } }), "Scoring settings saved")));
  return card;
}

// ---- traits ------------------------------------------------------------------------------------------
function traitsCard() {
  const card = h("section", { class: "card" }, h("h3", {}, "Personality traits"),
    h("p", { class: "muted", style: { fontSize: "0.88rem" } }, "Display names are shown in results and charts. The reading sentence is used in the personality interpretation."));
  const list = h("div", { class: "stack" });
  cfg.traits.forEach((t) => {
    const key = `trait:${t.id}`, d = draftFor(key);
    const row = h("div", { class: "answer-card card", style: { boxShadow: "none" } });
    row.append(h("div", { class: "row between" }, h("b", {}, t.id), h("span", { class: "muted mono" }, "")),
      h("div", { class: "grid two" },
        field("Display name", textInput(d.name, (v) => { d.name = v; row.refresh(); }, "Display name")),
        field("Description", textInput(d.description, (v) => { d.description = v; row.refresh(); }, "Description"))),
      field("Reading sentence", textInput(d.interpretation, (v) => { d.interpretation = v; row.refresh(); }, "Reading sentence")),
      actions(key, row, () => save(key, () => patch(`/traits/${t.id}`, { expected_revision: cfg.revision, ...d }), `Trait ${t.id} saved`)));
    list.append(row);
  });
  card.append(list);
  return card;
}

// ---- classes and specializations ----------------------------------------------------------------------
function classCard(c) {
  const key = `class:${c.id}`, d = draftFor(key);
  const card = h("section", { class: "card" });
  const head = h("div", { class: "answer-card card", style: { boxShadow: "none", marginBottom: "14px" } });
  head.append(h("div", { class: "grid two" },
    field("Class name", textInput(d.name, (v) => { d.name = v; head.refresh(); }, "Class name")),
    field("Class description", textInput(d.description, (v) => { d.description = v; head.refresh(); }, "Class description"))),
    field("What the class does (shown on the result)", textArea(d.overview, (v) => { d.overview = v; head.refresh(); }, "Class overview paragraph")),
    actions(key, head, () => save(key, () => patch(`/classes/${c.id}`, { expected_revision: cfg.revision, ...d }), `${c.name} saved`)));
  card.append(h("h3", {}, c.name), head, ...c.specializations.map((s) => specCard(c, s)));
  return card;
}

function specCard(c, s) {
  const key = `spec:${c.id}/${s.id}`, d = draftFor(key);
  const defSpec = defaults.classes.find((x) => x.id === c.id)?.specializations.find((x) => x.id === s.id);
  const card = h("div", { class: "answer-card card", style: { boxShadow: "none", marginTop: "12px" } });
  const rows = h("div", { class: "stack" });

  const paint = () => {
    clear(rows).append(...d.rows.map(([trait, mult], i) => {
      const sel = h("select", { "aria-label": "Trait", onchange: () => { d.rows[i][0] = sel.value; paintErrors(); card.refresh(); } },
        cfg.traits.map((t) => h("option", { value: t.id, selected: t.id === trait }, t.name)));
      const num = h("input", { type: "number", min: "0", step: "0.05", value: String(mult), "aria-label": "Multiplier", style: { width: "90px" }, oninput: () => { d.rows[i][1] = num.value === "" ? NaN : Number(num.value); paintErrors(); card.refresh(); } });
      return h("div", { class: "row" },
        h("span", { class: "pill", style: { minWidth: "84px", justifyContent: "center" } }, ["Primary", "Secondary", "Tertiary"][i] || `#${i + 1}`),
        sel, h("span", { "aria-hidden": "true" }, "×"), num,
        h("button", { class: "btn small ghost", type: "button", disabled: i === 0, "aria-label": "Move up", onclick: () => { [d.rows[i - 1], d.rows[i]] = [d.rows[i], d.rows[i - 1]]; paint(); card.refresh(); } }, "↑"),
        h("button", { class: "btn small ghost", type: "button", disabled: i === d.rows.length - 1, "aria-label": "Move down", onclick: () => { [d.rows[i + 1], d.rows[i]] = [d.rows[i], d.rows[i + 1]]; paint(); card.refresh(); } }, "↓"),
        h("button", { class: "btn small ghost", type: "button", disabled: d.rows.length <= 1, "aria-label": "Remove trait", onclick: () => { d.rows.splice(i, 1); paint(); card.refresh(); } }, "✕"));
    }));
  };
  const errs = h("div");
  const problems = () => {
    const p = [], seen = new Set();
    for (const [t, m] of d.rows) { if (seen.has(t)) p.push(`Trait "${t}" appears more than once.`); seen.add(t); if (!Number.isFinite(m) || m < 0) p.push("Multipliers must be non-negative numbers."); }
    return [...new Set(p)];
  };
  const paintErrors = () => { clear(errs).append(...(problems().length ? [h("ul", { class: "errors" }, problems().map((x) => h("li", {}, x)))] : [])); };

  const saveExtra = [
    h("button", { class: "btn small", type: "button", onclick: () => addRow() }, "+ Add trait"),
    h("button", { class: "btn small", type: "button", disabled: !defSpec, onclick: () => { Object.assign(d, clone(specForm(defSpec))); paint(); paintErrors(); card.refresh(); toast("Original profile loaded as a draft. Press Save to apply.", "ok"); } }, "Restore original"),
  ];
  const addRow = () => {
    const unused = cfg.traits.find((t) => !d.rows.some(([x]) => x === t.id));
    if (!unused) return;
    d.rows.push([unused.id, 0.25]); paint(); card.refresh();
  };
  const footer = actions(key, card, () => {
    const p = problems();
    if (p.length) { toast(p[0], "warn"); return; }
    save(key, () => patch(`/classes/${c.id}/specs/${s.id}`, { expected_revision: cfg.revision, description: d.description, overview: d.overview, trait_multipliers: Object.fromEntries(d.rows) }), `${c.name} / ${s.name} saved`);
  }, saveExtra);

  card.append(h("div", { class: "row between" }, h("b", {}, s.name), badge(roleLabel(s.role), "")),
    field("Description", textInput(d.description, (v) => { d.description = v; card.refresh(); }, "Specialization description")),
    field("What the specialization does (shown on the result)", textArea(d.overview, (v) => { d.overview = v; card.refresh(); }, "Specialization overview paragraph")),
    h("h4", { style: { margin: "12px 0 6px" } }, "Trait profile (order = priority)"), rows, errs, footer);
  paint(); paintErrors();
  return card;
}
