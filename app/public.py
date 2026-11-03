"""The participant-facing view of a configuration: what the quiz page and the result page may see.

Shared by the REST API (``main.py``) and the static-site exporter (``static_export.py``) so that both editions show
participants exactly the same questions and the same builds. Nothing here exposes scoring weights.
"""
from __future__ import annotations

from typing import Optional

from . import builds as builds_mod
from .models import (
    ALLOCATION_POINTS,
    LENGTHS,
    SCALE_MAX,
    SCALE_MIN,
    BuildDetail,
    Config,
    EvaluationResponse,
    PublicAnswer,
    PublicLength,
    PublicQuestion,
    PublicQuiz,
)


def public_question(q) -> PublicQuestion:
    """Participant view of a question. Scale questions expose only the statement and end labels, never the poles."""
    if q.type == "scale":
        return PublicQuestion(
            id=q.id, text=q.text, type="scale", low_label=q.low_label, high_label=q.high_label,
            scale_min=SCALE_MIN, scale_max=SCALE_MAX,
        )
    return PublicQuestion(
        id=q.id, text=q.text, type=q.type,
        answers=[PublicAnswer(id=a.id, text=a.text) for a in q.answers],
        pick_count=2 if q.type == "pick_two" else None,
        points=ALLOCATION_POINTS if q.type == "allocation" else None,
    )


#: How the lengths are presented to participants.
LENGTH_NAMES = {"short": "Short", "medium": "Medium", "long": "Long"}
LENGTH_BLURBS = {
    "short": "A quick reading from the most telling questions.",
    "medium": "A fuller reading, with more angles on your temperament.",
    "long": "The complete reading: every question, the most to go on.",
}
SECONDS_PER_QUESTION = 20


def public_lengths(cfg: Config) -> list[PublicLength]:
    """The quiz lengths on offer, shortest first. A length that asks the same questions as a longer one is left out."""
    qs = cfg.enabled_questions()
    found: list[tuple[str, list[str]]] = []
    for rank, length in enumerate(LENGTHS):
        ids = [q.id for q in qs if LENGTHS.index(q.min_length) <= rank]
        if not ids:
            continue
        if found and found[-1][1] == ids:
            found[-1] = (length, ids)          # same questions as the shorter one: keep the longer name
        else:
            found.append((length, ids))
    return [
        PublicLength(
            id=length, name=LENGTH_NAMES[length], description=LENGTH_BLURBS[length], question_count=len(ids),
            minutes=max(1, round(len(ids) * SECONDS_PER_QUESTION / 60)), question_ids=ids,
        )
        for length, ids in found
    ]


def public_quiz(cfg: Config) -> PublicQuiz:
    qs = cfg.enabled_questions()
    lengths = public_lengths(cfg)
    return PublicQuiz(
        quiz_id=cfg.quiz.id,
        title=cfg.quiz.title,
        subtitle=cfg.quiz.subtitle,
        question_count=len(qs),
        questions=[public_question(q) for q in qs],
        lengths=lengths,
        default_length="medium" if any(l.id == "medium" for l in lengths) else lengths[-1].id,
    )


def default_build_detail(cfg: Config, class_id: str, spec_id: str) -> Optional[BuildDetail]:
    """The default build of a specialization, ready to display (no validation report), or None when there is none."""
    b = builds_mod.default_build(cfg, class_id, spec_id)
    return builds_mod.describe_build(b, cfg, with_validation=False, with_trees=True) if b else None


def with_builds(cfg: Config, ev: EvaluationResponse) -> EvaluationResponse:
    """Attach the default build of each recommended specialization (display only)."""
    p = ev.result.primary_specialization
    p.build = default_build_detail(cfg, p.class_id, p.id)
    ev.result.build = p.build
    a = ev.alternatives.alternative_specialization
    a.build = default_build_detail(cfg, a.class_id, a.id)
    s = ev.alternatives.second_specialization_in_primary_class
    s.build = default_build_detail(cfg, s.class_id, s.id)
    return ev
