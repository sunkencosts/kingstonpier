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

export function compareText(pct: number): string {
  return pct >= 0 ? 'Busier than usual' : 'Quieter than usual';
}

export function compareColors(pct: number): { color: string; bg: string; busier: boolean } {
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
