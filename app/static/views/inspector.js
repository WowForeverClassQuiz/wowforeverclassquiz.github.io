// Scoring Inspector: shows exactly how each answer moved every class and trait, using the server's numbers.
import { h, clear, fmt, signed, badge, toast, errorList, barChart, chartLegend, tipRows, roleLabel, debounce } from "../ui.js";
import { post } from "../api.js";
import { state, ensureConfig, randomAnswers } from "../state.js";
import { answerPicker } from "./shared.js";

let root, cfg, out, countEl, pickerHost;
let selClass = null, selQuestion = null;

export async function render(container) {
  root = container;
  cfg = await ensureConfig(true);
  const answers = state.adminAnswers;
  selQuestion = null; selClass = null;

  countEl = h("span", { class: "muted" });
  pickerHost = h("div");
  out = h("div", { class: "stack", style: { marginTop: "20px" } });
  const run = debounce(evaluate, 150);

  const changed = () => { updateCount(); run(); };
  const mountPicker = () => clear(pickerHost).append(answerPicker(cfg, state.adminAnswers, changed));
  const set = (a) => { state.adminAnswers = a; mountPicker(); changed(); };

  clear(root).append(
    h("div", { class: "page-head" },
      h("div", {}, h("h1", {}, "Scoring Inspector"),
        h("p", {}, "Pick a response set and see how every answer affected every class and trait. All numbers come from the server's evaluation."))),
    h("div", { class: "card" },
      h("div", { class: "row between" },
        h("h3", { style: { margin: 0 } }, "Response set"),
        h("div", { class: "row" }, countEl,
          h("button", { class: "btn small", type: "button", disabled: !Object.keys(state.answers).length, title: "Copy the answers from the quiz you just took", onclick: () => set({ ...state.answers }) }, "Use my quiz answers"),
          h("button", { class: "btn small", type: "button", onclick: () => set(randomAnswers(cfg)) }, "Random"),
          h("button", { class: "btn small", type: "button", onclick: () => set({}) }, "Clear"))),
      h("details", { open: !Object.keys(answers).length, style: { marginTop: "12px" } }, h("summary", {}, "Choose answers (A–D per question)"), pickerHost)),
    out,
  );
  mountPicker();
  updateCount();
  evaluate();
}

function updateCount() {
  const total = cfg.questions.filter((q) => q.enabled).length;
  countEl.textContent = `${Object.keys(state.adminAnswers).length} of ${total} answered`;
}

async function evaluate() {
  const answers = state.adminAnswers;
  if (!Object.keys(answers).length) {
    state.adminEval = null;
    clear(out).append(h("div", { class: "note" }, "No answers selected yet. Take the quiz, use random answers, or pick answers above."));
    return;
  }
  try {
    const ev = await post("/evaluate", { answers, include_explanation: true, include_counterfactuals: true, allow_partial: true });
    state.adminEval = ev;
    drawResult(ev);
  } catch (e) { clear(out).append(h("div", { class: "card" }, errorList(e))); }
}

const cellClass = (v) => (v > 1e-9 ? "pos" : v < -1e-9 ? "neg" : "zero");
const cell = (v) => h("td", { class: `num ${cellClass(v)}` }, Math.abs(v) < 1e-9 ? "·" : signed(v));

