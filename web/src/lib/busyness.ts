// The busyness scale — the identity of the product (calm → warm).
// These thresholds, colors and the lo/hi math are the REAL spec (see design
// handoff), independent of any mock data. Keep them wherever a busyness state
// is shown.

export const LEVELS = ['Empty', 'Quiet', 'Moderate', 'Busy', 'Packed'] as const;
export type Level = (typeof LEVELS)[number];

export const LEVEL_COLORS = [
  '#86B6C7', // 0 Empty  — pale blue
  '#33A88B', // 1 Quiet  — teal-green
  '#E7B23C', // 2 Moderate — gold
  '#EC8A3F', // 3 Busy   — orange
  '#DE5240', // 4 Packed — coral-red
];

export const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] as const;
export type Day = (typeof DAYS)[number];

const LEVEL_FRACTIONS = [0.08, 0.3, 0.65];

export const DEFAULT_CAPACITY = 500;

export function levelForCount(count: number, capacity: number): number {
  if (count <= 0) return 0; // Empty
  const cap = capacity > 0 ? capacity : DEFAULT_CAPACITY;
  const f = count / cap;
  if (f < LEVEL_FRACTIONS[0]) return 1; // Quiet
  if (f < LEVEL_FRACTIONS[1]) return 2; // Moderate
  if (f < LEVEL_FRACTIONS[2]) return 3; // Busy
  return 4; // Packed
}

/** Soften the single approximate count into a "likely lo–hi" range. */
export function loHi(total: number): { lo: number; hi: number } {
  return { lo: Math.round(total * 0.85), hi: Math.round(total * 1.15) };
}

export const levelColor = (i: number) => LEVEL_COLORS[i];
export const levelWord = (i: number): Level => LEVELS[i];
