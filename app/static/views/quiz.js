// Participant interface: the assessment and the result reveal. Never requests scoring weights.
import { h, append, clear, fmt, signed, titleCase, roleLabel, purposeLabel, badge, toast, copyText, download, barChart, chartLegend, errorList, CLASS_COLORS } from "../ui.js";
import { get, post, STATIC } from "../api.js";
import { state } from "../state.js";
import { classIcon, specIcon, spellName } from "../icons.js";
import { talentTrees, dataNotice } from "../talenttree.js";

let root = null;
/** Null-safe: Element.append(null) would print the word "null" into the page. */
const put = (...kids) => append(root, kids);
let keyHandlerInstalled = false;

export async function render(container) {
  root = container;
  if (!state.quiz) state.quiz = await get("/quiz");
  installKeys();
  draw();
}

function draw() {
  clear(root);
  if (state.result) return drawResult();
  if (!state.started) return drawIntro();
  drawQuestion();
}

/** The quiz lengths on offer (an older server or configuration may offer none: then the whole quiz is the only length). */
const lengths = () => state.quiz.lengths || [];
const currentLength = () => lengths().find((l) => l.id === state.length) || lengths().find((l) => l.id === state.quiz.default_length) || lengths()[lengths().length - 1] || null;
/** The questions of the chosen length, in quiz order. */
const questions = () => {
  const len = currentLength();
  return len ? len.question_ids.map((id) => state.quiz.questions.find((q) => q.id === id)).filter(Boolean) : state.quiz.questions;
};
const total = () => questions().length;
const answered = () => questions().filter((q) => state.answers[q.id]).length;
const complete = () => answered() === total();
const nextLength = () => { const ls = lengths(), i = ls.findIndex((l) => l.id === currentLength()?.id); return i >= 0 && i < ls.length - 1 ? ls[i + 1] : null; };
const firstUnanswered = () => Math.max(0, questions().findIndex((q) => !state.answers[q.id]));

// ---------------------------------------------------------------------------- intro
function drawIntro() {
  const resuming = answered() > 0;
  put(
    h("section", { class: "hero" },
      h("div", { class: "sigil", "aria-hidden": "true" }, "✦"),
      h("h1", {}, state.quiz.title),
      h("p", { class: "sub" }, state.quiz.subtitle || "A short reading of your temperament."),
      lengthPicker(),
      h("p", { class: "sub" }, `${total()} questions. There are no right answers; choose whatever draws you first.`),
      h("button", { class: "btn primary large", type: "button", id: "begin", onclick: () => { state.started = true; state.length = currentLength()?.id || null; state.index = resuming ? firstUnanswered() : 0; draw(); } },
        resuming ? "Continue your reading" : "Begin"),
      h("p", { class: "muted", style: { marginTop: "28px", fontSize: "0.85rem" } },
        STATIC ? "Your answers are scored right here in your browser. Nothing is sent or stored anywhere."
          : "Your answers stay in this browser tab. Nothing is stored on the server."),
    ),
  );
  document.getElementById("begin").focus();
}

/** Short / medium / long: how many questions to answer. Nothing is chosen for you except the middle one when it exists. */
function lengthPicker() {
  const ls = lengths();
  if (ls.length < 2) return null;
  const chosen = currentLength();
  return h("fieldset", { class: "lengths" },
    h("legend", {}, "How long a reading would you like?"),
    ls.map((l) => h("label", { class: "length" },
      h("input", { type: "radio", name: "quiz-length", value: l.id, checked: chosen.id === l.id, onchange: () => { state.length = l.id; draw(); document.querySelector(`input[name="quiz-length"][value="${l.id}"]`)?.focus(); } }),
      h("span", { class: "length-name" }, l.name),
      h("span", { class: "length-meta" }, `${l.question_count} questions · about ${l.minutes} min`),
      h("span", { class: "length-blurb" }, l.description))));
}

// ---------------------------------------------------------------------------- question
state.picks ||= {};   // in-progress pick-two selections (a finished pair is stored in state.answers)

