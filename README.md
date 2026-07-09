# kingstonpier.ca

A small, fun live dashboard showing how busy the Breakwater Park pier in
Kingston, Ontario is right now — plus a weather widget and Google-style
"popular times". Counts and charts only; **no pier imagery is ever served or
stored** (privacy, and it sidesteps any question about re-serving the City's
webcam feed).

> Hobby project. Playful and calm, coastal/lakeside feel, readable at a glance
> on a phone.

## Architecture (locked)

```
City of Kingston webcams (5 JPEG snapshot URLs, Ozolio relay)
      │  HTTP pull, one frame/feed every ~3 min
      ▼
Raspberry Pi
  cv-worker  → trained density counter (torch/torchvision, CPU) → readings
  SQLite     ← single source of truth (integer counts only, no images)
  api        → FastAPI: /now /history /popular-times /weather
  cloudflared→ Cloudflare Tunnel → api.kingstonpier.ca (no open ports)
      ▼
Cloudflare: DNS + Pages (this Astro site) + short-TTL cache on api.*
      ▼
Visitor browser polls api.kingstonpier.ca and renders the dashboard.
```

No GPU anywhere: the counter is a small frozen-MobileNetV3 density model that
runs on **CPU** (torch/torchvision), so it fits on the Pi. It's trained on our
own point-labelled frames — a detector (YOLO) is used only to pre-seed labels,
never at runtime. See `tracker/README.md` for the model + labelling/training
loop, and `deploy/README.md` for the Pi services (confirm a 5-feed pass fits the
~3-min cadence before enabling the worker).

## Repo layout (monorepo)

| Path        | What                                                              | Status |
|-------------|------------------------------------------------------------------|--------|
| `web/`      | Astro frontend (this dashboard) → Cloudflare Pages               | **built**, wired to live API |
| `api/`      | FastAPI read-only service behind the tunnel                      | **built** |
| `tracker/`  | CV worker (density counter) + SQLite writer                      | **built**, works e2e |
| `db/`       | `readings` schema — the tracker↔API contract                    | **built** |
| `deploy/`   | Pi systemd units + installer (`install.sh`, tunnel is live)      | **built**, not yet on the Pi |

## Local dev — everything at once

```bash
./dev.sh          # tracker (--watch) + API (:8000) + dashboard (:4321)
```

Starts all three tiers wired together and streams their prefixed logs. Open
**http://localhost:4321** — the first tracker pass takes ~10-20s, then the
dashboard flips from "stale" to a live count from your local API. `Ctrl+C` stops
everything. It creates `web/.env` (git-ignored) pointing the dashboard at the
local API. One-time setup per tier (`uv sync` in `tracker/`, a venv in `api/`,
`npm install` in `web/`) — `dev.sh` preflights and tells you the exact command if
anything's missing. Override the API port with `KP_API_PORT=8001 ./dev.sh`.

## web/ — the dashboard

Built from the approved Claude Design ("Bento" layout, light + dark). Astro +
plain CSS custom properties for theming; charts are inline SVG / CSS (no chart
lib pulled in — see `web/README.md` for the rationale and the uPlot swap path).

```bash
cd web
npm install
npm run dev      # http://localhost:4321
npm run build    # static output → web/dist (deploy to Cloudflare Pages)
```

### Wiring to live data
The dashboard is **already wired to the live API**: `web/src/lib/api.ts` polls
`https://api.kingstonpier.ca/now` by default (override with `PUBLIC_API_BASE`).
The synthetic mock (`web/src/lib/mock.ts`) is only the first paint before the
first fetch resolves; set `PUBLIC_USE_MOCK=true` to serve it throughout (handy
for design work with no backend running). The busyness thresholds, color scale
and `lo/hi` math in `web/src/lib/busyness.ts` are the real spec — though they
were set to the synthetic scale and likely want retuning against real counts.
