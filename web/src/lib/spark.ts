// Today's-trend sparkline as inline SVG: a soft gradient area for the elapsed
// part of the day, a solid teal line up to "now", a dashed half-opacity segment
// for the rest of the day, and a dot at the current point. Reproduces the design
// mock's look exactly; swap for uPlot/Chart.js if live zoom/tooltips are wanted.

const TEAL = '#2E9E86';
const START_H = 6;
const END_H = 22;

let uid = 0;

/**
 * @param trend   24 hourly counts for today (index = hour)
 * @param nowHour current hour index
 */
export function renderSpark(trend: number[], nowHour: number): string {
  const pts: number[] = [];
  for (let h = START_H; h <= END_H; h++) pts.push(trend[h] ?? 0);

  const W = 340;
  const H = 104;
  const pad = 6;
  const top = 10;
  const bot = H - 14;
  const maxc = Math.max(...pts, 1) * 1.12;
  const X = (i: number) => pad + i * ((W - 2 * pad) / (pts.length - 1));
  const Y = (c: number) => top + (1 - c / maxc) * (bot - top);
  const nowI = Math.max(0, Math.min(pts.length - 1, nowHour - START_H));

  let solid = '';
  for (let i = 0; i <= nowI; i++) solid += (i === 0 ? 'M' : 'L') + X(i).toFixed(1) + ' ' + Y(pts[i]).toFixed(1) + ' ';
  let future = '';
  for (let i = nowI; i < pts.length; i++) future += (i === nowI ? 'M' : 'L') + X(i).toFixed(1) + ' ' + Y(pts[i]).toFixed(1) + ' ';
  let area = 'M' + X(0).toFixed(1) + ' ' + Y(pts[0]).toFixed(1);
  for (let i = 1; i <= nowI; i++) area += ' L' + X(i).toFixed(1) + ' ' + Y(pts[i]).toFixed(1);
  area += ' L' + X(nowI).toFixed(1) + ' ' + bot + ' L' + X(0).toFixed(1) + ' ' + bot + ' Z';

  const gid = 'spk-' + uid++;
  return (
    `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" ` +
    `style="width:100%;height:clamp(96px,17vw,124px);display:block;overflow:visible">` +
    `<defs><linearGradient id="${gid}" x1="0" y1="0" x2="0" y2="1">` +
    `<stop offset="0%" stop-color="${TEAL}" stop-opacity="0.32"/>` +
    `<stop offset="100%" stop-color="${TEAL}" stop-opacity="0.02"/>` +
    `</linearGradient></defs>` +
    `<path d="${area}" fill="url(#${gid})" stroke="none"/>` +
    `<path d="${future}" fill="none" stroke="${TEAL}" stroke-width="2" stroke-dasharray="2 4" ` +
    `stroke-opacity="0.45" vector-effect="non-scaling-stroke" stroke-linecap="round"/>` +
    `<path d="${solid}" fill="none" stroke="${TEAL}" stroke-width="2.4" ` +
    `vector-effect="non-scaling-stroke" stroke-linecap="round" stroke-linejoin="round"/>` +
    `<circle cx="${X(nowI).toFixed(1)}" cy="${Y(pts[nowI]).toFixed(1)}" r="4.5" ` +
    `fill="${TEAL}" stroke="var(--card)" stroke-width="2.5"/>` +
    `</svg>`
  );
}
