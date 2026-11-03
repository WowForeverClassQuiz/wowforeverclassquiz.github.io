"""The draft Forever talent data that ships with the application: a talent catalog and one build per specialization.

Neither was read from the game client, so the catalog is flagged ``data_status: "draft"`` and every build ``draft``;
the validator refuses to mark a build verified against draft data. They ship so every result can show a best-guess build
(clearly labelled) instead of "allocation pending". See catalog/RECONCILIATION.md for where the data came from.
"""
from __future__ import annotations

import json
from pathlib import Path

from .models import Build, Config, TalentCatalog

CATALOG_DIR = Path(__file__).resolve().parent.parent / "catalog"
CATALOG_FILE = CATALOG_DIR / "forever-talents-draft-2026-11-03.json"
BUILDS_FILE = CATALOG_DIR / "forever-builds-draft-2026-11-03.json"


def load_drafts() -> tuple[TalentCatalog, list[Build]]:
    catalog = TalentCatalog.model_validate(json.loads(CATALOG_FILE.read_text(encoding="utf-8")))
    builds = [Build.model_validate(b) for b in json.loads(BUILDS_FILE.read_text(encoding="utf-8"))]
    return catalog, builds


def apply_drafts(cfg: Config) -> Config:
    """Set the draft catalog and replace each specialization's placeholder build with its draft build (in place)."""
    catalog, builds = load_drafts()
    replaced = {b.id for b in builds}
    cfg.talent_catalog = catalog
    cfg.builds = [b for b in cfg.builds if b.id not in replaced] + builds
    return cfg
