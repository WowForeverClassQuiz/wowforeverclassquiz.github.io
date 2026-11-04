// Participant interface: the assessment and the result reveal. Never requests scoring weights.
import { h, append, clear, fmt, signed, roleLabel, toast, copyText, download, barChart, chartLegend, errorList, CLASS_COLORS } from "../ui.js";
import { get, post, STATIC } from "../api.js";
import { state } from "../state.js";
import { classIcon, specIcon, spellName } from "../icons.js";
import { overviewCard, guideCard, buildCard } from "../parts.js";
import { longDate } from "../talenttree.js";
import { DEFAULT_SHARE_TEMPLATE, renderShare, shareValues } from "../share.js";

let root = null;
/** Null-safe: Element.append(null) would print the word "null" into the page. */
const put = (...kids) => append(root, kids);
let keyHandlerInstalled = false;

export async function render(container) {
  root = container;
  if (!state.quiz) state.quiz = await get("/quiz");
  if (state.version === undefined) state.version = await get("/version").catch(() => null);
  installKeys();
  draw();
}

function draw() {
  clear(root);
  if (state.result) return drawResult();
  if (!state.started) return drawIntro();
  if (isAdaptive()) return drawAdaptiveQuestion();
  drawQuestion();
}

/** The quiz lengths on offer (an older server or configuration may offer none: then the whole quiz is the only length). */
const lengths = () => state.quiz.lengths || [];
const currentLength = () => lengths().find((l) => l.id === state.length) || lengths().find((l) => l.id === state.quiz.default_length) || lengths()[lengths().length - 1] || null;
/** Confidence mode (the default): the Oracle chooses each next question and stops once it is sure. */
const isAdaptive = () => !!currentLength()?.adaptive;
state.asked ||= [];          // confidence mode: the ids of the questions asked so far, in the order they were asked
state.meter ||= {};          // confidence mode: question id -> how sure the Oracle was when that question was put (what the meter shows)
const byId = (id) => state.quiz.questions.find((q) => q.id === id);
/** The questions of the chosen length, in quiz order (confidence mode: the ones asked so far, in the order asked). */
const questions = () => {
  const len = currentLength();
  if (len && len.adaptive) return state.asked.map(byId).filter(Boolean);
  return len ? len.question_ids.map(byId).filter(Boolean) : state.quiz.questions;
};
const total = () => questions().length;
const answered = () => questions().filter((q) => state.answers[q.id]).length;
const complete = () => (isAdaptive() ? answered() === total() && total() >= (state.status?.min_questions ?? 1) : answered() === total());
const nextLength = () => {
  if (isAdaptive()) return null;
  const ls = lengths().filter((l) => !l.adaptive), i = ls.findIndex((l) => l.id === currentLength()?.id);
  return i >= 0 && i < ls.length - 1 ? ls[i + 1] : null;
};
const askedAnswers = () => Object.fromEntries(state.asked.filter((id) => state.answers[id]).map((id) => [id, state.answers[id]]));
const answersKey = () => JSON.stringify(Object.entries(askedAnswers()).sort());
const firstUnanswered = () => Math.max(0, questions().findIndex((q) => !state.answers[q.id]));

// ---------------------------------------------------------------------------- intro
/** The line under the length picker. The picker already gives each reading's size and rule, so this repeats them only when there is no picker. */
function introCount() {
  if (lengths().length > 1) return "";
  const len = currentLength();
  return len && len.adaptive
    ? `The Oracle asks up to ${len.max_questions} questions and stops once it is ${Math.round(len.confidence * 100)}% sure.`
    : `${total()} questions.`;
}

function drawIntro() {
  const resuming = Object.keys(state.answers).length > 0;
  put(
    h("section", { class: "hero" },
      h("div", { class: "sigil", "aria-hidden": "true" }, "✦"),
      h("h1", {}, state.quiz.title),
      h("p", { class: "sub" }, state.quiz.subtitle || "A short reading of your temperament."),
      lengthPicker(),
      h("p", { class: "sub" }, [introCount(), "There are no right answers; choose whatever draws you first."].filter(Boolean).join(" ")),
      h("button", { class: "btn primary large", type: "button", id: "begin", onclick: begin }, resuming ? "Continue your reading" : "Begin"),
      h("p", { style: { marginTop: "14px" } }, h("a", { class: "btn ghost", href: "#/specs", id: "browse-classes" }, "Browse the classes and specializations")),
      credit(),
    ),
  );
  document.getElementById("begin").focus();
}

