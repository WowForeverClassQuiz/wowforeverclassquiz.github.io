"""Pure scoring engine.

Everything here is a deterministic function of a ``Config`` and a set of selected
answers. Nothing touches the database, the network, or any global state, so the
same functions serve evaluation, simulation, batch diagnostics, and unit tests.

Algorithm (version 1.0.0)
-------------------------
Stage 1 - class score. For class ``c``, question ``q`` and chosen answer ``a``::

    delta(q, c) = w[q, a, c] - mean over the question's answers of w[q, ., c]
    S_c         = sum over answered questions of delta(q, c)

Stage 2 - trait score ``T_t`` uses the identical normalization on trait weights.

Stage 3 - specialization score::

    P_s = sum over (trait, multiplier) in profile(s) of multiplier * T_trait
          + m * sum over answered questions of delta_spec(q, s)

where delta_spec uses the same baseline-subtracted rule on the optional direct specialization weights
('class/spec' keys) and m is ``scoring.spec_weight_multiplier`` (1.0). Questions without spec weights
contribute nothing to the second term, so the original sixteen questions behave exactly as before.

Question types. Every question is compiled into a table of possible responses, and each response has a weight
vector; the baseline is always the mean over that question's responses:

  choice    one response per answer.
  pick_two  one response per unordered pair of the four answers (id 'a+c'); a pair's weights are the sum of its
            two answers' weights.
  scale     ten responses '1'..'10'. With s = (r - 5.5) / 4.5 in [-1, 1], the response weights are
            max(s, 0) * agree + max(-s, 0) * disagree, where 'agree' and 'disagree' are the two pole answers.
  ranking   one response per ordering of the four answers (id 'c>a>d>b', best first, 24 in all); the answer
            ranked r-th (0 = first) counts (3 - r) / 2, i.e. 1.5, 1, 0.5, 0.
  allocation one response per way of spending six points over the four answers (id '2-0-3-1', 84 in all); an answer
            given p points counts p / 3.

Quiz lengths. A question's ``min_length`` (short, medium or long) is the shortest quiz that asks it, and longer quizzes ask it
too, so the quizzes are nested. A question marked "adaptive" is asked only in confidence mode and in no fixed quiz. Scoring a length uses only that length's questions; the arithmetic is otherwise unchanged. The
confidence margins scale with the square root of the share of questions asked (the gap between the top two classes of random answers
grows about that fast), so a short quiz is not called a "close call" merely for being short.

Only the winning class's specializations decide the primary result. Ties are broken
deterministically (class tie-break order, then specialization order, then trait order).
"""
from __future__ import annotations

import random
import itertools
from dataclasses import dataclass
from math import fsum, sqrt
from typing import Any, Optional, Sequence

from .models import (
    Alternatives,
    BatchSide,
    BatchSimulateResponse,
    Config,
    Confidence,
    ClassScore,
    ContributionCell,
    Counterfactual,
    EvaluationResponse,
    ExpandedOption,
    Explanation,
    FrequencyRow,
    Metadata,
    PrimaryPick,
    QuestionExplanation,
    Question,
    QuestionExpansion,
    QuestionInfluence,
    Rankings,
    ResultBlock,
    ScoreDiff,
    SimulationResponse,
    SpecGuide,
    SpecDiff,
    SpecPick,
    SpecScore,
    SpecTerm,
    TieBreak,
    TraitScore,
    ALLOCATION_POINTS,
    LENGTHS,
    TIERS,
    SCALE_MAX,
    SCALE_MIN,
)

#: Scores are compared after rounding to this many decimals, so float noise never
#: decides a result and exact ties are reproducible.
COMPARE_DECIMALS = 9
OUTPUT_DECIMALS = 10

FORMULAS = {
    "class_contribution": "delta(q,c) = w[q,chosen,c] - (1/n) * sum_a w[q,a,c]   (n = answers in the question)",
    "class_score": "S_c = sum over answered questions of delta(q,c)",
    "trait_score": "T_t = sum over answered questions of ( w[q,chosen,t] - (1/n) * sum_a w[q,a,t] )",
    "specialization_score": "P_s = sum over profile traits of multiplier * T_trait + m * sum over questions of delta_spec(q,s)",
    "direct_specialization": "delta_spec(q,s) = w[q,chosen,s] - (1/n) * sum_a w[q,a,s], using the answers' 'class/spec' weights; m = spec_weight_multiplier",
    "scale_response": "scale rating r in 1..10: s = (r - 5.5) / 4.5; response weights = max(s,0) * agree-pole + max(-s,0) * disagree-pole",
    "pick_two_response": "pick-two response 'a+c' carries the sum of the two chosen answers' weights; the baseline is the mean over all six pairs",
    "ranking_response": "ranking response 'c>a>d>b' weights the answers 1.5, 1, 0.5 and 0 from best to last; the baseline is the mean over all 24 orderings",
    "allocation_response": "allocation response '2-0-3-1' weights each answer by its points / 3 (six points in all); the baseline is the mean over all 84 splits",
    "interpretation": "Scores are relative compatibility indicators on a scale with no fixed maximum.",
}


class ScoringError(ValueError):
    """Base class for invalid scoring input."""


class UnknownQuestionError(ScoringError):
    pass


class UnknownAnswerError(ScoringError):
    pass


class InvalidOverrideError(ScoringError):
    pass


class IncompleteAssessmentError(ScoringError):
    def __init__(self, missing: Sequence[str]):
        self.missing = list(missing)
        super().__init__(
            f"{len(self.missing)} question(s) unanswered: {', '.join(self.missing)}"
            if self.missing
            else "At least one answer is required."
        )


def _r(x: float) -> float:
    """Comparison value: rounded, with -0.0 normalized to 0.0."""
    return round(x, COMPARE_DECIMALS) + 0.0


