// Question Editor: inspect and edit every answer's class, trait and direct specialization weights.
// Handles choice, pick-two and 1-10 scale questions. Edits are drafts until saved.
import { h, clear, signed, toast, confirmDialog, errorList, badge, debounce } from "../ui.js";
import { get, patch, post } from "../api.js";
import { state, ensureConfig } from "../state.js";
import { weightGrid, nonzero, comparisonView, batchView } from "./shared.js";

let root, cfg, defaults = null;
let qid = "q01";
let drafts = {};       // answer id -> {text, class_weights, trait_weights, spec_weights} (complete maps, zeros included)
let qd = {};           // question-level draft: {text, low_label, high_label, rationale}
let previewBox = {};   // answer id -> element
let matrixBody = null, matrixToken = 0;

const full = (ids, sparse) => Object.fromEntries(ids.map((i) => [i, sparse[i] ?? 0]));
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const classIds = () => cfg.classes.map((c) => c.id);
const traitIds = () => cfg.traits.map((t) => t.id);
const specItems = () => cfg.classes.flatMap((c) => c.specializations.map((s) => ({ id: `${c.id}/${s.id}`, name: s.name, classId: c.id })));
const specIds = () => specItems().map((s) => s.id);
const specName = (key) => { const it = specItems().find((s) => s.id === key); return it ? `${cfg.classes.find((c) => c.id === it.classId).name} · ${it.name}` : key; };

const TYPE_NAMES = { choice: "Choice", pick_two: "Pick two", scale: "Scale 1–10" };
const TYPE_HELP = {
  choice: "The participant picks one answer. The baseline for each class, trait and specialization is its average weight across the answers.",
  pick_two: "The participant picks two of the four items. A pair's weights are the SUM of its two items' weights; the baseline is the average over all six possible pairs.",
  scale: "The participant rates the statement 1–10. A rating r becomes s = (r − 5.5) / 4.5 (from −1 to +1): ratings above the middle blend in the AGREE pole, ratings below it the DISAGREE pole, in proportion to s. The baseline is the average over all ten ratings, so a neutral respondent contributes about zero.",
};

export async function render(container) {
  root = container;
  cfg = await ensureConfig(true);
  if (!defaults) defaults = await get("/config/default");
  if (state.editorQuestion) { qid = state.editorQuestion; state.editorQuestion = null; }
  if (!cfg.questions.some((q) => q.id === qid)) qid = cfg.questions[0].id;
  loadDrafts();
  draw();
  state.dirtyGuard = (silent) => !anyDirty() || (silent ? false : confirm("You have unsaved edits. Discard them?"));
}

const question = () => cfg.questions.find((q) => q.id === qid);
const qSaved = () => { const q = question(); return { text: q.text, low_label: q.low_label, high_label: q.high_label, rationale: q.rationale }; };

function draftOf(a) {
  return {
    text: a.text,
    class_weights: full(classIds(), a.class_weights),
    trait_weights: full(traitIds(), a.trait_weights),
    spec_weights: full(specIds(), a.spec_weights || {}),
  };
}
function loadDrafts() {
  const q = question();
  qd = qSaved();
  drafts = Object.fromEntries(q.answers.map((a) => [a.id, draftOf(a)]));
}
const savedAnswer = (aid) => question().answers.find((a) => a.id === aid);
const answerDirty = (aid) => !same(drafts[aid], draftOf(savedAnswer(aid)));
const qDirty = () => !same(qd, qSaved());
const anyDirty = () => root && cfg && (qDirty() || question().answers.some((a) => answerDirty(a.id)));
const valid = (d) => [...Object.values(d.class_weights), ...Object.values(d.trait_weights), ...Object.values(d.spec_weights)].every((v) => Number.isFinite(v) && v >= 0) && d.text.trim().length > 0;

async function selectQuestion(id) {
  if (anyDirty() && !(await confirmDialog("This question has unsaved edits. Discard them?", { confirmText: "Discard", danger: true }))) { draw(); return; }
  qid = id;
  loadDrafts();
  draw();
}

function answerTitle(q, a) {
  if (q.type === "scale") return a.id === "agree" ? "Agree pole (toward 10)" : "Disagree pole (toward 1)";
  if (q.type === "pick_two") return `Item ${a.id.toUpperCase()}`;
  return `Answer ${a.id.toUpperCase()}`;
}

