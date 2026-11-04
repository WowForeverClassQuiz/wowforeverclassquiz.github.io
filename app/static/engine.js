// Participant scoring in the browser, for the static (server-less) edition. A line-for-line port of app/scoring.py's
// evaluate() without the administrative explanation: same arithmetic, same tie-breaks, same wording.
//
// It runs on the tables exported by app/static_export.py, which carry the raw weights and per-question baselines.
// Baseline-subtracted deltas are recomputed here with the same IEEE operation Python used, and sums use an exact
// (Shewchuk) summation like math.fsum, so results match the Python engine to the last digit
// (tests/test_static_parity.py checks this against the live API).
//
// This module has no DOM access, so node can import it too.

export class ScoringError extends Error {
  constructor(code, message, extra = {}) {
    super(message);
    this.code = code;
    Object.assign(this, extra);
  }
}

/** Shortest to longest; a question is asked in the length of its length_rank and every longer one. */
export const LENGTHS = ["short", "medium", "long"];

const COMPARE_DECIMALS = 9;
const OUTPUT_DECIMALS = 10;

// ---------------------------------------------------------------------------------------------------------------
// Python-compatible numerics
// ---------------------------------------------------------------------------------------------------------------

/** Exactly rounded sum, as Python's math.fsum (finite inputs). */
export function fsum(values) {
  const partials = [];
  for (let x of values) {
    let i = 0;
    for (let y of partials) {
      if (Math.abs(x) < Math.abs(y)) [x, y] = [y, x];
      const hi = x + y;
      const lo = y - (hi - x);
      if (lo) partials[i++] = lo;
      x = hi;
    }
    partials.length = i;
    partials.push(x);
  }
  let n = partials.length;
  let hi = 0;
  if (n > 0) {
    hi = partials[--n];
    let lo = 0;
    while (n > 0) {
      const x = hi;
      const y = partials[--n];
      hi = x + y;
      lo = y - (hi - x);
      if (lo) break;
    }
    // Round-half-even correction when the discarded part sits exactly half way.
    if (n > 0 && ((lo < 0 && partials[n - 1] < 0) || (lo > 0 && partials[n - 1] > 0))) {
      const y = lo * 2;
      const x = hi + y;
      if (y === x - hi) hi = x;
    }
  }
  return hi;
}

/** x.toFixed(nd), but exact ties go to the even digit like Python (toFixed rounds them away from zero). */
export function fixed(x, nd) {
  let s = x.toFixed(nd);
  const t = x * 2 ** (nd + 1);                       // exact: scaling by a power of two
  if (Number.isInteger(t) && Math.abs(t) % 2 === 1 && Number(s[s.length - 1]) % 2 === 1) {
    const neg = s[0] === "-";
    const digits = (BigInt(s.replace(/[-.]/g, "")) - 1n).toString().padStart(nd + 1, "0");
    s = (neg ? "-" : "") + (nd ? `${digits.slice(0, -nd)}.${digits.slice(-nd)}` : digits);
  }
  return s;
}

/** Python's round(x, nd) + 0.0 (never -0). */
export const pyRound = (x, nd) => Number(fixed(x, nd)) + 0;

/** Python's f"{x:+.2f}". */
export function signed(x) {
  return `${x < 0 || Object.is(x, -0) ? "-" : "+"}${fixed(Math.abs(x), 2)}`;
}

/**
 * Python's "{:g}" for the profile multipliers (six significant digits, trailing zeros dropped). Exact ties are rounded to
 * even like Python in the plain-decimal range; in exponent form (|x| < 1e-4 or >= 1e6) they go to the larger digit.
 */
export function formatG(m) {
  if (m === 0) return Object.is(m, -0) ? "-0" : "0";
  const [mant, e] = m.toExponential(5).split("e");
  const exp = Number(e);
  if (exp < -4 || exp >= 6) {
    return `${mant.replace(/\.?0+$/, "")}e${exp < 0 ? "-" : "+"}${String(Math.abs(exp)).padStart(2, "0")}`;
  }
  const text = fixed(m, 5 - exp);
  return text.includes(".") ? text.replace(/\.?0+$/, "") : text;
}

