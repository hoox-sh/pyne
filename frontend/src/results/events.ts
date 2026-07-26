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

function barCloseAt(
  bars: Bar[] | undefined,
  barTime: number | undefined,
  barIndex: number | undefined,
): number | undefined {
  if (!bars?.length) return undefined;
  if (barTime != null && Number.isFinite(barTime)) {
    const byTime = bars.find((b) => b.time === barTime);
    if (byTime) return byTime.close;
  }
  if (barIndex != null && Number.isFinite(barIndex) && barIndex >= 0 && barIndex < bars.length) {
    return bars[barIndex]!.close;
  }
  return undefined;
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
  const time =
    typeof r.time === 'number' && Number.isFinite(r.time)
      ? r.time
      : typeof r.bar_time === 'number' && Number.isFinite(r.bar_time)
        ? r.bar_time
        : undefined;
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
    bar_time: typeof r.bar_time === 'number' ? r.bar_time : time,
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

  const sorted = events.slice().sort((a, b) => (a.time || 0) - (b.time || 0));
  for (const ev of sorted) {
    const t = ev.time;
    if (t === undefined || !Number.isFinite(t)) continue;
    const kind = String(ev.type || ev.event || '').toLowerCase();
    const id = String(ev.id || '');
    const dir = String(ev.dir || '').toLowerCase();

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
