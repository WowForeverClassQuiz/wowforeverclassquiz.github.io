"""Configuration repository: reads and writes the normalized SQLite tables.

Every change goes through ``Repository._commit`` which, in one transaction:

1. checks the caller's expected revision (optimistic concurrency),
2. loads the current configuration and lets a callback modify it,
3. re-validates the whole configuration (schema and cross-references),
4. rewrites the configuration tables, increments the revision, and
5. appends a snapshot and change record to ``config_revisions``.

If anything fails, nothing is written.
"""
from __future__ import annotations

import json
import threading
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Optional, Union

from pydantic import ValidationError

from .builds import validate_build
from .database import CONFIG_TABLES, connect, init_schema, transaction
from .models import (
    AnswerPatch,
    Build,
    BuildPatch,
    ClassPatch,
    Config,
    QuestionPatch,
    QuizPatch,
    ScoringPatch,
    SpecPatch,
    TalentCatalog,
    TraitPatch,
)
from .seed import build_default_config
from .validation import validate_config


class RepositoryError(Exception):
    """Base class for expected, reportable failures."""


class NotFoundError(RepositoryError):
    def __init__(self, kind: str, ident: str):
        self.kind, self.ident = kind, ident
        super().__init__(f"Unknown {kind} '{ident}'.")


class RevisionConflict(RepositoryError):
    def __init__(self, expected: int, current: int):
        self.expected, self.current = expected, current
        super().__init__(
            f"Configuration is at revision {current}, but the request expected revision {expected}. "
            "Reload the configuration and reapply the change."
        )


class ConfigInvalid(RepositoryError):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors[:5]) + (f" (+{len(errors) - 5} more)" if len(errors) > 5 else ""))


@dataclass
class Committed:
    config: Config
    description: str
    backup_path: Optional[str] = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False)


# --------------------------------------------------------------------------
# Table <-> Config mapping
# --------------------------------------------------------------------------


def _current_revision(conn) -> int:
    row = conn.execute("SELECT MAX(revision) AS r FROM config_revisions").fetchone()
    return row["r"] or 0


