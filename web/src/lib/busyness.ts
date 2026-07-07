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

/** Total combined pier count → busyness level index (0–4). */
export function totalLevel(t: number): number {
  if (t <= 0) return 0;
  if (t <= 20) return 1;
  if (t <= 55) return 2;
  if (t <= 90) return 3;
  return 4;
}

/** A 0–100 "typical" value → level index, for coloring the popular-times bars. */
export function mapV(v: number): number {
  return v <= 8 ? 0 : v <= 28 ? 1 : v <= 58 ? 2 : v <= 82 ? 3 : 4;
}

/** Soften the single approximate count into a "likely lo–hi" range. */
export function loHi(total: number): { lo: number; hi: number } {
  return { lo: Math.round(total * 0.85), hi: Math.round(total * 1.15) };
}

export const levelColor = (i: number) => LEVEL_COLORS[i];
export const levelWord = (i: number): Level => LEVELS[i];
