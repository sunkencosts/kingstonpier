# web/ — Kingston Pier dashboard (Astro)

Recreation of the approved Claude Design ("Kingston Pier — Live Busyness
Dashboard"), **Bento** layout in light + dark. Static Astro site for Cloudflare
Pages. Ships almost no JS: a few small vanilla islands (theme toggle, freshness
ticker, popular-times weekday switcher, and a ~60s data poll).

## Run

```bash
npm install
npm run dev      # http://localhost:4321
npm run build    # → dist/
npm run preview  # serve the build
```

## Structure

```
src/
  layouts/Layout.astro     base HTML, fonts, no-flash theme bootstrap
  pages/index.astro        composes the dashboard + live ticker/poll island
  components/
    Header.astro           logo, live/stale status pill, theme toggle
    HeroCard.astro         approximate count, range chip, compare badge, tide gauge
    WeatherCard.astro      Kingston conditions
    TrendChart.astro       "Today so far" sparkline (inline SVG)
    PopularTimes.astro     weekday switcher + hourly bars
    Footer.astro
  lib/
    busyness.ts            REAL spec: levels, colors, thresholds, lo/hi, mapV
    api.ts                 NowPayload type + fetchNow() (mock today, tunnel later)
    mock.ts                synthetic data (replace by pointing api.ts at the API)
    spark.ts               sparkline SVG builder (server + client)
    bars.ts                popular-times bar builder (server + client)
  styles/global.css        theme tokens (light/dark), bento grid, shared classes
```

## Design decisions worth knowing

- **Theming** is pure CSS custom properties. Default = light; dark applies from
  `prefers-color-scheme` *or* an explicit `[data-theme]` set by the toggle
  (persisted to `localStorage`, applied before first paint to avoid a flash).
- **No chart library.** The design's two charts are a hand-built gradient SVG
  sparkline (with a dashed "future" segment) and a per-hour CSS bar chart where
  each bar is colored by its busyness level with a ring on the current hour.
  Reproducing these as inline SVG + CSS is pixel-faithful and dependency-free —
  a charting lib would be *more* code here for *worse* fidelity. The plan names
  uPlot/Chart.js as an option; if live zoom/tooltips are ever wanted, swap
  `spark.ts`/`bars.ts` for a uPlot island — the data shape won't change.
- **Feed states.** `<main data-feed="live|stale">` drives the status pill and
  the amber "last known reading" note. The poll flips it to `stale` on fetch
  failure or a timestamp older than `STALE_AFTER_MS`, never blanking the page.
- **The per-pier breakdown was removed** by design request (the 5 feeds are
  overlapping camera views that double-count). The hero shows one combined,
  explicitly-approximate number.

## Fonts

Space Grotesk (display/numbers) + IBM Plex Sans (body) via Google Fonts. For a
fully self-hosted build (on-brand with the no-external-CDN stance), swap the
`<link>` in `Layout.astro` for `@fontsource` packages.
