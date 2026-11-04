"""Confidence mode: a probabilistic reading of the answers, and the choice of the most informative next question.

The quiz's scores are sums of baseline-subtracted weights. This module turns the very same numbers into probabilities with a
*logit choice model*: a person whose type is (class c, specialization s) is assumed to pick response r to question q with
probability proportional to exp(utility), where the utility is the response's contribution to that type's scores::

    u_q(r | c, s) = lambda_c * Dclass_q(r, c) + lambda_s * ( sum_t m_{s,t} * Dtrait_q(r, t) + M * Dspec_q(r, s) )
    P(r | c, s, q) = exp(u_q(r | c, s)) / sum_r' exp(u_q(r' | c, s))

Because the questions are answered independently given the type, the posterior over the 27 types is Bayes' rule with a uniform
prior::

    P(c, s | answers) is proportional to  prod_q P(r_q | c, s, q)

Its logarithm is lambda_c * S_c + lambda_s * P_s - (a normalizer per question and type): the scoring's own class and
specialization scores, corrected for how peaked each type's preferences are. The confidence in a result is the posterior
probability of the specialization the scoring recommends, plus partial credit for the probability on other specializations of its
class and on others with a similar role (tank, healer, melee damage, ranged damage), so a person torn between the three specializations
of one class, or between Protection Paladin and Protection Warrior, is not told the Oracle is unsure of everything. The next question is
the unanswered one with the largest expected information gain (expected drop of the posterior's entropy). Everything is a pure
function of the configuration and the answers.
The "probabilities" are exact within the model; how well the model describes real people is an assumption (see the PDF).
"""
from __future__ import annotations

from math import exp, fsum, log, tanh
from typing import NamedTuple, Optional

from .models import AdaptiveSettings, AdaptiveStatus, TypeProbability
from .scoring import (
    Compiled,
    _class_totals,
    _lean_primary,
    _spec_totals,
    _trait_totals,
    resolve_answers,
)

LN_TYPES_PRECISION = 9      # gains are compared after rounding to this many decimals, so float noise never decides a question


class ConfidenceParts(NamedTuple):
    """The confidence in a recommendation and what it is made of (all probabilities from the same posterior)."""

    overall: float      # spec + class_credit * (the rest of the class) + role_credit * (similar-role specializations outside the class)
    spec: float         # the recommended specialization
    class_: float       # all of its class
    role: float         # every specialization with a role like its role (any class)


