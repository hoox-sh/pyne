/**
 * Normalize Pro API / StrategyEvent parity payloads into the UI shape.
 *
 * Runtime emits: kind, direction, bar_time, bar_index, ohlc, id, qty, …
 * Legacy UI expected: type, dir, time, price, id.
 */

import type { Bar } from '../store/types';
import type { StrategyEvent } from './strategy';

export interface NormalizeOptions {
  /** OHLCV bars for price lookup when event.ohlc is empty */
  bars?: Bar[];
  /** Skip pending `order` / cancel noise for markers (default true for markers) */
  includeOrders?: boolean;
}

/** Align event times with chart bar units (sec vs ms). */
export function alignTimeToBars(t: number, bars?: Bar[]): number {
  if (!bars?.length || !Number.isFinite(t)) return t;
  const sample = bars[0]!.time;
  // Chart bars in ms, event in seconds
  if (sample > 1e12 && t < 1e12) return Math.floor(t * 1000);
  // Chart bars in seconds, event in ms
  if (sample < 1e12 && t > 1e12) return Math.floor(t / 1000);
  return t;
}

function barCloseAt(
  bars: Bar[] | undefined,
  barTime: number | undefined,
  barIndex: number | undefined,
): number | undefined {
  if (!bars?.length) return undefined;
  if (barTime != null && Number.isFinite(barTime)) {
    const aligned = alignTimeToBars(barTime, bars);
    const byTime = bars.find((b) => b.time === aligned);
    if (byTime) return byTime.close;
    // nearest bar (1 day tolerance in same units)
    let best: Bar | undefined;
    let bestD = Infinity;
    for (const b of bars) {
      const d = Math.abs(b.time - aligned);
      if (d < bestD) {
        bestD = d;
        best = b;
      }
    }
    if (best && bestD < Math.abs(sampleSpan(bars)) * 2) return best.close;
  }
  if (barIndex != null && Number.isFinite(barIndex) && barIndex >= 0 && barIndex < bars.length) {
    return bars[barIndex]!.close;
  }
  return undefined;
}

function sampleSpan(bars: Bar[]): number {
  if (bars.length < 2) return bars[0]!.time > 1e12 ? 86_400_000 : 86_400;
  return Math.abs(bars[1]!.time - bars[0]!.time) || 1;
}

function resolvePrice(raw: Record<string, unknown>, bars?: Bar[]): number | undefined {
  if (typeof raw.price === 'number' && Number.isFinite(raw.price)) return raw.price;

  const ohlc = raw.ohlc;
  if (Array.isArray(ohlc) && ohlc.length >= 4) {
    const close = Number(ohlc[3]);
    if (Number.isFinite(close) && close !== 0) return close;
    // Non-zero open/high/low also usable
    for (const i of [0, 1, 2]) {
      const v = Number(ohlc[i]);
      if (Number.isFinite(v) && v !== 0) return v;
    }
  }

  const barTime =
    typeof raw.bar_time === 'number'
      ? raw.bar_time
      : typeof raw.time === 'number'
        ? raw.time
        : undefined;
  const barIndex = typeof raw.bar_index === 'number' ? raw.bar_index : undefined;
  return barCloseAt(bars, barTime, barIndex);
}

/**
 * Map one raw event (parity or legacy) to StrategyEvent for Results / markers.
 */
export function normalizeStrategyEvent(
  raw: Record<string, unknown> | StrategyEvent,
  opts: NormalizeOptions = {},
): StrategyEvent {
  const r = raw as Record<string, unknown>;
  const kind = String(r.kind ?? r.type ?? r.event ?? '').toLowerCase();
  let time: number | undefined =
    typeof r.time === 'number' && Number.isFinite(r.time)
      ? r.time
      : typeof r.bar_time === 'number' && Number.isFinite(r.bar_time)
        ? r.bar_time
        : undefined;
  if (time != null) time = alignTimeToBars(time, opts.bars);
  const dir = String(r.dir ?? r.direction ?? '').toLowerCase() || undefined;
  const price = resolvePrice(r, opts.bars);

  return {
    ...r,
    type: kind || undefined,
    event: kind || undefined,
    kind,
    dir,
    direction: dir,
    time,
    bar_time: typeof r.bar_time === 'number' ? alignTimeToBars(r.bar_time, opts.bars) : time,
    bar_index: typeof r.bar_index === 'number' ? r.bar_index : undefined,
    price,
    id: r.id != null ? String(r.id) : undefined,
  };
}