function begin() {
  state.length = currentLength()?.id || null;
  if (isAdaptive()) return beginAdaptive();
  state.started = true;
  state.index = Object.keys(state.answers).length ? firstUnanswered() : 0;
  draw();
}

/** "Developed by Anibru" (a link to github.com/Anibru) with the version, build number, commit and date of this build. */
function credit() {
  const v = state.version || {};
  const when = v.date ? longDate(v.date) : "";
  return h("p", { class: "muted credit" }, "Developed by ",
    h("a", { href: v.developer_url || "https://github.com/Anibru", target: "_blank", rel: "noopener noreferrer" }, v.developer || "Anibru"),
    v.version ? ` · v${v.version}` : "",
    v.build ? ` · build ${v.build}${v.commit && v.commit !== "unknown" ? ` (${v.commit})` : ""}` : "",
    when ? ` · ${when}` : "");
}

/** Short, medium or long: how many questions to answer. Nothing is chosen for you except the middle one when it exists. */
function lengthPicker() {
  const ls = lengths();
  if (ls.length < 2) return null;
  const chosen = currentLength();
  return h("fieldset", { class: "lengths" },
    h("legend", {}, "How long a reading would you like?"),
    ls.map((l) => h("label", { class: "length" },
      h("input", { type: "radio", name: "quiz-length", value: l.id, checked: chosen.id === l.id, onchange: () => { state.length = l.id; draw(); document.querySelector(`input[name="quiz-length"][value="${l.id}"]`)?.focus(); } }),
      h("span", { class: "length-name" }, l.name),
      h("span", { class: "length-meta" }, l.adaptive ? (l.min_questions > 1 ? `${l.min_questions}–${l.max_questions} questions · about ${l.minutes}–${l.minutes_max} min` : `Up to ${l.max_questions} questions`) : `${l.question_count} questions · about ${l.minutes} min`),
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

// ---------------------------------------------------------------------------- confidence mode
let statusLoading = false;

/** Ask the engine how sure it is and what to ask next, once per distinct set of answers. */
function ensureStatus() {
  const key = answersKey();
  if (state.statusFor === key || statusLoading || state.statusFailed === key) return;
  statusLoading = true;
  post("/adaptive/next", { answers: askedAnswers() })
    .then((s) => { state.status = s; state.statusFor = key; state.statusFailed = null; })
    .catch((err) => { state.statusFailed = key; toast(err.message || "Could not reach the Oracle.", "bad"); })
    .finally(() => { statusLoading = false; if (state.started && !state.result && isAdaptive()) draw(); });
}

async function beginAdaptive() {
  state.started = true;
  state.asked = state.quiz.questions.filter((q) => state.answers[q.id]).map((q) => q.id);    // answers kept from an earlier try
  clear(root); put(h("p", { class: "muted", role: "status" }, "Choosing the first question…"));
  try {
    state.status = await post("/adaptive/next", { answers: askedAnswers() });
    state.statusFor = answersKey();
    let next = state.status.next_question_id;
    const openers = state.status.openers || [];
    if (state.status.answered === 0 && openers.length) next = openers[Math.floor(Math.random() * openers.length)];      // a random personality question to open with
    if (next && !state.asked.includes(next)) { state.asked.push(next); state.meter[next] = state.status; }
  } catch (err) {
    state.started = false; toast(err.message || "Could not reach the Oracle.", "bad");
  }
  state.index = Math.max(0, questions().findIndex((q) => !state.answers[q.id]));
  draw();
}

/** The meter shows how sure the Oracle was when this question was put to you. It moves when you go on to the next question, never when you choose an answer. */
function certainty(i, s) {
  const pct = s ? Math.round(s.confidence * 100) : 0;
  return h("div", { class: "certainty" },
    h("div", { class: "progress-label" }, h("span", {}, `Question ${i + 1}`),
      h("span", { id: "certainty-label" }, s ? `The Oracle is ${pct}% sure` : "Thinking…")),
    h("div", { class: "progress certainty-bar", role: "progressbar", "aria-valuemin": 0, "aria-valuemax": 100, "aria-valuenow": pct, "aria-label": "How sure the Oracle is" },
      h("i", { style: { width: `${pct}%` } }), s ? h("b", { class: "tick", style: { left: `${s.threshold * 100}%` }, title: `It stops at ${Math.round(s.threshold * 100)}%` }) : null),
    s && s.answered > 0 ? h("p", { class: "muted certainty-detail", id: "certainty-detail", title: "How likely the Oracle's model thinks each is right, given your answers so far" },
      `${s.recommended.class_name} ${Math.round(s.class_probability * 100)}% · ${s.recommended.specialization_name} ${Math.round(s.spec_probability * 100)}% · ${roleLabel(s.role)} ${Math.round(s.role_probability * 100)}%`) : null,
    s ? h("p", { class: "muted certainty-note" },
      `It asks the questions that tell it the most and stops once it is ${Math.round(s.threshold * 100)}% sure${s.min_questions > 1 ? `, after at least ${s.min_questions} questions` : ""} (${s.max_questions} at most). The figure only rises: it is the best certainty reached so far, counted for more as more questions are asked. A specialization of the same class, or with a similar role, counts partly toward it.`) : null);
}

function drawAdaptiveQuestion() {
  ensureStatus();
  const qs = questions();
  if (!qs.length) return put(h("div", { class: "card" }, h("p", {}, "There are no questions to ask."), h("button", { class: "btn", type: "button", onclick: restart }, "Back")));
  state.index = Math.min(state.index, qs.length - 1);
  const i = state.index, q = qs[i], chosen = state.answers[q.id];
  const s = state.status, fresh = state.statusFor === answersKey();
  const lastAsked = i === qs.length - 1;
  const dots = h("div", { class: "dots", role: "group", "aria-label": "Questions asked so far" },
    qs.map((qq, k) => h("button", {
      type: "button", class: `${state.answers[qq.id] ? "done" : ""} ${k === i ? "current" : ""}`,
      "aria-label": `Question ${k + 1}${state.answers[qq.id] ? ", answered" : ", unanswered"}`, "aria-current": k === i ? "step" : null,
      onclick: () => { state.index = k; draw(); },
    })));
  const groupId = `q-${q.id}`;
  const control = ({ scale: scaleControl, pick_two: pickControl, ranking: rankingControl, allocation: allocationControl }[q.type] || choiceControl)(q, groupId);

  let next;
  if (lastAsked && fresh && s && s.done) {
    next = h("button", { class: "btn primary large", type: "button", id: "reveal", disabled: !chosen, onclick: reveal }, "Reveal my reading");
  } else {
    next = h("button", { class: "btn primary", type: "button", id: "next", disabled: !chosen || (lastAsked && !fresh), onclick: () => {
      if (lastAsked && s && s.next_question_id && !state.asked.includes(s.next_question_id)) { state.asked.push(s.next_question_id); state.meter[s.next_question_id] = s; }
      state.index = i + 1; draw();
    } }, lastAsked && chosen && !fresh ? "Thinking…" : "Next");
  }
  put(
    certainty(i, state.meter[q.id] || s),
    dots,
    h("p", { class: "eyebrow-q" }, EYEBROWS[q.type] || EYEBROWS.choice),
    h("h2", { class: "question", id: groupId }, q.text),
    control,
    h("div", { class: "nav-row" },
      h("button", { class: "btn", type: "button", id: "prev", disabled: i === 0, onclick: () => { state.index = i - 1; draw(); } }, "Previous"),
      next),
    lastAsked && fresh && s && s.can_reveal && !s.done && chosen
      ? h("p", { style: { textAlign: "right", marginTop: "10px" } }, h("button", { class: "linkish", type: "button", id: "reveal-now", onclick: reveal },
        "Reveal now"))
      : null,
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
        h("input", { type: "checkbox", value: a.id, checked: rank > 0, "aria-label": `${a.text}${rank ? `, ranked ${rank}` : ", unranked"}`, onchange: () => tap(a.id) }),
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
  state.asked = []; state.meter = {}; state.status = null; state.statusFor = null; state.statusFailed = null;
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

/** The link a shared result points to: this page itself (without the #/ route), where anyone can take the quiz. */
const pageUrl = () => `${location.origin}${location.pathname}`;

/** The blurb to paste anywhere, from the share format the administrator chose (Admin > Profiles > Share format). */
function shareText(r) {
  return renderShare(state.quiz.share_template || DEFAULT_SHARE_TEMPLATE, shareValues(r, { link: pageUrl(), title: state.quiz.title }));
}

/** A prominent share button at the top of the result: the device's share sheet where there is one, otherwise the clipboard, with a few common places beside it. */
function shareBar(r) {
  const text = shareText(r), url = pageUrl(), title = state.quiz.title;
  const copy = async () => toast((await copyText(text)) ? "Copied. Paste it anywhere to share your result." : "Copy failed: select the text in the share box below and copy it by hand.", "ok");
  const share = async () => {
    if (typeof navigator !== "undefined" && navigator.share) {
      try { await navigator.share(text.includes(url) ? { title, text } : { title, text, url }); return; } catch (err) { if (err && err.name === "AbortError") return; }
    }
    await copy();
  };
  const enc = encodeURIComponent;
  const place = (label, href, id) => h("a", { class: "share-place", id, href, target: "_blank", rel: "noopener noreferrer" }, label);
  return h("div", { class: "share-top", id: "share-top" },
    h("button", { class: "btn primary large", type: "button", id: "share-main", onclick: share }, "Share my results!"),
    h("div", { class: "share-more" },
      h("button", { class: "linkish", type: "button", id: "share-top-copy", onclick: copy }, "Copy the text"),
      place("Post on X", `https://x.com/intent/post?text=${enc(text)}`, "share-x"),
      place("Reddit", `https://www.reddit.com/submit?title=${enc(`${title}: Forever Character Oracle`)}&url=${enc(url)}`, "share-reddit"),
      place("Email", `mailto:?subject=${enc(`${title}: Forever Character Oracle`)}&body=${enc(text)}`, "share-email")));
}

function shareCard(r) {
  const text = shareText(r);
  const copy = async () => toast((await copyText(text)) ? "Copied. Paste it anywhere to share your result." : "Copy failed: select the text and copy it by hand.", "ok");
  return h("div", { class: "card share" },
    h("h3", {}, "Share your result"),
    h("textarea", { id: "share-text", readonly: true, rows: 5, "aria-label": "The text that will be copied", onfocus: (e) => e.target.select() }, text),
    h("div", { class: "row", style: { marginTop: "10px" } },
      h("button", { class: "btn primary", type: "button", id: "share-copy", onclick: copy }, "Copy to share"),
      typeof navigator !== "undefined" && navigator.share
        ? h("button", { class: "btn", type: "button", onclick: () => navigator.share({ text, url: pageUrl() }).catch(() => {}) }, "Share…")
        : null));
}

function resultText(r) {
  const p = r.result, a = r.alternatives;
  const lines = [
    `${state.quiz.title}: Forever Character Oracle`,
    "",
    `Recommended: ${p.primary_specialization.name} ${p.primary_class.name} (${roleLabel(p.primary_specialization.role)})`,
    `Reading strength: ${p.confidence.label} (a heuristic based on the class gap), from ${r.metadata.total_questions} questions`,
    p.confidence.overall != null ? `Model confidence: ${Math.round(p.confidence.overall * 100)}% sure (${p.primary_class.name} ${Math.round(p.confidence.class_probability * 100)}%, ${p.primary_specialization.name} ${Math.round(p.confidence.probability * 100)}%, ${roleLabel(p.confidence.role)} ${Math.round(p.confidence.role_probability * 100)}%)` : "",
    p.build ? `Build: ${p.build.name} [${p.build.status}]${p.build.tree_distribution_text ? ` ${p.build.tree_distribution_text}` : ""}` : "",
    `Also in the stars: ${a.alternative_specialization.name} ${a.alternative_class.name}; closest in ${p.primary_class.name}: ${a.second_specialization_in_primary_class.name}`,
    "",
    p.personality_interpretation,
    "",
    p.specialization_interpretation,
    "",
    p.class_overview ? `What the ${p.primary_class.name} does: ${p.class_overview} ${p.primary_specialization.name}: ${p.specialization_overview}` : "",
    "",
    "Class scores (relative compatibility):",
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
        p.confidence.overall != null
          ? h("span", { class: "chip", title: "How sure the Oracle's model is: the probability it gives this specialization, plus partial credit for the rest of the class and for specializations with a similar role. The model is an assumption about how people answer; see the maths PDF." },
            h("b", {}, `${Math.round(p.confidence.overall * 100)}% sure`), h("i", {}, "model"))
          : null,
        p.dominant_traits.map((t) => h("span", { class: "chip" }, h("b", {}, t.name))),
        lengthChip(r)),
      p.confidence.overall != null
        ? h("p", { class: "muted", id: "confidence-detail", style: { fontSize: "0.88rem", margin: "10px 0 0" } },
          `The model gives ${p.primary_class.name} ${Math.round(p.confidence.class_probability * 100)}%, ${p.primary_specialization.name} ${Math.round(p.confidence.probability * 100)}% and ${roleLabel(p.confidence.role)} ${Math.round(p.confidence.role_probability * 100)}%.`)
        : null,
      shareBar(r),
    ),
    h("div", { class: "card prose" }, h("h3", {}, "Your temperament"), h("p", {}, p.personality_interpretation)),
    overviewCard({ className: p.primary_class.name, classOverview: p.class_overview, specName: p.primary_specialization.name, specOverview: p.specialization_overview, url: p.overview_url }),
    h("div", { class: "card prose" }, h("h3", {}, `Why ${p.primary_specialization.name}`), h("p", {}, p.specialization_interpretation)),
    guideCard(p.primary_specialization),
    buildCard(p.build, p.primary_specialization, p.primary_class.id),
    h("div", { class: "grid two", style: { marginTop: "20px" } },
      h("div", { class: "card" },
        h("h3", {}, "Also in the stars"),
        h("a", { class: "alt-link", href: `#/specs/${alt.alternative_class.id}/${alt.alternative_specialization.id}` },
          h("span", { class: "alt-line" }, classIcon(alt.alternative_class.id, 36, alt.alternative_class.name), specIcon(alt.alternative_class.id, alt.alternative_specialization.id, 36),
            h("span", {}, h("b", {}, alt.alternative_specialization.name), ` ${alt.alternative_class.name}`)),
          h("span", { class: "muted" }, alt.alternative_specialization.description),
          h("span", { class: "alt-go" }, "See this specialization →")),
        h("a", { class: "alt-link", href: `#/specs/${p.primary_class.id}/${alt.second_specialization_in_primary_class.id}` },
          h("span", { class: "alt-line" }, specIcon(p.primary_class.id, alt.second_specialization_in_primary_class.id, 36),
            h("span", {}, "Within ", h("b", {}, p.primary_class.name), ", your next-closest path is ", h("b", {}, alt.second_specialization_in_primary_class.name), ".")),
          h("span", { class: "muted" }, alt.second_specialization_in_primary_class.description),
          h("span", { class: "alt-go" }, "See this specialization →")),
        h("a", { class: "browse-link", href: "#/specs" }, "Browse every specialization →")),
      h("div", { class: "card" },
        h("h3", {}, "The numbers"),
        h("p", { class: "muted", style: { fontSize: "0.88rem" } }, "Relative compatibility scores. A longer bar to the right means a closer fit than the average answer pattern."),
        barChart(r.rankings.classes.map((c) => ({ id: c.id, label: c.name, value: c.score, icon: classIcon(c.id, 18, c.name) })), { leadId: p.primary_class.id }),
        chartLegend()),
    ),
    shareCard(r),
    h("div", { class: "row", style: { marginTop: "24px", justifyContent: "center" } },
      h("button", { class: "btn", type: "button", onclick: async () => toast((await copyText(resultText(r))) ? "Full result copied to the clipboard." : "Copy failed - select the text manually.", "ok") }, "Copy full details"),
      h("button", { class: "btn", type: "button", onclick: () => download("oracle-result.json", JSON.stringify(r, null, 2)) }, "Download JSON"),
      refineButton(),
      h("button", { class: "btn", type: "button", onclick: () => { state.started = true; state.result = null; state.index = 0; draw(); } }, "Revise my answers"),
      h("button", { class: "btn primary", type: "button", id: "restart", onclick: restart }, "Restart"),
      STATIC ? null : h("a", { class: "btn ghost", href: "#/admin/inspector" }, "Inspect in admin")),
  );
}