class Model:
    """Log-likelihood tables of the choice model for one compiled configuration."""

    def __init__(self, c: Compiled):
        self.c = c
        s = c.adaptive
        self.n_types = c.n_specs
        self.type_class = [0] * self.n_types
        self.type_roles: list[frozenset] = [frozenset()] * self.n_types      # a role like "melee_damage_or_tank" is two roles
        terms: list = [()] * self.n_types
        for ci, cls in enumerate(c.classes):
            for sp in cls.specs:
                self.type_class[sp.gidx] = ci
                self.type_roles[sp.gidx] = frozenset(sp.role.split("_or_"))
                terms[sp.gidx] = sp.terms
        self.logp: list[list[list[float]]] = []           # [question][response][type] = log P(response | type, question)
        for q in c.questions:
            rows = []
            for r in range(len(q.answer_ids)):
                u = []
                for g in range(self.n_types):
                    spec_part = fsum([m * q.trait_delta[r][t] for t, m in terms[g]]) + c.spec_multiplier * q.spec_delta[r][g]
                    u.append(s.sharpness_class * q.class_delta[r][self.type_class[g]] + s.sharpness_spec * spec_part)
                rows.append(u)
            for g in range(self.n_types):                 # log-softmax over the responses, per type
                top = max(rows[r][g] for r in range(len(rows)))
                lz = top + log(fsum(exp(rows[r][g] - top) for r in range(len(rows))))
                for r in range(len(rows)):
                    rows[r][g] -= lz
            self.logp.append(rows)

    def posterior(self, picks) -> list[float]:
        lp = [fsum([self.logp[qi][ri][g] for qi, ri in picks]) for g in range(self.n_types)]
        top = max(lp)
        w = [exp(x - top) for x in lp]
        total = fsum(w)
        return [x / total for x in w]

    def eligible(self, post, qi: int, tiebreak_mass: float) -> bool:
        """An ordinary question is always a candidate; a tiebreaker only when its finalists together hold at least ``tiebreak_mass``."""
        finalists = self.c.questions[qi].finalists
        return not finalists or fsum(post[g] for g in finalists) >= tiebreak_mass

    def decision(self, post, picks, s: AdaptiveSettings) -> Optional[tuple[int, int]]:
        """(specialization, question) when an answered tiebreaker settles the reading, else None.

        A tiebreaker is settled when at least ``tiebreak_min_questions`` questions have been answered, its finalists together still hold
        ``tiebreak_mass`` of the probability, and the scaled confidence in the specialization its answer names is within ``SOFT_BAND`` of the
        threshold. Of several such answers, the named specialization the model finds most probable wins. The result does not depend on the
        order of the answers.
        """
        n = len(picks)
        if s.tiebreak_min_questions <= 0 or n < max(s.tiebreak_min_questions, s.min_questions):
            return None
        named = []
        for qi, ai in picks:
            finalists = self.c.questions[qi].finalists
            if finalists and fsum(post[g] for g in finalists) >= s.tiebreak_mass:
                named.append((-round(post[finalists[ai]], LN_TYPES_PRECISION), finalists[ai], qi))
        if not named:
            return None
        _, g, qi = min(named)
        floor = max(s.confidence - SOFT_BAND, 0.0)
        reach = question_factor(n, s.question_scaling) * self.confidence_parts(post, g, s.class_credit, s.role_credit).overall
        return (g, qi) if reach >= floor else None

    def confidence_parts(self, post, rec: int, class_credit: float, role_credit: float) -> ConfidenceParts:
        """How sure the model is of ``rec``: its own probability, its class's, its role's, and the combined confidence.

        Every type earns credit toward the confidence: 1 for ``rec`` itself, ``class_credit`` for another specialization of its class,
        ``role_credit`` for one that shares a role with it, and the larger of the two when both apply. The confidence is the posterior's
        expected credit, so with both credits at 0 it is just the probability of ``rec``.
        """
        same_class = [self.type_class[g] == self.type_class[rec] for g in range(self.n_types)]
        same_role = [bool(self.type_roles[g] & self.type_roles[rec]) for g in range(self.n_types)]
        credit = [
            1.0 if g == rec else max(class_credit if same_class[g] else 0.0, role_credit if same_role[g] else 0.0)
            for g in range(self.n_types)
        ]
        return ConfidenceParts(
            overall=fsum(post[g] * credit[g] for g in range(self.n_types)),
            spec=post[rec],
            class_=fsum(post[g] for g in range(self.n_types) if same_class[g]),
            role=fsum(post[g] for g in range(self.n_types) if same_role[g]),
        )

    @staticmethod
    def entropy(p) -> float:
        return -fsum(x * log(x) for x in p if x > 0)

    def expected_gain(self, post, qi: int) -> float:
        """Expected drop of the posterior's entropy (in nats) from asking question ``qi`` next."""
        h0 = self.entropy(post)
        expected = 0.0
        for row in self.logp[qi]:
            joint = [post[g] * exp(row[g]) for g in range(self.n_types)]
            pr = fsum(joint)
            if pr > 0:
                expected += pr * self.entropy([x / pr for x in joint])
        return h0 - expected

    def effort(self, qi: int) -> float:
        """How much a question asks of the person, as a multiple of a single choice (rankings and six-point splits ask more)."""
        s = self.c.adaptive
        return {"ranking": s.effort_ranking, "allocation": s.effort_allocation}.get(self.c.questions[qi].type, 1.0)

    def best_question(self, post, remaining) -> tuple[Optional[int], float]:
        """The question with the most expected information per unit of effort, and its expected information gain."""
        best, best_score, best_gain = None, 0.0, 0.0
        for qi in remaining:
            gain = self.expected_gain(post, qi)
            score = gain / self.effort(qi)
            if best is None or round(score, LN_TYPES_PRECISION) > round(best_score, LN_TYPES_PRECISION):
                best, best_score, best_gain = qi, score, gain
        return best, best_gain


