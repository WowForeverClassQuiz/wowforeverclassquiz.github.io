// Simulation: evaluate hypothetical answers under temporary weight changes. Nothing here is ever saved.
import { h, clear, badge, toast, errorList, debounce } from "../ui.js";
import { post } from "../api.js";
import { state, ensureConfig, randomAnswers } from "../state.js";
import { answerPicker, weightGrid, nonzero, comparisonView, batchView } from "./shared.js";

let root, cfg, overridesBox, specBox, resultBox, countEl, pickerHost;
const overrides = [];      // {question_id, answer_id, class_weights, trait_weights} with complete maps
const specOverrides = [];  // {class_id, specialization_id, text}

const full = (ids, sparse) => Object.fromEntries(ids.map((i) => [i, sparse[i] ?? 0]));
const specKeys = () => cfg.classes.flatMap((c) => c.specializations.map((s) => `${c.id}/${s.id}`));

let lengthSel = null;   // the quiz-length menu of the run panel

export async function render(container) {
  root = container;
  cfg = await ensureConfig(true);
  countEl = h("span", { class: "muted" });
  pickerHost = h("div");
  overridesBox = h("div", { class: "stack" });
  specBox = h("div", { class: "stack" });
  resultBox = h("div", { class: "stack", style: { marginTop: "20px" } });

  const mountPicker = () => clear(pickerHost).append(answerPicker(cfg, state.adminAnswers, updateCount));
  const set = (a) => { state.adminAnswers = a; mountPicker(); updateCount(); };

  const qSel = h("select", { "aria-label": "Question to override" }, cfg.questions.map((q) => h("option", { value: q.id },
    `${q.id.toUpperCase()} · ${q.type === "scale" ? "scale" : q.type === "pick_two" ? "pick two" : "choice"}: ${q.text.slice(0, 44)}…`)));
  const aSel = h("select", { "aria-label": "Answer to override" });
  const fillAnswers = () => {
    const q = cfg.questions.find((x) => x.id === qSel.value);
    clear(aSel).append(...q.answers.map((a) => h("option", { value: a.id },
      q.type === "scale" ? (a.id === "agree" ? "Agree pole" : "Disagree pole") : q.type === "pick_two" ? `Item ${a.id.toUpperCase()}` : `Answer ${a.id.toUpperCase()}`)));
  };
  qSel.addEventListener("change", fillAnswers); fillAnswers();
  const cSel = h("select", { "aria-label": "Class" }, cfg.classes.map((c) => h("option", { value: c.id }, c.name)));
  const sSel = h("select", { "aria-label": "Specialization" });
  const fillSpecs = () => { clear(sSel).append(...cfg.classes.find((c) => c.id === cSel.value).specializations.map((s) => h("option", { value: s.id }, s.name))); };
  cSel.addEventListener("change", fillSpecs); fillSpecs();

  const count = h("input", { type: "number", min: "100", max: "20000", step: "500", value: "5000", "aria-label": "Number of random answer sets" });
  const seed = h("input", { type: "number", step: "1", placeholder: "random", "aria-label": "Random seed (optional)" });
  lengthSel = h("select", { "aria-label": "Quiz length" }, [["long", "Long quiz"], ["medium", "Medium quiz"], ["short", "Short quiz"]].map(([v, t]) => h("option", { value: v }, t)));

  clear(root).append(
    h("div", { class: "page-head" }, h("div", {}, h("h1", {}, "Simulation"),
      h("p", {}, "Try temporary weight changes against a hypothetical participant. Results are computed on the server and never saved."))),
    h("div", { class: "card" },
      h("div", { class: "row between" }, h("h3", { style: { margin: 0 } }, "1. Hypothetical responses"),
        h("div", { class: "row" }, countEl,
          h("button", { class: "btn small", type: "button", disabled: !Object.keys(state.answers).length, onclick: () => set({ ...state.answers }) }, "Use my quiz answers"),
          h("button", { class: "btn small", type: "button", onclick: () => set(randomAnswers(cfg)) }, "Random"),
          h("button", { class: "btn small", type: "button", onclick: () => set({}) }, "Clear"))),
      h("details", { style: { marginTop: "12px" } }, h("summary", {}, "Choose answers manually"), pickerHost),
      h("p", { class: "muted", style: { fontSize: "0.85rem" } }, "Partial response sets are allowed in simulations.")),
    h("div", { class: "card" },
      h("h3", {}, "2. Temporary changes"),
      h("div", { class: "grid two" },
        h("div", { class: "stack" },
          h("h4", {}, "Answer weights"),
          h("div", { class: "row" }, qSel, aSel, h("button", { class: "btn small", type: "button", onclick: () => addOverride(qSel.value, aSel.value) }, "Add override")),
          overridesBox),
        h("div", { class: "stack" },
          h("h4", {}, "Specialization profiles"),
          h("div", { class: "row" }, cSel, sSel, h("button", { class: "btn small", type: "button", onclick: () => addSpecOverride(cSel.value, sSel.value) }, "Add override")),
          specBox))),
    h("div", { class: "card" },
      h("h3", {}, "3. Run"),
      h("div", { class: "row" },
        h("button", { class: "btn primary", type: "button", onclick: () => runCompare() }, "Compare saved vs simulated"),
        h("span", { class: "muted" }, "or"),
        h("label", { class: "field", style: { width: "130px" } }, "Random sets", count),
        h("label", { class: "field", style: { width: "130px" } }, "Seed", seed),
        h("label", { class: "field", style: { width: "150px" } }, "Quiz length", lengthSel),
        h("button", { class: "btn", type: "button", style: { alignSelf: "end" }, onclick: () => runBatch(+count.value, seed.value === "" ? null : +seed.value) }, "Run batch diagnostic")),
      h("p", { class: "muted", style: { fontSize: "0.85rem", marginTop: "10px" } }, "A batch scores uniformly random answer sets to reveal systematic bias. Frequencies diagnose the scoring rules and say nothing about how real people answer.")),
    resultBox,
  );
  mountPicker(); updateCount(); drawOverrides(); drawSpecOverrides();
}