const TIPS = {
  choice: "Tip: press 1\u20134 to choose, Enter for next.",
  scale: "Tip: press 1\u20139 for a rating (0 for 10), Enter for next.",
  pick_two: "Tip: press 1\u20134 to pick or unpick, Enter for next.",
  ranking: "Tip: press 1\u20134 to rank an item next (press it again to undo from there), Backspace to start over, Enter for next.",
  allocation: "Tip: press 1\u20134 to give an item a point, Backspace to start over, Enter for next.",
};

const EYEBROWS = { choice: "Choose one", scale: "How much do you agree?", pick_two: "Choose two", ranking: "Put them in order", allocation: "Spend your points" };

function drawQuestion() {
  const qs = questions();
  state.index = Math.min(state.index, qs.length - 1);
  const q = qs[state.index];
  const n = total(), i = state.index;
  const isLast = i === n - 1;
  const chosen = state.answers[q.id];

  const dots = h("div", { class: "dots", role: "group", "aria-label": "Jump to a question" },
    qs.map((qq, k) => h("button", {
      type: "button", class: `${state.answers[qq.id] ? "done" : ""} ${k === i ? "current" : ""}`,
      "aria-label": `Question ${k + 1}${state.answers[qq.id] ? ", answered" : ", unanswered"}`,
      "aria-current": k === i ? "step" : null,
      onclick: () => { state.index = k; draw(); },
    })));

  const groupId = `q-${q.id}`;
  const control = ({ scale: scaleControl, pick_two: pickControl, ranking: rankingControl, allocation: allocationControl }[q.type] || choiceControl)(q, groupId);

  const missing = total() - answered();
  const next = isLast
    ? h("button", { class: "btn primary large", type: "button", id: "reveal", disabled: !complete(), onclick: reveal }, "Reveal my reading")
    : h("button", { class: "btn primary", type: "button", id: "next", disabled: !chosen, onclick: () => { state.index = i + 1; draw(); } }, "Next");

  put(
    h("div", { class: "progress-label" }, h("span", {}, `Question ${i + 1} of ${n}`), h("span", {}, `${answered()} answered`)),
    h("div", { class: "progress", role: "progressbar", "aria-valuemin": 0, "aria-valuemax": n, "aria-valuenow": answered(), "aria-label": "Questions answered" },
      h("i", { style: { width: `${(answered() / n) * 100}%` } })),
    dots,
    h("p", { class: "eyebrow-q" }, EYEBROWS[q.type] || EYEBROWS.choice),
    h("h2", { class: "question", id: groupId }, q.text),
    control,
    h("div", { class: "nav-row" },
      h("button", { class: "btn", type: "button", id: "prev", disabled: i === 0, onclick: () => { state.index = i - 1; draw(); } }, "Previous"),
      next),
    ...(isLast && missing > 0
      ? [h("p", { class: "muted", style: { textAlign: "right", marginTop: "10px" } }, `${missing} question${missing === 1 ? " is" : "s are"} still unanswered. Use the dots above to find ${missing === 1 ? "it" : "them"}.`)]
      : []),
    h("p", { class: "muted", style: { fontSize: "0.82rem", marginTop: "18px" } }, TIPS[q.type] || TIPS.choice),
  );
}

function choiceControl(q, groupId) {
  const chosen = state.answers[q.id];
  return h("div", { class: "answers", role: "radiogroup", "aria-labelledby": groupId }, q.answers.map((a, k) =>
    h("label", { class: "answer" },
      h("input", {
        type: "radio", name: groupId, value: a.id, checked: chosen === a.id,
        onchange: () => choose(q, a.id),
      }),
      h("span", { class: "key", "aria-hidden": "true" }, String(k + 1)),
      h("span", {}, a.text))));
}

/** 1-10 agreement scale. The participant never sees what each rating is worth. */
function scaleControl(q, groupId) {
  const chosen = state.answers[q.id];
  const lo = q.scale_min ?? 1, hi = q.scale_max ?? 10;
  const values = Array.from({ length: hi - lo + 1 }, (_, k) => String(lo + k));
  return h("div", { class: "scale", role: "radiogroup", "aria-labelledby": groupId },
    h("div", { class: "scale-row" }, values.map((v) =>
      h("label", { class: "scale-opt" },
        h("input", {
          type: "radio", name: groupId, value: v, checked: chosen === v,
          "aria-label": `${v} of ${hi}${v === String(lo) ? `, ${q.low_label}` : v === String(hi) ? `, ${q.high_label}` : ""}`,
          onchange: () => choose(q, v),
        }),
        h("span", {}, v)))),
    h("div", { class: "scale-ends", "aria-hidden": "true" }, h("span", {}, q.low_label), h("span", {}, q.high_label)));
}

