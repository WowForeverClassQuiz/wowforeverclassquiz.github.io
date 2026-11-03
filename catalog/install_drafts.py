"""Install the DRAFT Forever talent catalog and the 27 draft builds into the application database.

    python catalog/install_drafts.py                 # uses $ORACLE_DB or data/oracle.db (created if missing)
    python catalog/install_drafts.py --db other.db

One new configuration revision is written (a backup file of the previous configuration is saved first).
Existing builds with the same ids are replaced; any other builds are kept. A talent catalog that is NOT
marked draft is never overwritten unless --force is given. Nothing installed here is verified.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from app.models import Build, TalentCatalog  # noqa: E402
from app.repository import ConfigInvalid, Repository  # noqa: E402

DEFAULT_DB = HERE.parent / "data" / "oracle.db"   # same default as app.main (not imported: importing it would create the database)
CATALOG = HERE / "forever-talents-draft-2026-11-03.json"
BUILDS = HERE / "forever-builds-draft-2026-11-03.json"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", help="database file (default: $ORACLE_DB or data/oracle.db)")
    ap.add_argument("--force", action="store_true", help="replace an existing talent catalog even if it is not a draft")
    args = ap.parse_args(argv)

    path = Path(args.db or os.environ.get("ORACLE_DB") or DEFAULT_DB)
    repo = Repository(path)
    repo.initialize()
    cfg = repo.get_config().model_copy(deep=True)

    if cfg.talent_catalog is not None and cfg.talent_catalog.data_status != "draft" and not args.force:
        print(f"Refusing to replace the existing non-draft talent catalog ({cfg.talent_catalog.client_version}). Use --force to override.", file=sys.stderr)
        return 2

    cfg.talent_catalog = TalentCatalog.model_validate(json.loads(CATALOG.read_text(encoding="utf-8")))
    new = [Build.model_validate(b) for b in json.loads(BUILDS.read_text(encoding="utf-8"))]
    replaced_ids = {b.id for b in new}
    kept = [b for b in cfg.builds if b.id not in replaced_ids]
    foreign_defaults = {(b.class_id, b.specialization_id) for b in kept if b.is_default}
    for b in new:
        if (b.class_id, b.specialization_id) in foreign_defaults:
            b.is_default = False        # do not take over a default the administrator chose
    cfg.builds = kept + new

    try:
        done = repo.import_config(cfg.revision, cfg, "Installed draft Forever talent catalog and 27 draft builds (unverified)")
    except ConfigInvalid as exc:
        print("The draft data did not validate against the current configuration:", file=sys.stderr)
        for e in exc.errors[:10]:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"Installed {len(new)} draft builds and the draft talent catalog into {path} (revision {done.config.revision}).")
    print(f"Previous configuration backed up to {done.backup_path}")
    print("All builds are marked draft; none is verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