function updateCount() {
  countEl.textContent = `${Object.keys(state.adminAnswers).length} of ${cfg.questions.filter((q) => q.enabled).length} answered`;
}

function addOverride(qid, aid) {
  if (overrides.some((o) => o.question_id === qid && o.answer_id === aid)) { toast("That answer already has an override.", "warn"); return; }
  const a = cfg.questions.find((q) => q.id === qid).answers.find((x) => x.id === aid);
  if (!a) { toast("That question has no such answer.", "warn"); return; }
  overrides.push({ question_id: qid, answer_id: aid, class_weights: full(cfg.classes.map((c) => c.id), a.class_weights), trait_weights: full(cfg.traits.map((t) => t.id), a.trait_weights),
    spec_weights: full(specKeys(), a.spec_weights || {}) });
  drawOverrides();
}

function drawOverrides() {
  clear(overridesBox);
  if (!overrides.length) overridesBox.append(h("p", { class: "muted" }, "No answer overrides."));
  overrides.forEach((o, idx) => {
    const saved = cfg.questions.find((q) => q.id === o.question_id).answers.find((a) => a.id === o.answer_id);
    overridesBox.append(h("details", { open: true },
      h("summary", {}, `${o.question_id.toUpperCase()} answer ${o.answer_id.toUpperCase()}`, " ", badge("temporary", "info")),
      h("p", { class: "muted", style: { fontSize: "0.85rem" } }, saved.text),
      h("h4", {}, "Class weights"),
      weightGrid(cfg.classes.map((c) => ({ id: c.id, name: c.name })), o.class_weights, (id, v) => { o.class_weights[id] = v; }, full(cfg.classes.map((c) => c.id), saved.class_weights)),
      h("h4", { style: { marginTop: "10px" } }, "Trait weights"),
      weightGrid(cfg.traits.map((t) => ({ id: t.id, name: t.name })), o.trait_weights, (id, v) => { o.trait_weights[id] = v; }, full(cfg.traits.map((t) => t.id), saved.trait_weights)),
      h("details", { style: { marginTop: "10px" } }, h("summary", {}, "Direct specialization weights"),
        cfg.classes.map((c) => h("div", { style: { marginTop: "6px" } }, h("h4", { style: { margin: "0 0 4px" } }, c.name),
          weightGrid(c.specializations.map((sp) => ({ id: `${c.id}/${sp.id}`, name: sp.name })), o.spec_weights, (id, v) => { o.spec_weights[id] = v; }, full(specKeys(), saved.spec_weights || {}))))),
      h("div", { class: "row", style: { marginTop: "10px" } }, h("button", { class: "btn small danger", type: "button", onclick: () => { overrides.splice(idx, 1); drawOverrides(); } }, "Remove override"))));
  });
}