export function normalizeStrategyEvents(
  events: unknown[] | undefined | null,
  opts: NormalizeOptions = {},
): StrategyEvent[] {
  if (!events?.length) return [];
  const includeOrders = opts.includeOrders !== false;
  const out: StrategyEvent[] = [];
  for (const ev of events) {
    if (!ev || typeof ev !== 'object') continue;
    const n = normalizeStrategyEvent(ev as Record<string, unknown>, opts);
    const kind = String(n.type || n.kind || '').toLowerCase();
    if (!includeOrders && (kind === 'order' || kind.startsWith('cancel'))) continue;
    out.push(n);
  }
  return out;
}

export interface TradeMarker {
  time: number;
  position: 'aboveBar' | 'belowBar' | 'inBar';
  color: string;
  shape: 'arrowUp' | 'arrowDown' | 'circle' | 'square';
  text: string;
}

const COLOR = {
  longEntry: '#5ecf8a',
  shortEntry: '#e8a03a',
  exit: '#e85d4c',
  order: '#8b8e9c',
};

/**
 * Build LWC series markers from normalized strategy events.
 * Tracks open position dir so exits get a sensible arrow direction.
 */
export function eventsToMarkers(events: StrategyEvent[]): TradeMarker[] {
  const openDir = new Map<string, string>();
  const markers: TradeMarker[] = [];

  const timeOf = (ev: StrategyEvent) => {
    if (typeof ev.time === 'number' && Number.isFinite(ev.time)) return ev.time;
    if (typeof ev.bar_time === 'number' && Number.isFinite(ev.bar_time)) return ev.bar_time;
    return undefined;
  };

  const sorted = events.slice().sort((a, b) => (timeOf(a) || 0) - (timeOf(b) || 0));
  for (const ev of sorted) {
    const t = timeOf(ev);
    if (t === undefined || !Number.isFinite(t)) continue;
    const kind = String(ev.type || ev.event || ev.kind || '').toLowerCase();
    const id = String(ev.id || '');
    const dir = String(ev.dir || ev.direction || '').toLowerCase();

    if (kind.includes('entry')) {
      const isShort = dir.includes('short');
      openDir.set(id || '_default', isShort ? 'short' : 'long');
      markers.push({
        time: t,
        position: isShort ? 'aboveBar' : 'belowBar',
        color: isShort ? COLOR.shortEntry : COLOR.longEntry,
        shape: isShort ? 'arrowDown' : 'arrowUp',
        text: id || (isShort ? 'S' : 'L'),
      });
    } else if (kind.includes('close') || kind.includes('exit')) {
      const open = openDir.get(id || '_default') || openDir.get('_default') || dir || 'long';
      const isShort = open.includes('short');
      openDir.delete(id || '_default');
      markers.push({
        time: t,
        position: isShort ? 'belowBar' : 'aboveBar',
        color: COLOR.exit,
        shape: isShort ? 'arrowUp' : 'arrowDown',
        text: id || 'X',
      });
    }
    // pending order / cancel skipped for chart noise
  }

  // LWC requires unique times sorted ascending; collapse same-bar by keeping last
  markers.sort((a, b) => a.time - b.time);
  const byTime = new Map<number, TradeMarker>();
  for (const m of markers) byTime.set(m.time, m);
  return Array.from(byTime.values()).sort((a, b) => a.time - b.time);
}

/**
 * Equity curve from closed trades: initial capital + cumulative PnL at each exit.
 */
export function buildEquityCurve(
  trades: { exitTime: number; pnl: number }[],
  initialCapital = 10_000,
): { time: number; value: number }[] {
  if (!trades.length) return [];
  const sorted = trades.slice().sort((a, b) => a.exitTime - b.exitTime);
  let equity = initialCapital;
  const points: { time: number; value: number }[] = [];
  // Seed at first entry-ish: start flat at first exit-1 is awkward; just step at exits
  for (const t of sorted) {
    if (!Number.isFinite(t.exitTime)) continue;
    equity += t.pnl;
    points.push({ time: t.exitTime, value: +equity.toFixed(2) });
  }
  return points;
}
