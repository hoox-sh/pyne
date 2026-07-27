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

  it('maps trend/rect aliases and polyline points', () => {
    const list = normalizeScriptDrawings([
      {
        kind: 'trend',
        x1: 10,
        y1: 1,
        x2: 20,
        y2: 2,
        style: 'dashed',
        extend: 'right',
      },
      {
        type: 'rect',
        left: 5,
        top: 9,
        right: 15,
        bottom: 3,
        border_color: '#abc',
        border_width: 2,
        text: 'zone',
      },
      {
        type: 'text',
        time: 50,
        price: 7,
        text: 'lbl',
      },
      {
        type: 'polyline',
        points: [
          { t: 1, p: 1 },
          { time: 2, y: 3 },
          { bad: true },
        ],
        closed: true,
        color: '#0f0',
      },
      { type: 'polyline', points: [{ time: 1, price: 1 }] }, // too short
      'skip-me',
      null,
    ]);
    expect(list.map((d) => d.type)).toEqual(['line', 'box', 'label', 'polyline']);
    expect(list[0].extend).toBe('right');
    expect(list[1].text).toBe('zone');
    expect(list[1].width).toBe(2);
    expect(list[2].text).toBe('lbl');
    expect(list[3].points).toHaveLength(2);
    expect(list[3].closed).toBe(true);
  });
});