function profileText(map) { return Object.entries(map).map(([k, v]) => `${k}=${v}`).join(", "); }
function parseProfile(text) {
  const out = {}, ids = new Set(cfg.traits.map((t) => t.id));
  for (const part of text.split(/[,\n]/).map((s) => s.trim()).filter(Boolean)) {
    const [k, v] = part.split(/\s*[=:]\s*/);
    const n = Number(v);
    if (!ids.has(k)) throw new Error(`Unknown trait "${k}". Known traits: ${[...ids].join(", ")}`);
    if (!Number.isFinite(n) || n < 0) throw new Error(`"${part}" needs a non-negative number.`);
    out[k] = n;
  }
  if (!Object.keys(out).length) throw new Error("A profile needs at least one trait.");
  return out;
}

function addSpecOverride(cid, sid) {
  if (specOverrides.some((o) => o.class_id === cid && o.specialization_id === sid)) { toast("That specialization already has an override.", "warn"); return; }
  const spec = cfg.classes.find((c) => c.id === cid).specializations.find((s) => s.id === sid);
  specOverrides.push({ class_id: cid, specialization_id: sid, text: profileText(spec.trait_multipliers) });
  drawSpecOverrides();
}

function drawSpecOverrides() {
  clear(specBox);
  if (!specOverrides.length) specBox.append(h("p", { class: "muted" }, "No profile overrides."));
  specOverrides.forEach((o, idx) => {
    const err = h("div");
    const ta = h("textarea", { rows: 2, "aria-label": `Profile for ${o.class_id} ${o.specialization_id}`, oninput: () => { o.text = ta.value; try { parseProfile(o.text); clear(err); } catch (e) { clear(err).append(h("p", { class: "errors" }, e.message)); } } }, o.text);
    specBox.append(h("details", { open: true },
      h("summary", {}, `${o.class_id}: ${o.specialization_id}`, " ", badge("temporary", "info")),
      h("p", { class: "muted", style: { fontSize: "0.85rem" } }, "trait=multiplier pairs in order: primary, secondary, tertiary… (any number of traits)"),
      ta, err,
      h("div", { class: "row", style: { marginTop: "8px" } }, h("button", { class: "btn small danger", type: "button", onclick: () => { specOverrides.splice(idx, 1); drawSpecOverrides(); } }, "Remove override"))));
  });
}

function payloadOverrides() {
  const specs = specOverrides.map((o) => ({ class_id: o.class_id, specialization_id: o.specialization_id, trait_multipliers: parseProfile(o.text) }));
  const ans = overrides.map((o) => {
    const bad = [...Object.values(o.class_weights), ...Object.values(o.trait_weights), ...Object.values(o.spec_weights)].some((v) => !Number.isFinite(v));
    if (bad) throw new Error(`Override ${o.question_id}/${o.answer_id} contains an invalid weight.`);
    return { question_id: o.question_id, answer_id: o.answer_id, class_weights: nonzero(o.class_weights), trait_weights: nonzero(o.trait_weights), spec_weights: nonzero(o.spec_weights) };
  });
  return { overrides: ans, specialization_overrides: specs };
}

async function runCompare() {
  if (!Object.keys(state.adminAnswers).length) { toast("Choose at least one answer first.", "warn"); return; }
  try {
    const rank = { short: 0, medium: 1, long: 2 }, length = lengthSel.value;
    const asked = new Set(cfg.questions.filter((q) => q.enabled && rank[q.min_length || "long"] <= rank[length]).map((q) => q.id));   // only this length's questions
    const body = { answers: Object.fromEntries(Object.entries(state.adminAnswers).filter(([id]) => asked.has(id))), length, ...payloadOverrides() };
    clear(resultBox).append(h("p", { class: "muted" }, "Evaluating…"));
    const sim = await post("/simulate", body);
    clear(resultBox).append(h("div", { class: "card" }, h("h3", {}, "Saved vs simulated"),
      !body.overrides.length && !body.specialization_overrides.length ? h("p", { class: "note" }, "No temporary changes yet, so both sides are identical.") : null,
      comparisonView(sim)));
  } catch (e) { clear(resultBox).append(h("div", { class: "card" }, errorList(e))); }
}

async function runBatch(count, seed) {
  if (!Number.isInteger(count) || count < 1 || count > 20000) { toast("Choose between 1 and 20,000 random sets.", "warn"); return; }
  try {
    const body = { count, length: lengthSel.value, ...(seed !== null && Number.isFinite(seed) ? { seed } : {}), ...payloadOverrides() };
    clear(resultBox).append(h("p", { class: "muted" }, `Scoring ${count.toLocaleString()} random answer sets…`));
    const batch = await post("/simulate/batch", body);
    clear(resultBox).append(h("div", { class: "card" }, h("h3", {}, "Batch diagnostic"), batchView(batch)));
  } catch (e) { clear(resultBox).append(h("div", { class: "card" }, errorList(e))); }
}
