// applyNow(payload): repaint every live region of the dashboard from a /now
// response. Runs on the client on first load and on each poll. Updates existing
// elements in place (by id/class) so the tide-gauge and bar transitions animate
// and there's no layout thrash — the server-rendered structure stays put.

import { LEVELS, LEVEL_COLORS, totalLevel, loHi, DAYS, type Day } from './busyness';
import { renderSpark } from './spark';
import { renderBars, scaleMaxOf } from './bars';
import { sceneTime, compareText, compareColors } from './format';
import type { NowPayload } from './api';

function setText(id: string, value: string | number): void {
  const el = document.getElementById(id);
  if (el) el.textContent = String(value);
}

function applyGauge(idx: number): void {
  const tide = document.getElementById('tide');
  if (!tide) return;
  tide.querySelectorAll<HTMLElement>('.tide-seg').forEach((el, i) => {
    const c = LEVEL_COLORS[i];
    const filled = i <= idx;
    el.style.background = filled ? c : 'var(--card-2)';
    el.style.border = `1px solid ${filled ? c : 'var(--border)'}`;
    el.style.boxShadow = i === idx ? `0 0 0 3px color-mix(in srgb, ${c} 32%, transparent)` : 'none';
  });
}

export function applyNow(now: NowPayload): void {
  const idx = totalLevel(now.total);
  const { lo, hi } = loHi(now.total);
  const scene = sceneTime(now.lastUpdated);

  // Hero — count + range
  setText('hero-total', now.total);
  setText('hero-lo', lo);
  setText('hero-hi', hi);
  setText('hero-ts', scene.timestamp);

  // Hero — level word
  const word = document.getElementById('hero-word');
  if (word) {
    word.textContent = LEVELS[idx];
    word.style.color = LEVEL_COLORS[idx];
  }

  // Hero — comparison badge + subline
  const { color, bg, busier } = compareColors(now.comparePct);
  const cmp = document.getElementById('hero-compare');
  if (cmp) {
    cmp.style.background = bg;
    cmp.style.color = color;
  }
  setText('hero-compare-text', compareText(now.comparePct));
  const chev = document.getElementById('hero-compare-chev');
  if (chev) chev.style.transform = busier ? '' : 'rotate(180deg)';

  applyGauge(idx);

  // Weather
  const w = now.weather;
  setText('wx-temp', `${w.tempC}°`);
  setText('wx-cond', `${w.condition} · feels like ${w.feelsLikeC}°`);
  setText('wx-wind', w.windKmh);
  setText('wx-wind-dir', w.windDir);
  setText('wx-rise', w.sunrise);
  setText('wx-set', w.sunset);
  setText('wx-lake', w.lake);

  // Today's trend
  const trendEl = document.getElementById('trend-svg');
  if (trendEl) trendEl.innerHTML = renderSpark(now.trend, now.nowHour);

  // Popular times: refresh the switcher's data source, then repaint whichever
  // day is currently selected (keeping the user's choice across polls).
  const scaleMax = scaleMaxOf(now.popularByDay);
  const todayDay: Day = DAYS.includes(scene.todayDay) ? scene.todayDay : 'Thu';
  const dataEl = document.getElementById('pop-data');
  if (dataEl) {
    dataEl.textContent = JSON.stringify({
      popularByDay: now.popularByDay,
      todayDay,
      nowHour: now.nowHour,
      scaleMax,
    });
  }
  const chips = document.getElementById('day-chips');
  const active = chips?.querySelector<HTMLButtonElement>('button.chip.active');
  const day = (active?.dataset.day as string) ?? todayDay;
  const bars = document.getElementById('pop-bars');
  if (bars && now.popularByDay[day]) {
    bars.innerHTML = renderBars(now.popularByDay[day], day === todayDay ? now.nowHour : null, scaleMax);
  }
}