def _read_config(conn) -> Config:
    meta = {r["key"]: json.loads(r["value"]) for r in conn.execute("SELECT key, value FROM meta")}
    traits = [
        dict(r)
        for r in conn.execute("SELECT id, name, description, interpretation FROM traits ORDER BY display_order")
    ]

    profiles: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    for r in conn.execute(
        "SELECT class_id, specialization_id, trait_id, weight FROM specialization_trait_weights "
        "ORDER BY class_id, specialization_id, position"
    ):
        profiles[(r["class_id"], r["specialization_id"])][r["trait_id"]] = r["weight"]
    specs: dict[str, list[dict]] = defaultdict(list)
    for r in conn.execute(
        "SELECT class_id, id, name, description, role, overview, guide FROM specializations ORDER BY class_id, display_order"
    ):
        specs[r["class_id"]].append(
            {
                "id": r["id"], "name": r["name"], "description": r["description"], "role": r["role"],
                "overview": r["overview"],
                "guide": json.loads(r["guide"]) if r["guide"] else {},
                "trait_multipliers": profiles[(r["class_id"], r["id"])],
            }
        )
    classes = [
        {"id": r["id"], "name": r["name"], "description": r["description"], "overview": r["overview"],
         "overview_url": r["overview_url"], "specializations": specs[r["id"]]}
        for r in conn.execute("SELECT id, name, description, overview, overview_url FROM classes ORDER BY display_order")
    ]

    spec_w: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    for r in conn.execute("SELECT question_id, answer_id, spec_key, weight FROM answer_spec_weights ORDER BY rowid"):
        spec_w[(r["question_id"], r["answer_id"])][r["spec_key"]] = r["weight"]
    class_w: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    for r in conn.execute("SELECT question_id, answer_id, class_id, weight FROM answer_class_weights ORDER BY rowid"):
        class_w[(r["question_id"], r["answer_id"])][r["class_id"]] = r["weight"]
    trait_w: dict[tuple[str, str], dict[str, float]] = defaultdict(dict)
    for r in conn.execute("SELECT question_id, answer_id, trait_id, weight FROM answer_trait_weights ORDER BY rowid"):
        trait_w[(r["question_id"], r["answer_id"])][r["trait_id"]] = r["weight"]
    answers: dict[str, list[dict]] = defaultdict(list)
    for r in conn.execute("SELECT question_id, id, text FROM answers ORDER BY question_id, display_order"):
        key = (r["question_id"], r["id"])
        answers[r["question_id"]].append(
            {"id": r["id"], "text": r["text"], "class_weights": class_w[key], "trait_weights": trait_w[key],
             "spec_weights": spec_w[key]}
        )
    questions = [
        {"id": r["id"], "text": r["text"], "enabled": bool(r["enabled"]), "type": r["type"],
         "low_label": r["low_label"], "high_label": r["high_label"], "rationale": r["rationale"],
         "min_length": r["min_length"], "finalists": json.loads(r["finalists"] or "[]"), "answers": answers[r["id"]]}
        for r in conn.execute(
            "SELECT id, text, enabled, type, low_label, high_label, rationale, min_length, finalists FROM questions ORDER BY display_order"
        )
    ]

    allocations: dict[str, dict[str, int]] = defaultdict(dict)
    for r in conn.execute("SELECT build_id, talent_id, rank FROM build_talent_allocations ORDER BY rowid"):
        allocations[r["build_id"]][r["talent_id"]] = r["rank"]
    builds = [
        {
            "id": r["id"], "class_id": r["class_id"], "specialization_id": r["specialization_id"],
            "name": r["name"], "role": r["role"], "purpose": r["purpose"], "level": r["level"],
            "total_points": r["total_points"], "allocations": allocations[r["id"]],
            "leveling_order": json.loads(r["leveling_order"]),
            "combat_priorities": json.loads(r["combat_priorities"]),
            "equipment_notes": json.loads(r["equipment_notes"]),
            "professions": json.loads(r["professions"]),
            "source": r["source"], "source_url": r["source_url"], "calculator_url": r["calculator_url"],
            "verified_at": r["verified_at"], "client_version": r["client_version"],
            "status": r["status"], "is_default": bool(r["is_default"]), "notes": r["notes"],
        }
        for r in conn.execute("SELECT * FROM builds ORDER BY display_order, rowid")
    ]
    cat_row = conn.execute("SELECT data FROM talent_catalog WHERE id = 1").fetchone()

    return Config.model_validate(
        {
            "revision": _current_revision(conn),
            "quiz": meta["quiz"],
            "scoring": meta["scoring"],
            "traits": traits,
            "classes": classes,
            "questions": questions,
            "builds": builds,
            "talent_catalog": json.loads(cat_row["data"]) if cat_row else None,
        }
    )