const r = (x) => pyRound(x, COMPARE_DECIMALS);   // comparison value
const o = (x) => pyRound(x, OUTPUT_DECIMALS);    // output value

function join(items) {
  if (items.length <= 1) return items.join("");
  if (items.length === 2) return `${items[0]} and ${items[1]}`;
  return `${items.slice(0, -1).join(", ")}, and ${items[items.length - 1]}`;
}

// ---------------------------------------------------------------------------------------------------------------
// Preparing the exported data
// ---------------------------------------------------------------------------------------------------------------

/** Turn the exported JSON (static_export.py) into the arrays evaluate() uses. */
export function prepare(data) {
  const e = data.engine;
  const sub = (rows, base) => rows.map((row) => row.map((v, i) => v - base[i]));
  const questions = e.questions.map((q) => ({
    ...q,
    class_delta: sub(q.class_raw, q.class_base),
    trait_delta: sub(q.trait_raw, q.trait_base),
    spec_delta: sub(q.spec_raw, q.spec_base),
  }));
  return {
    revision: e.revision,
    algorithm_version: e.algorithm_version,
    strong_margin: e.strong_margin,
    moderate_margin: e.moderate_margin,
    spec_multiplier: e.spec_multiplier,
    adaptive: e.adaptive,
    traits: e.traits,
    classes: e.classes,
    active_specs: e.active_specs,
    questions,
    qIndex: new Map(questions.map((q, i) => [q.id, i])),
    builds: data.builds || {},
  };
}

// ---------------------------------------------------------------------------------------------------------------
// Evaluation
// ---------------------------------------------------------------------------------------------------------------

function resolveAnswers(c, answers, active, length) {
  const picks = [];
  for (const [qid, given] of Object.entries(answers || {})) {
    const qi = c.qIndex.get(qid);
    if (qi === undefined) throw new ScoringError("unknown_question", `Unknown or disabled question '${qid}'.`);
    if (!active.includes(qi)) throw new ScoringError("unknown_question", `Question '${qid}' is not part of the ${length} quiz.`);
    const q = c.questions[qi];
    let aid = String(given);
    if (q.type === "pick_two") {                                   // accept either order: 'c+a' is 'a+c'
      const parts = aid.split("+");
      if (parts.length === 2 && parts[0] !== parts[1] && parts.every((p) => q.item_ids.includes(p))) {
        aid = [...parts].sort((a, b) => q.item_ids.indexOf(a) - q.item_ids.indexOf(b)).join("+");
      }
    }
    const ai = q.answer_ids.indexOf(aid);
    if (ai < 0) throw new ScoringError("unknown_answer", `Question '${qid}' has no answer '${aid}'.`);
    picks.push([qi, ai]);
  }
  return picks.sort((a, b) => a[0] - b[0]);
}

/** Stable ordering by descending rounded score, then by the given tie-break key. */
function order(n, score, tie) {
  return Array.from({ length: n }, (_, i) => i).sort((a, b) => (r(score(b)) - r(score(a))) || (tie(a) - tie(b)) || (a - b));
}

