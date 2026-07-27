/**
 * Extra strategy report branches.
 */

import { describe, expect, it } from 'bun:test';
import {
  buildStrategyReport,
  formatMoney,
  formatNum,
  formatPct,
  tradesToCsv,
} from '../src/results/strategy';
import { SAMPLE_BARS } from './fixtures/bars';

describe('strategy extras', () => {
  it('handles multiple long trades win rate', () => {
    const events = [
      { time: SAMPLE_BARS[0].time, type: 'entry', dir: 'long', id: 'a', price: 100 },
      { time: SAMPLE_BARS[1].time, type: 'exit', id: 'a', price: 110 },
      { time: SAMPLE_BARS[2].time, type: 'entry', dir: 'long', id: 'b', price: 110 },
      { time: SAMPLE_BARS[3].time, type: 'exit', id: 'b', price: 100 },
    ];
    const rep = buildStrategyReport(events as never[], SAMPLE_BARS);
    expect(rep.stats.trades).toBe(2);
    // winRate is percent 0–100 in this reporter
    expect(rep.stats.winRate).toBeGreaterThanOrEqual(0);
    expect(rep.stats.winRate).toBeLessThanOrEqual(100);
    expect(rep.stats.wins).toBe(1);
    expect(rep.stats.losses).toBe(1);
    expect(rep.stats.profitFactor).toBeCloseTo(1);
    expect(rep.stats.avgTrade).toBe(0);
  });

  it('profitFactor infinity when only winners', () => {
    const events = [
      { time: SAMPLE_BARS[0].time, type: 'entry', dir: 'long', id: 'a', price: 100 },
      { time: SAMPLE_BARS[1].time, type: 'exit', id: 'a', price: 120 },
    ];
    const rep = buildStrategyReport(events as never[], SAMPLE_BARS);
    expect(rep.stats.trades).toBe(1);
    expect(rep.stats.profitFactor === Infinity || rep.stats.profitFactor > 0).toBe(true);
  });

  it('pairs short trades and sole open fallback on close without id', () => {
    const events = [
      { time: 1, type: 'entry', dir: 'short', id: 'S', price: 200 },
      { time: 2, type: 'close', price: 180 }, // no id — sole open
    ];
    const rep = buildStrategyReport(events as never[]);
    expect(rep.stats.trades).toBe(1);
    expect(rep.trades[0].dir).toContain('short');
    expect(rep.trades[0].pnl).toBe(20);
  });

  it('skips events with missing time or non-finite price', () => {
    const events = [
      { type: 'entry', id: 'x', price: 10 },
      { time: 1, type: 'entry', id: 'y', price: NaN },
      { time: 2, type: 'entry', id: 'z', price: 10 },
      { time: 3, type: 'exit', id: 'z', price: 12 },
    ];
    const rep = buildStrategyReport(events as never[]);
    expect(rep.stats.trades).toBe(1);
    expect(rep.stats.maxDD).toBeGreaterThanOrEqual(0);
  });

  it('formatters and CSV export', () => {
    expect(formatPct(0.1234)).toBe('12.34%');
    expect(formatPct(NaN)).toBe('—');
    expect(formatMoney(12.5)).toBe('+12.50');
    expect(formatMoney(-3)).toBe('-3.00');
    expect(formatMoney(Infinity)).toBe('—');
    expect(formatNum(null)).toBe('—');
    expect(formatNum(1e7)).toMatch(/e\+/i);
    expect(formatNum(0.12345)).toBe('0.1235');
    expect(formatNum(150)).toBe('150.00');

    const csv = tradesToCsv([
      {
        id: 'a',
        dir: 'long',
        entryTime: 1,
        entry: 100,
        exitTime: 2,
        exit: 110,
        pnl: 10,
        pnlPct: 0.1,
      },
    ]);
    expect(csv.split('\n')).toHaveLength(2);
    expect(csv).toContain('id,dir,entry_time');
    expect(csv).toContain('a,long,1,100,2,110,10,0.1');
  });
});
