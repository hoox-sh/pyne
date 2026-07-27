/**
 * OHLCV parse helpers.
 */

import { describe, expect, it } from 'bun:test';
import { parseOhlcvText, parseOhlcvFile } from '../src/data/parse-bars';

describe('parseOhlcvText', () => {
  it('parses headerless CSV', () => {
    const csv = `1700000000,1,2,0.5,1.5,10
1700086400,1.5,2.5,1,2,20`;
    const bars = parseOhlcvText(csv, 'data.csv');
    expect(bars).toHaveLength(2);
    expect(bars[0].open).toBe(1);
    expect(bars[1].close).toBe(2);
  });

  it('parses CSV with header', () => {
    const csv = `time,open,high,low,close,volume
2024-01-01T00:00:00Z,10,12,9,11,100`;
    const bars = parseOhlcvText(csv, 'x.csv');
    expect(bars).toHaveLength(1);
    expect(bars[0].close).toBe(11);
  });

  it('parses JSON array of objects', () => {
    const bars = parseOhlcvText(
      JSON.stringify([
        { time: 1700000000, open: 1, high: 2, low: 0.5, close: 1.5, volume: 9 },
      ]),
      'x.json',
    );
    expect(bars[0].volume).toBe(9);
  });

  it('parses JSON { bars: [...] }', () => {
    const bars = parseOhlcvText(
      JSON.stringify({ bars: [[1700000000, 1, 2, 0.5, 1.5]] }),
      'x.json',
    );
    expect(bars).toHaveLength(1);
  });

  it('converts ms timestamps', () => {
    const bars = parseOhlcvText(
      JSON.stringify([{ t: 1700000000000, o: 1, h: 2, l: 0.5, c: 1.5 }]),
      'x.json',
    );
    expect(bars[0].time).toBe(1700000000);
  });

  it('throws on empty', () => {
    expect(() => parseOhlcvText('   ')).toThrow(/empty/i);
  });

  it('throws when no valid rows', () => {
    expect(() => parseOhlcvText('not,enough\n1,2', 'x.csv')).toThrow(/No valid/);
  });

  it('parseOhlcvFile reads File', async () => {
    const f = new File(
      ['[{"time":1,"open":1,"high":1,"low":1,"close":1}]'],
      'bars.json',
      { type: 'application/json' },
    );
    const bars = await parseOhlcvFile(f);
    expect(bars).toHaveLength(1);
  });
});