/** Score a complete set of answers (question id -> answer id). Mirrors scoring.evaluate(include_explanation=False). */
export function evaluate(c, answers, { allowPartial = false, length = "long" } = {}) {
  let active, picks, missing;
  const given = answers || {};
  if (length === "adaptive") {
    // confidence mode: the quiz is exactly the questions that were answered
    active = Object.keys(given).filter((q) => c.qIndex.has(q)).map((q) => c.qIndex.get(q)).sort((a, b) => a - b);
    picks = resolveAnswers(c, answers, active, length);
    missing = [];
    if (!picks.length) throw new ScoringError("incomplete_assessment", "At least one answer is required.", { missing });
    if (picks.length < c.adaptive.min_questions && !allowPartial) {
      throw new ScoringError("scoring_error", `Confidence mode needs at least ${c.adaptive.min_questions} answers; got ${picks.length}.`);
    }
  } else {
    const rank = LENGTHS.indexOf(length);
    if (rank < 0) throw new ScoringError("scoring_error", `Unknown quiz length '${length}'.`);
    active = c.questions.map((q, i) => i).filter((i) => c.questions[i].length_rank <= rank);
    if (!active.length) throw new ScoringError("scoring_error", `The ${length} quiz has no questions.`);
    picks = resolveAnswers(c, answers, active, length);
    missing = active.map((i) => c.questions[i].id).filter((id) => !Object.prototype.hasOwnProperty.call(given, id));
    if (!picks.length || (missing.length && !allowPartial)) {
      throw new ScoringError("incomplete_assessment",
        missing.length ? `${missing.length} question(s) unanswered: ${missing.join(", ")}` : "At least one answer is required.", { missing });
    }
  }
  const nc = c.classes.length, nt = c.traits.length;
  if (nc < 2) throw new ScoringError("scoring_error", "At least two classes are required.");

  const sumOver = (n, pick) => Array.from({ length: n }, (_, i) => fsum(picks.map(([qi, ai]) => pick(c.questions[qi], ai)[i])));
  const classTotals = sumOver(nc, (q, ai) => q.class_delta[ai]);
  const traitTotals = sumOver(nt, (q, ai) => q.trait_delta[ai]);
  const specTotals = new Array(c.classes.reduce((n, cl) => n + cl.specs.length, 0)).fill(0);
  for (const g of c.active_specs) specTotals[g] = fsum(picks.map(([qi, ai]) => c.questions[qi].spec_delta[ai][g]));
  const classRaw = sumOver(nc, (q, ai) => q.class_raw[ai]);
  const classExp = Array.from({ length: nc }, (_, i) => fsum(picks.map(([qi]) => c.questions[qi].class_base[i])));
  const traitRaw = sumOver(nt, (q, ai) => q.trait_raw[ai]);
  const traitExp = Array.from({ length: nt }, (_, i) => fsum(picks.map(([qi]) => c.questions[qi].trait_base[i])));
  const appearances = Array.from({ length: nt }, (_, i) => picks.filter(([qi, ai]) => c.questions[qi].trait_raw[ai][i] > 0).length);

  const classOrder = order(nc, (i) => classTotals[i], (i) => c.classes[i].tie_rank);
  const traitOrder = order(nt, (i) => traitTotals[i], () => 0);
  const specScores = c.classes.map((cl) => cl.specs.map((s) =>
    fsum(s.terms.map(([t, m]) => m * traitTotals[t])) + c.spec_multiplier * specTotals[s.gidx]));
  const specOrders = specScores.map((scores) => order(scores.length, (j) => scores[j], () => 0));

  const leader = classTotals[classOrder[0]];
  const classRows = classOrder.map((i, k) => ({
    id: c.classes[i].id,
    name: c.classes[i].name,
    score: o(classTotals[i]),
    rank: k + 1,
    raw_points: o(classRaw[i]),
    expected_points: o(classExp[i]),
    gap_to_leader: o(leader - classTotals[i]),
    tied_with_previous: k > 0 && r(classTotals[i]) === r(classTotals[classOrder[k - 1]]),
  }));
  const traitRows = traitOrder.map((i, k) => ({
    id: c.traits[i].id,
    name: c.traits[i].name,
    score: o(traitTotals[i]),
    rank: k + 1,
    raw_points: o(traitRaw[i]),
    expected_points: o(traitExp[i]),
    appearances: appearances[i],
    tied_with_previous: k > 0 && r(traitTotals[i]) === r(traitTotals[traitOrder[k - 1]]),
  }));

  const specRows = (ci) => {
    const cl = c.classes[ci], scores = specScores[ci], ord = specOrders[ci];
    return ord.map((j, k) => {
      const s = cl.specs[j];
      return {
        class_id: cl.id,
        id: s.id,
        name: s.name,
        role: s.role,
        score: o(scores[j]),
        rank: k + 1,
        tied_with_previous: k > 0 && r(scores[j]) === r(scores[ord[k - 1]]),
        direct_score: o(c.spec_multiplier * specTotals[s.gidx]),
        terms: s.terms.map(([t, m]) => ({
          trait_id: c.traits[t].id,
          trait_name: c.traits[t].name,
          multiplier: m,
          trait_score: o(traitTotals[t]),
          contribution: o(m * traitTotals[t]),
        })),
      };
    });
  };
  const allSpecRows = c.classes.map((_, ci) => specRows(ci));
  const pCi = classOrder[0], altCi = classOrder[1];
  const primarySpecs = allSpecRows[pCi], altSpecs = allSpecRows[altCi];

  const pick = (ci, row) => {
    const s = c.classes[ci].specs.find((x) => x.id === row.id);
    const out = {
      class_id: c.classes[ci].id, class_name: c.classes[ci].name, id: row.id, name: row.name, role: row.role,
      score: row.score, description: s.description,
    };
    if (s.guide) out.guide = s.guide;                              // roles and gear guidance, when the specialization has any
    const build = c.builds[`${c.classes[ci].id}/${row.id}`];
    if (build) out.build = build;                                   // display only, as the API's with_builds()
    return out;
  };
  const primaryPick = pick(pCi, primarySpecs[0]);
  const secondPick = pick(pCi, primarySpecs[1] || primarySpecs[0]);
  const altPick = pick(altCi, altSpecs[0]);

  // -- interpretation ------------------------------------------------------------------------------------------
  const dominantAll = traitRows.filter((t) => t.score > 0).slice(0, 3);
  const dominant = dominantAll.length ? dominantAll : traitRows.slice(0, 1);
  const pCls = c.classes[pCi];
  const traitIndex = new Map(c.traits.map((t, i) => [t.id, i]));
  const readings = dominant.map((t) => c.traits[traitIndex.get(t.id)].reading).filter(Boolean).join(" ");
  const personality = `The stars lean toward the ${pCls.name}: ${pCls.description.replace(/\.+$/, "")}. `
    + `Your answers emphasized ${join(dominant.map((t) => t.name))}. ${readings}`;
  const pSpec = pCls.specs.find((s) => s.id === primaryPick.id);
  const model = adaptiveModel(c);
  const confidenceParts = model.confidenceParts(model.posterior(picks), pSpec.gidx, c.adaptive.class_credit, c.adaptive.role_credit);
  const weighed = pSpec.terms.map(([t, m]) => `${c.traits[t].name} (×${formatG(m)})`).join(", then ");
  const scored = pSpec.terms.map(([t]) => signed(traitTotals[t])).join(", ");
  const specReading = `${pSpec.description} The ${pCls.name} ${pSpec.name} profile weighs ${weighed}; `
    + `your adjusted scores in those traits were ${scored}.`;

  const gap = classTotals[classOrder[0]] - classTotals[classOrder[1]];
  // the margins scale with the square root of the share of questions asked (1 for the full quiz), as scoring.margin_scale
  const scale = Math.sqrt(active.length / c.questions.filter((q) => q.length_rank < LENGTHS.length).length);
  const strongMargin = c.strong_margin * scale, moderateMargin = c.moderate_margin * scale;
  const label = r(gap) >= strongMargin ? "Strong lean" : r(gap) >= moderateMargin ? "Clear lean" : "Close call";

  const result = {
    primary_class: classRows[0],
    primary_class_description: pCls.description,
    class_overview: pCls.overview,
    specialization_overview: pSpec.overview,
    overview_url: pCls.overview_url,
    primary_specialization: primaryPick,
    dominant_traits: dominant,
    personality_interpretation: personality.trim(),
    specialization_interpretation: specReading.trim(),
    confidence: {
      label,
      probability: o(confidenceParts.spec),
      class_probability: o(confidenceParts.class),
      role_probability: o(confidenceParts.role),
      overall: o(confidenceParts.overall),
      role: pSpec.role,
      class_gap: o(gap),
      strong_margin: strongMargin,
      moderate_margin: moderateMargin,
      note: "Heuristic descriptor based on the gap between the top two class scores "
        + "and configurable margins. The probability field comes from the confidence model.",
    },
  };
  if (primaryPick.build) result.build = primaryPick.build;
  return {
    result,
    alternatives: {
      alternative_class: classRows[1],
      alternative_specialization: altPick,
      second_specialization_in_primary_class: secondPick,
    },
    rankings: {
      classes: classRows,
      specializations: primarySpecs,
      alternative_class_specializations: altSpecs,
      all_specializations: allSpecRows.flat(),
      traits: traitRows,
    },
    metadata: {
      config_revision: c.revision,
      algorithm_version: c.algorithm_version,
      answered_questions: picks.length,
      total_questions: active.length,
      complete: !missing.length,
      provisional: !!missing.length,
      missing_questions: missing,
      spec_weight_multiplier: c.spec_multiplier,
      quiz_length: length,
      scores_are_probabilities: false,
      note: "Scores are relative compatibility indicators on a scale with no fixed maximum. "
        + "Confidence labels are heuristics based on the gap between the top two class scores.",
    },
  };
}