function drawResult(ev) {
  const { result: p, rankings: rk, explanation: ex, metadata: m } = ev;
  const leader = rk.classes[0];
  if (!selClass || !rk.classes.some((c) => c.id === selClass)) selClass = leader.id;
  clear(out);

  out.append(h("div", { class: "card" },
    h("div", { class: "stats" },
      stat(`${p.primary_specialization.name} ${p.primary_class.name}`, "primary result"),
      stat(`${ev.alternatives.alternative_specialization.name} ${ev.alternatives.alternative_class.name}`, "alternative class"),
      stat(ev.alternatives.second_specialization_in_primary_class.name, `second specialization in ${p.primary_class.name}`),
      stat(`${p.confidence.label} (${fmt(p.confidence.class_gap)})`, "gap between top two classes (heuristic)"),
      stat(`r${m.config_revision}`, "configuration revision"),
      stat(m.algorithm_version, "scoring algorithm"),
      stat(`×${m.spec_weight_multiplier}`, "direct specialization weight multiplier")),
    h("div", { class: "row", style: { marginTop: "12px" } },
      badge(m.complete ? "complete assessment" : `provisional: ${m.answered_questions} of ${m.total_questions} answered`, m.complete ? "ok" : "warn"),
      ex.tie_breaks.length ? badge(`${ex.tie_breaks.length} tie-break${ex.tie_breaks.length > 1 ? "s" : ""} applied`, "info") : badge("no ties", ""))));

  // -- class chart + trait table
  const rows = rk.classes.map((c) => ({
    id: c.id, label: c.name, value: c.score,
    tip: [["Adjusted score", signed(c.score)], ["Raw points", fmt(c.raw_points)], ["Expected (baseline)", fmt(c.expected_points)], ["Gap to leader", fmt(c.gap_to_leader)]],
  }));
  out.append(h("div", { class: "grid two" },
    h("div", { class: "card" }, h("h3", {}, "Class scores"),
      h("p", { class: "muted", style: { fontSize: "0.88rem" } }, "Adjusted score = chosen weight minus the question's average weight, summed over questions. Click a class to highlight its column below."),
      barChart(rows, { selectedId: selClass, leadId: leader.id, onSelect: (id) => { selClass = id; drawResult(ev); } }),
      chartLegend()),
    h("div", { class: "card" }, h("h3", {}, "Personality traits"), traitTable(rk.traits)),
  ));

  // -- specializations
  out.append(h("div", { class: "grid two" },
    h("div", { class: "card" }, h("h3", {}, `Specializations: ${p.primary_class.name} (winning class)`), specTable(rk.specializations)),
    h("div", { class: "card" }, h("h3", {}, `Specializations: ${ev.alternatives.alternative_class.name} (alternative)`), specTable(rk.alternative_class_specializations))));

  if (ex.tie_breaks.length) out.append(h("div", { class: "card" }, h("h3", {}, "Tie-breaking"),
    h("ul", {}, ex.tie_breaks.map((t) => h("li", {}, `${t.scope === "class" ? "Classes" : `${t.scope_id} specializations`} tied at ${signed(t.score)}: ${t.tied.join(", ")} (positions ${t.positions.join(", ")}). ${t.rule}`)))));

  // -- per-question contribution table
  out.append(contributionCard(ev));
  out.append(h("div", { id: "qdetail" }));
  if (selQuestion) drawQuestionDetail(ev);
  out.append(counterfactualCard(ev));
}

const stat = (value, label) => h("div", { class: "stat" }, h("b", { style: { fontSize: "1.15rem" } }, value), h("span", {}, label));

function traitTable(traits) {
  return h("div", { class: "table-wrap" }, h("table", {},
    h("thead", {}, h("tr", {}, h("th", {}, "#"), h("th", {}, "Trait"), h("th", { class: "num" }, "Adjusted"), h("th", { class: "num", title: "Sum of the chosen answers' raw weights" }, "Raw"), h("th", { class: "num", title: "Sum of the questions' average weights" }, "Expected"), h("th", { class: "num", title: "Selected answers that gave this trait weight" }, "Appeared"))),
    h("tbody", {}, traits.map((t) => h("tr", {}, h("td", {}, String(t.rank)), h("td", {}, t.name, t.tied_with_previous ? " (tie)" : ""), h("td", { class: `num ${cellClass(t.score)}` }, signed(t.score)), h("td", { class: "num" }, fmt(t.raw_points)), h("td", { class: "num" }, fmt(t.expected_points)), h("td", { class: "num" }, String(t.appearances)))))));
}

