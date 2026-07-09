#!/usr/bin/env python3
"""SQLite `readings` store — the contract with the kingstonpier API.

The tracker APPENDS one integer-count row per sampling pass; the API reads this
table (mode=ro) and never imports the tracker. The schema here is a copy of
kingstonpier/db/schema.sql — keep them in sync.

By default it writes the repo's db/data/readings.db — the exact path the API
reads (api/app/config.py computes the same default), so the two agree with no
configuration. Override with KP_DB_PATH if you keep the store elsewhere.
"""
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from feeds import FEEDS, HERE, slug

SCHEMA = """
CREATE TABLE IF NOT EXISTS readings (
  ts        TEXT    NOT NULL,            -- UTC, ISO-8601 'YYYY-MM-DDTHH:MM:SSZ'
  pier_1    INTEGER NOT NULL DEFAULT 0,
  pier_2    INTEGER NOT NULL DEFAULT 0,
  pier_3    INTEGER NOT NULL DEFAULT 0,
  pier_4    INTEGER NOT NULL DEFAULT 0,
  pier_5    INTEGER NOT NULL DEFAULT 0,
  total     INTEGER NOT NULL,
  feeds_ok  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_readings_ts ON readings (ts);
"""


def db_path() -> Path:
    # repo/db/data/readings.db — same default the API uses. HERE is tracker/,
    # so HERE.parent is the repo root.
    default = HERE.parent / "db" / "data" / "readings.db"
    return Path(os.getenv("KP_DB_PATH", str(default)))


def _connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    # WAL so the API's read-only reader never blocks on the worker's writes (and
    # vice-versa). journal_mode is persisted in the DB file; synchronous=NORMAL
    # is the durable-enough + fast pairing for WAL. Both are cheap to re-assert.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(SCHEMA)   # CREATE ... IF NOT EXISTS, cheap every time
    return conn


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_reading(counts: dict[str, int], when_iso: str | None = None) -> None:
    """Append one row. `counts` maps feed name ('Pier 1'...) -> int; missing
    feeds are recorded as 0 and don't count toward feeds_ok."""
    cols = [slug(name) for name, _ in FEEDS]
    vals = [int(counts.get(name, 0)) for name, _ in FEEDS]
    total = sum(vals)
    feeds_ok = sum(1 for name, _ in FEEDS if name in counts)
    with _connect() as conn:
        conn.execute(
            f"INSERT INTO readings (ts, {', '.join(cols)}, total, feeds_ok) "
            f"VALUES (?, {', '.join('?' for _ in cols)}, ?, ?)",
            [when_iso or utc_now_iso(), *vals, total, feeds_ok])
