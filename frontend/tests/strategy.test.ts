// Strategy tester + event normalizer (parity API shape → closed trades / markers).

import { describe, expect, it } from 'bun:test';
import { buildStrategyReport } from '../src/results/strategy.ts';
import {
  normalizeStrategyEvents,
  eventsToMarkers,
  buildEquityCurve,
} from '../src/results/events.ts';

describe('Strategy tester', () => {
  it('returns no trades for an empty event list', () => {
    const r = buildStrategyReport([]);
    expect(r.trades).toHaveLength(0);
    expect(r.stats.winRate).toBe(0);
    expect(r.stats.profitFactor).toBe(0);
  });

  it('pairs entries with subsequent closes (legacy fields)', () => {
    const events = [
      { time: 1, type: 'entry', id: 'L', dir: 'long', price: 100 },
      { time: 2, type: 'close', id: 'L', price: 110 },
    ];
    const r = buildStrategyReport(events);
    expect(r.trades).toHaveLength(1);
    expect(r.trades[0].pnl).toBe(10);
    expect(r.trades[0].pnlPct).toBeCloseTo(0.1);
  });

  it('pairs Pro API parity events (kind/bar_time/direction/ohlc)', () => {
    const events = [
      {
        kind: 'entry',
        id: 'L',
        direction: 'long',
        qty: 1,
        bar_index: 5,
        bar_time: 1300,
        ohlc: [100, 102, 99, 101],
        script_id: '',
        run_id: '',
      },
      {
        kind: 'close',
        id: 'L',
        direction: null,
        qty: 1,
        bar_index: 15,
        bar_time: 1900,
        ohlc: [110, 112, 109, 111],
        script_id: '',
        run_id: '',
      },
    ];
    const r = buildStrategyReport(events as any);
    expect(r.trades).toHaveLength(1);
    expect(r.trades[0].entry).toBe(101);
    expect(r.trades[0].exit).toBe(111);
    expect(r.trades[0].pnl).toBe(10);
  });

  it('resolves price from bars when ohlc is zeros', () => {
    const bars = [
      { time: 1000, open: 1, high: 2, low: 0.5, close: 50 },
      { time: 1060, open: 1, high: 2, low: 0.5, close: 55 },
    ];
    const events = [
      {
        kind: 'entry',
        id: 'A',
        direction: 'long',
        bar_time: 1000,
        bar_index: 0,
        ohlc: [0, 0, 0, 0],
      },
      {
        kind: 'close',
        id: 'A',
        bar_time: 1060,
        bar_index: 1,
        ohlc: [0, 0, 0, 0],
      },
    ];
    const r = buildStrategyReport(events as any, bars);
    expect(r.trades).toHaveLength(1);
    expect(r.trades[0].entry).toBe(50);
    expect(r.trades[0].exit).toBe(55);
    expect(r.trades[0].pnl).toBe(5);
  });

  it('inverts PnL for short positions', () => {
    const events = [
      { time: 1, type: 'entry', id: 'S', dir: 'short', price: 100 },
      { time: 2, type: 'close', id: 'S', price: 90 },
    ];
    const r = buildStrategyReport(events);
    expect(r.trades[0].pnl).toBe(10);
  });

  it('handles multiple trades and computes winRate + avg', () => {
    const events = [
      { time: 1, type: 'entry', id: 'A', dir: 'long', price: 100 },
      { time: 2, type: 'close', id: 'A', price: 110 },
      { time: 3, type: 'entry', id: 'B', dir: 'long', price: 50 },
      { time: 4, type: 'close', id: 'B', price: 45 },
      { time: 5, type: 'entry', id: 'C', dir: 'long', price: 200 },
      { time: 6, type: 'close', id: 'C', price: 220 },
    ];
    const r = buildStrategyReport(events);
    expect(r.trades).toHaveLength(3);
    expect(r.stats.wins).toBe(2);
    expect(r.stats.losses).toBe(1);
    expect(r.stats.totalPnl).toBe(25);
    expect(r.stats.winRate).toBeCloseTo(66.666, 1);
    expect(r.stats.avgTrade).toBeCloseTo(25 / 3);
  });

  it('ignores closes without a matching entry', () => {
    const events = [{ time: 1, type: 'close', id: 'X', price: 100 }];
    const r = buildStrategyReport(events);
    expect(r.trades).toHaveLength(0);
  });

  it('supports closing only the matching id', () => {
    const events = [
      { time: 1, type: 'entry', id: 'A', dir: 'long', price: 100 },
      { time: 2, type: 'entry', id: 'B', dir: 'long', price: 200 },
      { time: 3, type: 'close', id: 'A', price: 110 },
    ];
    const r = buildStrategyReport(events);
    expect(r.trades).toHaveLength(1);
    expect(r.trades[0].id).toBe('A');
    expect(r.trades[0].pnl).toBe(10);
  });

  it('computes profitFactor as Infinity when there are no losses', () => {
    const events = [
      { time: 1, type: 'entry', id: 'A', dir: 'long', price: 100 },
      { time: 2, type: 'close', id: 'A', price: 110 },
    ];
    const r = buildStrategyReport(events);
    expect(r.stats.profitFactor).toBe(Infinity);
  });
});

describe('eventsToMarkers', () => {
  it('builds long entry belowBar and exit aboveBar', () => {
    const events = normalizeStrategyEvents([
      { kind: 'entry', id: 'L', direction: 'long', bar_time: 10, ohlc: [1, 1, 1, 100] },
      { kind: 'close', id: 'L', bar_time: 20, ohlc: [1, 1, 1, 110] },
    ]);
    const markers = eventsToMarkers(events);
    expect(markers).toHaveLength(2);
    expect(markers[0].shape).toBe('arrowUp');
    expect(markers[0].position).toBe('belowBar');
    expect(markers[1].shape).toBe('arrowDown');
    expect(markers[1].position).toBe('aboveBar');
  });

  it('skips pending order events when includeOrders false', () => {
    const events = normalizeStrategyEvents(
      [
        { kind: 'order', id: 'P', bar_time: 5, ohlc: [1, 1, 1, 50] },
        { kind: 'entry', id: 'L', direction: 'long', bar_time: 10, ohlc: [1, 1, 1, 100] },
      ],
      { includeOrders: false },
    );
    expect(events.every((e) => e.type !== 'order')).toBe(true);
    expect(eventsToMarkers(events)).toHaveLength(1);
  });
});

describe('buildEquityCurve', () => {
  it('accumulates pnl on initial capital', () => {
    const curve = buildEquityCurve(
      [
        { exitTime: 2, pnl: 10 },
        { exitTime: 4, pnl: -5 },
      ],
      10000,
    );
    expect(curve).toEqual([
      { time: 2, value: 10010 },
      { time: 4, value: 10005 },
    ]);
  });
});