def _o(x: float) -> float:
    """Output value: rounded for display, with -0.0 normalized to 0.0."""
    return round(x, OUTPUT_DECIMALS) + 0.0


# --------------------------------------------------------------------------
# Compiled (array) form of a configuration
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CQuestion:
    id: str
    text: str
    type: str
    length_rank: int  # position of min_length in TIERS: 0 short, 1 medium, 2 long, 3 only confidence mode
    item_ids: tuple[str, ...]  # the selectable answers as authored (pick_two needs them to parse 'a+c')
    answer_ids: tuple[str, ...]  # every possible RESPONSE id (answers, answer pairs, or '1'..'10')
    answer_texts: tuple[str, ...]
    class_raw: tuple[tuple[float, ...], ...]  # [response][class]
    trait_raw: tuple[tuple[float, ...], ...]  # [response][trait]
    spec_raw: tuple[tuple[float, ...], ...]  # [response][global specialization index]
    class_base: tuple[float, ...]  # [class]
    trait_base: tuple[float, ...]  # [trait]
    spec_base: tuple[float, ...]  # [specialization]
    class_delta: tuple[tuple[float, ...], ...]
    trait_delta: tuple[tuple[float, ...], ...]
    spec_delta: tuple[tuple[float, ...], ...]
    finalists: tuple[int, ...] = ()  # tiebreaker: global specialization indexes of the finalists (empty: an ordinary question)
    opener: bool = False  # confidence mode may open with this question


@dataclass(frozen=True)
class CSpec:
    id: str
    key: str  # 'class/spec'
    gidx: int  # global specialization index
    name: str
    role: str
    description: str
    terms: tuple[tuple[int, float], ...]  # (trait index, multiplier), profile order
    overview: str = ""
    guide: Optional[dict] = None  # SpecGuide as a plain dict, or None when it holds nothing


@dataclass(frozen=True)
class CClass:
    id: str
    name: str
    description: str
    specs: tuple[CSpec, ...]
    overview: str = ""
    overview_url: str = ""


@dataclass(frozen=True)
class Compiled:
    revision: int
    algorithm_version: str
    class_ids: tuple[str, ...]
    trait_ids: tuple[str, ...]
    trait_names: tuple[str, ...]
    trait_readings: tuple[str, ...]
    classes: tuple[CClass, ...]
    tie_rank: tuple[int, ...]  # class index -> position in the tie-break order
    questions: tuple[CQuestion, ...]
    q_index: dict[str, int]
    strong_margin: float
    moderate_margin: float
    spec_keys: tuple[str, ...]
    spec_multiplier: float
    active_specs: tuple[int, ...]  # specializations that some question gives direct weight
    adaptive: Any = None  # AdaptiveSettings: the confidence-mode parameters

    @property
    def n_specs(self) -> int:
        return len(self.spec_keys)

    @property
    def n_core(self) -> int:
        """How many questions the fixed quizzes draw on (the long quiz asks all of them); confidence-mode-only questions are extra."""
        return sum(1 for q in self.questions if q.length_rank < len(LENGTHS))

    @property
    def n_classes(self) -> int:
        return len(self.class_ids)

    @property
    def n_traits(self) -> int:
        return len(self.trait_ids)


def active_questions(c: Compiled, length: str = "long") -> tuple[int, ...]:
    """Indices of the questions a quiz of this length asks, in quiz order."""
    if length not in LENGTHS:
        raise ScoringError(f"Unknown quiz length '{length}'.")
    rank = LENGTHS.index(length)
    active = tuple(i for i, q in enumerate(c.questions) if q.length_rank <= rank)
    if not active:
        raise ScoringError(f"The {length} quiz has no questions.")
    return active


def margin_scale(c: Compiled, active: Sequence[int]) -> float:
    """Factor applied to the confidence margins: sqrt of the share of the long quiz's questions that are asked (1.0 for the full quiz)."""
    return sqrt(len(active) / c.n_core)


