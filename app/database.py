"""SQLite connection handling and schema.

Connections are short-lived (one per operation) and run in autocommit mode so that
transactions are always explicit. Writers use ``BEGIN IMMEDIATE`` to serialize.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Union

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL            -- JSON
);

CREATE TABLE IF NOT EXISTS traits (
    id             TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    description    TEXT NOT NULL DEFAULT '',
    interpretation TEXT NOT NULL DEFAULT '',
    display_order  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS classes (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    display_order INTEGER NOT NULL,
    overview      TEXT NOT NULL DEFAULT '',
    overview_url  TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS specializations (
    class_id      TEXT NOT NULL REFERENCES classes(id),
    id            TEXT NOT NULL,
    name          TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    role          TEXT NOT NULL,
    display_order INTEGER NOT NULL,
    overview      TEXT NOT NULL DEFAULT '',
    guide         TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (class_id, id)
);

CREATE TABLE IF NOT EXISTS specialization_trait_weights (
    class_id          TEXT NOT NULL,
    specialization_id TEXT NOT NULL,
    trait_id          TEXT NOT NULL REFERENCES traits(id),
    weight            REAL NOT NULL,
    position          INTEGER NOT NULL,       -- primary = 0, secondary = 1, ...
    PRIMARY KEY (class_id, specialization_id, trait_id),
    FOREIGN KEY (class_id, specialization_id) REFERENCES specializations(class_id, id)
);

CREATE TABLE IF NOT EXISTS questions (
    id            TEXT PRIMARY KEY,
    text          TEXT NOT NULL,
    display_order INTEGER NOT NULL,
    enabled       INTEGER NOT NULL DEFAULT 1,
    type          TEXT NOT NULL DEFAULT 'choice',          -- choice | scale | pick_two
    low_label     TEXT NOT NULL DEFAULT 'Strongly disagree',
    high_label    TEXT NOT NULL DEFAULT 'Strongly agree',
    rationale     TEXT NOT NULL DEFAULT '',
    min_length    TEXT NOT NULL DEFAULT 'long',
    finalists     TEXT NOT NULL DEFAULT '[]'              -- JSON list of 'class/spec' keys: a tiebreaker for these finalists
);

CREATE TABLE IF NOT EXISTS answers (
    question_id   TEXT NOT NULL REFERENCES questions(id),
    id            TEXT NOT NULL,
    text          TEXT NOT NULL,
    display_order INTEGER NOT NULL,
    PRIMARY KEY (question_id, id)
);

CREATE TABLE IF NOT EXISTS answer_class_weights (
    question_id TEXT NOT NULL,
    answer_id   TEXT NOT NULL,
    class_id    TEXT NOT NULL REFERENCES classes(id),
    weight      REAL NOT NULL,
    PRIMARY KEY (question_id, answer_id, class_id),
    FOREIGN KEY (question_id, answer_id) REFERENCES answers(question_id, id)
);

CREATE TABLE IF NOT EXISTS answer_trait_weights (
    question_id TEXT NOT NULL,
    answer_id   TEXT NOT NULL,
    trait_id    TEXT NOT NULL REFERENCES traits(id),
    weight      REAL NOT NULL,
    PRIMARY KEY (question_id, answer_id, trait_id),
    FOREIGN KEY (question_id, answer_id) REFERENCES answers(question_id, id)
);

CREATE TABLE IF NOT EXISTS answer_spec_weights (
    question_id TEXT NOT NULL,
    answer_id   TEXT NOT NULL,
    spec_key    TEXT NOT NULL,                              -- 'class_id/specialization_id'
    weight      REAL NOT NULL,
    PRIMARY KEY (question_id, answer_id, spec_key),
    FOREIGN KEY (question_id, answer_id) REFERENCES answers(question_id, id)
);

CREATE TABLE IF NOT EXISTS builds (
    id                TEXT PRIMARY KEY,
    class_id          TEXT NOT NULL,
    specialization_id TEXT NOT NULL,
    name              TEXT NOT NULL,
    role              TEXT NOT NULL,
    purpose           TEXT NOT NULL,
    level             INTEGER NOT NULL,
    total_points      INTEGER NOT NULL,
    source            TEXT NOT NULL DEFAULT '',
    source_url        TEXT NOT NULL DEFAULT '',
    calculator_url    TEXT NOT NULL DEFAULT '',
    verified_at       TEXT,
    client_version    TEXT NOT NULL DEFAULT '',
    status            TEXT NOT NULL,
    is_default        INTEGER NOT NULL DEFAULT 0,
    notes             TEXT NOT NULL DEFAULT '',
    leveling_order    TEXT NOT NULL DEFAULT '[]',   -- JSON list of talent ids
    combat_priorities TEXT NOT NULL DEFAULT '[]',   -- JSON list
    equipment_notes   TEXT NOT NULL DEFAULT '[]',   -- JSON list
    professions       TEXT NOT NULL DEFAULT '[]',   -- JSON list
    display_order     INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (class_id, specialization_id) REFERENCES specializations(class_id, id)
);

CREATE TABLE IF NOT EXISTS build_talent_allocations (
    build_id  TEXT NOT NULL REFERENCES builds(id),
    talent_id TEXT NOT NULL,
    rank      INTEGER NOT NULL,
    PRIMARY KEY (build_id, talent_id)
);

CREATE TABLE IF NOT EXISTS talent_catalog (
    id   INTEGER PRIMARY KEY CHECK (id = 1),
    data TEXT NOT NULL                              -- JSON
);

CREATE TABLE IF NOT EXISTS config_revisions (
    revision           INTEGER PRIMARY KEY,
    created_at         TEXT NOT NULL,
    change_type        TEXT NOT NULL,
    change_description TEXT NOT NULL,
    change_detail      TEXT,                        -- JSON
    snapshot           TEXT NOT NULL                -- JSON of the full configuration
);
"""

