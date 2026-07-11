// Popular-times bar chart, rendered as plain DOM so each bar can carry its own
// busyness color. Used both server-side (first paint) and client-side (switch).
//
// Every hour is a single bar colored by its busyness level (Empty→Packed),
// relative to `capacity`. The one special case is the LIVE hour (only when the
// selected day is today): it's a wider, two-tone bar that shows the live count
// against the historical typical — a darker cap ABOVE the "usual" height when
// we're busier than usual, a faded cap when quieter. Past hours just show the
// typical curve; only "now" gets the live treatment (à la Google popular times).
//
// Two references, deliberately decoupled: bar COLOR/level is relative to
// `capacity` (the count that means "packed"), so a busy-but-not-packed pier
// isn't painted red; bar HEIGHT is relative to `heightMax` (the observed peak),
// so the chart stays legible while real counts sit well below capacity. As
// crowds grow toward capacity the two references converge. The selection ring is
// hover/focus/tap only; see .bar-col::after in global.css.

import { DEFAULT_CAPACITY, LEVEL_COLORS, levelForCount } from './busyness';
import { hourLabel } from './format';

const START_H = 6;
const END_H = 23;
const MAX_BAR_PX = 88;

/** Peak value across every day (and today's trend) — the height reference. */
export function heightMaxOf(popularByDay: Record<string, number[]>, trend?: number[]): number {
  let m = 1;
  for (const arr of Object.values(popularByDay)) for (const v of arr) if (v > m) m = v;
  if (trend) for (const v of trend) if (v > m) m = v;
  return m;
}

function barPx(v: number, heightMax: number): number {
  const denom = heightMax > 0 ? heightMax : 1;
  return Math.min(MAX_BAR_PX, Math.max(3, (v / denom) * MAX_BAR_PX));
}

/**
 * @param typical  24 hourly "typical" (average) values for the selected day
 * @param live     24 hourly ACTUAL values for *today* (the /now `trend`), or
 *                 null when viewing a day that isn't today — then every hour is
 *                 just its typical bar with no live treatment
 * @param nowHour  current hour; only this hour gets the live-vs-typical bar
 * @param capacity the count that maps to the "Packed" band — drives bar COLOR
 * @param heightMax the observed peak that maps to a full-height bar — drives bar
 *                  HEIGHT, kept separate from capacity so the chart stays legible
 */
export function renderBars(
  typical: number[],
  live: number[] | null,
  nowHour: number | null,
  capacity = DEFAULT_CAPACITY,
  heightMax = 1,
): string {
  let out = '';
  for (let h = START_H; h <= END_H; h++) {
    const typV = Math.round(typical[h] ?? 0);
    const typH = barPx(typV, heightMax);
    const time = hourLabel(h);
    const isLive = live !== null && nowHour !== null && h === nowHour;

    if (isLive) {
      // Two-tone live bar: solid up to the smaller of live/typical, then a cap
      // for the difference — darker when busier, faded when quieter than usual.
      const liveV = Math.round(live![nowHour] ?? 0);
      const li = levelForCount(liveV, capacity);
      const hue = LEVEL_COLORS[li];
      const busier = liveV >= typV;
      const lo = Math.min(liveV, typV);
      const hi = Math.max(liveV, typV);
      const baseH = barPx(lo, heightMax);
      const hiH = barPx(hi, heightMax);
      const capH = hiH - baseH;
      const capColor = busier
        ? `color-mix(in srgb, #000 24%, ${hue})` // surplus above usual — deeper
        : `color-mix(in srgb, ${hue} 30%, var(--card))`; // shortfall — faded
      out +=
        `<div class="bar-col is-live" role="button" tabindex="0" ` +
        `style="height:${hiH.toFixed(1)}px" ` +
        `aria-label="${time}: ${liveV} now, usually ${typV}">` +
        `<div class="bar bar-base${capH > 0.5 ? '' : ' bar-solo'}" ` +
        `style="height:${baseH.toFixed(1)}px;background:${hue};"></div>` +
        (capH > 0.5
          ? `<div class="bar bar-cap" style="height:${capH.toFixed(1)}px;` +
            `bottom:${baseH.toFixed(1)}px;background:${capColor};"></div>`
          : '') +
        `<span class="bar-tip" role="tooltip">` +
        `<span class="bar-tip-time">${time} · now</span>` +
        `<span class="bar-tip-val">${liveV} now · ${typV} usual</span>` +
        `</span>` +
        `</div>`;
    } else {
      const li = levelForCount(typV, capacity);
      const future = nowHour !== null && h > nowHour;
      // Elapsed hours today carry a real actual (past hours of `live`); future
      // hours only mirror the typical curve, so there's no distinct "today".
      const elapsed = live !== null && nowHour !== null && h < nowHour;
      const todayV = elapsed ? Math.round(live![h] ?? 0) : null;
      const valLine =
        todayV !== null ? `${todayV} today · ${typV} usual` : `${typV} usual`;
      const aria =
        todayV !== null
          ? `${time}: ${todayV} today, usually ${typV}`
          : `${time}: usually ${typV}`;
      out +=
        `<div class="bar-col${future ? ' is-future' : ''}" role="button" tabindex="0" ` +
        `style="height:${typH.toFixed(1)}px" aria-label="${aria}">` +
        `<div class="bar bar-plain" style="height:${typH.toFixed(1)}px;` +
        `background:${LEVEL_COLORS[li]};"></div>` +
        `<span class="bar-tip" role="tooltip">` +
        `<span class="bar-tip-time">${time}</span>` +
        `<span class="bar-tip-val">${valLine}</span>` +
        `</span>` +
        `</div>`;
    }
  }
  return out;
}
