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

function resolveAnswers(c, answers) {
  const picks = [];
  for (const [qid, given] of Object.entries(answers || {})) {
    const qi = c.qIndex.get(qid);
    if (qi === undefined) throw new ScoringError("unknown_question", `Unknown or disabled question '${qid}'.`);
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
export function evaluate(c, answers, { allowPartial = false } = {}) {
  const picks = resolveAnswers(c, answers);
  const given = answers || {};
  const missing = c.questions.filter((q) => !Object.prototype.hasOwnProperty.call(given, q.id)).map((q) => q.id);
  if (!picks.length || (missing.length && !allowPartial)) {
    throw new ScoringError("incomplete_assessment",
      missing.length ? `${missing.length} question(s) unanswered: ${missing.join(", ")}` : "At least one answer is required.", { missing });
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
  const weighed = pSpec.terms.map(([t, m]) => `${c.traits[t].name} (×${formatG(m)})`).join(", then ");
  const scored = pSpec.terms.map(([t]) => signed(traitTotals[t])).join(", ");
  const specReading = `${pSpec.description} The ${pCls.name} ${pSpec.name} profile weighs ${weighed}; `
    + `your adjusted scores in those traits were ${scored}.`;

  const gap = classTotals[classOrder[0]] - classTotals[classOrder[1]];
  const label = r(gap) >= c.strong_margin ? "Strong lean" : r(gap) >= c.moderate_margin ? "Clear lean" : "Close call";

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
      class_gap: o(gap),
      strong_margin: c.strong_margin,
      moderate_margin: c.moderate_margin,
      note: "Heuristic descriptor based on the gap between the top two class scores "
        + "and configurable margins. It is not a statistical estimate or a probability.",
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
      total_questions: c.questions.length,
      complete: !missing.length,
      provisional: !!missing.length,
      missing_questions: missing,
      spec_weight_multiplier: c.spec_multiplier,
      scores_are_probabilities: false,
      note: "Scores are relative compatibility indicators, not probabilities. "
        + "Confidence labels are heuristics, not statistical estimates.",
    },
  };
}
