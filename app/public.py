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
    TIERS,
    SCALE_MAX,
    SCALE_MIN,
    BuildDetail,
    ClassesResponse,
    ClassListing,
    Config,
    EvaluationResponse,
    PublicAnswer,
    PublicLength,
    PublicQuestion,
    PublicQuiz,
    SpecListing,
    SpecPage,
    SpecTraitInfo,
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
        ids = [q.id for q in qs if TIERS.index(q.min_length) <= rank]
        if not ids:
            continue
        if found and found[-1][1] == ids:
            found[-1] = (length, ids)          # same questions as the shorter one: keep the longer name
        else:
            found.append((length, ids))
    lengths = [
        PublicLength(
            id=length, name=LENGTH_NAMES[length], description=LENGTH_BLURBS[length], question_count=len(ids),
            minutes=max(1, round(len(ids) * SECONDS_PER_QUESTION / 60)), question_ids=ids,
        )
        for length, ids in found
    ]
    ad = cfg.scoring.adaptive
    if ad.enabled and len(qs) >= ad.min_questions:
        top = min(ad.max_questions, len(qs))
        minutes = lambda n: max(1, round(n * SECONDS_PER_QUESTION / 60))
        lengths.insert(0, PublicLength(
            id="adaptive", name="Confidence", adaptive=True, question_count=top, question_ids=[q.id for q in qs],
            minutes=minutes(ad.min_questions), minutes_max=minutes(top), min_questions=ad.min_questions, max_questions=top, confidence=ad.confidence,
            description=f"Adaptive: the Oracle picks each question to learn the most and stops once it is {round(ad.confidence * 100)}% sure of your specialization "
                        + (f"(at least {ad.min_questions} questions)." if ad.min_questions > 1 else f"(never more than {top} questions)."),
        ))
    return lengths


def public_quiz(cfg: Config) -> PublicQuiz:
    qs = cfg.enabled_questions()
    lengths = public_lengths(cfg)
    return PublicQuiz(
        quiz_id=cfg.quiz.id,
        title=cfg.quiz.title,
        subtitle=cfg.quiz.subtitle,
        question_count=sum(1 for q in qs if q.min_length != "adaptive"),
        questions=[public_question(q) for q in qs],
        lengths=lengths,
        share_template=cfg.quiz.share_template,
        default_length="adaptive" if any(l.id == "adaptive" for l in lengths) else "medium" if any(l.id == "medium" for l in lengths) else lengths[-1].id,
    )


def public_classes(cfg: Config, include_scores: bool = False, include_builds: bool = True) -> ClassesResponse:
    """Classes with their specializations and roles (the participant listing)."""
    return ClassesResponse(
        classes=[
            ClassListing(
                id=c.id,
                name=c.name,
                description=c.description,
                overview=c.overview,
                overview_url=c.overview_url,
                specializations=[
                    SpecListing(
                        id=s.id,
                        name=s.name,
                        role=s.role,
                        description=s.description,
                        trait_multipliers=dict(s.trait_multipliers) if include_scores else None,
                        builds=[builds_mod.summarize_build(b) for b in builds_mod.builds_for(cfg, c.id, s.id)] if include_builds else None,
                    )
                    for s in c.specializations
                ],
            )
            for c in cfg.classes
        ]
    )


def spec_page(cfg: Config, class_id: str, spec_id: str, include_build: bool = True) -> Optional[SpecPage]:
    """The page of one specialization, or None when there is no such class or specialization."""
    cls, spec = cfg.get_class(class_id), cfg.get_spec(class_id, spec_id)
    if cls is None or spec is None:
        return None
    traits = {t.id: t for t in cfg.traits}
    guide = spec.guide if any(spec.guide.model_dump().values()) else None
    return SpecPage(
        class_id=cls.id, class_name=cls.name, class_description=cls.description, class_overview=cls.overview, overview_url=cls.overview_url,
        id=spec.id, name=spec.name, role=spec.role, description=spec.description, overview=spec.overview, guide=guide,
        traits=[
            SpecTraitInfo(id=tid, name=traits[tid].name, description=traits[tid].description, interpretation=traits[tid].interpretation,
                          multiplier=m, order=i)
            for i, (tid, m) in enumerate(spec.trait_multipliers.items(), start=1) if tid in traits
        ],
        build=default_build_detail(cfg, class_id, spec_id) if include_build else None,
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
