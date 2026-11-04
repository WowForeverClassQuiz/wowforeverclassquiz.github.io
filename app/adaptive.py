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
probability of the specialization the scoring recommends. The next question is the unanswered one with the largest expected
information gain (expected drop of the posterior's entropy). Everything is a pure function of the configuration and the answers.
The "probabilities" are exact within the model; how well the model describes real people is an assumption (see the PDF).
"""
from __future__ import annotations

from math import exp, fsum, log
from typing import Optional

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


class Model:
    """Log-likelihood tables of the choice model for one compiled configuration."""

    def __init__(self, c: Compiled):
        self.c = c
        s = c.adaptive
        self.n_types = c.n_specs
        self.type_class = [0] * self.n_types
        terms: list = [()] * self.n_types
        for ci, cls in enumerate(c.classes):
            for sp in cls.specs:
                self.type_class[sp.gidx] = ci
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

    def best_question(self, post, remaining) -> tuple[Optional[int], float]:
        best, best_gain = None, 0.0
        for qi in remaining:
            gain = self.expected_gain(post, qi)
            if best is None or round(gain, LN_TYPES_PRECISION) > round(best_gain, LN_TYPES_PRECISION):
                best, best_gain = qi, gain
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
    remaining = [qi for qi in range(len(c.questions)) if qi not in answered_q]
    limit = min(s.max_questions, len(c.questions))
    confidence = post[rec]
    if n >= s.min_questions and confidence >= s.confidence:
        done, reason = True, "confident"
    elif n >= limit or not remaining:
        done, reason = True, "limit"
    else:
        done, reason = False, None
    nxt, gain = (None, None) if done else model.best_question(post, remaining)
    return AdaptiveStatus(
        answered=n, min_questions=s.min_questions, max_questions=limit, threshold=s.confidence, confidence=confidence,
        recommended=_type_probability(c, rec, confidence),
        top=[_type_probability(c, g, post[g]) for g in order[:5]],
        entropy=model.entropy(post), done=done, reason=reason, can_reveal=n >= s.min_questions,
        next_question_id=c.questions[nxt].id if nxt is not None else None, expected_gain=gain,
    )
