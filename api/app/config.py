"""Runtime configuration, all overridable by environment variables.

Nothing here couples to the tracker — the only shared knob is KP_DB_PATH, the
location of the SQLite file the tracker writes and the API reads.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

# Kingston, ON. Its wall-clock time drives "now", the day/hour buckets, and the
# weather query.
KINGSTON_TZ = ZoneInfo("America/Toronto")
KINGSTON_LAT = 44.2312
KINGSTON_LON = -76.4860

# Repo root = two levels up from this file (api/app/config.py -> repo/).
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _split(csv: str) -> list[str]:
    return [s.strip() for s in csv.split(",") if s.strip()]


@dataclass(frozen=True)
class Settings:
    db_path: str = os.getenv("KP_DB_PATH", str(_REPO_ROOT / "db" / "data" / "readings.db"))

    # CORS: the Pages site in prod + the Astro dev server locally.
    cors_origins: list[str] = field(
        default_factory=lambda: _split(
            os.getenv(
                "KP_CORS_ORIGINS",
                "https://kingstonpier.ca,https://www.kingstonpier.ca,http://localhost:4321",
            )
        )
    )

    # Cache-Control max-age (seconds) per endpoint — Cloudflare caches on these.
    now_cache: int = int(os.getenv("KP_NOW_CACHE", "60"))
    history_cache: int = int(os.getenv("KP_HISTORY_CACHE", "60"))
    popular_cache: int = int(os.getenv("KP_POPULAR_CACHE", "3600"))
    weather_cache: int = int(os.getenv("KP_WEATHER_CACHE", "600"))

    # "Popular times" trailing window, and when a reading counts as stale.
    popular_weeks: int = int(os.getenv("KP_POPULAR_WEEKS", "8"))
    stale_after_s: int = int(os.getenv("KP_STALE_AFTER_S", "600"))

    # Busyness capacity — the count that reads as "packed" / a full-height bar.
    # A one-way ratchet: it starts at the physical prior and only ever rises to
    # track a genuinely busier observed peak, so a quiet peak can never masquerade
    # as packed. The prior is a physical estimate of a full pier, not a tuning
    # knob; the level bands live on the frontend as fractions of this. See the
    # capacity() aggregate.
    capacity_prior: int = int(os.getenv("KP_CAPACITY_PRIOR", "500"))
    capacity_headroom: float = float(os.getenv("KP_CAPACITY_HEADROOM", "1.15"))


@lru_cache
def settings() -> Settings:
    return Settings()
