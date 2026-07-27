import type { Bar } from '../../src/store/types';

/** Deterministic OHLCV sample (oldest → newest). */
export function makeBars(n = 10, startTime = 1_700_000_000, step = 86_400): Bar[] {
  const out: Bar[] = [];
  let price = 100;
  for (let i = 0; i < n; i++) {
    const open = price;
    const close = price + (i % 2 === 0 ? 1 : -0.5);
    out.push({
      time: startTime + i * step,
      open,
      high: Math.max(open, close) + 0.5,
      low: Math.min(open, close) - 0.5,
      close,
      volume: 1000 + i,
    });
    price = close;
  }
  return out;
}

export const SAMPLE_BARS = makeBars(5);