// ---------------------------------------------------------------------------------------------------------------
// Confidence mode: the logit choice model and the choice of the next question (a port of app/adaptive.py)
// ---------------------------------------------------------------------------------------------------------------

/** Log-likelihood tables of the choice model: logp[question][response][type] = log P(response | type, question). */
export function adaptiveModel(c) {
  if (c.__model) return c.__model;
  const s = c.adaptive;
  const nTypes = c.classes.reduce((n, cl) => n + cl.specs.length, 0);
  const typeClass = new Array(nTypes).fill(0);
  const typeRoles = new Array(nTypes).fill(null);                // a role like "melee_damage_or_tank" is two roles
  const terms = new Array(nTypes).fill([]);
  c.classes.forEach((cl, ci) => cl.specs.forEach((sp) => { typeClass[sp.gidx] = ci; typeRoles[sp.gidx] = sp.role.split("_or_"); terms[sp.gidx] = sp.terms; }));
  const logp = c.questions.map((q) => {
    const rows = q.class_delta.map((_, r) => {
      const u = [];
      for (let g = 0; g < nTypes; g++) {
        const specPart = fsum(terms[g].map(([t, m]) => m * q.trait_delta[r][t])) + c.spec_multiplier * q.spec_delta[r][g];
        u.push(s.sharpness_class * q.class_delta[r][typeClass[g]] + s.sharpness_spec * specPart);
      }
      return u;
    });
    for (let g = 0; g < nTypes; g++) {
      const top = Math.max(...rows.map((row) => row[g]));
      const lz = top + Math.log(fsum(rows.map((row) => Math.exp(row[g] - top))));
      rows.forEach((row) => { row[g] -= lz; });
    }
    return rows;
  });
  /** The confidence in specialization `rec` and what it is made of, as adaptive.Model.confidence_parts: credit 1 for rec, class_credit for the rest of its class, role_credit for similar roles. */
  const confidenceParts = (post, rec, classCredit, roleCredit) => {
    const sameClass = post.map((p, g) => typeClass[g] === typeClass[rec]);
    const sameRole = post.map((p, g) => typeRoles[g].some((r) => typeRoles[rec].includes(r)));
    const credit = post.map((p, g) => (g === rec ? 1 : Math.max(sameClass[g] ? classCredit : 0, sameRole[g] ? roleCredit : 0)));
    return {
      overall: fsum(post.map((p, g) => p * credit[g])),
      spec: post[rec],
      class: fsum(post.filter((p, g) => sameClass[g])),
      role: fsum(post.filter((p, g) => sameRole[g])),
    };
  };
  const entropy = (p) => -fsum(p.filter((x) => x > 0).map((x) => x * Math.log(x)));
  const posterior = (picks) => {
    const lp = Array.from({ length: nTypes }, (_, g) => fsum(picks.map(([qi, ri]) => logp[qi][ri][g])));
    const top = Math.max(...lp);
    const w = lp.map((x) => Math.exp(x - top));
    const total = fsum(w);
    return w.map((x) => x / total);
  };
  const expectedGain = (post, qi) => {
    const h0 = entropy(post);
    let expected = 0;
    for (const row of logp[qi]) {
      const joint = post.map((p, g) => p * Math.exp(row[g]));
      const pr = fsum(joint);
      if (pr > 0) expected += pr * entropy(joint.map((x) => x / pr));
    }
    return h0 - expected;
  };
  const bestQuestion = (post, remaining) => {
    let best = null, bestGain = 0;
    for (const qi of remaining) {
      const gain = expectedGain(post, qi);
      if (best === null || pyRound(gain, 9) > pyRound(bestGain, 9)) { best = qi; bestGain = gain; }
    }
    return [best, bestGain];
  };
  c.__model = { nTypes, typeClass, typeRoles, logp, entropy, confidenceParts, posterior, expectedGain, bestQuestion };
  return c.__model;
}