def _write_config(conn, cfg: Config) -> None:
    """Replace the live configuration tables with ``cfg`` (inside a transaction)."""
    for table in CONFIG_TABLES:
        conn.execute(f"DELETE FROM {table}")
    conn.execute("INSERT INTO meta VALUES ('quiz', ?)", (_json(cfg.quiz.model_dump(mode="json")),))
    conn.execute("INSERT INTO meta VALUES ('scoring', ?)", (_json(cfg.scoring.model_dump(mode="json")),))
    conn.executemany(
        "INSERT INTO traits VALUES (?,?,?,?,?)",
        [(t.id, t.name, t.description, t.interpretation, i) for i, t in enumerate(cfg.traits)],
    )
    for ci, cls in enumerate(cfg.classes):
        conn.execute(
            "INSERT INTO classes (id, name, description, display_order, overview, overview_url) VALUES (?,?,?,?,?,?)",
            (cls.id, cls.name, cls.description, ci, cls.overview, cls.overview_url),
        )
        for si, s in enumerate(cls.specializations):
            conn.execute(
                "INSERT INTO specializations (class_id, id, name, description, role, display_order, overview, guide) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (cls.id, s.id, s.name, s.description, s.role, si, s.overview, s.guide.model_dump_json()),
            )
            conn.executemany(
                "INSERT INTO specialization_trait_weights VALUES (?,?,?,?,?)",
                [(cls.id, s.id, t, w, pos) for pos, (t, w) in enumerate(s.trait_multipliers.items())],
            )
    for qi, q in enumerate(cfg.questions):
        conn.execute(
            "INSERT INTO questions (id, text, display_order, enabled, type, low_label, high_label, rationale, min_length, finalists) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (q.id, q.text, qi, int(q.enabled), q.type, q.low_label, q.high_label, q.rationale, q.min_length, json.dumps(q.finalists)),
        )
        for ai, a in enumerate(q.answers):
            conn.execute("INSERT INTO answers VALUES (?,?,?,?)", (q.id, a.id, a.text, ai))
            conn.executemany(
                "INSERT INTO answer_class_weights VALUES (?,?,?,?)",
                [(q.id, a.id, k, w) for k, w in a.class_weights.items() if w],
            )
            conn.executemany(
                "INSERT INTO answer_trait_weights VALUES (?,?,?,?)",
                [(q.id, a.id, k, w) for k, w in a.trait_weights.items() if w],
            )
            conn.executemany(
                "INSERT INTO answer_spec_weights VALUES (?,?,?,?)",
                [(q.id, a.id, k, w) for k, w in a.spec_weights.items() if w],
            )
    for bi, b in enumerate(cfg.builds):
        conn.execute(
            "INSERT INTO builds (id, class_id, specialization_id, name, role, purpose, level, total_points, "
            "source, source_url, calculator_url, verified_at, client_version, status, is_default, notes, "
            "leveling_order, combat_priorities, equipment_notes, professions, display_order) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                b.id, b.class_id, b.specialization_id, b.name, b.role, b.purpose, b.level, b.total_points,
                b.source, b.source_url, b.calculator_url,
                b.verified_at.isoformat() if b.verified_at else None,
                b.client_version, b.status, int(b.is_default), b.notes,
                _json(b.leveling_order), _json(b.combat_priorities), _json(b.equipment_notes),
                _json(b.professions), bi,
            ),
        )
        conn.executemany(
            "INSERT INTO build_talent_allocations VALUES (?,?,?)",
            [(b.id, t, r) for t, r in b.allocations.items()],
        )
    if cfg.talent_catalog is not None:
        conn.execute("INSERT INTO talent_catalog VALUES (1, ?)", (_json(cfg.talent_catalog.model_dump(mode="json")),))


def _insert_revision(conn, cfg: Config, change_type: str, description: str, detail: Optional[dict]) -> None:
    conn.execute(
        "INSERT INTO config_revisions VALUES (?,?,?,?,?,?)",
        (
            cfg.revision, _now(), change_type, description,
            _json(detail) if detail is not None else None,
            cfg.model_dump_json(),
        ),
    )


# --------------------------------------------------------------------------
# Repository
# --------------------------------------------------------------------------


