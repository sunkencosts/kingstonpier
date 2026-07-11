// Popular-times bar chart, rendered as plain DOM so each bar can carry its own
// busyness color and the current hour can get a subtle emphasis — all
// pixel-faithful to the design and cheap to re-render on a weekday switch. Used
// both server-side (first paint) and client-side (switch). The selection ring
// is hover/focus/tap only; see .bar box-shadow in global.css.

import { LEVEL_COLORS, levelWord, mapV } from './busyness';

const START_H = 6;
const END_H = 23;
const MAX_BAR_PX = 88;

/** 17 → "5 PM", 12 → "12 PM", 6 → "6 AM". */
function hourLabel(h: number): string {
  const period = h < 12 ? 'AM' : 'PM';
  const hr = h % 12 === 0 ? 12 : h % 12;
  return `${hr} ${period}`;
}

/** Peak value across every day — the reference the bars fill to. */
export function scaleMaxOf(popularByDay: Record<string, number[]>): number {
  let m = 1;
  for (const arr of Object.values(popularByDay)) for (const v of arr) if (v > m) m = v;
  return m;
}

/**
 * @param vals     24 hourly "typical" values for the selected day
 * @param nowHour  emphasise this hour (subtle opacity bump), or null for none
 * @param scaleMax value that maps to a full-height bar (heights stay comparable
 *                 across days when the same scaleMax is passed for all of them)
 */
export function renderBars(vals: number[], nowHour: number | null, scaleMax = 100): string {
  const denom = scaleMax > 0 ? scaleMax : 100;
  let out = '';
  for (let h = START_H; h <= END_H; h++) {
    const v = vals[h] ?? 0;
    const li = mapV(v);
    const isNow = nowHour !== null && h === nowHour;
    const height = Math.min(MAX_BAR_PX, Math.max(3, (v / denom) * MAX_BAR_PX));
    const time = hourLabel(h);
    const word = levelWord(li);
    const raw = Math.round(v);
    out +=
      `<div class="bar-col" role="button" tabindex="0" ` +
      `aria-label="${time}: ${word}, ${raw} out of 100">` +
      `<div class="bar" style="height:${height.toFixed(1)}px;` +
      `background:${LEVEL_COLORS[li]};opacity:${isNow ? 1 : 0.88};"></div>` +
      `<span class="bar-tip" role="tooltip">` +
      `<span class="bar-tip-time">${time}</span>` +
      `<span class="bar-tip-val">${word} · ${raw}</span>` +
      `</span>` +
      `</div>`;
  }
  return out;
}