def compile_config(config: Config) -> Compiled:
    class_ids = tuple(c.id for c in config.classes)
    trait_ids = tuple(t.id for t in config.traits)
    nc, nt = len(class_ids), len(trait_ids)
    trait_index = {t: i for i, t in enumerate(trait_ids)}
    if len(set(class_ids)) != nc or len(set(trait_ids)) != nt:
        raise ScoringError("Class and trait identifiers must be unique.")

    spec_keys = tuple(f"{cl.id}/{sp.id}" for cl in config.classes for sp in cl.specializations)
    spec_pos = {k: i for i, k in enumerate(spec_keys)}
    ns = len(spec_keys)

    questions: list[CQuestion] = []
    for q in config.enabled_questions():
        for a in q.answers:
            bad = (set(a.class_weights) - set(class_ids)) | (set(a.trait_weights) - set(trait_ids)) | (set(a.spec_weights) - set(spec_keys))
            if bad:
                raise ScoringError(f"Answer {q.id}/{a.id} references unknown ids: {sorted(bad)}")
        table = _response_table(q)
        n = len(table)
        class_raw = tuple(tuple(float(cw.get(cid, 0.0)) for cid in class_ids) for _, _, cw, _, _ in table)
        trait_raw = tuple(tuple(float(tw.get(tid, 0.0)) for tid in trait_ids) for _, _, _, tw, _ in table)
        spec_raw = tuple(tuple(float(sw.get(k, 0.0)) for k in spec_keys) for _, _, _, _, sw in table)
        class_base = tuple(fsum(row[i] for row in class_raw) / n for i in range(nc))
        trait_base = tuple(fsum(row[i] for row in trait_raw) / n for i in range(nt))
        spec_base = tuple(fsum(row[i] for row in spec_raw) / n for i in range(ns))
        questions.append(
            CQuestion(
                id=q.id,
                text=q.text,
                type=q.type,
                length_rank=TIERS.index(q.min_length),
                finalists=tuple(spec_keys.index(k) for k in q.finalists if k in spec_keys),
                opener=q.opener,
                item_ids=tuple(a.id for a in q.answers),
                answer_ids=tuple(r[0] for r in table),
                answer_texts=tuple(r[1] for r in table),
                class_raw=class_raw,
                trait_raw=trait_raw,
                spec_raw=spec_raw,
                class_base=class_base,
                trait_base=trait_base,
                spec_base=spec_base,
                class_delta=tuple(tuple(row[i] - class_base[i] for i in range(nc)) for row in class_raw),
                trait_delta=tuple(tuple(row[i] - trait_base[i] for i in range(nt)) for row in trait_raw),
                spec_delta=tuple(tuple(row[i] - spec_base[i] for i in range(ns)) for row in spec_raw),
            )
        )
    active_specs = tuple(sorted({g for q in questions for row in q.spec_raw for g, v in enumerate(row) if v}))

    classes: list[CClass] = []
    for cls in config.classes:
        specs = []
        for s in cls.specializations:
            unknown = [t for t in s.trait_multipliers if t not in trait_index]
            if unknown:
                raise ScoringError(f"Specialization {cls.id}/{s.id} references unknown traits: {unknown}")
            specs.append(
                CSpec(
                    id=s.id,
                    key=f"{cls.id}/{s.id}",
                    gidx=spec_pos[f"{cls.id}/{s.id}"],
                    name=s.name,
                    role=s.role,
                    description=s.description,
                    overview=s.overview,
                    guide=s.guide.model_dump() if any(s.guide.model_dump().values()) else None,
                    terms=tuple((trait_index[t], float(m)) for t, m in s.trait_multipliers.items()),
                )
            )
        classes.append(CClass(cls.id, cls.name, cls.description, tuple(specs), cls.overview, cls.overview_url))

    order = list(config.scoring.class_tie_break_order)
    tie_rank = [len(order)] * nc
    for pos, cid in enumerate(order):
        if cid in class_ids:
            tie_rank[class_ids.index(cid)] = pos

    return Compiled(
        revision=config.revision,
        algorithm_version=config.scoring.algorithm_version,
        class_ids=class_ids,
        trait_ids=trait_ids,
        trait_names=tuple(t.name for t in config.traits),
        trait_readings=tuple(t.interpretation for t in config.traits),
        classes=tuple(classes),
        tie_rank=tuple(tie_rank),
        questions=tuple(questions),
        q_index={q.id: i for i, q in enumerate(questions)},
        strong_margin=float(config.scoring.confidence_margins.strong),
        moderate_margin=float(config.scoring.confidence_margins.moderate),
        spec_keys=spec_keys,
        spec_multiplier=float(config.scoring.spec_weight_multiplier),
        active_specs=active_specs,
        adaptive=config.scoring.adaptive,
    )


def _mix(parts) -> dict[str, float]:
    """Weighted sum of weight dictionaries: [(factor, {key: weight}), ...]."""
    out: dict[str, float] = {}
    for factor, weights in parts:
        if not factor:
            continue
        for k, v in weights.items():
            out[k] = out.get(k, 0.0) + factor * v
    return out


def response_coefficients(q: Question) -> list[tuple[str, str, list[float]]]:
    """Every possible response to a question as (id, label, coefficient of each answer, in answer order).

    A response's weights are always the coefficient-weighted sum of its answers' weights, so one table describes
    every question type (and lets tuning tools reason about a single answer's influence)."""
    n = len(q.answers)
    if q.type == "choice":
        if n < 2:
            raise ScoringError(f"Question {q.id} needs at least two answers.")
        return [(a.id, a.text, [1.0 if j == i else 0.0 for j in range(n)]) for i, a in enumerate(q.answers)]
    if q.type in ("pick_two", "ranking", "allocation") and n != 4:
        raise ScoringError(f"Question {q.id} ({q.type}) needs exactly four answers.")
    if q.type == "pick_two":
        return [
            (f"{q.answers[i].id}+{q.answers[j].id}", f"{q.answers[i].text} + {q.answers[j].text}",
             [1.0 if k in (i, j) else 0.0 for k in range(4)])
            for i, j in itertools.combinations(range(4), 2)
        ]
    if q.type == "ranking":  # the answer ranked r-th (0 = first) counts (3 - r) / 2: 1.5, 1, 0.5, 0
        rows = []
        for perm in itertools.permutations(range(4)):
            coefs = [0.0] * 4
            for rank, i in enumerate(perm):
                coefs[i] = (3 - rank) / 2
            rows.append((">".join(q.answers[i].id for i in perm), " > ".join(q.answers[i].text for i in perm), coefs))
        return rows
    if q.type == "allocation":  # six points over four answers; an answer given p points counts p / 3
        rows = []
        for pts in itertools.product(range(ALLOCATION_POINTS + 1), repeat=4):
            if sum(pts) != ALLOCATION_POINTS:
                continue
            label = ", ".join(f"{q.answers[i].text} x{p}" for i, p in enumerate(pts) if p)
            rows.append(("-".join(str(p) for p in pts), label, [p / (ALLOCATION_POINTS / 2) for p in pts]))
        return rows
    if q.type == "scale":
        poles = {a.id: i for i, a in enumerate(q.answers)}
        if n != 2 or set(poles) != {"agree", "disagree"}:
            raise ScoringError(f"Question {q.id} (scale) needs exactly the answers 'agree' and 'disagree'.")
        mid, half = (SCALE_MIN + SCALE_MAX) / 2, (SCALE_MAX - SCALE_MIN) / 2
        rows = []
        for r in range(SCALE_MIN, SCALE_MAX + 1):
            s = (r - mid) / half
            coefs = [0.0, 0.0]
            coefs[poles["agree"]], coefs[poles["disagree"]] = max(s, 0.0), max(-s, 0.0)
            rows.append((str(r), f"{r} of {SCALE_MAX}", coefs))
        return rows
    raise ScoringError(f"Question {q.id} has unknown type '{q.type}'.")


