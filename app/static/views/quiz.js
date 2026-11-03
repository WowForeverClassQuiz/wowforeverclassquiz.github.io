// Participant interface: the assessment and the result reveal. Never requests scoring weights.
import { h, clear, fmt, signed, titleCase, roleLabel, purposeLabel, badge, toast, copyText, download, barChart, chartLegend, errorList, CLASS_COLORS } from "../ui.js";
import { get, post, STATIC } from "../api.js";
import { state } from "../state.js";

let root = null;
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

const total = () => state.quiz.questions.length;
const answered = () => Object.keys(state.answers).length;
const complete = () => answered() === total() && state.quiz.questions.every((q) => state.answers[q.id]);

// ---------------------------------------------------------------------------- intro
function drawIntro() {
  const resuming = answered() > 0;
  root.append(
    h("section", { class: "hero" },
      h("div", { class: "sigil", "aria-hidden": "true" }, "✦"),
      h("h1", {}, state.quiz.title),
      h("p", { class: "sub" }, state.quiz.subtitle || "A short reading of your temperament."),
      h("p", { class: "sub" }, `${total()} questions. There are no right answers; choose whatever draws you first.`),
      h("button", { class: "btn primary large", type: "button", id: "begin", onclick: () => { state.started = true; if (!resuming) state.index = 0; draw(); } },
        resuming ? "Continue your reading" : "Begin"),
      h("p", { class: "muted", style: { marginTop: "28px", fontSize: "0.85rem" } },
        STATIC ? "Your answers are scored right here in your browser. Nothing is sent or stored anywhere."
          : "Your answers stay in this browser tab. Nothing is stored on the server."),
    ),
  );
  document.getElementById("begin").focus();
}

// ---------------------------------------------------------------------------- question
state.picks ||= {};   // in-progress pick-two selections (a finished pair is stored in state.answers)

const TIPS = {
  choice: "Tip: press 1\u20134 to choose, Enter for next.",
  scale: "Tip: press 1\u20139 for a rating (0 for 10), Enter for next.",
  pick_two: "Tip: press 1\u20134 to pick or unpick, Enter for next.",
};

function drawQuestion() {
  const q = state.quiz.questions[state.index];
  const n = total(), i = state.index;
  const isLast = i === n - 1;
  const chosen = state.answers[q.id];

  const dots = h("div", { class: "dots", role: "group", "aria-label": "Jump to a question" },
    state.quiz.questions.map((qq, k) => h("button", {
      type: "button", class: `${state.answers[qq.id] ? "done" : ""} ${k === i ? "current" : ""}`,
      "aria-label": `Question ${k + 1}${state.answers[qq.id] ? ", answered" : ", unanswered"}`,
      "aria-current": k === i ? "step" : null,
      onclick: () => { state.index = k; draw(); },
    })));

  const groupId = `q-${q.id}`;
  const control = q.type === "scale" ? scaleControl(q, groupId) : q.type === "pick_two" ? pickControl(q, groupId) : choiceControl(q, groupId);

  const missing = total() - answered();
  const next = isLast
    ? h("button", { class: "btn primary large", type: "button", id: "reveal", disabled: !complete(), onclick: reveal }, "Reveal my reading")
    : h("button", { class: "btn primary", type: "button", id: "next", disabled: !chosen, onclick: () => { state.index = i + 1; draw(); } }, "Next");

  root.append(
    h("div", { class: "progress-label" }, h("span", {}, `Question ${i + 1} of ${n}`), h("span", {}, `${answered()} answered`)),
    h("div", { class: "progress", role: "progressbar", "aria-valuemin": 0, "aria-valuemax": n, "aria-valuenow": answered(), "aria-label": "Questions answered" },
      h("i", { style: { width: `${(answered() / n) * 100}%` } })),
    dots,
    q.type === "scale" ? h("p", { class: "eyebrow-q" }, "How much do you agree?") : q.type === "pick_two" ? h("p", { class: "eyebrow-q" }, "Choose two") : null,
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
    const q = state.quiz.questions[state.index];
    if (/^[0-9]$/.test(e.key)) {
      if (q.type === "scale") {
        choose(q, e.key === "0" ? String(q.scale_max ?? 10) : e.key);
      } else if (q.type === "pick_two") {
        const a = q.answers[+e.key - 1];
        const box = a && root.querySelector(`input[value="${CSS.escape(a.id)}"]`);
        if (box && !box.disabled) box.click();
      } else if (q.answers[+e.key - 1]) {
        choose(q, q.answers[+e.key - 1].id);
      }
    } else if (e.key === "Enter" && state.answers[q.id] && e.target.tagName !== "BUTTON") {
      const btn = document.getElementById("next") || document.getElementById("reveal");
      if (btn && !btn.disabled) btn.click();
    }
  });
}