#: Tables holding the live configuration, children before parents (for DELETE order).
CONFIG_TABLES = (
    "build_talent_allocations",
    "builds",
    "answer_class_weights",
    "answer_trait_weights",
    "answer_spec_weights",
    "answers",
    "questions",
    "specialization_trait_weights",
    "specializations",
    "classes",
    "traits",
    "talent_catalog",
    "meta",
)


def connect(path: Union[str, Path]) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=15, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.DatabaseError:  # e.g. read-only or network filesystem; fall back silently
        pass
    return conn


#: Columns added after the first release: (table, column, definition). Applied to databases created earlier.
_ADDED_COLUMNS = (
    ("questions", "type", "TEXT NOT NULL DEFAULT 'choice'"),
    ("questions", "low_label", "TEXT NOT NULL DEFAULT 'Strongly disagree'"),
    ("questions", "high_label", "TEXT NOT NULL DEFAULT 'Strongly agree'"),
    ("questions", "rationale", "TEXT NOT NULL DEFAULT ''"),
    ("questions", "min_length", "TEXT NOT NULL DEFAULT 'long'"),
    ("questions", "finalists", "TEXT NOT NULL DEFAULT '[]'"),
    ("classes", "overview", "TEXT NOT NULL DEFAULT ''"),
    ("classes", "overview_url", "TEXT NOT NULL DEFAULT ''"),
    ("specializations", "overview", "TEXT NOT NULL DEFAULT ''"),
    ("specializations", "guide", "TEXT NOT NULL DEFAULT ''"),
)


def init_schema(conn: sqlite3.Connection) -> None:
    """Create missing tables and add columns introduced after the first release (idempotent)."""
    conn.executescript(SCHEMA)
    for table, column, definition in _ADDED_COLUMNS:
        existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Explicit write transaction: BEGIN IMMEDIATE ... COMMIT, ROLLBACK on error."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")