function draw() {
  clear(root);
  const q = question();
  const idx = cfg.questions.findIndex((x) => x.id === qid);
  const label = (x) => `${String(cfg.questions.indexOf(x) + 1).padStart(2, "0")} · ${x.id.toUpperCase()} · ${TYPE_NAMES[x.type] || x.type} – ${x.text.length > 56 ? x.text.slice(0, 54) + "…" : x.text}`;
  const select = h("select", { id: "qselect", "aria-label": "Question", onchange: (e) => selectQuestion(e.target.value) },
    cfg.questions.map((x) => h("option", { value: x.id, selected: x.id === qid }, label(x))));

  const saveQ = h("button", { class: "btn small primary", type: "button", onclick: saveQuestion }, "Save question details");
  const discardQ = h("button", { class: "btn small", type: "button", onclick: () => { qd = qSaved(); draw(); } }, "Discard");
  const refreshQ = () => { const dirty = qDirty(); saveQ.disabled = !dirty || !qd.text.trim() || !qd.low_label.trim() || !qd.high_label.trim(); discardQ.disabled = !dirty; };
  const field = (key, rows, labelText, hint) => {
    const el = h(rows === 1 ? "input" : "textarea", rows === 1 ? { type: "text", value: qd[key] } : { rows }, rows === 1 ? null : qd[key]);
    el.setAttribute("aria-label", labelText);
    el.addEventListener("input", () => { qd[key] = el.value; el.classList.toggle("dirty", qd[key] !== qSaved()[key]); refreshQ(); });
    el.classList.toggle("dirty", qd[key] !== qSaved()[key]);
    return h("label", { class: "field", style: { marginTop: "12px" } }, labelText, el, hint ? h("small", {}, hint) : null);
  };

  root.append(
    h("div", { class: "page-head" },
      h("div", {}, h("h1", {}, "Question Editor"),
        h("p", {}, "Edits are drafts until you press Save. Saving creates a new configuration revision.")),
      h("div", { class: "row" }, h("button", { class: "btn small", type: "button", disabled: idx === 0, onclick: () => selectQuestion(cfg.questions[idx - 1].id) }, "← Prev"),
        h("button", { class: "btn small", type: "button", disabled: idx === cfg.questions.length - 1, onclick: () => selectQuestion(cfg.questions[idx + 1].id) }, "Next →"))),
    h("div", { class: "card" },
      h("label", { class: "field" }, "Question (in quiz order)", select),
      h("div", { class: "row", style: { marginTop: "10px" } }, badge(TYPE_NAMES[q.type] || q.type, "info"), h("span", { class: "muted" }, `Revision ${cfg.revision}`)),
      h("p", { class: "note", style: { marginTop: "10px" } }, TYPE_HELP[q.type] || ""),
      field("text", 2, q.type === "scale" ? "Statement shown to the participant" : "Question text"),
      q.type === "scale" ? h("div", { class: "grid two" }, field("low_label", 1, "Label at rating 1"), field("high_label", 1, "Label at rating 10")) : null,
      field("rationale", 3, "Why the weights are what they are (administrator note, never shown to participants)"),
      h("div", { class: "row", style: { marginTop: "10px" } }, saveQ, discardQ)),
    ...q.answers.map((a) => answerCard(q, a)),
    matrixCard(),
  );
  refreshQ();
  refreshMatrix();
}

async function saveQuestion() {
  try {
    await patch(`/questions/${qid}`, { expected_revision: cfg.revision, ...qd });
    toast("Question details saved.", "ok");
    await reload();
  } catch (e) { await failed(e); }
}

