/**
 * manager-access setDataToChart / getManager without Solid.
 */

import './setup';
import { describe, expect, it, beforeAll, beforeEach } from 'bun:test';
import { installLightweightChartsMock } from './helpers/mock-lwc';

beforeAll(() => {
  installLightweightChartsMock();
});

const {
  getManager,
  setManager,
  getDrawingLayer,
  setDrawingLayer,
  setDataToChart,
} = await import('../src/chart/manager-access');
const { createBaseChart } = await import('../src/chart/series-factory');

describe('manager-access', () => {
  beforeEach(() => {
    setManager(undefined);
    setDrawingLayer(undefined);
  });

  it('get/set manager', () => {
    expect(getManager()).toBeUndefined();
    const el = document.createElement('div') as unknown as HTMLElement;
    const chart = createBaseChart(el);
    const fake = {
      getPane: () => undefined,
      clearTradeMarkers: () => {},
      chart,
    };
    setManager(fake as never);
    expect(getManager()).toBe(fake);
  });

  it('setDataToChart no-ops without manager', () => {
    setDataToChart([{ time: 1, open: 1, high: 1, low: 1, close: 1 }]);
  });

  it('setDataToChart fills candle and volume series', () => {
    // No #pane-price → drawing layer skipped (needs real SVG DOM)
    const el = document.createElement('div') as unknown as HTMLElement;
    document.body.appendChild(el as never);

    const chart = createBaseChart(el);
    const panes = new Map<string, { id: string; series: Record<string, unknown>; chart: typeof chart }>();
    panes.set('price', { id: 'price', series: {}, chart });
    panes.set('volume', { id: 'volume', series: {}, chart });

    setManager({
      getPane: (id: string) => panes.get(id),
      clearTradeMarkers: () => {},
    } as never);

    setDataToChart([
      { time: 1, open: 1, high: 2, low: 0.5, close: 1.5, volume: 10 },
      { time: 2, open: 1.5, high: 2.5, low: 1, close: 1.2, volume: 12 },
    ]);
    expect(panes.get('price')!.series['candle']).toBeDefined();
    expect(panes.get('volume')!.series['volume']).toBeDefined();
  });

  it('drawing layer get/set', () => {
    expect(getDrawingLayer()).toBeUndefined();
    setDrawingLayer({ destroy: () => {} } as never);
    expect(getDrawingLayer()).toBeDefined();
    setDrawingLayer(undefined);
  });
});