/** The specialization (global index) the scoring recommends for these picks: best class, then best specialization in it. */
function recommendedType(c, picks) {
  const nc = c.classes.length, nt = c.traits.length;
  const classTotals = Array.from({ length: nc }, (_, i) => fsum(picks.map(([qi, ai]) => c.questions[qi].class_delta[ai][i])));
  const traitTotals = Array.from({ length: nt }, (_, i) => fsum(picks.map(([qi, ai]) => c.questions[qi].trait_delta[ai][i])));
  const nSpecs = c.classes.reduce((n, cl) => n + cl.specs.length, 0);
  const specTotals = new Array(nSpecs).fill(0);
  for (const g of c.active_specs) specTotals[g] = fsum(picks.map(([qi, ai]) => c.questions[qi].spec_delta[ai][g]));
  const ci = order(nc, (i) => classTotals[i], (i) => c.classes[i].tie_rank)[0];
  const scores = c.classes[ci].specs.map((s) => fsum(s.terms.map(([t, m]) => m * traitTotals[t])) + c.spec_multiplier * specTotals[s.gidx]);
  return c.classes[ci].specs[order(scores.length, (j) => scores[j], () => 0)[0]].gidx;
}

function typeProbability(c, g, p) {
  for (const cl of c.classes) for (const sp of cl.specs) {
    if (sp.gidx === g) return { class_id: cl.id, class_name: cl.name, specialization_id: sp.id, specialization_name: sp.name, probability: p };
  }
  throw new Error(`no type ${g}`);
}

