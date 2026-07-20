"""Turn raw (ts, total) samples into the shapes the dashboard consumes.

All bucketing is done in Kingston local time (day-of-week + hour), so timezone
and DST are handled in one place. At ~1 sample / 3 min over an 8-week window
(~27k rows) this is trivial to compute in Python on each request.
"""

from __future__ import annotations

import heapq
from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .db import Sample

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]  # Python weekday(): Mon=0


def _local(ts_iso: str, tz: ZoneInfo) -> datetime:
    """Parse a stored UTC timestamp into a tz-aware Kingston-local datetime."""
    dt = datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz)


def popular_by_day(samples: list[Sample], tz: ZoneInfo) -> dict[str, list[int]]:
    """Average total per (weekday, hour) → {'Mon': [24 ints], ...}.

    Hours with no history come back as 0.
    """
    sums: dict[tuple[int, int], float] = defaultdict(float)
    counts: dict[tuple[int, int], int] = defaultdict(int)
    for s in samples:
        lt = _local(s.ts, tz)
        key = (lt.weekday(), lt.hour)
        sums[key] += s.total
        counts[key] += 1

    out: dict[str, list[int]] = {}
    for wd, name in enumerate(DAYS):
        out[name] = [
            round(sums[(wd, h)] / counts[(wd, h)]) if counts[(wd, h)] else 0 for h in range(24)
        ]
    return out


def todays_trend(
    samples: list[Sample],
    tz: ZoneInfo,
    now_local: datetime,
    latest_total: int | None,
    typical_today: list[int],
) -> list[int]:
    """Hourly series for *today* (index = hour).

    Past hours use today's actual average (falling back to the typical curve if
    a gap); the current hour uses the latest live count; future hours are filled
    with the typical curve — that's the dashed "rest of day" the sparkline draws.
    """
    today = now_local.date()
    now_hour = now_local.hour
    sums: dict[int, float] = defaultdict(float)
    counts: dict[int, int] = defaultdict(int)
    for s in samples:
        lt = _local(s.ts, tz)
        if lt.date() == today:
            sums[lt.hour] += s.total
            counts[lt.hour] += 1

    trend: list[int] = []
    for h in range(24):
        if h < now_hour:
            trend.append(round(sums[h] / counts[h]) if counts[h] else typical_today[h])
        elif h == now_hour:
            if latest_total is not None:
                trend.append(latest_total)
            else:
                trend.append(round(sums[h] / counts[h]) if counts[h] else typical_today[h])
        else:
            trend.append(typical_today[h])
    return trend


def capacity(samples: list[Sample], prior: int, headroom: float) -> int:
    """The count that means "packed" (full-height bar), as a one-way ratchet.

    Anchored at `prior` (a physical estimate of a full pier) and only ever
    raised — never lowered — to `p99(observed) * headroom` once real crowds
    exceed it. This is deliberately NOT an auto-fit to the observed peak: that
    would make whatever hour is busiest look packed even on a quiet dataset.
    The frontend derives its Empty→Packed bands as fractions of this value.
    """
    if not samples:
        return prior
    # p99 is the element at ascending rank int(0.99*(n-1)) — i.e. the k-th
    # largest, where k is the ~1% tail above it. nlargest(k) selects just that
    # tail instead of fully sorting all ~27k rows on the /now hot path.
    n = len(samples)
    k = n - int(0.99 * (n - 1))
    p99 = heapq.nlargest(k, (s.total for s in samples))[-1]
    return max(prior, round(p99 * headroom))


def compare_pct(total: int, typical_today: list[int], now_hour: int) -> int | None:
    """How far the current count sits above/below the typical for this slot (%).

    Returns None when there's no historical baseline for this hour yet - a bare
    0 would be indistinguishable from "exactly typical" and mislead the badge.
    """
    typ = typical_today[now_hour] if 0 <= now_hour < len(typical_today) else 0
    if not typ:
        return None
    return round((total - typ) / typ * 100)


def to_utc_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
