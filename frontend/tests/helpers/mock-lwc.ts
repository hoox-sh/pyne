/**
 * Minimal lightweight-charts mock for series-factory / PaneManager tests.
 */

import { mock } from 'bun:test';

export type FakeSeries = {
  setData: (d: unknown) => void;
  applyOptions: (o: unknown) => void;
  priceScale: () => { applyOptions: (o: unknown) => void };
  setMarkers?: (m: unknown) => void;
};

export type FakeChart = {
  addSeries: (type: unknown, opts?: unknown, paneIndex?: number) => FakeSeries;
  applyOptions: (o: unknown) => void;
  remove: () => void;
  priceScale: (id: string) => { applyOptions: (o: unknown) => void };
  timeScale: () => {
    fitContent: () => void;
    subscribeVisibleLogicalRangeChange: (cb: (r: unknown) => void) => void;
    setVisibleLogicalRange: (r: unknown) => void;
    setVisibleRange: (r: unknown) => void;
    timeToCoordinate: (t: unknown) => number | null;
    coordinateToLogical: (c: number) => number | null;
  };
  subscribeCrosshairMove: (cb: (p: unknown) => void) => void;
  _series: FakeSeries[];
};

export function makeFakeChart(): FakeChart {
  const series: FakeSeries[] = [];
  const makeSeries = (): FakeSeries => {
    const s: FakeSeries = {
      setData: () => {},
      applyOptions: () => {},
      priceScale: () => ({ applyOptions: () => {} }),
    };
    series.push(s);
    return s;
  };
  let rangeCb: ((r: unknown) => void) | null = null;
  return {
    _series: series,
    addSeries: () => makeSeries(),
    applyOptions: () => {},
    remove: () => {},
    priceScale: () => ({ applyOptions: () => {} }),
    timeScale: () => ({
      fitContent: () => {},
      subscribeVisibleLogicalRangeChange: (cb) => {
        rangeCb = cb;
      },
      setVisibleLogicalRange: () => {},
      setVisibleRange: () => {},
      timeToCoordinate: () => 10,
      coordinateToLogical: () => 5,
    }),
    subscribeCrosshairMove: () => {},
  };
}

export function installLightweightChartsMock() {
  const charts: FakeChart[] = [];
  mock.module('lightweight-charts', () => ({
    createChart: () => {
      const c = makeFakeChart();
      charts.push(c);
      return c;
    },
    createSeriesMarkers: (_series: unknown, markers: unknown) => ({
      setMarkers: () => {},
      markers: () => markers,
    }),
    ColorType: { Solid: 'solid' },
    CrosshairMode: { Normal: 0 },
    CandlestickSeries: 'CandlestickSeries',
    HistogramSeries: 'HistogramSeries',
    LineSeries: 'LineSeries',
    AreaSeries: 'AreaSeries',
  }));
  return charts;
}