/** How a confidence-mode quiz stands after these answers (question id -> response id): the same document as POST /adaptive/next. */
export function adaptiveStatus(c, answers) {
  const s = c.adaptive, model = adaptiveModel(c);
  const picks = resolveAnswers(c, answers, c.questions.map((q, i) => i), "long");
  const n = picks.length;
  const post = model.posterior(picks);
  let rec;
  if (n) rec = recommendedType(c, picks);
  else { rec = 0; post.forEach((p, g) => { if (pyRound(p, 9) > pyRound(post[rec], 9)) rec = g; }); }
  const ranked = post.map((p, g) => g).sort((a, b) => (pyRound(post[b], 9) - pyRound(post[a], 9)) || (a - b));
  const answered = new Set(picks.map(([qi]) => qi));
  const eligible = (i) => !c.questions[i].finalists.length || fsum(c.questions[i].finalists.map((g) => post[g])) >= s.tiebreak_mass;
  const remaining = c.questions.map((q, i) => i).filter((i) => !answered.has(i) && eligible(i));
  const limit = Math.min(s.max_questions, c.questions.length);
  const parts = model.confidenceParts(post, rec, s.class_credit, s.role_credit);
  const confidence = parts.overall;
  let done, reason = null;
  if (n >= s.min_questions && confidence >= s.confidence) { done = true; reason = "confident"; }
  else if (n >= limit || !remaining.length) { done = true; reason = "limit"; }
  else done = false;
  const [nxt, gain] = done ? [null, null] : model.bestQuestion(post, remaining);
  const out = {
    answered: n, min_questions: s.min_questions, max_questions: limit, threshold: s.confidence, confidence,
    spec_probability: parts.spec, class_probability: parts.class, role_probability: parts.role, role: c.classes.flatMap((cl) => cl.specs).find((sp) => sp.gidx === rec).role,
    recommended: typeProbability(c, rec, parts.spec), top: ranked.slice(0, 5).map((g) => typeProbability(c, g, post[g])),
    entropy: model.entropy(post), done, can_reveal: n >= s.min_questions,
  };
  if (reason) out.reason = reason;
  if (nxt !== null) { out.next_question_id = c.questions[nxt].id; out.expected_gain = gain; }
  return out;
}