// ---------------------------------------------------------------------------- reveal
async function reveal() {
  if (!complete()) {
    const first = state.quiz.questions.findIndex((q) => !state.answers[q.id]);
    toast(`Question ${first + 1} is still unanswered.`, "warn");
    state.index = first;
    return draw();
  }
  clear(root).append(h("div", { class: "reveal", role: "status" },
    h("div", { class: "sigil", "aria-hidden": "true" }, "✦"),
    h("h2", {}, "Reading the stars…")));
  try {
    const [result] = await Promise.all([
      post("/evaluate", { answers: state.answers, include_explanation: false }),
      new Promise((r) => setTimeout(r, window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 1300)),
    ]);
    state.result = result;
    state.adminAnswers = { ...state.answers };
    state.adminEval = null;
    draw();
    window.scrollTo(0, 0);
  } catch (err) {
    clear(root).append(h("div", { class: "card" }, h("h2", {}, "The reading could not be completed"), errorList(err),
      h("button", { class: "btn", type: "button", onclick: () => draw() }, "Back to the questions")));
  }
}

// ---------------------------------------------------------------------------- result
function restart() {
  state.answers = {}; state.picks = {}; state.index = 0; state.started = false; state.result = null;
  draw();
  window.scrollTo(0, 0);
}

function resultText(r) {
  const p = r.result, a = r.alternatives;
  const lines = [
    `${state.quiz.title} - Forever Character Oracle`,
    "",
    `Recommended: ${p.primary_class.name} - ${p.primary_specialization.name} (${roleLabel(p.primary_specialization.role)})`,
    `Reading strength: ${p.confidence.label} (heuristic, not a probability)`,
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
  root.append(
    h("section", { class: "result-hero", style: { "--cls": cls } },
      h("div", { class: "eyebrow" }, "The stars have chosen"),
      h("h1", {}, p.primary_class.name),
      h("h2", {}, p.primary_specialization.name),
      h("div", { class: "chips" },
        h("span", { class: "chip" }, h("b", {}, roleLabel(p.primary_specialization.role))),
        h("span", { class: "chip", title: p.confidence.note }, h("b", {}, p.confidence.label), h("i", {}, "heuristic")),
        p.dominant_traits.map((t) => h("span", { class: "chip" }, h("b", {}, t.name)))),
    ),
    h("div", { class: "card prose" }, h("h3", {}, "Your temperament"), h("p", {}, p.personality_interpretation)),
    overviewCard(p),
    h("div", { class: "card prose" }, h("h3", {}, `Why ${p.primary_specialization.name}`), h("p", {}, p.specialization_interpretation)),
    buildCard(p.build, p.primary_specialization),
    h("div", { class: "grid two", style: { marginTop: "20px" } },
      h("div", { class: "card" },
        h("h3", {}, "Also in the stars"),
        h("p", {}, h("span", { class: "dot", style: { "--cls": CLASS_COLORS[alt.alternative_class.id] } }), h("b", {}, alt.alternative_class.name), ` – ${alt.alternative_specialization.name}`),
        h("p", { class: "muted" }, alt.alternative_specialization.description),
        h("hr", { style: { border: 0, borderTop: "1px solid var(--border)", margin: "14px 0" } }),
        h("p", {}, "Within ", h("b", {}, p.primary_class.name), ", your next-closest path is ", h("b", {}, alt.second_specialization_in_primary_class.name), "."),
        h("p", { class: "muted" }, alt.second_specialization_in_primary_class.description)),
      h("div", { class: "card" },
        h("h3", {}, "The numbers"),
        h("p", { class: "muted", style: { fontSize: "0.88rem" } }, "Relative compatibility, not probabilities. A longer bar to the right means a closer fit than the average answer pattern."),
        barChart(r.rankings.classes.map((c) => ({ id: c.id, label: c.name, value: c.score })), { leadId: p.primary_class.id }),
        chartLegend()),
    ),
    h("div", { class: "row", style: { marginTop: "24px", justifyContent: "center" } },
      h("button", { class: "btn", type: "button", onclick: async () => toast((await copyText(resultText(r))) ? "Result copied to the clipboard." : "Copy failed - select the text manually.", "ok") }, "Copy result"),
      h("button", { class: "btn", type: "button", onclick: () => download("oracle-result.json", JSON.stringify(r, null, 2)) }, "Download JSON"),
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

function buildCard(build, spec) {
  if (!build) {
    return h("div", { class: "card" }, h("h3", {}, "Your build"), h("p", { class: "muted" }, `No build has been configured for ${spec.name} yet.`));
  }
  const kind = { verified: "ok", draft: "warn", unverified: "warn", pending: "info" }[build.status] || "";
  const label = { verified: "Verified", draft: "Draft - not verified", unverified: "Unverified", pending: "Allocation pending" }[build.status] || build.status;
  const names = Object.fromEntries(build.talents.map((t) => [t.talent_id, t.name || t.talent_id]));
  const byTree = {};
  build.talents.forEach((t) => (byTree[t.tree_id || "other"] ||= []).push(t));
  const hasAlloc = build.talents.length > 0;

  const alloc = hasAlloc ? h("div", { class: "tree-cols" }, Object.entries(byTree).map(([tree, ts]) =>
    h("div", { class: "tree-col" }, h("h4", {}, `${titleCase(tree)} · ${ts.reduce((s, t) => s + t.rank, 0)} pts`),
      h("ul", {}, ts.map((t) => h("li", {}, h("span", {}, names[t.talent_id]), h("span", { class: "mono" }, t.max_rank ? `${t.rank}/${t.max_rank}` : t.rank))))))) : null;

  const verified = build.status === "verified";
  const sourceLine = h("p", { class: "muted", style: { fontSize: "0.85rem", marginTop: "12px" } },
    `Source: ${build.source}`, build.client_version ? ` · talent data ${build.client_version}` : "", build.verified_at ? ` · verified ${build.verified_at}` : "",
    safeUrl(build.source_url) ? [" · ", h("a", { href: safeUrl(build.source_url), target: "_blank", rel: "noopener noreferrer" }, "model build page")] : null,
    safeUrl(build.calculator_url) ? [" · ", h("a", { href: safeUrl(build.calculator_url), target: "_blank", rel: "noopener noreferrer" }, "talent calculator")] : null);
  // Everything below is shown inline for a verified build and tucked inside a labelled section for a provisional one.
  const body = hasAlloc ? [
    alloc,
    build.leveling_order.length
      ? h("details", { style: { marginTop: "12px" } }, h("summary", {}, "Order to spend points while leveling"),
          h("ol", { class: "order", start: 10 }, build.leveling_order.map((id, k) => h("li", { value: 10 + k }, `${names[id] || id}`))))
      : null,
    build.combat_priorities.length ? h("div", { style: { marginTop: "12px" } }, h("h4", {}, "Notes on this build"), h("ul", {}, build.combat_priorities.map((c) => h("li", {}, c)))) : null,
    build.equipment_notes.length ? h("div", { style: { marginTop: "12px" } }, h("h4", {}, "Attributes and equipment"), h("ul", {}, build.equipment_notes.map((c) => h("li", {}, c)))) : null,
    build.professions.length ? h("p", {}, h("b", {}, "Professions: "), build.professions.join(", ")) : null,
    !verified && build.notes ? h("div", { style: { marginTop: "12px" } }, h("h4", {}, "How this was put together"), h("p", { style: { fontSize: "0.92rem" } }, build.notes)) : null,
    sourceLine,
  ] : [];
  return h("div", { class: "card" },
    h("div", { class: "row between" },
      h("h3", { style: { margin: 0 } }, "Your build"),
      h("span", { class: "row" }, badge(label, kind), build.tree_distribution_text ? badge(`${build.tree_distribution_text} points`, "") : null)),
    h("p", { style: { margin: "10px 0 4px" } }, h("b", {}, build.name), ` · ${purposeLabel(build.purpose)} · level ${build.level}`),
    h("p", { class: `note${verified ? "" : " warn"}` }, build.status_note),
    hasAlloc && verified ? body : null,
    hasAlloc && !verified ? h("details", { style: { marginTop: "12px" } }, h("summary", {}, "Best-guess build details (not verified)"), body) : null,
  );
}