/** Pick exactly two of the four items. Once two are chosen the others lock until one is released. */
function pickControl(q, groupId) {
  const order = q.answers.map((a) => a.id);
  const sel = state.answers[q.id] ? state.answers[q.id].split("+") : (state.picks[q.id] || []);
  const toggle = (id) => {
    let next = sel.includes(id) ? sel.filter((x) => x !== id) : sel.length < 2 ? [...sel, id] : sel;
    state.picks[q.id] = next;
    if (next.length === 2) state.answers[q.id] = [...next].sort((a, b) => order.indexOf(a) - order.indexOf(b)).join("+");
    else delete state.answers[q.id];
    draw();
    focusAnswer(id);
  };
  return h("div", {},
    h("div", { class: "answers", role: "group", "aria-labelledby": groupId }, q.answers.map((a, k) =>
      h("label", { class: "answer" },
        h("input", { type: "checkbox", value: a.id, checked: sel.includes(a.id), disabled: sel.length >= 2 && !sel.includes(a.id), onchange: () => toggle(a.id) }),
        h("span", { class: "key", "aria-hidden": "true" }, String(k + 1)),
        h("span", {}, a.text)))),
    h("p", { class: "pickhint", role: "status" }, `${sel.length} of 2 chosen`));
}

/** Rank all four items: tap them in order, best first. Tapping a ranked item undoes the ranking from that item on. */
function rankingControl(q, groupId) {
  const ids = q.answers.map((a) => a.id);
  const ranked = state.answers[q.id] ? state.answers[q.id].split(">") : (state.picks[q.id] || []);
  const tap = (id) => {
    const next = ranked.includes(id) ? ranked.slice(0, ranked.indexOf(id)) : [...ranked, id];
    state.picks[q.id] = next;
    if (next.length === ids.length) state.answers[q.id] = next.join(">"); else delete state.answers[q.id];
    draw();
    focusAnswer(id);
  };
  return h("div", {},
    h("div", { class: "answers", role: "group", "aria-labelledby": groupId }, q.answers.map((a) => {
      const rank = ranked.indexOf(a.id) + 1;
      return h("label", { class: "answer ranking" },
        h("input", { type: "checkbox", value: a.id, checked: rank > 0, "aria-label": `${a.text}${rank ? `, ranked ${rank}` : ", not ranked yet"}`, onchange: () => tap(a.id) }),
        h("span", { class: "key", "aria-hidden": "true" }, rank ? String(rank) : "\u2013"),
        h("span", {}, a.text));
    })),
    h("p", { class: "pickhint", role: "status" }, ranked.length === ids.length ? "All four ranked." : `${ranked.length} of ${ids.length} ranked: tap the next one.`,
      ranked.length ? [" ", h("button", { class: "linkish", type: "button", onclick: () => { state.picks[q.id] = []; delete state.answers[q.id]; draw(); } }, "Start over")] : null));
}

