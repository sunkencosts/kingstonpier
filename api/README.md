# api/ — FastAPI read-only service

Serves the dashboard's data contract for `https://api.kingstonpier.ca` (behind a
Cloudflare Tunnel on the Pi). Small, `uvicorn`-hosted, **read-only**.

## The decoupling (why this is safe to build alongside a churning tracker)

This service is intentionally isolated from the CV/tracker code you iterate on:

- **It only reads `readings`** (see `../db/schema.sql`) — the single contract.
- **It never writes**, and **never imports `tracker/`**. Refactor the tracker
  however/whenever; as long as it keeps appending `readings` rows, the API is
  unaffected.
- **Its dependencies are tiny** (`fastapi`, `uvicorn`, `httpx`) — no
  `ultralytics`/`torch`. It installs and runs in seconds, in its own venv.
- **It boots without a DB.** Missing file or empty table → it serves a
  `live:false` / empty payload instead of erroring, so ordering of bring-up
  doesn't matter.

## Run (dev)

```bash
cd api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python seed.py                       # build db/data/readings.db (synthetic history)
uvicorn app.main:app --reload        # http://127.0.0.1:8000

curl -s localhost:8000/now | python -m json.tool
```

Point the frontend at it for a live end-to-end test: in `web/`, set
`PUBLIC_API_BASE=http://localhost:8000` and flip `USE_MOCK=false` in
`src/lib/api.ts`.

## Endpoints

| Endpoint | Returns | Cache |
|---|---|---|
| `GET /now` | Full dashboard bundle: `total`, `lastUpdated`, `comparePct`, `trend[24]`, `nowHour`, `popularByDay{}`, `weather{}`, `live`. Matches the frontend's `NowPayload`. | 60s |
| `GET /popular-times?dow=Thu` | `{day, hours[24]}` — average count per hour for a weekday. | 3600s |
| `GET /history?range=24h\|7d\|30d` | `{range, points[]}` — downsampled `(ts,total)` series. | 60s |
| `GET /weather` | Kingston conditions via Open-Meteo (cached). | 600s |
| `GET /healthz` | Liveness + whether a readings DB with data is reachable. | — |

`Cache-Control` is set per endpoint so Cloudflare shields the origin.

## How the numbers are derived

- **`total`** = the latest reading's `total`. **`live`** = that reading is newer
  than `KP_STALE_AFTER_S`.
- **`popularByDay`** = average `total` bucketed by (weekday, hour) over the
  trailing `KP_POPULAR_WEEKS`, in Kingston local time (DST-correct).
- **`trend`** = today's hourly averages up to now, the live count at the current
  hour, and the typical curve for the rest of the day (the sparkline's dashed
  "future").
- **`comparePct`** = how far `total` sits above/below the typical value for the
  current weekday+hour slot.

The busyness *labels/colors* are derived on the frontend from `total`
(`web/src/lib/busyness.ts`); the API returns raw numbers so there's one place to
tune the scale.

## Layout

```
app/
  config.py     env-driven settings (DB path, CORS, cache TTLs, window)
  db.py         read-only SQLite access — the ONLY coupling to the schema
  aggregate.py  popular-times / trend / compare bucketing (Kingston tz)
  weather.py    Open-Meteo fetch + in-process cache
  models.py     pydantic responses (camelCase, matches the frontend)
  main.py       FastAPI app + routes
seed.py         build a synthetic readings.db for dev
```

## Deploy (later)

`systemd` unit running `uvicorn app.main:app` on the Pi, exposed as
`api.kingstonpier.ca` via the existing `cloudflared` tunnel. Reuse the Pi venv.