function answerCard(q, a) {
  const d = drafts[a.id];
  const saved = savedAnswer(a.id);
  const card = h("section", { class: "card answer-card", "aria-label": answerTitle(q, a) });
  const status = h("span", {});
  const textLabel = q.type === "scale" ? "Description of this pole (administrator note)" : "Answer text";
  const text = h("textarea", { rows: 2, "aria-label": textLabel, oninput: () => { d.text = text.value; refresh(); } }, d.text);
  const save = h("button", { class: "btn primary small", type: "button", onclick: () => saveAnswer(a.id) }, "Save");
  const discard = h("button", { class: "btn small", type: "button", onclick: () => { drafts[a.id] = draftOf(savedAnswer(a.id)); draw(); } }, "Discard changes");
  const prev = h("button", { class: "btn small", type: "button", onclick: () => preview(a.id) }, "Preview impact");
  const restore = h("button", { class: "btn small", type: "button", onclick: () => restoreOriginal(a.id) }, "Restore original weights");
  const out = h("div", { style: { marginTop: "14px" } });
  previewBox[a.id] = out;

  const classItems = cfg.classes.map((c) => ({ id: c.id, name: c.name }));
  const traitItems = cfg.traits.map((t) => ({ id: t.id, name: t.name, hint: t.description }));
  const onC = (id, v) => { d.class_weights[id] = v; refresh(); };
  const onT = (id, v) => { d.trait_weights[id] = v; refresh(); };
  const onS = (id, v) => { d.spec_weights[id] = v; refresh(); };
  const savedFull = draftOf(saved);
  const specSummary = h("summary", {});
  const specBox = h("details", { open: Object.values(d.spec_weights).some((v) => v > 0) }, specSummary,
    h("p", { class: "muted", style: { fontSize: "0.85rem", margin: "6px 0" } },
      "Direct specialization weights add to a specialization's score on top of its trait profile. They only matter if that specialization's class is the winning class."),
    cfg.classes.map((c) => h("div", { style: { marginTop: "8px" } }, h("h4", { style: { margin: "0 0 4px" } }, c.name),
      weightGrid(c.specializations.map((s) => ({ id: `${c.id}/${s.id}`, name: s.name })), d.spec_weights, onS, savedFull.spec_weights))));

  function refresh() {
    const dirty = answerDirty(a.id), ok = valid(d);
    card.classList.toggle("is-dirty", dirty);
    text.classList.toggle("dirty", d.text !== saved.text);
    save.disabled = !dirty || !ok; discard.disabled = !dirty;
    status.replaceChildren(...[dirty ? badge("unsaved changes", "info") : null, !ok ? badge("invalid value", "bad") : null].filter(Boolean));
    specSummary.textContent = `Direct specialization weights (${Object.values(d.spec_weights).filter((v) => v > 0).length} set)`;
    refreshMatrix();
  }

  card.append(
    h("h3", {}, h("span", { class: "letter" }, a.id === "agree" ? "+" : a.id === "disagree" ? "−" : a.id.toUpperCase()), answerTitle(q, a), status),
    h("label", { class: "field" }, textLabel, text),
    h("h4", { style: { margin: "14px 0 6px" } }, "Class weights"),
    weightGrid(classItems, d.class_weights, onC, savedFull.class_weights),
    h("h4", { style: { margin: "14px 0 6px" } }, "Personality trait weights"),
    weightGrid(traitItems, d.trait_weights, onT, savedFull.trait_weights),
    h("div", { style: { marginTop: "14px" } }, specBox),
    h("div", { class: "row", style: { marginTop: "14px" } }, save, discard, prev, restore),
    out,
  );
  queueMicrotask(refresh);
  return card;
}

async function restoreOriginal(aid) {
  const orig = defaults.questions.find((q) => q.id === qid)?.answers.find((a) => a.id === aid);
  if (!orig) { toast("This answer does not exist in the original configuration.", "warn"); return; }
  drafts[aid] = draftOf(orig);
  draw();
  toast(`Now showing the original values as a draft. Press Save to apply.`, "ok");
}

async function saveAnswer(aid) {
  const d = drafts[aid];
  try {
    const r = await patch(`/questions/${qid}/answers/${aid}`, {
      expected_revision: cfg.revision, text: d.text, class_weights: nonzero(d.class_weights),
      trait_weights: nonzero(d.trait_weights), spec_weights: nonzero(d.spec_weights),
    });
    toast(`Saved (revision ${r.revision}).`, "ok");
    state.adminEval = null;
    await reload(aid);
  } catch (e) { await failed(e); }
}

async function reload(savedAid = null) {
  const prev = drafts, prevQ = qd;
  cfg = await ensureConfig(true);
  loadDrafts();
  for (const [k, d] of Object.entries(prev)) if (k !== savedAid) drafts[k] = d;   // keep unrelated unsaved edits
  if (savedAid) qd = prevQ;
  draw();
}

async function failed(e) {
  if (e.status === 409) {
    toast("Someone else changed the configuration. Your draft was discarded; the latest values are shown.", "bad", 8000);
    cfg = await ensureConfig(true); loadDrafts(); draw();
  } else {
    toast(e.message, "bad", 8000);
  }
}