def _response_table(q: Question) -> list[tuple[str, str, dict, dict, dict]]:
    """Every possible response to a question: (id, label, class weights, trait weights, spec weights)."""
    return [
        (
            rid, label,
            _mix([(f, a.class_weights) for f, a in zip(coefs, q.answers)]),
            _mix([(f, a.trait_weights) for f, a in zip(coefs, q.answers)]),
            _mix([(f, a.spec_weights) for f, a in zip(coefs, q.answers)]),
        )
        for rid, label, coefs in response_coefficients(q)
    ]


# --------------------------------------------------------------------------
# Core arithmetic
# --------------------------------------------------------------------------

Picks = list[tuple[int, int]]  # (question index, answer index), sorted by question


def resolve_answers(c: Compiled, answers: dict[str, str], active: Optional[Sequence[int]] = None, length: str = "long", keep_order: bool = False) -> Picks:
    """The (question index, response index) of every answer. Sorted by question unless ``keep_order``, which keeps the order they were given in."""
    picks: Picks = []
    for qid, aid in answers.items():
        qi = c.q_index.get(qid)
        if qi is None:
            raise UnknownQuestionError(f"Unknown or disabled question '{qid}'.")
        if active is not None and qi not in active:
            raise UnknownQuestionError(f"Question '{qid}' is not part of the {length} quiz.")
        q = c.questions[qi]
        if q.type == "pick_two":  # accept either order: 'c+a' is 'a+c'
            parts = aid.split("+")
            if len(parts) == 2 and parts[0] != parts[1] and all(p in q.item_ids for p in parts):
                aid = "+".join(sorted(parts, key=q.item_ids.index))
        if aid not in q.answer_ids:
            raise UnknownAnswerError(f"Question '{qid}' has no answer '{aid}'.")
        picks.append((qi, q.answer_ids.index(aid)))
    if not keep_order:
        picks.sort()
    return picks


def _class_totals(c: Compiled, picks: Picks) -> list[float]:
    return [fsum(c.questions[qi].class_delta[ai][i] for qi, ai in picks) for i in range(c.n_classes)]


def _trait_totals(c: Compiled, picks: Picks) -> list[float]:
    return [fsum(c.questions[qi].trait_delta[ai][i] for qi, ai in picks) for i in range(c.n_traits)]


def _spec_totals(c: Compiled, picks: Picks) -> list[float]:
    totals = [0.0] * c.n_specs
    for g in c.active_specs:
        totals[g] = fsum(c.questions[qi].spec_delta[ai][g] for qi, ai in picks)
    return totals


def _class_order(c: Compiled, totals: Sequence[float]) -> list[int]:
    return sorted(range(c.n_classes), key=lambda i: (-_r(totals[i]), c.tie_rank[i]))


def _spec_scores(c: Compiled, ci: int, trait_totals: Sequence[float], spec_totals: Sequence[float]) -> list[float]:
    return [
        fsum(m * trait_totals[t] for t, m in s.terms) + c.spec_multiplier * spec_totals[s.gidx]
        for s in c.classes[ci].specs
    ]


def _spec_order(scores: Sequence[float]) -> list[int]:
    return sorted(range(len(scores)), key=lambda j: (-_r(scores[j]), j))


def _lean_primary(c: Compiled, class_totals: Sequence[float], trait_totals: Sequence[float], spec_totals: Sequence[float]):
    """(class index, spec index, gap between the top two classes) without building any output."""
    order = _class_order(c, class_totals)
    ci = order[0]
    sc = _spec_scores(c, ci, trait_totals, spec_totals)
    si = _spec_order(sc)[0]
    gap = class_totals[order[0]] - class_totals[order[1]] if len(order) > 1 else 0.0
    return ci, si, gap


def _tie_groups(order: Sequence[int], scores: Sequence[float]) -> list[list[int]]:
    """Positions (0-based) of runs of equal (rounded) scores of length > 1."""
    groups: list[list[int]] = []
    run = [0]
    for pos in range(1, len(order)):
        if _r(scores[order[pos]]) == _r(scores[order[pos - 1]]):
            run.append(pos)
        else:
            if len(run) > 1:
                groups.append(run)
            run = [pos]
    if len(run) > 1:
        groups.append(run)
    return groups


def decision_note(c: Compiled, qi: int) -> str:
    """The sentence a result carries when a tiebreaker question settled it, naming the finalists of that question."""
    names = []
    for g in c.questions[qi].finalists:
        for cls in c.classes:
            for sp in cls.specs:
                if sp.gidx == g:
                    names.append(f"{sp.name} {cls.name}")
    return f"Your answer to a tiebreaker question settled the choice between {_join(names)}."


def _join(items: Sequence[str]) -> str:
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def _signed(x: float) -> str:
    return f"{x:+.2f}"


# --------------------------------------------------------------------------
# Evaluation
# --------------------------------------------------------------------------


