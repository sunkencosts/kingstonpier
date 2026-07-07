"""Response models. Field names are camelCase to match the frontend's
NowPayload / WeatherNow types verbatim (web/src/lib/api.ts) — the API and the
Astro site share one contract.
"""

from __future__ import annotations

from pydantic import BaseModel


class Weather(BaseModel):
    tempC: int
    feelsLikeC: int
    condition: str
    windKmh: int
    windDir: str
    sunrise: str
    sunset: str
    lake: str


class NowResponse(BaseModel):
    total: int
    lastUpdated: str  # UTC ISO-8601 of the reading
    comparePct: int  # signed: +ve busier than typical, -ve quieter
    trend: list[int]  # 24 hourly counts for today (index = hour)
    nowHour: int
    popularByDay: dict[str, list[int]]  # {'Mon': [24], ...}
    weather: Weather
    live: bool  # false => stale / no fresh reading


class PopularTimesResponse(BaseModel):
    day: str
    hours: list[int]  # 24 typical counts


class HistoryPoint(BaseModel):
    ts: str
    total: int


class HistoryResponse(BaseModel):
    range: str
    points: list[HistoryPoint]
