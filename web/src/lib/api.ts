// The shape the dashboard consumes. In production this comes from the FastAPI
// service behind the Cloudflare tunnel (GET https://api.kingstonpier.ca/now).
// For this frontend-only build it is served by the local mock (see mock.ts).

import { getMockNow } from './mock';

export interface WeatherNow {
  tempC: number;
  feelsLikeC: number;
  condition: string; // "Sunny", "Cloudy", …
  windKmh: number;
  windDir: string; // "WSW"
  sunrise: string; // "5:42a"
  sunset: string; // "8:51p"
  lake: string; // "Calm lake"
}

export interface NowPayload {
  total: number; // combined, explicitly-approximate people count
  lastUpdated: string; // ISO timestamp of the reading
  comparePct: number; // +14 => 14% busier than a typical slot; negative => quieter
  trend: number[]; // 24 hourly counts for *today* (index = hour of day)
  nowHour: number; // current hour index into `trend`
  capacity: number; // count that reads as "packed" — full bar / top level band
  popularByDay: Record<Day, number[]>; // typical counts, 24 per weekday
  weather: WeatherNow;
  live: boolean; // false => data is stale / feed unavailable
}

import type { Day } from './busyness';

const API_BASE = import.meta.env.PUBLIC_API_BASE ?? 'https://api.kingstonpier.ca';

/** Consider data stale if older than this (matches the ~1min poll cadence). */
export const STALE_AFTER_MS = 6 * 60 * 1000;

/**
 * Fetch the current reading from the live API. Returns `null` on any failure so
 * callers keep the last-good payload and switch to the stale UI (never blank the
 * page). Set PUBLIC_USE_MOCK=true to serve the synthetic mock instead (handy for
 * design work with no backend running).
 */
const USE_MOCK = import.meta.env.PUBLIC_USE_MOCK === 'true';

export async function fetchNow(): Promise<NowPayload | null> {
  if (USE_MOCK) return getMockNow();
  try {
    const res = await fetch(`${API_BASE}/now`, { headers: { accept: 'application/json' } });
    if (!res.ok) return null;
    return (await res.json()) as NowPayload;
  } catch {
    return null;
  }
}

/** Server-side first paint uses the mock synchronously. */
export function initialNow(): NowPayload {
  return getMockNow();
}