/** Spend a fixed number of points across the four items with + and - buttons. */
function allocationControl(q, groupId) {
  const total = q.points || 6;
  const pts = state.answers[q.id] ? state.answers[q.id].split("-").map(Number) : (state.picks[q.id] || q.answers.map(() => 0));
  const left = total - pts.reduce((s, x) => s + x, 0);
  const change = (i, delta) => {
    const next = [...pts];
    next[i] += delta;
    state.picks[q.id] = next;
    if (next.reduce((s, x) => s + x, 0) === total) state.answers[q.id] = next.join("-"); else delete state.answers[q.id];
    draw();
    const again = root.querySelector(`[data-alloc="${i}:${delta > 0 ? "+" : "-"}"]`);
    (again && !again.disabled ? again : root.querySelector(`[data-alloc="${i}:${delta > 0 ? "-" : "+"}"]`) || root).focus?.();
  };
  return h("div", {},
    h("div", { class: "alloc", role: "group", "aria-labelledby": groupId }, q.answers.map((a, i) =>
      h("div", { class: `alloc-row${pts[i] ? " has" : ""}` },
        h("span", { class: "key", "aria-hidden": "true" }, String(i + 1)),
        h("span", { class: "alloc-text" }, a.text),
        h("span", { class: "alloc-ctl" },
          h("button", { type: "button", class: "step", "data-alloc": `${i}:-`, disabled: pts[i] === 0, "aria-label": `Take a point from: ${a.text}`, onclick: () => change(i, -1) }, "\u2212"),
          h("span", { class: "alloc-val", "aria-label": `${pts[i]} of ${total} points` }, String(pts[i])),
          h("button", { type: "button", class: "step", "data-alloc": `${i}:+`, disabled: left === 0, "aria-label": `Give a point to: ${a.text}`, onclick: () => change(i, 1) }, "+")),
        h("span", { class: "alloc-pips", "aria-hidden": "true" }, Array.from({ length: total }, (_, k) => h("i", { class: k < pts[i] ? "on" : "" })))))),
    h("p", { class: "pickhint", role: "status" }, left === 0 ? `All ${total} points spent.` : `${left} of ${total} points left to spend.`,
      left < total ? [" ", h("button", { class: "linkish", type: "button", onclick: () => { state.picks[q.id] = q.answers.map(() => 0); delete state.answers[q.id]; draw(); } }, "Start over")] : null));
}

function choose(q, value) {
  state.answers[q.id] = value;
  draw();
  focusAnswer(value);
}

function focusAnswer(id) {
  const el = root.querySelector(`input[value="${CSS.escape(id)}"]`);
  if (el) el.focus();
}