def evaluate(
    config: Config,
    answers: dict[str, str],
    *,
    allow_partial: bool = False,
    include_explanation: bool = True,
    include_counterfactuals: bool = False,
    compiled: Optional[Compiled] = None,
    length: str = "long",
) -> EvaluationResponse:
    """Score a set of selected answers to the questions of one quiz length. Pure: no I/O, no mutation of ``config``."""
    c = compiled or compile_config(config)
    if length == "adaptive":
        # confidence mode: the questions were chosen one at a time, so the quiz is exactly the questions that were answered
        active = tuple(sorted(c.q_index[q] for q in answers if q in c.q_index))
        picks = resolve_answers(c, answers, active, length)
        missing = []
        if not picks:
            raise IncompleteAssessmentError(missing)
        if len(picks) < c.adaptive.min_questions and not allow_partial:
            raise ScoringError(f"Confidence mode needs at least {c.adaptive.min_questions} answers; got {len(picks)}.")
    else:
        active = active_questions(c, length)
        picks = resolve_answers(c, answers, active, length)
        missing = [c.questions[i].id for i in active if c.questions[i].id not in answers]
        if not picks or (missing and not allow_partial):
            raise IncompleteAssessmentError(missing)

    nc, nt = c.n_classes, c.n_traits
    if nc < 2:
        raise ScoringError("At least two classes are required.")

    class_totals = _class_totals(c, picks)
    trait_totals = _trait_totals(c, picks)
    spec_totals = _spec_totals(c, picks)
    class_raw = [fsum(c.questions[qi].class_raw[ai][i] for qi, ai in picks) for i in range(nc)]
    class_exp = [fsum(c.questions[qi].class_base[i] for qi, _ in picks) for i in range(nc)]
    trait_raw = [fsum(c.questions[qi].trait_raw[ai][i] for qi, ai in picks) for i in range(nt)]
    trait_exp = [fsum(c.questions[qi].trait_base[i] for qi, _ in picks) for i in range(nt)]
    appearances = [sum(1 for qi, ai in picks if c.questions[qi].trait_raw[ai][i] > 0) for i in range(nt)]

    class_order = _class_order(c, class_totals)
    trait_order = sorted(range(nt), key=lambda i: (-_r(trait_totals[i]), i))
    spec_scores = [_spec_scores(c, ci, trait_totals, spec_totals) for ci in range(nc)]
    spec_orders = [_spec_order(s) for s in spec_scores]

    model, decided = None, None
    if length == "adaptive":
        from .adaptive import Model, settled_by_tiebreaker     # imported here: adaptive.py builds on this module
        model = Model(c)
        decided = settled_by_tiebreaker(c, picks, model)
    if decided:        # confidence mode: an answered tiebreaker between the frontrunners names the result, ahead of the scores
        d_cls = next(ci for ci, cls in enumerate(c.classes) if any(sp.gidx == decided[0] for sp in cls.specs))
        d_idx = next(j for j, sp in enumerate(c.classes[d_cls].specs) if sp.gidx == decided[0])
        class_order = [d_cls] + [i for i in class_order if i != d_cls]
        spec_orders[d_cls] = [d_idx] + [j for j in spec_orders[d_cls] if j != d_idx]

    leader = class_totals[class_order[0]]
    class_rows: list[ClassScore] = []
    for rank, i in enumerate(class_order, start=1):
        class_rows.append(
            ClassScore(
                id=c.class_ids[i],
                name=c.classes[i].name,
                score=_o(class_totals[i]),
                rank=rank,
                raw_points=_o(class_raw[i]),
                expected_points=_o(class_exp[i]),
                gap_to_leader=_o(max(leader - class_totals[i], 0.0)),
                tied_with_previous=rank > 1 and _r(class_totals[i]) == _r(class_totals[class_order[rank - 2]]),
            )
        )

    trait_rows: list[TraitScore] = []
    for rank, i in enumerate(trait_order, start=1):
        trait_rows.append(
            TraitScore(
                id=c.trait_ids[i],
                name=c.trait_names[i],
                score=_o(trait_totals[i]),
                rank=rank,
                raw_points=_o(trait_raw[i]),
                expected_points=_o(trait_exp[i]),
                appearances=appearances[i],
                tied_with_previous=rank > 1 and _r(trait_totals[i]) == _r(trait_totals[trait_order[rank - 2]]),
            )
        )

    def spec_rows(ci: int) -> list[SpecScore]:
        cls = c.classes[ci]
        scores, order = spec_scores[ci], spec_orders[ci]
        rows = []
        for rank, j in enumerate(order, start=1):
            s = cls.specs[j]
            rows.append(
                SpecScore(
                    class_id=cls.id,
                    id=s.id,
                    name=s.name,
                    role=s.role,
                    score=_o(scores[j]),
                    rank=rank,
                    tied_with_previous=rank > 1 and _r(scores[j]) == _r(scores[order[rank - 2]]),
                    direct_score=_o(c.spec_multiplier * spec_totals[s.gidx]),
                    terms=[
                        SpecTerm(
                            trait_id=c.trait_ids[t],
                            trait_name=c.trait_names[t],
                            multiplier=m,
                            trait_score=_o(trait_totals[t]),
                            contribution=_o(m * trait_totals[t]),
                        )
                        for t, m in s.terms
                    ],
                )
            )
        return rows

    all_spec_rows = [spec_rows(ci) for ci in range(nc)]
    p_ci, alt_ci = class_order[0], class_order[1]
    primary_specs = all_spec_rows[p_ci]
    alt_specs = all_spec_rows[alt_ci]

    def pick(ci: int, row: SpecScore) -> SpecPick:
        s = next(x for x in c.classes[ci].specs if x.id == row.id)
        return SpecPick(
            class_id=c.class_ids[ci],
            class_name=c.classes[ci].name,
            id=row.id,
            name=row.name,
            role=row.role,
            score=row.score,
            description=s.description,
            guide=SpecGuide.model_validate(s.guide) if s.guide else None,
        )

    primary_pick = pick(p_ci, primary_specs[0])
    second_pick = pick(p_ci, primary_specs[1] if len(primary_specs) > 1 else primary_specs[0])
    alt_pick = pick(alt_ci, alt_specs[0])

    # -- interpretation ------------------------------------------------------
    dominant = [t for t in trait_rows if t.score > 0][:3] or trait_rows[:1]
    p_cls = c.classes[p_ci]
    readings = " ".join(
        c.trait_readings[c.trait_ids.index(t.id)] for t in dominant if c.trait_readings[c.trait_ids.index(t.id)]
    )
    personality = (
        f"The stars lean toward the {p_cls.name}: {p_cls.description.rstrip('.')}. "
        f"Your answers emphasized {_join([t.name for t in dominant])}. {readings}"
    ).strip()
    p_spec = next(s for s in p_cls.specs if s.id == primary_pick.id)
    weighed = ", then ".join(f"{c.trait_names[t]} (×{m:g})" for t, m in p_spec.terms)
    scored = ", ".join(_signed(trait_totals[t]) for t, _ in p_spec.terms)
    spec_reading = (
        f"{p_spec.description} The {p_cls.name} {p_spec.name} profile weighs {weighed}; "
        f"your adjusted scores in those traits were {scored}."
    ).strip()

    gap = max(class_totals[class_order[0]] - class_totals[class_order[1]], 0.0)
    scale = margin_scale(c, active)
    strong_margin, moderate_margin = c.strong_margin * scale, c.moderate_margin * scale
    if _r(gap) >= strong_margin:
        label = "Strong lean"
    elif _r(gap) >= moderate_margin:
        label = "Clear lean"
    else:
        label = "Close call"
    from .adaptive import Model, question_factor
    model = model or Model(c)
    parts = model.confidence_parts(model.posterior(picks), p_spec.gidx, c.adaptive.class_credit, c.adaptive.role_credit)
    factor = question_factor(len(picks), c.adaptive.question_scaling)       # a result states the current confidence, scaled; only the meter keeps the best so far
    stated = factor * parts.overall
    if decided:
        from .adaptive import decided_confidence
        stated = decided_confidence(c, model, answers, model.posterior(picks), decided[0], c.adaptive)          # the figure the meter was heading to, so it does not fall on the reveal
    confidence = Confidence(
        label=label,
        probability=_o(parts.spec),
        class_probability=_o(parts.class_),
        role_probability=_o(parts.role),
        overall=_o(stated),
        question_factor=_o(factor),
        role=p_spec.role,
        decided_by=c.questions[decided[1]].id if decided else None,
        decision_note=decision_note(c, decided[1]) if decided else None,
        class_gap=_o(gap),
        strong_margin=strong_margin,
        moderate_margin=moderate_margin,
        note=(
            "Heuristic descriptor based on the gap between the top two class scores "
            "and configurable margins. The probability field comes from the confidence model."
        ),
    )

    result = ResultBlock(
        primary_class=class_rows[0],
        primary_class_description=p_cls.description,
        class_overview=p_cls.overview,
        specialization_overview=p_spec.overview,
        overview_url=p_cls.overview_url,
        primary_specialization=primary_pick,
        dominant_traits=dominant,
        personality_interpretation=personality,
        specialization_interpretation=spec_reading,
        confidence=confidence,
    )
    alternatives = Alternatives(
        alternative_class=class_rows[1],
        alternative_specialization=alt_pick,
        second_specialization_in_primary_class=second_pick,
    )
    rankings = Rankings(
        classes=class_rows,
        specializations=primary_specs,
        alternative_class_specializations=alt_specs,
        all_specializations=[row for rows in all_spec_rows for row in rows],
        traits=trait_rows,
    )
    metadata = Metadata(
        config_revision=c.revision,
        algorithm_version=c.algorithm_version,
        answered_questions=len(picks),
        total_questions=len(active),
        quiz_length=length,
        complete=not missing,
        provisional=bool(missing),
        missing_questions=missing,
        spec_weight_multiplier=c.spec_multiplier,
    )

    explanation = None
    if include_explanation:
        explanation = _explain(
            c, picks, class_order, class_totals, trait_totals, spec_totals, spec_scores, spec_orders, p_ci, alt_ci,
            trait_order, include_counterfactuals and not decided,          # the what-if answers describe the scores alone, which a tiebreaker decision overrides
        )
    return EvaluationResponse(
        result=result, alternatives=alternatives, rankings=rankings, explanation=explanation, metadata=metadata
    )


