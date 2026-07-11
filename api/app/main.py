"""FastAPI read-only service for kingstonpier.ca.

Serves the dashboard's data contract from the readings table. Never writes.
Runs (and returns sensible empty/stale payloads) even when the DB doesn't exist
yet, so it can be brought up before the tracker.

    uvicorn app.main:app --reload      # dev, from the api/ directory
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Query, Response
from fastapi.middleware.cors import CORSMiddleware

from . import aggregate, db, weather
from .aggregate import DAYS, to_utc_iso
from .config import KINGSTON_TZ, settings
from .models import (
    HistoryPoint,
    HistoryResponse,
    NowResponse,
    PopularTimesResponse,
)

cfg = settings()
app = FastAPI(title="Kingston Pier API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.cors_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)

_RANGES = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


def _cache(response: Response, seconds: int) -> None:
    response.headers["Cache-Control"] = f"public, max-age={seconds}"


def _edge_cache(response: Response, seconds: int) -> None:
    response.headers["Cache-Control"] = f"public, max-age=0, s-maxage={seconds}"


def _age_seconds(ts_iso: str) -> float:
    dt = datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - dt).total_seconds()


def _downsample(points: list, target: int = 600) -> list:
    """Evenly thin a list of (ts, total) samples to at most `target` points."""
    n = len(points)
    if n <= target:
        return points
    step = n / target
    return [points[int(i * step)] for i in range(target)]


@app.get("/now", response_model=NowResponse)
def now(response: Response) -> NowResponse:
    _edge_cache(response, cfg.now_cache)
    now_local = datetime.now(KINGSTON_TZ)
    now_hour = now_local.hour

    latest = db.latest(cfg.db_path)
    since = now_local - timedelta(weeks=cfg.popular_weeks)
    samples = db.samples_since(cfg.db_path, to_utc_iso(since))

    popular = aggregate.popular_by_day(samples, KINGSTON_TZ)
    typical_today = popular[DAYS[now_local.weekday()]]

    latest_total = latest.total if latest else None
    trend = aggregate.todays_trend(
        samples, KINGSTON_TZ, now_local, latest_total, typical_today
    )
    total = latest_total if latest_total is not None else 0
    compare = aggregate.compare_pct(total, typical_today, now_hour)
    cap = aggregate.capacity(samples, cfg.capacity_prior, cfg.capacity_headroom)

    if latest is not None:
        live = _age_seconds(latest.ts) <= cfg.stale_after_s
        last_updated = latest.ts
    else:
        live = False
        last_updated = to_utc_iso(now_local)

    return NowResponse(
        total=total,
        lastUpdated=last_updated,
        comparePct=compare,
        trend=trend,
        nowHour=now_hour,
        capacity=cap,
        popularByDay=popular,
        weather=weather.get_weather(),
        live=live,
    )


@app.get("/popular-times", response_model=PopularTimesResponse)
def popular_times(response: Response, dow: str = Query("Thu")) -> PopularTimesResponse:
    _cache(response, cfg.popular_cache)
    now_local = datetime.now(KINGSTON_TZ)
    since = now_local - timedelta(weeks=cfg.popular_weeks)
    samples = db.samples_since(cfg.db_path, to_utc_iso(since))
    popular = aggregate.popular_by_day(samples, KINGSTON_TZ)
    day = dow if dow in popular else DAYS[now_local.weekday()]
    return PopularTimesResponse(day=day, hours=popular[day])


@app.get("/history", response_model=HistoryResponse)
def history(response: Response, range: str = Query("24h")) -> HistoryResponse:
    _cache(response, cfg.history_cache)
    window = _RANGES.get(range, _RANGES["24h"])
    since = datetime.now(KINGSTON_TZ) - window
    samples = _downsample(db.samples_since(cfg.db_path, to_utc_iso(since)))
    return HistoryResponse(
        range=range if range in _RANGES else "24h",
        points=[HistoryPoint(ts=s.ts, total=s.total) for s in samples],
    )


@app.get("/weather")
def get_weather(response: Response):
    _cache(response, cfg.weather_cache)
    return weather.get_weather()


@app.get("/healthz")
def healthz():
    """Liveness + whether a readings DB is currently reachable with data."""
    latest = db.latest(cfg.db_path)
    return {
        "ok": True,
        "hasData": latest is not None,
        "latest": latest.ts if latest else None,
    }
