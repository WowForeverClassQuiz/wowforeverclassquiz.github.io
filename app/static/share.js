// The blurb people copy to share their result. It is a template with {placeholders} that an administrator can edit
// (Admin > Profiles > Share format); this module fills it in. Pure functions, no DOM, so node can run them in tests.

/** The placeholders a template may use, with what each stands for. Keep in step with SHARE_FIELDS in app/models.py. */
export const SHARE_FIELDS = [
  ["class", "The recommended class, for example Druid"],
  ["spec", "The recommended specialization, for example Feral Combat"],
  ["spec_score", "The specialization's score, for example +13.39"],
  ["class_scores", "The three best class scores, for example Druid +13.39 · Hunter +3.08 · Shaman +2.97"],
  ["traits", "The three strongest traits, for example Intuition, Spontaneity, Intensity"],
  ["confidence", "How decisive the reading was, for example strong lean"],
  ["questions", "How many questions the reading rests on, for example 20"],
  ["quiz_length", "Which quiz length it was: short, medium or long"],
  ["also_class", "The runner-up class"],
  ["also_spec", "The runner-up specialization"],
  ["next_spec", "The next-closest specialization within the recommended class"],
  ["title", "The quiz title"],
  ["link", "The link where anyone can take the quiz"],
];

/** The template used until an administrator changes it. Keep in step with DEFAULT_SHARE_TEMPLATE in app/models.py. */
export const DEFAULT_SHARE_TEMPLATE = [
  "The stars say I'm a {spec} {class}! ✦",
  "Class scores: {class_scores} ({confidence}, {questions} questions; relative scores).",
  "Also in the stars: {also_spec} {also_class}. Closest in {class}: {next_spec}.",
  "Find yours on the Forever Character Oracle: {link}",
].join("\n");

const signed = (n) => `${n > 0 ? "+" : n < 0 ? "−" : ""}${Math.abs(n).toFixed(2)}`;

/** The value of every placeholder for one evaluation result. */
export function shareValues(r, { link = "", title = "" } = {}) {
  const p = r.result, a = r.alternatives, m = r.metadata;
  return {
    class: p.primary_class.name,
    spec: p.primary_specialization.name,
    spec_score: signed(p.primary_specialization.score),
    class_scores: r.rankings.classes.slice(0, 3).map((c) => `${c.name} ${signed(c.score)}`).join(" · "),
    traits: p.dominant_traits.map((t) => t.name).join(", "),
    confidence: p.confidence.label.toLowerCase(),
    questions: String(m.total_questions),
    quiz_length: m.quiz_length || "long",
    also_class: a.alternative_class.name,
    also_spec: a.alternative_specialization.name,
    next_spec: a.second_specialization_in_primary_class.name,
    title,
    link,
  };
}

/** Fill a template in. A placeholder that is not one of SHARE_FIELDS is left as written. */
export function renderShare(template, values) {
  return template.replace(/\{(\w+)\}/g, (whole, key) => (Object.prototype.hasOwnProperty.call(values, key) ? values[key] : whole));
}

/** A made-up result, for previewing a template. */
export const SAMPLE_RESULT = {
  result: {
    primary_class: { name: "Druid" },
    primary_specialization: { name: "Feral Combat", score: 13.39 },
    dominant_traits: [{ name: "Intuition" }, { name: "Spontaneity" }, { name: "Intensity" }],
    confidence: { label: "Strong lean" },
  },
  alternatives: {
    alternative_class: { name: "Hunter" },
    alternative_specialization: { name: "Marksmanship" },
    second_specialization_in_primary_class: { name: "Balance" },
  },
  rankings: { classes: [{ name: "Druid", score: 13.39 }, { name: "Hunter", score: 3.08 }, { name: "Shaman", score: 2.97 }, { name: "Mage", score: -1.2 }] },
  metadata: { total_questions: 20, quiz_length: "medium" },
};