def _explain(
    c: Compiled,
    picks: Picks,
    class_order: list[int],
    class_totals: list[float],
    trait_totals: list[float],
    spec_totals: list[float],
    spec_scores: list[list[float]],
    spec_orders: list[list[int]],
    p_ci: int,
    alt_ci: int,
    trait_order: list[int],
    include_counterfactuals: bool,
) -> Explanation:
    nc, nt = c.n_classes, c.n_traits
    questions: list[QuestionExplanation] = []
    for qi, ai in picks:
        q = c.questions[qi]
        cc = {
            c.class_ids[i]: ContributionCell(
                raw=_o(q.class_raw[ai][i]), baseline=_o(q.class_base[i]), adjusted=_o(q.class_delta[ai][i])
            )
            for i in range(nc)
        }
        tc = {
            c.trait_ids[i]: ContributionCell(
                raw=_o(q.trait_raw[ai][i]), baseline=_o(q.trait_base[i]), adjusted=_o(q.trait_delta[ai][i])
            )
            for i in range(nt)
        }
        spec_cells = {
            c.spec_keys[g]: ContributionCell(
                raw=_o(q.spec_raw[ai][g]), baseline=_o(q.spec_base[g]), adjusted=_o(q.spec_delta[ai][g])
            )
            for g in c.active_specs
            if q.spec_base[g] or any(row[g] for row in q.spec_raw)
        }
        questions.append(
            QuestionExplanation(
                question_id=q.id,
                question_text=q.text,
                question_type=q.type,
                spec_contributions=spec_cells,
                answer_id=q.answer_ids[ai],
                answer_text=q.answer_texts[ai],
                class_contributions=cc,
                trait_contributions=tc,
                class_adjusted_sum=_o(fsum(q.class_delta[ai])),
                trait_adjusted_sum=_o(fsum(q.trait_delta[ai])),
                leader_margin_effect=_o(q.class_delta[ai][class_order[0]] - q.class_delta[ai][class_order[1]]),
            )
        )

    ties: list[TieBreak] = []
    for run in _tie_groups(class_order, class_totals):
        if run[0] < 2:
            ties.append(
                TieBreak(
                    scope="class",
                    tied=[c.class_ids[class_order[p]] for p in run],
                    score=_o(class_totals[class_order[run[0]]]),
                    positions=[p + 1 for p in run],
                    rule="Equal class scores are resolved by the configured class tie-break order.",
                )
            )
    for ci, limit in ((p_ci, 2), (alt_ci, 1)):
        order = spec_orders[ci]
        for run in _tie_groups(order, spec_scores[ci]):
            if run[0] < limit:
                cls = c.classes[ci]
                ties.append(
                    TieBreak(
                        scope="specialization",
                        scope_id=cls.id,
                        tied=[cls.specs[order[p]].id for p in run],
                        score=_o(spec_scores[ci][order[run[0]]]),
                        positions=[p + 1 for p in run],
                        rule="Equal specialization scores are resolved by the specialization order within the class.",
                    )
                )

    counterfactuals = None
    if include_counterfactuals:
        counterfactuals = []
        base_c, base_s = p_ci, spec_orders[p_ci][0]
        for qi, sel in picks:
            q = c.questions[qi]
            for ai in range(len(q.answer_ids)):
                if ai == sel:
                    continue
                ct = [class_totals[i] - q.class_delta[sel][i] + q.class_delta[ai][i] for i in range(nc)]
                tt = [trait_totals[i] - q.trait_delta[sel][i] + q.trait_delta[ai][i] for i in range(nt)]
                st = list(spec_totals)
                for g in c.active_specs:
                    st[g] += q.spec_delta[ai][g] - q.spec_delta[sel][g]
                ci, si, gap = _lean_primary(c, ct, tt, st)
                counterfactuals.append(
                    Counterfactual(
                        question_id=q.id,
                        answer_id=q.answer_ids[ai],
                        answer_text=q.answer_texts[ai],
                        primary_class_id=c.class_ids[ci],
                        primary_class_name=c.classes[ci].name,
                        primary_specialization_id=c.classes[ci].specs[si].id,
                        primary_specialization_name=c.classes[ci].specs[si].name,
                        class_changed=ci != base_c,
                        specialization_changed=(ci, si) != (base_c, base_s),
                        class_gap=_o(gap),
                    )
                )
    return Explanation(questions=questions, tie_breaks=ties, formulas=FORMULAS, counterfactuals=counterfactuals)


