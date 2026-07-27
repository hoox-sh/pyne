/**
 * series-factory with mocked lightweight-charts.
 */

import './setup';
import { mock, describe, expect, it, beforeAll } from 'bun:test';
import { installLightweightChartsMock, makeFakeChart } from './helpers/mock-lwc';

beforeAll(() => {
  installLightweightChartsMock();
});

// Dynamic import after mock
const {
  TV,
  PLOT_PALETTE,
  createBaseChart,
  createCandleSeries,
  createVolumeSeries,
  createLineSeries,
  createAreaSeries,
} = await import('../src/chart/series-factory');

describe('series-factory', () => {
  it('exports brand tokens and palette', () => {
    expect(TV.bg).toMatch(/^#/);
    expect(PLOT_PALETTE.length).toBeGreaterThan(3);
  });

  it('createBaseChart returns chart api', () => {
    const el = document.createElement('div') as unknown as HTMLElement;
    const chart = createBaseChart(el);
    expect(chart).toBeDefined();
    expect(typeof chart.addSeries).toBe('function');
  });

  it('createCandleSeries / volume / line / area attach series', () => {
    const chart = makeFakeChart() as never;
    const candle = createCandleSeries(chart);
    const vol = createVolumeSeries(chart, 1);
    const line = createLineSeries(chart, 'rsi', '#f00');
    const area = createAreaSeries(chart, 'eq');
    expect(candle).toBeDefined();
    expect(vol).toBeDefined();
    expect(line).toBeDefined();
    expect(area).toBeDefined();
  });
});
