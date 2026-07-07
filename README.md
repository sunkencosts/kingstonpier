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
  cv-worker  → yolov8s@960 NCNN person count → readings
  SQLite     ← single source of truth (integer counts only, no images)
  api        → FastAPI: /now /history /popular-times /weather
  cloudflared→ Cloudflare Tunnel → api.kingstonpier.ca (no open ports)
      ▼
Cloudflare: DNS + Pages (this Astro site) + short-TTL cache on api.*
      ▼
Visitor browser polls api.kingstonpier.ca and renders the dashboard.
```

The GPU miner (GTX 1080) stays off; the Pi runs a lighter NCNN model. See the
full plan in `~/.claude/plans/this-is-a-small-functional-duckling.md`.

## Repo layout (monorepo)

| Path        | What                                                              | Status |
|-------------|------------------------------------------------------------------|--------|
| `web/`      | Astro frontend (this dashboard) → Cloudflare Pages               | **built** |
| `api/`      | FastAPI read-only service behind the tunnel                      | planned |
| `tracker/`  | CV worker + SQLite writer (refactored from the CLI prototype)    | planned |

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
The dashboard currently renders from a synthetic mock (`web/src/lib/mock.ts`)
shaped exactly like the real API. To go live, point `web/src/lib/api.ts` at
`https://api.kingstonpier.ca` (set `USE_MOCK = false`, or `PUBLIC_API_BASE`).
The busyness thresholds, color scale and `lo/hi` math in
`web/src/lib/busyness.ts` are the real spec and stay put.
