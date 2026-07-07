"""Read-only access to the readings table.

This module is the API's *entire* coupling to the tracker: the table/column
names in db/schema.sql. It never writes. If the DB file is missing (tracker not
running yet, fresh box), every function degrades gracefully to "no data" so the
API still boots and serves a stale/empty payload rather than 500ing.
"""

from __future__ import annotations

import sqlite3
from typing import NamedTuple, Optional


class Reading(NamedTuple):
    ts: str  # UTC ISO-8601
    total: int
    feeds_ok: int


class Sample(NamedTuple):
    ts: str  # UTC ISO-8601
    total: int


def _connect(path: str) -> Optional[sqlite3.Connection]:
    """Open the DB strictly read-only; return None if it isn't there yet."""
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2.0)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.OperationalError:
        return None


def latest(path: str) -> Optional[Reading]:
    """Most recent reading, or None if the table is empty/absent."""
    conn = _connect(path)
    if conn is None:
        return None
    try:
        row = conn.execute(
            "SELECT ts, total, feeds_ok FROM readings ORDER BY ts DESC LIMIT 1"
        ).fetchone()
    except sqlite3.OperationalError:
        return None  # table doesn't exist yet
    finally:
        conn.close()
    if row is None:
        return None
    return Reading(row["ts"], int(row["total"]), int(row["feeds_ok"]))


def samples_since(path: str, since_utc_iso: str) -> list[Sample]:
    """All (ts, total) at/after the given UTC ISO timestamp, oldest first.

    ISO-8601 in a fixed 'YYYY-MM-DDTHH:MM:SSZ' shape sorts lexicographically, so
    a plain string comparison is a correct time comparison.
    """
    conn = _connect(path)
    if conn is None:
        return []
    try:
        rows = conn.execute(
            "SELECT ts, total FROM readings WHERE ts >= ? ORDER BY ts ASC",
            (since_utc_iso,),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()
    return [Sample(r["ts"], int(r["total"])) for r in rows]