# --------------------------------------------------------------------------
# Simulation
# --------------------------------------------------------------------------


def apply_overrides(config: Config, overrides=(), spec_overrides=()) -> Config:
    """Return a modified deep copy of ``config``. The input is never mutated."""
    sim = config.model_copy(deep=True)
    class_ids = {cl.id for cl in sim.classes}
    trait_ids = {t.id for t in sim.traits}
    spec_keys = {f"{cl.id}/{sp.id}" for cl in sim.classes for sp in cl.specializations}
    for o in overrides:
        q = sim.get_question(o.question_id)
        if q is None:
            raise UnknownQuestionError(f"Unknown question '{o.question_id}'.")
        a = next((x for x in q.answers if x.id == o.answer_id), None)
        if a is None:
            raise UnknownAnswerError(f"Question '{o.question_id}' has no answer '{o.answer_id}'.")
        if o.class_weights is not None:
            bad = set(o.class_weights) - class_ids
            if bad:
                raise InvalidOverrideError(f"Unknown class id(s) in override: {sorted(bad)}")
            a.class_weights = {k: v for k, v in o.class_weights.items() if v}
        if o.trait_weights is not None:
            bad = set(o.trait_weights) - trait_ids
            if bad:
                raise InvalidOverrideError(f"Unknown trait id(s) in override: {sorted(bad)}")
            a.trait_weights = {k: v for k, v in o.trait_weights.items() if v}
        if o.spec_weights is not None:
            bad = set(o.spec_weights) - spec_keys
            if bad:
                raise InvalidOverrideError(f"Unknown specialization key(s) in override: {sorted(bad)}")
            a.spec_weights = {k: v for k, v in o.spec_weights.items() if v}
    for so in spec_overrides:
        spec = sim.get_spec(so.class_id, so.specialization_id)
        if spec is None:
            raise InvalidOverrideError(f"Unknown specialization '{so.class_id}/{so.specialization_id}'.")
        bad = set(so.trait_multipliers) - trait_ids
        if bad:
            raise InvalidOverrideError(f"Unknown trait id(s) in override: {sorted(bad)}")
        spec.trait_multipliers = dict(so.trait_multipliers)
    return sim


def _primary_pick(ev: EvaluationResponse) -> PrimaryPick:
    p = ev.result
    return PrimaryPick(
        class_id=p.primary_class.id,
        class_name=p.primary_class.name,
        specialization_id=p.primary_specialization.id,
        specialization_name=p.primary_specialization.name,
    )


