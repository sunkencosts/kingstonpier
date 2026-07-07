# api/ — FastAPI read-only service (planned)

Not built yet. This will be a small `uvicorn`/FastAPI app on the Raspberry Pi,
exposed as `https://api.kingstonpier.ca` via a Cloudflare Tunnel.

Planned endpoints (the `web/` frontend is already written against this shape —
see `web/src/lib/api.ts`):

- `GET /now` — latest reading: combined approximate `total`, `lastUpdated`,
  `comparePct` (vs typical weekday+hour), `trend[24]`, `nowHour`,
  `popularByDay{}`, `weather{}`, `live`.
- `GET /history?range=24h|7d|30d` — downsampled series for the trend chart.
- `GET /popular-times?dow=…` — averaged counts per hour for a weekday.
- `GET /weather` — Kingston conditions via Open-Meteo, server-side cached.

Set short `Cache-Control` (~60s) so Cloudflare shields the origin.