async function preview(aid) {
  const d = drafts[aid], box = previewBox[aid];
  if (!valid(d)) { toast("Fix the invalid values first.", "warn"); return; }
  clear(box).append(h("p", { class: "muted" }, "Running the preview…"));
  const override = { question_id: qid, answer_id: aid, class_weights: nonzero(d.class_weights), trait_weights: nonzero(d.trait_weights), spec_weights: nonzero(d.spec_weights) };
  try {
    const hasAnswers = Object.keys(state.adminAnswers).length > 0;
    const [batch, single] = await Promise.all([
      post("/simulate/batch", { count: 3000, seed: 1, overrides: [override] }),
      hasAnswers ? post("/simulate", { answers: state.adminAnswers, overrides: [override] }) : null,
    ]);
    clear(box).append(h("div", { class: "card", style: { background: "var(--surface-2)" } },
      h("h3", {}, `Impact preview for ${answerTitle(question(), savedAnswer(aid))} (nothing is saved)`),
      single
        ? h("div", {}, h("h4", {}, `Your hypothetical answers (${Object.keys(state.adminAnswers).length} answered)`), comparisonView(single))
        : h("p", { class: "note" }, "No hypothetical answers are set. Complete the quiz, or choose answers in the Scoring Inspector, to also preview a single result."),
      h("h4", { style: { marginTop: "18px" } }, "Across 3,000 random answer sets (same sets before and after)"),
      batchView(batch)));
  } catch (e) { clear(box).append(errorList(e)); }
}

// ---- how the question is normalized: computed by the server from the current drafts -----------
function matrixCard() {
  matrixBody = h("div", {}, h("p", { class: "muted" }, "Calculating…"));
  return h("div", { class: "card" }, h("details", { open: true }, h("summary", {}, "How this question turns into numbers (computed by the server from the values above)"),
    h("p", { class: "muted", style: { fontSize: "0.88rem" } },
      "Each column is one possible response. A cell shows what that response adds to the row after the question's average (baseline) is subtracted: blue adds, red subtracts. Only rows this question touches are listed."),
    matrixBody));
}

const refreshMatrix = debounce(async () => {
  if (!matrixBody) return;
  const token = ++matrixToken;
  const q = question();
  const draftQ = {
    id: q.id, text: qd.text || q.text, enabled: true, type: q.type,
    low_label: qd.low_label || "Strongly disagree", high_label: qd.high_label || "Strongly agree", rationale: "",
    answers: q.answers.map((a) => ({ id: a.id, text: drafts[a.id]?.text || a.text, class_weights: nonzero(drafts[a.id]?.class_weights || {}),
      trait_weights: nonzero(drafts[a.id]?.trait_weights || {}), spec_weights: nonzero(drafts[a.id]?.spec_weights || {}) })),
  };
  try {
    const ex = await post("/questions/expand", { question: draftQ });
    if (token !== matrixToken) return;
    matrixBody.replaceChildren(
      matrixTable("Classes", cfg.classes.map((c) => [c.id, c.name]), ex, "class"),
      matrixTable("Personality traits", cfg.traits.map((t) => [t.id, t.name]), ex, "trait"),
      matrixTable("Direct specialization weights", specItems().map((s) => [s.id, specName(s.id)]), ex, "spec"),
    );
  } catch (e) { if (token === matrixToken) matrixBody.replaceChildren(errorList(e)); }
}, 250);

function matrixTable(title, rows, ex, kind) {
  const base = ex[`${kind}_baseline`];
  const touched = rows.filter(([id]) => base[id] || ex.options.some((o) => o[`${kind}_raw`][id]));
  if (!touched.length) return h("div", { style: { marginBottom: "12px" } }, h("h4", {}, title), h("p", { class: "muted", style: { fontSize: "0.88rem" } }, "No weights set."));
  const head = (o) => (ex.type === "scale" ? o.id : o.id.toUpperCase());
  return h("div", { style: { marginBottom: "14px" } }, h("h4", {}, title),
    h("div", { class: "table-wrap" }, h("table", {},
      h("thead", {}, h("tr", {}, h("th", {}, ""), ex.options.map((o) => h("th", { class: "num", title: o.label }, head(o))), h("th", { class: "num", title: "Average weight over all responses; subtracted from each response" }, "Baseline"))),
      h("tbody", {}, touched.map(([id, name]) => h("tr", {}, h("td", {}, name),
        ex.options.map((o) => { const v = o[`${kind}_adjusted`][id] || 0; return h("td", { class: `num ${v > 1e-9 ? "pos" : v < -1e-9 ? "neg" : "zero"}`, title: `${o.label} → raw weight ${(o[`${kind}_raw`][id] || 0).toFixed(2)}` }, signed(v, 2)); }),
        h("td", { class: "num" }, (base[id] || 0).toFixed(3)))))))
  );
}