def simulate(
    config: Config,
    answers: dict[str, str],
    overrides=(),
    spec_overrides=(),
    include_explanation: bool = False,
    length: str = "long",
) -> SimulationResponse:
    """Evaluate ``answers`` under the saved configuration and under a temporary override.

    The saved configuration is never modified. Partial answer sets are allowed here.
    """
    simulated_cfg = apply_overrides(config, overrides, spec_overrides)
    original = evaluate(config, answers, allow_partial=True, length=length)
    simulated = evaluate(simulated_cfg, answers, allow_partial=True, length=length)

    def diffs(a, b):
        by_id = {r.id: r for r in b}
        return [
            ScoreDiff(
                id=r.id, name=r.name, original=r.score, simulated=by_id[r.id].score,
                difference=_o(by_id[r.id].score - r.score),
            )
            for r in a
        ]

    cfg_order = {cid: i for i, cid in enumerate(cl.id for cl in config.classes)}
    class_diffs = sorted(diffs(original.rankings.classes, simulated.rankings.classes), key=lambda d: cfg_order[d.id])
    trait_order = {t.id: i for i, t in enumerate(config.traits)}
    trait_diffs = sorted(diffs(original.rankings.traits, simulated.rankings.traits), key=lambda d: trait_order[d.id])
    sim_specs = {(s.class_id, s.id): s for s in simulated.rankings.all_specializations}
    spec_diffs = [
        SpecDiff(
            class_id=s.class_id, id=s.id, name=s.name, original=s.score,
            simulated=sim_specs[(s.class_id, s.id)].score,
            difference=_o(sim_specs[(s.class_id, s.id)].score - s.score),
        )
        for s in original.rankings.all_specializations
    ]

    # Per-question influence on the winner-vs-runner-up margin under each configuration.
    eff_o = {q.question_id: q.leader_margin_effect for q in original.explanation.questions}
    eff_s = {q.question_id: q.leader_margin_effect for q in simulated.explanation.questions}
    influence = sorted(
        (QuestionInfluence(question_id=q, original_effect=eff_o[q], simulated_effect=eff_s[q]) for q in eff_o),
        key=lambda x: (-max(abs(x.original_effect), abs(x.simulated_effect)), x.question_id),
    )
    op, sp = _primary_pick(original), _primary_pick(simulated)
    if not include_explanation:
        original.explanation = simulated.explanation = None
    return SimulationResponse(
        original=original,
        simulated=simulated,
        original_primary=op,
        simulated_primary=sp,
        class_differences=class_diffs,
        trait_differences=trait_diffs,
        specialization_differences=spec_diffs,
        winning_class_changed=op.class_id != sp.class_id,
        winning_specialization_changed=(op.class_id, op.specialization_id) != (sp.class_id, sp.specialization_id),
        question_influence=influence,
        overrides_applied=len(list(overrides)) + len(list(spec_overrides)),
    )


def _batch_side(c: Compiled, count: int, seed: int, length: str = "long") -> BatchSide:
    rng = random.Random(seed)
    active = active_questions(c, length)
    sizes = [(qi, len(c.questions[qi].answer_ids)) for qi in active]
    moderate = c.moderate_margin * margin_scale(c, active)
    nc = c.n_classes
    class_counts = [0] * nc
    class_sums = [0.0] * nc
    spec_counts = [[0] * len(cls.specs) for cls in c.classes]
    gap_sum = 0.0
    close = 0
    for _ in range(count):
        picks = [(qi, rng.randrange(n)) for qi, n in sizes]
        ct = _class_totals(c, picks)
        tt = _trait_totals(c, picks)
        ci, si, gap = _lean_primary(c, ct, tt, _spec_totals(c, picks))
        class_counts[ci] += 1
        spec_counts[ci][si] += 1
        for i in range(nc):
            class_sums[i] += ct[i]
        gap_sum += gap
        if _r(gap) < moderate:
            close += 1
    class_rows = [
        FrequencyRow(
            id=c.class_ids[i], name=c.classes[i].name, count=class_counts[i],
            frequency=class_counts[i] / count, mean_score=_o(class_sums[i] / count),
        )
        for i in range(nc)
    ]
    spec_rows = [
        FrequencyRow(
            id=s.id, name=s.name, class_id=cls.id, count=spec_counts[ci][j], frequency=spec_counts[ci][j] / count,
        )
        for ci, cls in enumerate(c.classes)
        for j, s in enumerate(cls.specs)
    ]
    return BatchSide(
        class_frequencies=class_rows,
        specialization_frequencies=spec_rows,
        mean_class_gap=_o(gap_sum / count),
        close_calls=close,
    )


def batch_simulate(
    config: Config, count: int, seed: Optional[int] = None, overrides=(), spec_overrides=(), length: str = "long"
) -> BatchSimulateResponse:
    """Score ``count`` uniformly random answer sets to expose systematic biases.

    When overrides are given, the same random answer sets are scored under both the
    saved and the overridden configuration.
    """
    seed = random.randrange(2**31) if seed is None else seed
    baseline = _batch_side(compile_config(config), count, seed, length)
    simulated = None
    if overrides or spec_overrides:
        simulated = _batch_side(compile_config(apply_overrides(config, overrides, spec_overrides)), count, seed, length)
    return BatchSimulateResponse(
        count=count,
        seed=seed,
        uniform_class_frequency=1 / len(config.classes),
        baseline=baseline,
        simulated=simulated,
    )


def expand_question(config: Config, question: Question) -> QuestionExpansion:
    """List every possible response to ``question`` with its raw weights and baseline-subtracted contributions.

    This is the single source of truth for how a question (including scale and pick-two types) turns into numbers;
    the administrative editor calls it to reuse the same arithmetic.
    """
    tmp = config.model_copy(update={"questions": [question.model_copy(update={"enabled": True})]})
    c = compile_config(tmp)
    q = c.questions[0]

    def sparse(ids, values, nonzero_only=True):
        return {i: _o(v) for i, v in zip(ids, values) if (v or not nonzero_only)}

    options = []
    for ai in range(len(q.answer_ids)):
        options.append(ExpandedOption(
            id=q.answer_ids[ai], label=q.answer_texts[ai],
            class_raw=sparse(c.class_ids, q.class_raw[ai]), trait_raw=sparse(c.trait_ids, q.trait_raw[ai]),
            spec_raw=sparse(c.spec_keys, q.spec_raw[ai]),
            class_adjusted=sparse(c.class_ids, q.class_delta[ai]), trait_adjusted=sparse(c.trait_ids, q.trait_delta[ai]),
            spec_adjusted=sparse(c.spec_keys, q.spec_delta[ai]),
        ))
    return QuestionExpansion(
        type=q.type, options=options,
        class_baseline=sparse(c.class_ids, q.class_base), trait_baseline=sparse(c.trait_ids, q.trait_base),
        spec_baseline=sparse(c.spec_keys, q.spec_base),
    )