def recommended_type(c: Compiled, picks) -> int:
    """The global specialization index the scoring recommends for these answers (class first, then specialization)."""
    ci, si, _gap = _lean_primary(c, _class_totals(c, picks), _trait_totals(c, picks), _spec_totals(c, picks))
    return c.classes[ci].specs[si].gidx


def _type_probability(c: Compiled, g: int, p: float) -> TypeProbability:
    for cls in c.classes:
        for sp in cls.specs:
            if sp.gidx == g:
                return TypeProbability(class_id=cls.id, class_name=cls.name, specialization_id=sp.id, specialization_name=sp.name, probability=p)
    raise KeyError(g)


#: Until the Oracle is actually sure, the stated confidence stays at least this far below the threshold.
HEADROOM = 0.01
#: The top of the stated scale is compressed from this far below the threshold up, so the figure still rises as it nears it.
SOFT_BAND = 0.10


def compress(x: float, theta: float) -> float:
    """Squeeze the part of the scale above theta - SOFT_BAND into the band below theta - HEADROOM, smoothly, so it never reaches the threshold and never goes flat."""
    cap = max(theta - HEADROOM, 0.0)
    start = max(theta - SOFT_BAND, 0.0)
    if x <= start or cap <= start:
        return min(x, cap)
    width = cap - start
    return start + width * tanh((x - start) / width)


def question_factor(n: int, scaling: float) -> float:
    """What n questions earn of the confidence: n / (n + scaling). 0 before the first answer; 1 for every n when ``scaling`` is 0."""
    if n <= 0:
        return 0.0
    return n / (n + scaling) if scaling > 0 else 1.0


def confidence_trace(c: Compiled, model: Model, ordered_picks, s: AdaptiveSettings) -> list[float]:
    """The unscaled confidence after each answer, in the order the answers were given (the scoring itself never depends on that order)."""
    out = []
    for m in range(1, len(ordered_picks) + 1):
        prefix = sorted(ordered_picks[:m])
        out.append(model.confidence_parts(model.posterior(prefix), recommended_type(c, prefix), s.class_credit, s.role_credit).overall)
    return out


def stated_confidence(trace: list[float], s: AdaptiveSettings) -> tuple[float, float, float]:
    """(stated, current, factor) from the unscaled confidence after each answer.

    The current confidence is the latest one scaled by the number of questions asked; the stopping rule tests it. The stated confidence is
    the best one so far, scaled the same way, so it rises with every question. Above 80% (a tenth under the threshold) it is compressed
    smoothly toward a point under the threshold, which only the current confidence can reach, so the Oracle never states that it is
    sure while it is still asking and the figure never goes flat.
    """
    n = len(trace)
    if not n:
        return 0.0, 0.0, 0.0
    factor = question_factor(n, s.question_scaling)
    current = factor * trace[-1]
    if current >= s.confidence:
        return current, current, factor
    return compress(factor * max(trace), s.confidence), current, factor


def _role_of(c: Compiled, g: int) -> str:
    for cls in c.classes:
        for sp in cls.specs:
            if sp.gidx == g:
                return sp.role
    raise KeyError(g)


def decided_confidence(c: Compiled, model: Model, answers: dict[str, str], post, g: int, s: AdaptiveSettings) -> float:
    """What the Oracle states when a tiebreaker has named specialization ``g``: the meter's figure for these answers, or the current confidence if that is higher."""
    ordered = resolve_answers(c, answers, keep_order=True)
    overall = model.confidence_parts(post, g, s.class_credit, s.role_credit).overall
    stated, current, _ = stated_confidence(confidence_trace(c, model, ordered[:-1], s) + [overall], s)
    return max(stated, current)


