import { describe, expect, it } from 'bun:test';
import { normalizeScriptDrawings } from '../src/chart/pine-drawings.ts';

describe('normalizeScriptDrawings', () => {
  it('maps line/box/label API payloads', () => {
    const list = normalizeScriptDrawings([
      {
        type: 'line',
        t1: 100,
        p1: 10,
        t2: 200,
        p2: 20,
        color: '#F23645',
        width: 2,
      },
      {
        type: 'box',
        t1: 100,
        p1: 30,
        t2: 200,
        p2: 5,
        color: '#22AB94',
        bgcolor: 'rgba(0,0,0,0)',
      },
      { type: 'label', t1: 150, p1: 25, text: 'hi', color: '#2962FF', textcolor: '#fff' },
    ]);
    expect(list).toHaveLength(3);
    expect(list[0].type).toBe('line');
    expect(list[0].t2).toBe(200);
    expect(list[1].type).toBe('box');
    expect(list[2].text).toBe('hi');
  });

  it('skips incomplete objects', () => {
    expect(normalizeScriptDrawings([{ type: 'line', t1: 1 }])).toHaveLength(0);
    expect(normalizeScriptDrawings(null)).toHaveLength(0);
  });
});
