// SYNTHETIC data only — a stand-in for the real JSON API during frontend
// development. The Gaussian "typical times" curve (peak ~4:30pm, a lunch bump,
// a weekend evening bump) is lifted from the design mock so the charts look
// right. Replace this whole module's role by pointing api.ts at the live
// endpoint; the busyness thresholds / colors / lo-hi math in busyness.ts are
// the parts that stay.

import { DAYS, DEFAULT_CAPACITY, type Day } from './busyness';
import type { NowPayload } from './api';

const CAP = 300; // scales the 0–100 curve to a plausible pier headcount

// deterministic pseudo-noise so the mock is stable across renders
function rnd(n: number): number {
  const x = Math.sin(n * 12.9898) * 43758.5453;
  return x - Math.floor(x);
}

export function curve(dayIndex: number, hour: number, noise: boolean): number {
  const weekend = dayIndex >= 5;
  let g = Math.exp(-Math.pow((hour - 16.5) / 5.2, 2)) * (weekend ? 98 : 82);
  const lunch = Math.exp(-Math.pow((hour - 12) / 1.7, 2)) * (weekend ? 16 : 24);
  const eve = weekend
    ? Math.exp(-Math.pow((hour - 20.5) / 1.5, 2)) * 28
    : Math.exp(-Math.pow((hour - 19) / 1.5, 2)) * 14;
  if (hour < 6) g *= 0.12;
  let v = g * 0.72 + lunch + eve;
  if (noise) v += (rnd(dayIndex * 31 + hour) - 0.5) * 9;
  return Math.max(0, Math.min(100, Math.round(v)));
}

function popularByDay(): Record<Day, number[]> {
  const out = {} as Record<Day, number[]>;
  DAYS.forEach((d, di) => {
    out[d] = Array.from({ length: 24 }, (_, h) => curve(di, h, true));
  });
  return out;
}

/** Current hour + weekday index (Mon=0…Sun=6) in Kingston's timezone. */
function kingstonNow(): { hour: number; dayIndex: number } {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/Toronto',
    weekday: 'short',
    hour: 'numeric',
    hour12: false,
  }).formatToParts(new Date());
  const hourRaw = parts.find((p) => p.type === 'hour')?.value ?? '12';
  const hour = Number(hourRaw) % 24; // "24" → 0
  const wk = parts.find((p) => p.type === 'weekday')?.value ?? 'Thu';
  const dayIndex = Math.max(0, DAYS.indexOf(wk as Day));
  return { hour, dayIndex };
}

export function getMockNow(): NowPayload {
  const { hour: nowHour, dayIndex } = kingstonNow();
  const typNow = Math.round((curve(dayIndex, nowHour, false) / 100) * CAP);
  const total = Math.round(typNow * 1.14); // "busier than usual"

  const trend = Array.from({ length: 24 }, (_, h) => Math.round((curve(dayIndex, h, false) / 100) * CAP));
  trend[nowHour] = total;

  return {
    total,
    lastUpdated: new Date().toISOString(),
    comparePct: 14,
    trend,
    nowHour,
    capacity: DEFAULT_CAPACITY,
    popularByDay: popularByDay(),
    weather: {
      tempC: 21,
      feelsLikeC: 22,
      condition: 'Sunny',
      windKmh: 14,
      windDir: 'WSW',
      sunrise: '5:42a',
      sunset: '8:51p',
      lake: 'Calm lake',
    },
    live: true,
  };
}