function installKeys() {
  if (keyHandlerInstalled) return;
  keyHandlerInstalled = true;
  document.addEventListener("keydown", (e) => {
    if (!state.started || state.result || !state.quiz || !document.getElementById("view").contains(root) || location.hash.replace(/^#\/?/, "") !== "") return;
    if (e.target.matches("input[type=text], textarea, select") || e.metaKey || e.ctrlKey || e.altKey) return;
    const q = questions()[state.index];
    if (!q) return;
    if (/^[0-9]$/.test(e.key)) {
      if (q.type === "scale") {
        choose(q, e.key === "0" ? String(q.scale_max ?? 10) : e.key);
      } else if (q.type === "pick_two" || q.type === "ranking") {
        const a = q.answers[+e.key - 1];
        const box = a && root.querySelector(`input[value="${CSS.escape(a.id)}"]`);
        if (box && !box.disabled) box.click();
      } else if (q.type === "allocation") {
        const plus = root.querySelector(`[data-alloc="${+e.key - 1}:+"]`);
        if (plus && !plus.disabled) plus.click();
      } else if (q.answers[+e.key - 1]) {
        choose(q, q.answers[+e.key - 1].id);
      }
    } else if (e.key === "Backspace" && (q.type === "ranking" || q.type === "allocation") && !e.target.matches("input[type=text], textarea")) {
      e.preventDefault();
      state.picks[q.id] = q.type === "allocation" ? q.answers.map(() => 0) : [];
      delete state.answers[q.id];
      draw();
    } else if (e.key === "Enter" && state.answers[q.id] && e.target.tagName !== "BUTTON") {
      const btn = document.getElementById("next") || document.getElementById("reveal");
      if (btn && !btn.disabled) btn.click();
    }
  });
}

// ---------------------------------------------------------------------------- reveal
async function reveal() {
  if (!complete()) {
    const first = firstUnanswered();
    toast(`Question ${first + 1} is still unanswered.`, "warn");
    state.index = first;
    return draw();
  }
  clear(root); put(h("div", { class: "reveal", role: "status" },
    h("div", { class: "sigil", "aria-hidden": "true" }, "✦"),
    h("h2", {}, "Reading the stars…")));
  try {
    const [result] = await Promise.all([
      post("/evaluate", { answers: Object.fromEntries(questions().map((q) => [q.id, state.answers[q.id]])), length: currentLength()?.id || "long", include_explanation: false }),
      new Promise((r) => setTimeout(r, window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 1300)),
    ]);
    state.result = result;
    state.adminAnswers = { ...state.answers };
    state.adminEval = null;
    draw();
    window.scrollTo(0, 0);
  } catch (err) {
    clear(root); put(h("div", { class: "card" }, h("h2", {}, "The reading could not be completed"), errorList(err),
      h("button", { class: "btn", type: "button", onclick: () => draw() }, "Back to the questions")));
  }
}

// ---------------------------------------------------------------------------- result
function restart() {
  state.answers = {}; state.picks = {}; state.index = 0; state.started = false; state.result = null; state.length = null;
  draw();
  window.scrollTo(0, 0);
}

function lengthChip(r) {
  const meta = r.metadata, len = lengths().find((l) => l.id === meta.quiz_length);
  if (!len || lengths().length < 2) return null;
  return h("span", { class: "chip", title: "How many questions this reading is based on" }, h("b", {}, `${len.name} reading`), h("i", {}, `${meta.total_questions} questions`));
}

/** After a shorter reading: answer the extra questions of the next length and keep every answer already given. */
function refineButton() {
  const next = nextLength();
  if (!next) return null;
  const more = next.question_count - total();
  return h("button", { class: "btn", type: "button", id: "refine", onclick: () => {
    state.length = next.id; state.started = true; state.result = null; state.index = firstUnanswered(); draw(); window.scrollTo(0, 0);
  } }, `Sharpen it: ${more} more question${more === 1 ? "" : "s"} (${next.name.toLowerCase()})`);
}

function resultText(r) {
  const p = r.result, a = r.alternatives;
  const lines = [
    `${state.quiz.title} - Forever Character Oracle`,
    "",
    `Recommended: ${p.primary_class.name} - ${p.primary_specialization.name} (${roleLabel(p.primary_specialization.role)})`,
    `Reading strength: ${p.confidence.label} (heuristic, not a probability), from ${r.metadata.total_questions} questions`,
    p.build ? `Build: ${p.build.name} [${p.build.status}]${p.build.tree_distribution_text ? ` ${p.build.tree_distribution_text}` : ""}` : "",
    `Also in the stars: ${a.alternative_class.name} - ${a.alternative_specialization.name}; within ${p.primary_class.name}, ${a.second_specialization_in_primary_class.name}`,
    "",
    p.personality_interpretation,
    "",
    p.specialization_interpretation,
    "",
    p.class_overview ? `What the ${p.primary_class.name} does: ${p.class_overview} ${p.primary_specialization.name}: ${p.specialization_overview}` : "",
    "",
    "Class scores (relative compatibility, not probabilities):",
    ...r.rankings.classes.map((c) => `  ${c.rank}. ${c.name} ${signed(c.score)}`),
    "",
    `Configuration revision ${r.metadata.config_revision}, algorithm ${r.metadata.algorithm_version}`,
  ];
  return lines.filter((l, i) => l !== "" || lines[i - 1] !== "").join("\n");
}

function drawResult() {
  const r = state.result, p = r.result, alt = r.alternatives;
  const cls = CLASS_COLORS[p.primary_class.id] || "var(--accent)";
  put(
    h("section", { class: "result-hero", style: { "--cls": cls } },
      h("div", { class: "eyebrow" }, "The stars have chosen"),
      h("div", { class: "hero-icons", title: `${p.primary_class.name}: ${spellName(p.primary_class.id, p.primary_specialization.id) || p.primary_specialization.name}` },
        classIcon(p.primary_class.id, 56, p.primary_class.name), specIcon(p.primary_class.id, p.primary_specialization.id, 56)),
      h("h1", {}, p.primary_class.name),
      h("h2", {}, p.primary_specialization.name),
      h("div", { class: "chips" },
        h("span", { class: "chip" }, h("b", {}, roleLabel(p.primary_specialization.role))),
        h("span", { class: "chip", title: p.confidence.note }, h("b", {}, p.confidence.label), h("i", {}, "heuristic")),
        p.dominant_traits.map((t) => h("span", { class: "chip" }, h("b", {}, t.name))),
        lengthChip(r)),
    ),
    h("div", { class: "card prose" }, h("h3", {}, "Your temperament"), h("p", {}, p.personality_interpretation)),
    overviewCard(p),
    h("div", { class: "card prose" }, h("h3", {}, `Why ${p.primary_specialization.name}`), h("p", {}, p.specialization_interpretation)),
    guideCard(p.primary_specialization),
    buildCard(p.build, p.primary_specialization, p.primary_class.id),
    h("div", { class: "grid two", style: { marginTop: "20px" } },
      h("div", { class: "card" },
        h("h3", {}, "Also in the stars"),
        h("p", { class: "alt-line" }, classIcon(alt.alternative_class.id, 36, alt.alternative_class.name), specIcon(alt.alternative_class.id, alt.alternative_specialization.id, 36),
          h("span", {}, h("b", {}, alt.alternative_class.name), ` – ${alt.alternative_specialization.name}`)),
        h("p", { class: "muted" }, alt.alternative_specialization.description),
        h("hr", { style: { border: 0, borderTop: "1px solid var(--border)", margin: "14px 0" } }),
        h("p", { class: "alt-line" }, specIcon(p.primary_class.id, alt.second_specialization_in_primary_class.id, 36),
          h("span", {}, "Within ", h("b", {}, p.primary_class.name), ", your next-closest path is ", h("b", {}, alt.second_specialization_in_primary_class.name), ".")),
        h("p", { class: "muted" }, alt.second_specialization_in_primary_class.description)),
      h("div", { class: "card" },
        h("h3", {}, "The numbers"),
        h("p", { class: "muted", style: { fontSize: "0.88rem" } }, "Relative compatibility, not probabilities. A longer bar to the right means a closer fit than the average answer pattern."),
        barChart(r.rankings.classes.map((c) => ({ id: c.id, label: c.name, value: c.score, icon: classIcon(c.id, 18, c.name) })), { leadId: p.primary_class.id }),
        chartLegend()),
    ),
    h("div", { class: "row", style: { marginTop: "24px", justifyContent: "center" } },
      h("button", { class: "btn", type: "button", onclick: async () => toast((await copyText(resultText(r))) ? "Result copied to the clipboard." : "Copy failed - select the text manually.", "ok") }, "Copy result"),
      h("button", { class: "btn", type: "button", onclick: () => download("oracle-result.json", JSON.stringify(r, null, 2)) }, "Download JSON"),
      refineButton(),
      h("button", { class: "btn", type: "button", onclick: () => { state.started = true; state.result = null; state.index = 0; draw(); } }, "Revise my answers"),
      h("button", { class: "btn primary", type: "button", id: "restart", onclick: restart }, "Restart"),
      STATIC ? null : h("a", { class: "btn ghost", href: "#/admin/inspector" }, "Inspect in admin")),
  );
}

/** "What the class does": the class paragraph, then the specialization's, with a link back to Blizzard's class page. */
function overviewCard(p) {
  if (!p.class_overview && !p.specialization_overview) return null;
  return h("div", { class: "card prose" },
    h("h3", {}, `What the ${p.primary_class.name} does`),
    p.class_overview ? h("p", {}, p.class_overview) : null,
    p.specialization_overview ? h("p", {}, h("b", {}, `${p.primary_specialization.name}. `), p.specialization_overview) : null,
    safeUrl(p.overview_url)
      ? h("p", { class: "muted", style: { fontSize: "0.85rem" } }, "In our own words, from Blizzard's published class description. ",
          h("a", { href: safeUrl(p.overview_url), target: "_blank", rel: "noopener noreferrer" }, `Read Blizzard's ${p.primary_class.name} page`))
      : null);
}

function safeUrl(u) { return /^https?:\/\//i.test(u || "") ? u : null; }

/** Roles in dungeons and raids, gear to look for, and who competes for it. */
function guideCard(spec) {
  const g = spec.guide;
  if (!g) return null;
  const list = (items) => (items && items.length ? h("ul", {}, items.map((x) => h("li", {}, x))) : null);
  return h("div", { class: "card guide" },
    h("h3", {}, `Your role and gear as a ${spec.name} ${spec.class_name}`),
    h("div", { class: "grid two roles" },
      g.dungeon_role ? h("div", {}, h("h4", {}, "In dungeons"), h("p", {}, g.dungeon_role)) : null,
      g.raid_role ? h("div", {}, h("h4", {}, "In raids"), h("p", {}, g.raid_role)) : null),
    g.gear && g.gear.length ? h("div", {}, h("h4", {}, "Gear to look out for"), list(g.gear)) : null,
    g.competes_with && g.competes_with.length ? h("div", {}, h("h4", {}, "Who competes with you for gear"), list(g.competes_with)) : null,
    g.note ? h("p", { class: "muted guide-note" }, g.note) : null);
}

function buildCard(build, spec, classId) {
  if (!build) {
    return h("div", { class: "card" }, h("h3", {}, "Your build"), h("p", { class: "muted" }, `No build has been configured for ${spec.name} yet.`));
  }
  const kind = { verified: "ok", draft: "warn", unverified: "warn", pending: "info" }[build.status] || "";
  const label = { verified: "Verified", draft: "Draft - not verified", unverified: "Unverified", pending: "Allocation pending" }[build.status] || build.status;
  const names = Object.fromEntries(build.talents.map((t) => [t.talent_id, t.name || t.talent_id]));
  const hasAlloc = build.talents.length > 0;
  const trees = hasAlloc ? talentTrees(build, classId, spec.id) : null;
  const verified = build.status === "verified";
  const sourceLine = h("p", { class: "muted", style: { fontSize: "0.85rem", marginTop: "12px" } },
    `Source: ${build.source}`, build.client_version ? ` · talent data ${build.client_version}` : "", build.verified_at ? ` · verified ${build.verified_at}` : "",
    safeUrl(build.source_url) ? [" · ", h("a", { href: safeUrl(build.source_url), target: "_blank", rel: "noopener noreferrer" }, "model build page")] : null,
    safeUrl(build.calculator_url) ? [" · ", h("a", { href: safeUrl(build.calculator_url), target: "_blank", rel: "noopener noreferrer" }, "talent calculator")] : null);
  return h("div", { class: "card build" },
    h("div", { class: "row between" },
      h("h3", { style: { margin: 0 } }, "Your build"),
      h("span", { class: "row" }, badge(label, kind), build.tree_distribution_text ? badge(`${build.tree_distribution_text} points`, "") : null)),
    h("p", { style: { margin: "10px 0 4px" } }, h("b", {}, build.name), ` · ${purposeLabel(build.purpose)} · level ${build.level}`),
    h("p", { class: `note${verified ? "" : " warn"}` }, build.status_note),
    hasAlloc ? dataNotice(build) : null,
    trees,
    hasAlloc && !trees ? h("p", { class: "muted" }, "The talent trees for this class are not available, so only the allocation order is shown.") : null,
    hasAlloc && build.leveling_order.length
      ? h("details", { style: { marginTop: "14px" } }, h("summary", {}, "Order to spend points while leveling"),
          h("ol", { class: "order", start: 10 }, build.leveling_order.map((id, k) => h("li", { value: 10 + k }, `${names[id] || id}`))))
      : null,
    hasAlloc && build.combat_priorities.length ? h("div", { style: { marginTop: "12px" } }, h("h4", {}, "Notes on this build"), h("ul", {}, build.combat_priorities.map((c) => h("li", {}, c)))) : null,
    hasAlloc && build.equipment_notes.length ? h("div", { style: { marginTop: "12px" } }, h("h4", {}, "Attributes and equipment"), h("ul", {}, build.equipment_notes.map((c) => h("li", {}, c)))) : null,
    hasAlloc && build.professions.length ? h("p", {}, h("b", {}, "Professions: "), build.professions.join(", ")) : null,
    hasAlloc && !verified && build.notes ? h("div", { style: { marginTop: "12px" } }, h("h4", {}, "How this was put together"), h("p", { style: { fontSize: "0.92rem" } }, build.notes)) : null,
    hasAlloc ? sourceLine : null);
}
