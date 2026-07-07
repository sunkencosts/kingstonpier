#!/usr/bin/env python3
"""Create + populate a synthetic readings DB so the API is fully functional
before the real tracker exists.

Applies db/schema.sql, then writes ~28 days of readings at a 3-minute cadence
using the same Gaussian "typical times" shape as the design mock (afternoon
peak, lunch bump, weekend evening bump). This is the ONLY writer in this repo
that isn't the tracker; the API itself never writes.

    python api/seed.py            # → db/data/readings.db
    python api/seed.py --days 56  # more history
"""

from __future__ import annotations

import argparse
import math
import random
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = REPO_ROOT / "db" / "schema.sql"
DEFAULT_DB = REPO_ROOT / "db" / "data" / "readings.db"
TZ = ZoneInfo("America/Toronto")
CAP = 80  # scales the 0–100 curve to a plausible pier headcount
STEP_S = 180  # 3-minute cadence


def curve(day_index: int, hour: float, noise: bool) -> float:
    weekend = day_index >= 5
    g = math.exp(-((hour - 16.5) / 5.2) ** 2) * (98 if weekend else 82)
    lunch = math.exp(-((hour - 12) / 1.7) ** 2) * (16 if weekend else 24)
    eve = (
        math.exp(-((hour - 20.5) / 1.5) ** 2) * 28
        if weekend
        else math.exp(-((hour - 19) / 1.5) ** 2) * 14
    )
    if hour < 6:
        g *= 0.12
    v = g * 0.72 + lunch + eve
    if noise:
        v += (random.random() - 0.5) * 9
    return max(0.0, min(100.0, v))


def split_piers(total: int) -> list[int]:
    """Spread the total across 5 feeds (they overlap in reality; shape only)."""
    if total <= 0:
        return [0, 0, 0, 0, 0]
    ratios = [0.29, 0.13, 0.22, 0.26, 0.10]
    piers = [round(total * r) for r in ratios]
    piers[0] += total - sum(piers)  # keep the sum exact
    return piers


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=28, help="days of history to generate")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = ap.parse_args()

    random.seed(1789)
    args.db.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(args.db)
    try:
        conn.executescript(SCHEMA.read_text())
        conn.execute("DELETE FROM readings")  # idempotent reseed

        now = datetime.now(timezone.utc)
        start = now - timedelta(days=args.days)
        rows = []
        t = start
        while t <= now:
            local = t.astimezone(TZ)
            h = local.hour + local.minute / 60.0
            base = curve(local.weekday(), h, noise=True) / 100.0 * CAP
            total = max(0, round(base + random.gauss(0, 1.5)))
            p = split_piers(total)
            rows.append((t.strftime("%Y-%m-%dT%H:%M:%SZ"), *p, total, 5))
            t += timedelta(seconds=STEP_S)

        conn.executemany(
            "INSERT INTO readings (ts, pier_1, pier_2, pier_3, pier_4, pier_5, total, feeds_ok) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
        print(f"seeded {len(rows):,} readings over {args.days} days → {args.db}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