class Repository:
    def __init__(self, db_path: Union[str, Path], backup_dir: Union[str, Path, None] = None):
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir) if backup_dir else self.db_path.parent / "backups"
        self._lock = threading.Lock()
        self._cache: Optional[tuple[int, Config]] = None

    # -- lifecycle -------------------------------------------------------------
    def initialize(self) -> None:
        """Create the schema and seed the original configuration on first launch."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = connect(self.db_path)
        try:
            init_schema(conn)
            with transaction(conn):
                revision = _current_revision(conn)
                if revision == 0:
                    seed = build_default_config()
                    _write_config(conn, seed)
                    _insert_revision(conn, seed, "seed", "Initial seed configuration", None)
                elif revision == 1:
                    # A database that still holds the untouched seed of an older release is brought up to date.
                    # Anything edited (revision > 1) is never touched; use Reset or Import to adopt a newer seed.
                    row = conn.execute("SELECT change_type, snapshot FROM config_revisions WHERE revision = 1").fetchone()
                    seed = build_default_config()
                    if row["change_type"] == "seed" and Config.model_validate_json(row["snapshot"]).model_dump() != seed.model_dump():
                        _write_config(conn, seed)
                        conn.execute(
                            "UPDATE config_revisions SET snapshot = ?, change_description = ? WHERE revision = 1",
                            (seed.model_dump_json(), "Initial seed configuration (upgraded: the stored seed was unedited and older)"),
                        )
        finally:
            conn.close()

    # -- reads -----------------------------------------------------------------
    def revision(self) -> int:
        conn = connect(self.db_path)
        try:
            return _current_revision(conn)
        finally:
            conn.close()

    def get_config(self) -> Config:
        """Current configuration. Treat the result as read-only; it may be shared."""
        conn = connect(self.db_path)
        try:
            rev = _current_revision(conn)
            cached = self._cache
            if cached and cached[0] == rev:
                return cached[1]
            cfg = _read_config(conn)
        finally:
            conn.close()
        self._cache = (cfg.revision, cfg)
        return cfg

    def history(self, limit: int = 50, offset: int = 0) -> list[dict]:
        conn = connect(self.db_path)
        try:
            rows = conn.execute(
                "SELECT revision, created_at, change_type, change_description, change_detail "
                "FROM config_revisions ORDER BY revision DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        finally:
            conn.close()
        return [
            {
                "revision": r["revision"], "created_at": r["created_at"], "change_type": r["change_type"],
                "change_description": r["change_description"],
                "change_detail": json.loads(r["change_detail"]) if r["change_detail"] else None,
            }
            for r in rows
        ]

    def snapshot(self, revision: int) -> Config:
        conn = connect(self.db_path)
        try:
            row = conn.execute("SELECT snapshot FROM config_revisions WHERE revision = ?", (revision,)).fetchone()
        finally:
            conn.close()
        if row is None:
            raise NotFoundError("revision", str(revision))
        return Config.model_validate_json(row["snapshot"])

    # -- the single write path ----------------------------------------------------
    def write_backup(self, cfg: Config, tag: str) -> str:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = self.backup_dir / f"config-r{cfg.revision}-{tag}-{stamp}.json"
        path.write_text(cfg.model_dump_json(indent=2), encoding="utf-8")
        return str(path)

    def _commit(
        self,
        expected_revision: int,
        change_type: str,
        description: str,
        fn: Callable[[Config], tuple[Config, Optional[dict]]],
        backup_tag: Optional[str] = None,
    ) -> Committed:
        with self._lock:
            conn = connect(self.db_path)
            try:
                with transaction(conn):
                    current = _current_revision(conn)
                    if current != expected_revision:
                        raise RevisionConflict(expected_revision, current)
                    before = _read_config(conn)
                    backup_path = self.write_backup(before, backup_tag) if backup_tag else None
                    new_cfg, detail = fn(before.model_copy(deep=True))
                    new_cfg.revision = current + 1
                    try:  # re-validate the whole schema, including values assigned by `fn`
                        new_cfg = Config.model_validate(new_cfg.model_dump())
                    except ValidationError as exc:
                        raise ConfigInvalid(
                            [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
                        ) from exc
                    errors = validate_config(new_cfg)
                    if errors:
                        raise ConfigInvalid(errors)
                    _write_config(conn, new_cfg)
                    _insert_revision(conn, new_cfg, change_type, description, detail)
            finally:
                conn.close()
        self._cache = (new_cfg.revision, new_cfg)
        return Committed(new_cfg, description, backup_path)

    # -- quiz content ------------------------------------------------------------------
    def update_answer(self, qid: str, aid: str, patch: AnswerPatch) -> Committed:
        def fn(cfg: Config):
            q = cfg.get_question(qid)
            if q is None:
                raise NotFoundError("question", qid)
            a = next((x for x in q.answers if x.id == aid), None)
            if a is None:
                raise NotFoundError("answer", f"{qid}/{aid}")
            before = a.model_dump(mode="json")
            classes, traits = {c.id for c in cfg.classes}, {t.id for t in cfg.traits}
            if patch.class_weights is not None:
                bad = sorted(set(patch.class_weights) - classes)
                if bad:
                    raise ConfigInvalid([f"Unknown class id(s): {', '.join(bad)}."])
                a.class_weights = {k: v for k, v in patch.class_weights.items() if v}
            if patch.trait_weights is not None:
                bad = sorted(set(patch.trait_weights) - traits)
                if bad:
                    raise ConfigInvalid([f"Unknown trait id(s): {', '.join(bad)}."])
                a.trait_weights = {k: v for k, v in patch.trait_weights.items() if v}
            if patch.spec_weights is not None:
                known = {f"{cl.id}/{sp.id}" for cl in cfg.classes for sp in cl.specializations}
                bad = sorted(set(patch.spec_weights) - known)
                if bad:
                    raise ConfigInvalid([f"Unknown specialization key(s): {', '.join(bad)}."])
                a.spec_weights = {k: v for k, v in patch.spec_weights.items() if v}
            if patch.text is not None:
                a.text = patch.text
            return cfg, {"target": f"{qid}/{aid}", "before": before, "after": a.model_dump(mode="json")}

        return self._commit(patch.expected_revision, "answer", f"Edited answer {qid}/{aid}", fn)

    def update_question(self, qid: str, patch: QuestionPatch) -> Committed:
        def fn(cfg: Config):
            q = cfg.get_question(qid)
            if q is None:
                raise NotFoundError("question", qid)
            fields = ("text", "enabled", "low_label", "high_label", "rationale", "min_length", "finalists")
            before = {f: getattr(q, f) for f in fields}
            for f in fields:
                value = getattr(patch, f)
                if value is not None:
                    setattr(q, f, value)
            return cfg, {"target": qid, "before": before, "after": {f: getattr(q, f) for f in fields}}

        return self._commit(patch.expected_revision, "question", f"Edited question {qid}", fn)

    def update_spec(self, class_id: str, spec_id: str, patch: SpecPatch) -> Committed:
        def fn(cfg: Config):
            s = cfg.get_spec(class_id, spec_id)
            if s is None:
                raise NotFoundError("specialization", f"{class_id}/{spec_id}")
            before = s.model_dump(mode="json")
            if patch.trait_multipliers is not None:
                bad = sorted(set(patch.trait_multipliers) - {t.id for t in cfg.traits})
                if bad:
                    raise ConfigInvalid([f"Unknown trait id(s): {', '.join(bad)}."])
                s.trait_multipliers = dict(patch.trait_multipliers)
            for field in ("name", "description", "role", "overview"):
                value = getattr(patch, field)
                if value is not None:
                    setattr(s, field, value)
            if patch.guide is not None:
                s.guide = patch.guide
            return cfg, {"target": f"{class_id}/{spec_id}", "before": before, "after": s.model_dump(mode="json")}

        return self._commit(patch.expected_revision, "specialization", f"Edited specialization {class_id}/{spec_id}", fn)

    def update_class(self, class_id: str, patch: ClassPatch) -> Committed:
        def fn(cfg: Config):
            c = cfg.get_class(class_id)
            if c is None:
                raise NotFoundError("class", class_id)
            fields = ("name", "description", "overview")
            before = {f: getattr(c, f) for f in fields}
            for f in fields:
                value = getattr(patch, f)
                if value is not None:
                    setattr(c, f, value)
            return cfg, {"target": class_id, "before": before, "after": {f: getattr(c, f) for f in fields}}

        return self._commit(patch.expected_revision, "class", f"Edited class {class_id}", fn)

    def update_trait(self, trait_id: str, patch: TraitPatch) -> Committed:
        def fn(cfg: Config):
            t = cfg.get_trait(trait_id)
            if t is None:
                raise NotFoundError("trait", trait_id)
            before = t.model_dump(mode="json")
            for field in ("name", "description", "interpretation"):
                value = getattr(patch, field)
                if value is not None:
                    setattr(t, field, value)
            return cfg, {"target": trait_id, "before": before, "after": t.model_dump(mode="json")}

        return self._commit(patch.expected_revision, "trait", f"Edited trait {trait_id}", fn)

    def update_quiz(self, patch: QuizPatch) -> Committed:
        def fn(cfg: Config):
            fields = ("title", "subtitle", "share_template")
            before = {f: getattr(cfg.quiz, f) for f in fields}
            for f in fields:
                value = getattr(patch, f)
                if value is not None:
                    setattr(cfg.quiz, f, value)
            return cfg, {"target": "quiz", "before": before, "after": {f: getattr(cfg.quiz, f) for f in fields}}

        return self._commit(patch.expected_revision, "quiz", "Edited quiz title, subtitle or share format", fn)

    def update_scoring(self, patch: ScoringPatch) -> Committed:
        def fn(cfg: Config):
            before = cfg.scoring.model_dump(mode="json")
            if patch.adaptive is not None:
                cfg.scoring.adaptive = patch.adaptive
            if patch.confidence_margins is not None:
                cfg.scoring.confidence_margins = patch.confidence_margins
            if patch.class_tie_break_order is not None:
                cfg.scoring.class_tie_break_order = list(patch.class_tie_break_order)
            if patch.spec_weight_multiplier is not None:
                cfg.scoring.spec_weight_multiplier = patch.spec_weight_multiplier
            return cfg, {"target": "scoring", "before": before, "after": cfg.scoring.model_dump(mode="json")}

        return self._commit(patch.expected_revision, "scoring", "Edited scoring settings", fn)

    # -- whole-configuration operations --------------------------------------------------
    def import_config(self, expected_revision: int, new_cfg: Config, description: Optional[str] = None) -> Committed:
        def fn(_current: Config):
            return new_cfg.model_copy(deep=True), {"imported_questions": len(new_cfg.questions)}

        return self._commit(
            expected_revision, "import", description or "Imported configuration", fn, backup_tag="before-import"
        )

    def reset(self, expected_revision: int) -> Committed:
        def fn(_current: Config):
            return build_default_config(), None

        return self._commit(
            expected_revision, "reset", "Restored the original seed configuration", fn, backup_tag="before-reset"
        )

    def restore(self, expected_revision: int, revision: int) -> Committed:
        target = self.snapshot(revision)

        def fn(_current: Config):
            return target, {"restored_from": revision}

        return self._commit(
            expected_revision, "restore", f"Restored configuration from revision {revision}", fn,
            backup_tag="before-restore",
        )

    # -- builds ----------------------------------------------------------------------------
    def create_build(self, expected_revision: int, build: Build) -> Committed:
        def fn(cfg: Config):
            if cfg.get_build(build.id) is not None:
                raise ConfigInvalid([f"A build with id '{build.id}' already exists."])
            new = build.model_copy(deep=True)
            if new.is_default:
                _clear_defaults(cfg, new.class_id, new.specialization_id)
            cfg.builds.append(new)
            return cfg, {"target": new.id, "after": new.model_dump(mode="json")}

        return self._commit(expected_revision, "build", f"Created build {build.id}", fn)

    def update_build(self, build_id: str, patch: BuildPatch) -> Committed:
        def fn(cfg: Config):
            b = cfg.get_build(build_id)
            if b is None:
                raise NotFoundError("build", build_id)
            before = b.model_dump(mode="json")
            for field in patch.model_fields_set - {"expected_revision"}:
                value = getattr(patch, field)
                if value is None and field != "verified_at":
                    continue
                setattr(b, field, value)
            return cfg, {"target": build_id, "before": before, "after": b.model_dump(mode="json")}

        return self._commit(patch.expected_revision, "build", f"Edited build {build_id}", fn)

    def delete_build(self, expected_revision: int, build_id: str) -> Committed:
        def fn(cfg: Config):
            b = cfg.get_build(build_id)
            if b is None:
                raise NotFoundError("build", build_id)
            cfg.builds = [x for x in cfg.builds if x.id != build_id]
            return cfg, {"target": build_id, "before": b.model_dump(mode="json")}

        return self._commit(expected_revision, "build", f"Deleted build {build_id}", fn)

    def set_default_build(self, expected_revision: int, build_id: str) -> Committed:
        def fn(cfg: Config):
            b = cfg.get_build(build_id)
            if b is None:
                raise NotFoundError("build", build_id)
            _clear_defaults(cfg, b.class_id, b.specialization_id)
            b.is_default = True
            return cfg, {"target": build_id}

        return self._commit(expected_revision, "build", f"Set {build_id} as the default build", fn)

    def set_catalog(self, expected_revision: int, catalog: Optional[TalentCatalog]) -> tuple[Committed, list[str]]:
        downgraded: list[str] = []

        def fn(cfg: Config):
            cfg.talent_catalog = catalog.model_copy(deep=True) if catalog else None
            for b in cfg.builds:
                if b.status == "verified" and not validate_build(b, cfg).valid:
                    b.status = "unverified"
                    downgraded.append(b.id)
            detail = {
                "client_version": catalog.client_version if catalog else None,
                "downgraded_builds": list(downgraded),
            }
            return cfg, detail

        desc = f"Imported talent catalog ({catalog.client_version})" if catalog else "Removed talent catalog"
        committed = self._commit(expected_revision, "catalog", desc, fn)
        return committed, downgraded


def _clear_defaults(cfg: Config, class_id: str, spec_id: str) -> None:
    for b in cfg.builds:
        if b.class_id == class_id and b.specialization_id == spec_id:
            b.is_default = False
