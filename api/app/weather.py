"""Kingston weather via Open-Meteo (free, no API key), cached in-process.

Independent of the tracker/DB entirely. On any failure it serves the last good
value (or a calm default) so the widget never breaks the page.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

import httpx

from .config import KINGSTON_LAT, KINGSTON_LON, settings
from .models import Weather

_OPEN_METEO = "https://api.open-meteo.com/v1/forecast"

# WMO weather codes → short human label (the common ones).
_WMO = {
    0: "Clear",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Rime fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Heavy drizzle",
    61: "Light rain",
    63: "Rain",
    65: "Heavy rain",
    71: "Light snow",
    73: "Snow",
    75: "Heavy snow",
    80: "Rain showers",
    81: "Showers",
    82: "Heavy showers",
    95: "Thunderstorm",
    96: "Thunderstorm",
    99: "Thunderstorm",
}

_COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]

_DEFAULT = Weather(
    tempC=0, feelsLikeC=0, condition="—", windKmh=0, windDir="", sunrise="", sunset="", lake="Lake"
)

# module-level cache: (payload, fetched_at_monotonic)
_cache: Optional[tuple[Weather, float]] = None


def _compass(deg: float) -> str:
    return _COMPASS[round(deg / 22.5) % 16]


def _clock(iso: str) -> str:
    """'2026-07-07T05:42' → '5:42a'."""
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return ""
    h = dt.hour % 12 or 12
    suffix = "a" if dt.hour < 12 else "p"
    return f"{h}:{dt.minute:02d}{suffix}"


def _lake(wind_kmh: float) -> str:
    if wind_kmh < 12:
        return "Calm lake"
    if wind_kmh < 25:
        return "Light chop"
    return "Choppy lake"


def _fetch() -> Weather:
    params = {
        "latitude": KINGSTON_LAT,
        "longitude": KINGSTON_LON,
        "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m,wind_direction_10m",
        "daily": "sunrise,sunset",
        "timezone": "America/Toronto",
        "wind_speed_unit": "kmh",
        "forecast_days": 1,
    }
    resp = httpx.get(_OPEN_METEO, params=params, timeout=6.0)
    resp.raise_for_status()
    data = resp.json()
    cur = data["current"]
    daily = data.get("daily", {})
    wind = float(cur.get("wind_speed_10m", 0))
    return Weather(
        tempC=round(float(cur["temperature_2m"])),
        feelsLikeC=round(float(cur.get("apparent_temperature", cur["temperature_2m"]))),
        condition=_WMO.get(int(cur.get("weather_code", -1)), "—"),
        windKmh=round(wind),
        windDir=_compass(float(cur.get("wind_direction_10m", 0))),
        sunrise=_clock((daily.get("sunrise") or [""])[0]),
        sunset=_clock((daily.get("sunset") or [""])[0]),
        lake=_lake(wind),
    )


def get_weather() -> Weather:
    global _cache
    now = time.monotonic()
    if _cache and now - _cache[1] < settings().weather_cache:
        return _cache[0]
    try:
        wx = _fetch()
        _cache = (wx, now)
        return wx
    except Exception:
        # keep serving the last good value; only fall to default on a cold miss
        return _cache[0] if _cache else _DEFAULT
