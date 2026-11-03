"""Everything the static (server-less) edition needs, exported from a ``Config`` as plain JSON-able data.

The static site has no API. Its browser code (``static/engine.js``) scores answers itself from the compiled tables
exported here, so the numbers a visitor sees are the numbers the Python engine would produce (``tests/test_static_parity.py``
checks this against the live API).

Raw weights and per-question baselines are exported rather than the baseline-subtracted deltas: the browser subtracts them
with the same IEEE arithmetic Python used, which keeps the two engines bit-for-bit identical.

Privacy note: unlike the API, this data *does* contain every scoring weight, because the browser needs them to score.
"""
from __future__ import annotations

from .models import Config
from .public import default_build_detail, public_quiz
from .scoring import compile_config

FORMAT = 1


def export_static_data(cfg: Config) -> dict:
    c = compile_config(cfg)
    classes = []
    for ci, cls in enumerate(c.classes):
        classes.append({
            "id": cls.id,
            "name": cls.name,
            "description": cls.description,
            "overview": cls.overview,
            "overview_url": cls.overview_url,
            "tie_rank": c.tie_rank[ci],
            "specs": [
                {
                    "id": s.id,
                    "name": s.name,
                    "role": s.role,
                    "description": s.description,
                    "overview": s.overview,
                    "guide": s.guide,
                    "gidx": s.gidx,
                    "terms": [[t, m] for t, m in s.terms],
                }
                for s in cls.specs
            ],
        })
    questions = [
        {
            "id": q.id,
            "type": q.type,
            "item_ids": list(q.item_ids),
            "answer_ids": list(q.answer_ids),
            "class_raw": [list(r) for r in q.class_raw],
            "trait_raw": [list(r) for r in q.trait_raw],
            "spec_raw": [list(r) for r in q.spec_raw],
            "class_base": list(q.class_base),
            "trait_base": list(q.trait_base),
            "spec_base": list(q.spec_base),
        }
        for q in c.questions
    ]
    builds = {}
    for cls in cfg.classes:
        for s in cls.specializations:
            detail = default_build_detail(cfg, cls.id, s.id)
            if detail is not None:
                builds[f"{cls.id}/{s.id}"] = detail.model_dump(mode="json", exclude_none=True)
    return {
        "format": FORMAT,
        "quiz": public_quiz(cfg).model_dump(mode="json"),
        "engine": {
            "revision": c.revision,
            "algorithm_version": c.algorithm_version,
            "strong_margin": c.strong_margin,
            "moderate_margin": c.moderate_margin,
            "spec_multiplier": c.spec_multiplier,
            "traits": [{"id": i, "name": n, "reading": r} for i, n, r in zip(c.trait_ids, c.trait_names, c.trait_readings)],
            "classes": classes,
            "active_specs": list(c.active_specs),
            "questions": questions,
        },
        "builds": builds,
    }