function specTable(specs) {
  return h("div", { class: "table-wrap" }, h("table", {},
    h("thead", {}, h("tr", {}, h("th", {}, "#"), h("th", {}, "Specialization"), h("th", { class: "num" }, "Score"), h("th", {}, "Calculation (multiplier × trait score)"))),
    h("tbody", {}, specs.map((s) => h("tr", {}, h("td", {}, String(s.rank)), h("td", {}, h("b", {}, s.name), h("div", { class: "muted", style: { fontSize: "0.78rem" } }, roleLabel(s.role)), s.tied_with_previous ? " (tie)" : ""),
      h("td", { class: `num ${cellClass(s.score)}` }, signed(s.score)),
      h("td", { class: "wrap", style: { fontSize: "0.82rem" } },
        s.terms.map((t) => `${t.trait_name}: ${t.multiplier} × ${signed(t.trait_score)} = ${signed(t.contribution)}`).join("  ·  "),
        s.direct_score ? `  ·  direct question weights: ${signed(s.direct_score)}` : ""))))));
}

function contributionCard(ev) {
  const ex = ev.explanation;
  const order = ev.rankings.classes.map((c) => ({ id: c.id, name: c.name, score: c.score }));
  const totals = Object.fromEntries(order.map((c) => [c.id, ex.questions.reduce((s, q) => s + q.class_contributions[c.id].adjusted, 0)]));
  const ok = order.every((c) => Math.abs(totals[c.id] - c.score) < 1e-6);
  const lead = order[0].name, runner = order[1].name;
  return h("div", { class: "card" },
    h("h3", {}, "Per-question contributions to each class"),
    h("p", { class: "muted", style: { fontSize: "0.88rem" } }, "Each cell is the chosen answer's adjusted contribution (blue +, red −). Click a row for the raw, baseline and adjusted values behind it."),
    h("div", { class: "table-wrap" }, h("table", {},
      h("thead", {}, h("tr", {}, h("th", {}, "Q"), h("th", {}, "Chosen"),
        order.map((c) => h("th", { class: `num${c.id === selClass ? " sel" : ""}`, style: c.id === selClass ? { background: "var(--accent-soft)", color: "var(--text)" } : null }, c.name)),
        h("th", { class: "num", title: "Sum over classes; zero under the original weighting" }, "Σ"),
        h("th", { class: "num", title: `Contribution to ${lead} minus ${runner}` }, `${lead} − ${runner}`))),
      h("tbody", {}, ex.questions.map((q) => h("tr", { class: `clickable${q.question_id === selQuestion ? " sel" : ""}`, tabindex: 0, onclick: () => selectQuestion(ev, q.question_id), onkeydown: (e) => { if (e.key === "Enter") selectQuestion(ev, q.question_id); } },
        h("td", { class: "mono", title: q.question_text }, q.question_id), h("td", { title: q.answer_text }, q.question_type === "scale" ? q.answer_id : q.answer_id.toUpperCase()),
        order.map((c) => cell(q.class_contributions[c.id].adjusted)),
        h("td", { class: "num zero" }, signed(q.class_adjusted_sum)),
        h("td", { class: `num ${cellClass(q.leader_margin_effect)}` }, signed(q.leader_margin_effect))))),
      h("tfoot", {}, h("tr", {}, h("td", { colspan: 2 }, "Total"), order.map((c) => h("td", { class: "num" }, signed(totals[c.id]))), h("td", {}, ""),
        h("td", { class: "num" }, signed(ex.questions.reduce((s, q) => s + q.leader_margin_effect, 0))))))),
    h("p", { class: "bar-note" }, ok ? "✓ Column totals equal the class scores in the ranking above." : "⚠ Column totals differ from the ranking. This should never happen."));
}

function selectQuestion(ev, id) { selQuestion = selQuestion === id ? null : id; drawResult(ev); if (selQuestion) document.getElementById("qdetail")?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }

function drawQuestionDetail(ev) {
  const q = ev.explanation.questions.find((x) => x.question_id === selQuestion);
  const host = document.getElementById("qdetail");
  if (!q || !host) return;
  const names = Object.fromEntries([...cfg.classes, ...cfg.traits].map((x) => [x.id, x.name]));
  for (const cl of cfg.classes) for (const sp of cl.specializations) names[`${cl.id}/${sp.id}`] = `${cl.name} · ${sp.name}`;
  const tbl = (cells, label) => h("div", { class: "table-wrap" }, h("table", {},
    h("thead", {}, h("tr", {}, h("th", {}, label), h("th", { class: "num" }, "Raw weight"), h("th", { class: "num" }, "Baseline (mean)"), h("th", { class: "num" }, "Adjusted"))),
    h("tbody", {}, Object.entries(cells).map(([id, c]) => h("tr", { class: id === selClass ? "sel" : "" }, h("td", {}, names[id] || id), h("td", { class: "num" }, fmt(c.raw)), h("td", { class: "num" }, fmt(c.baseline, 3)), h("td", { class: `num ${cellClass(c.adjusted)}` }, signed(c.adjusted, 3)))))));
  host.append(h("div", { class: "card" },
    h("div", { class: "row between" }, h("h3", { style: { margin: 0 } }, `${q.question_id.toUpperCase()}, answer ${q.answer_id.toUpperCase()}`),
      h("a", { class: "btn small", href: "#/admin/questions", onclick: () => { state.editorQuestion = q.question_id; } }, "Edit these weights")),
    h("p", { class: "muted" }, q.question_text), h("p", {}, h("b", {}, "Chosen: "), q.answer_text),
    h("div", { class: "grid two" }, h("div", {}, h("h4", {}, "Classes"), tbl(q.class_contributions, "Class")), h("div", {}, h("h4", {}, "Traits"), tbl(q.trait_contributions, "Trait"))),
    Object.keys(q.spec_contributions || {}).length
      ? h("div", { style: { marginTop: "16px" } }, h("h4", {}, `Direct specialization weights (multiplied by ${ev.metadata.spec_weight_multiplier} before they are added)`), tbl(q.spec_contributions, "Specialization"))
      : h("p", { class: "muted", style: { marginTop: "12px", fontSize: "0.88rem" } }, "This question has no direct specialization weights; it moves specializations only through traits.")));
}

function counterfactualCard(ev) {
  const cfs = ev.explanation.counterfactuals || [];
  const changing = cfs.filter((c) => c.specialization_changed);
  const row = (c) => h("tr", {}, h("td", { class: "mono" }, c.question_id), h("td", { class: "wrap" }, `${c.answer_id.toUpperCase()}. ${c.answer_text}`),
    h("td", {}, `${c.primary_specialization_name} ${c.primary_class_name}`), h("td", {}, c.class_changed ? badge("class changes", "bad") : c.specialization_changed ? badge("specialization changes", "warn") : badge("same", "")), h("td", { class: "num" }, fmt(c.class_gap)));
  const table = (list) => h("div", { class: "table-wrap" }, h("table", {}, h("thead", {}, h("tr", {}, ["Q", "If this answer were chosen instead", "Result", "Effect", "Gap"].map((t) => h("th", {}, t)))), h("tbody", {}, list.map(row))));
  return h("div", { class: "card" },
    h("h3", {}, "What-if: choosing a different answer"),
    h("p", { class: "muted", style: { fontSize: "0.88rem" } }, `${changing.length} of ${cfs.length} single-answer changes would alter the recommended specialization.`),
    changing.length ? table(changing) : h("p", { class: "note" }, "No single answer change would alter the result: the recommendation is stable."),
    cfs.length ? h("details", { style: { marginTop: "12px" } }, h("summary", {}, `All ${cfs.length} alternatives`), table(cfs)) : null);
}
