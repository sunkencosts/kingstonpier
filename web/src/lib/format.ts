// Scene-time + comparison-copy formatting, shared by the server (first paint)
// and the client (live repaint) so the two always agree. All wall-clock is
// Kingston local time.

import { DAYS, type Day } from './busyness';

const TZ = 'America/Toronto';

export interface Scene {
  timestamp: string; // "Thu · 3:07 PM"
  dow: string; // "Thu"
  dowLong: string; // "Thursday"
  daypart: string; // "morning" | "afternoon" | "evening"
  todayDay: Day; // dow, clamped to a known weekday
}

export function sceneTime(iso: string): Scene {
  const d = new Date(iso);
  const f = (opts: Intl.DateTimeFormatOptions) =>
    new Intl.DateTimeFormat('en-US', { timeZone: TZ, ...opts }).format(d);

  const dow = f({ weekday: 'short' });
  const dowLong = f({ weekday: 'long' });
  const clock = f({ hour: 'numeric', minute: '2-digit', hour12: true });
  const hourNum = Number(f({ hour: 'numeric', hour12: false })) % 24;
  const daypart = hourNum < 12 ? 'morning' : hourNum < 17 ? 'afternoon' : 'evening';
  const todayDay = ((DAYS as readonly string[]).includes(dow) ? dow : 'Thu') as Day;

  return { timestamp: `${dow} · ${clock}`, dow, dowLong, daypart, todayDay };
}

/** 17 → "5 PM", 12 → "12 PM", 6 → "6 AM". Shared by the bars and the caption. */
export function hourLabel(h: number): string {
  const hh = ((h % 24) + 24) % 24;
  const period = hh < 12 ? 'AM' : 'PM';
  const hr = hh % 12 === 0 ? 12 : hh % 12;
  return `${hr} ${period}`;
}

/**
 * The "usually busiest around …" line, derived from real weekday history rather
 * than hard-coded. Averages Mon–Fri per hour, finds the peak, and names the
 * peak→next-hour window. Falls back to a neutral line until data accumulates.
 */
export function busiestCaption(popularByDay: Record<string, number[]>): string {
  const weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];
  const sums = new Array(24).fill(0);
  const counts = new Array(24).fill(0);
  for (const d of weekdays) {
    const arr = popularByDay[d] ?? [];
    for (let h = 0; h < 24; h++) {
      if (arr[h] > 0) {
        sums[h] += arr[h];
        counts[h] += 1;
      }
    }
  }
  let peakH = -1;
  let peak = 0;
  for (let h = 0; h < 24; h++) {
    const avg = counts[h] ? sums[h] / counts[h] : 0;
    if (avg > peak) {
      peak = avg;
      peakH = h;
    }
  }
  if (peakH < 0) return 'Popular times will fill in as we gather more data.';

  const la = hourLabel(peakH); // e.g. "5 PM"
  const lb = hourLabel(peakH + 1); // e.g. "6 PM"
  // Collapse a shared period ("5 PM–6 PM" → "5–6 PM"); hourLabel owns the format.
  const range = la.slice(-2) === lb.slice(-2) ? `${la.slice(0, -3)}–${lb}` : `${la}–${lb}`;
  return `Usually busiest around ${range} on weekdays.`;
}

export function compareText(pct: number | null): string {
  if (pct === null) return 'Not enough data yet';
  return pct >= 0 ? 'Busier than usual' : 'Quieter than usual';
}

export function compareColors(pct: number | null): {
  color: string;
  bg: string;
  busier: boolean | null;
} {
  if (pct === null) {
    return { busier: null, color: 'var(--muted)', bg: 'color-mix(in srgb, var(--muted) 14%, var(--card))' };
  }
  const busier = pct >= 0;
  return {
    busier,
    // Warm accent for "busier", cool teal for "quieter".
    color: busier ? '#D9772E' : '#2E9E86',
    bg: busier
      ? 'color-mix(in srgb, #E8863C 16%, var(--card))'
      : 'color-mix(in srgb, #2E9E86 15%, var(--card))',
  };
}
