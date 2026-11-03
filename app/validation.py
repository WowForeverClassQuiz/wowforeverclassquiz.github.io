"""Semantic validation of a complete configuration.

Pydantic already guarantees field types and that every weight is finite and
non-negative. This module checks the cross-references and structural rules that a
schema cannot express. It returns a list of human-readable problems (empty = valid).
"""
from __future__ import annotations

import math
from collections import Counter

from .builds import validate_build
from .models import Config


def _dupes(ids) -> list[str]:
    return sorted(k for k, n in Counter(ids).items() if n > 1)


def validate_config(config: Config) -> list[str]:
    errors: list[str] = []

    # -- identifiers ----------------------------------------------------------
    for label, ids in (
        ("trait", [t.id for t in config.traits]),
        ("class", [c.id for c in config.classes]),
        ("question", [q.id for q in config.questions]),
        ("build", [b.id for b in config.builds]),
    ):
        for d in _dupes(ids):
            errors.append(f"Duplicate {label} id '{d}'.")
    class_ids = {c.id for c in config.classes}
    trait_ids = {t.id for t in config.traits}
    spec_keys: set[tuple[str, str]] = set()

    if len(config.classes) < 2:
        errors.append("At least two classes are required.")
    if not config.traits:
        errors.append("At least one trait is required.")

    # -- classes and specialization profiles ---------------------------------------
    for cls in config.classes:
        if not cls.specializations:
            errors.append(f"Class '{cls.id}' has no specializations.")
        for d in _dupes(s.id for s in cls.specializations):
            errors.append(f"Duplicate specialization id '{d}' in class '{cls.id}'.")
        for s in cls.specializations:
            spec_keys.add((cls.id, s.id))
            if not s.trait_multipliers:
                errors.append(f"Specialization '{cls.id}/{s.id}' has an empty trait profile.")
            for tid, m in s.trait_multipliers.items():
                if tid not in trait_ids:
                    errors.append(f"Specialization '{cls.id}/{s.id}' references unknown trait '{tid}'.")
                if not math.isfinite(m) or m < 0:
                    errors.append(f"Specialization '{cls.id}/{s.id}' has invalid multiplier for '{tid}'.")

    # -- scoring settings ------------------------------------------------------
    order = config.scoring.class_tie_break_order
    if sorted(order) != sorted(class_ids) or len(order) != len(class_ids):
        errors.append("scoring.class_tie_break_order must list every class id exactly once.")
    if not math.isfinite(config.scoring.spec_weight_multiplier) or config.scoring.spec_weight_multiplier < 0:
        errors.append("scoring.spec_weight_multiplier must be a finite, non-negative number.")
    margins = config.scoring.confidence_margins
    if margins.strong < margins.moderate:
        errors.append("confidence_margins.strong must be at least confidence_margins.moderate.")

    # -- questions ---------------------------------------------------------------
    spec_key_strs = {f"{cl.id}/{sp.id}" for cl in config.classes for sp in cl.specializations}
    enabled = [q for q in config.questions if q.enabled]
    if len(enabled) != config.quiz.expected_question_count:
        errors.append(
            f"The quiz requires exactly {config.quiz.expected_question_count} enabled questions; found {len(enabled)}."
        )
    for q in config.questions:
        n = len(q.answers)
        answer_ids = [a.id for a in q.answers]
        if q.type == "choice" and not 2 <= n <= 8:
            errors.append(f"Question '{q.id}' (choice) has {n} answers; between 2 and 8 are required.")
        elif q.type in ("pick_two", "ranking", "allocation") and n != 4:
            errors.append(f"Question '{q.id}' ({q.type}) has {n} answers; exactly 4 are required.")
        elif q.type == "scale":
            if sorted(answer_ids) != ["agree", "disagree"]:
                errors.append(f"Question '{q.id}' (scale) must have exactly the answers 'agree' and 'disagree'.")
            if not q.low_label.strip() or not q.high_label.strip():
                errors.append(f"Question '{q.id}' (scale) needs low and high labels.")
        for d in _dupes(answer_ids):
            errors.append(f"Duplicate answer id '{d}' in question '{q.id}'.")
        for a in q.answers:
            for kind, weights, known in (
                ("class", a.class_weights, class_ids),
                ("trait", a.trait_weights, trait_ids),
                ("specialization", a.spec_weights, spec_key_strs),
            ):
                for key, w in weights.items():
                    if key not in known:
                        errors.append(f"Answer '{q.id}/{a.id}' references unknown {kind} '{key}'.")
                    if not math.isfinite(w) or w < 0:
                        errors.append(f"Answer '{q.id}/{a.id}' has invalid {kind} weight for '{key}'.")

    # -- talent catalog ---------------------------------------------------------------
    cat = config.talent_catalog
    if cat is not None:
        for d in _dupes(c.id for c in cat.classes):
            errors.append(f"Talent catalog lists class '{d}' more than once.")
        for cc in cat.classes:
            cls = config.get_class(cc.id)
            if cls is None:
                errors.append(f"Talent catalog references unknown class '{cc.id}'.")
                continue
            spec_ids = {s.id for s in cls.specializations}
            seen: set[str] = set()
            all_ids = {t.id for tree in cc.trees for t in tree.talents}
            for tree in cc.trees:
                if tree.id not in spec_ids:
                    errors.append(f"Talent tree '{tree.id}' does not match a specialization of '{cc.id}'.")
                for t in tree.talents:
                    if t.id in seen:
                        errors.append(f"Duplicate talent id '{t.id}' in class '{cc.id}'.")
                    seen.add(t.id)
                    for req in t.requires:
                        if req.talent_id not in all_ids:
                            errors.append(f"Talent '{cc.id}/{t.id}' requires unknown talent '{req.talent_id}'.")
                        elif req.talent_id == t.id:
                            errors.append(f"Talent '{cc.id}/{t.id}' requires itself.")

    # -- builds --------------------------------------------------------------------------
    defaults = Counter()
    for b in config.builds:
        if (b.class_id, b.specialization_id) not in spec_keys:
            errors.append(f"Build '{b.id}' references unknown specialization '{b.class_id}/{b.specialization_id}'.")
            continue
        if b.is_default:
            defaults[(b.class_id, b.specialization_id)] += 1
        v = validate_build(b, config)
        if b.status == "verified" and not v.valid:
            errors.extend(f"Build '{b.id}': {e}" for e in v.errors)
    for key, n in defaults.items():
        if n > 1:
            errors.append(f"More than one default build for '{key[0]}/{key[1]}'.")
    return errors