def settled_by_tiebreaker(c: Compiled, picks, model: Optional[Model] = None, settings: Optional[AdaptiveSettings] = None) -> Optional[tuple[int, int]]:
    """(specialization, question) a tiebreaker has decided for these answers, or None: what ``status`` reports as ``reason == "decided"``.

    The scoring's own recommendation keeps its place when the Oracle is already confident of it.
    """
    s = settings or c.adaptive
    model = model or Model(c)
    n = len(picks)
    if not n:
        return None
    post = model.posterior(picks)
    parts = model.confidence_parts(post, recommended_type(c, picks), s.class_credit, s.role_credit)
    if n >= s.min_questions and question_factor(n, s.question_scaling) * parts.overall >= s.confidence:
        return None
    return model.decision(post, picks, s)


def model_probability(c: Compiled, picks, model: Optional[Model] = None) -> float:
    """Probability the model gives the recommended specialization given these answers."""
    model = model or Model(c)
    return model.posterior(picks)[recommended_type(c, picks)]


def status(c: Compiled, answers: dict[str, str], settings: Optional[AdaptiveSettings] = None, model: Optional[Model] = None) -> AdaptiveStatus:
    """How a confidence-mode quiz stands after ``answers`` (question id -> response id), and what to ask next."""
    s = settings or c.adaptive
    model = model or Model(c)
    picks = resolve_answers(c, answers)
    n = len(picks)
    post = model.posterior(picks)
    rec = recommended_type(c, picks) if picks else max(range(model.n_types), key=lambda g: (round(post[g], 9), -g))
    order = sorted(range(model.n_types), key=lambda g: (-round(post[g], 9), g))
    answered_q = {qi for qi, _ in picks}
    remaining = [qi for qi in range(len(c.questions)) if qi not in answered_q and model.eligible(post, qi, s.tiebreak_mass)]
    limit = min(s.max_questions, len(c.questions))
    parts = model.confidence_parts(post, rec, s.class_credit, s.role_credit)
    ordered = resolve_answers(c, answers, keep_order=True)
    earlier = confidence_trace(c, model, ordered[:-1], s) if n else []
    stated, current, factor = stated_confidence(earlier + [parts.overall] if n else [], s)
    decided = None if (n >= s.min_questions and current >= s.confidence) else model.decision(post, picks, s)
    if decided:                                 # a tiebreaker answer names the specialization; the scoring's own pick gives way
        rec = decided[0]
        parts = model.confidence_parts(post, rec, s.class_credit, s.role_credit)
        stated, current, factor = stated_confidence(earlier + [parts.overall], s)
        stated = max(stated, current)
    if n >= s.min_questions and current >= s.confidence:
        done, reason = True, "confident"
    elif decided:
        done, reason = True, "decided"
    elif n >= limit or not remaining:
        done, reason = True, "limit"
    else:
        done, reason = False, None
    nxt, gain = (None, None) if done else model.best_question(post, remaining)
    openers = [c.questions[qi].id for qi in remaining if c.questions[qi].opener] if (n == 0 and s.random_opening and not done) else []
    return AdaptiveStatus(
        answered=n, min_questions=s.min_questions, max_questions=limit, threshold=s.confidence, confidence=stated,
        current_confidence=current, question_factor=factor, spec_probability=parts.spec, class_probability=parts.class_, role_probability=parts.role, role=_role_of(c, rec),
        recommended=_type_probability(c, rec, parts.spec),
        top=[_type_probability(c, g, post[g]) for g in order[:5]],
        entropy=model.entropy(post), done=done, reason=reason, can_reveal=n >= s.min_questions,
        next_question_id=c.questions[nxt].id if nxt is not None else None, expected_gain=gain, openers=openers,
    )
