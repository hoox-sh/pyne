/**
 * PaneManager.syncOverlayLines updates in place without destroy flash.
 */

import './setup';
import { describe, expect, it, beforeAll, beforeEach, afterEach } from 'bun:test';
import { installLightweightChartsMock } from './helpers/mock-lwc';

beforeAll(() => {
  installLightweightChartsMock();
});

const { PaneManager } = await import('../src/chart/pane-manager');

describe('syncOverlayLines', () => {
  let root: HTMLElement;
  let pm: InstanceType<typeof PaneManager>;

  beforeEach(() => {
    root = document.createElement('div');
    document.body.appendChild(root);
    pm = new PaneManager(root);
    pm.createPane('price', 'price', 'Price');
  });

  afterEach(() => {
    try {
      pm.dispose();
    } catch {
      /* ignore */
    }
    root?.remove();
    document.getElementById('pane-price')?.remove();
  });

  it('creates overlay series then updates data in place', () => {
    const data1 = [
      { time: 1, value: 10 },
      { time: 2, value: 12 },
    ];
    pm.syncOverlayLines('price', [{ name: 'plotA', data: data1, color: '#fff' }]);
    const pane = pm.getPane('price')!;
    expect(pane.series['overlay_plotA']).toBeDefined();
    const series = pane.series['overlay_plotA'];
    let setCount = 0;
    const orig = series.setData.bind(series);
    series.setData = (d: unknown) => {
      setCount += 1;
      return orig(d);
    };

    pm.syncOverlayLines('price', [
      {
        name: 'plotA',
        data: [
          { time: 1, value: 11 },
          { time: 2, value: 13 },
        ],
        color: '#fff',
      },
    ]);
    expect(setCount).toBe(1);
    // same key — not recreated as a different object identity requirement;
    // series map still has the key
    expect(pane.series['overlay_plotA']).toBe(series);
  });

  it('removes stale overlay keys', () => {
    pm.syncOverlayLines('price', [
      { name: 'a', data: [{ time: 1, value: 1 }] },
      { name: 'b', data: [{ time: 1, value: 2 }] },
    ]);
    const pane = pm.getPane('price')!;
    expect(pane.series['overlay_a']).toBeDefined();
    expect(pane.series['overlay_b']).toBeDefined();

    pm.syncOverlayLines('price', [{ name: 'a', data: [{ time: 1, value: 3 }] }]);
    expect(pane.series['overlay_a']).toBeDefined();
    expect(pane.series['overlay_b']).toBeUndefined();
  });
});
