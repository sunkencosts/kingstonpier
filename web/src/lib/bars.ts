// Popular-times bar chart, rendered as plain DOM so each bar can carry its own
// busyness color, the current hour can get a ring, and a "now" label can sit
// above it — all pixel-faithful to the design and cheap to re-render on a
// weekday switch. Used both server-side (first paint) and client-side (switch).

import { LEVEL_COLORS, mapV } from './busyness';

const START_H = 6;
const END_H = 23;

/**
 * @param vals    24 hourly "typical" values (0–100) for the selected day
 * @param nowHour highlight this hour with a ring + "now" label, or null for none
 */
export function renderBars(vals: number[], nowHour: number | null): string {
  let out = '';
  for (let h = START_H; h <= END_H; h++) {
    const v = vals[h] ?? 0;
    const li = mapV(v);
    const isNow = nowHour !== null && h === nowHour;
    const height = Math.max(3, (v / 100) * 88);
    const ring = isNow ? 'box-shadow:0 0 0 2px var(--card),0 0 0 3.5px var(--text);' : '';
    out +=
      `<div class="bar-col">` +
      (isNow ? `<span class="bar-now">now</span>` : ``) +
      `<div class="bar" style="height:${height.toFixed(1)}px;` +
      `background:${LEVEL_COLORS[li]};opacity:${isNow ? 1 : 0.88};${ring}"></div>` +
      `</div>`;
  }
  return out;
}
