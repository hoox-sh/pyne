import {
  createChart,
  ColorType,
  CrosshairMode,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type LineWidth,
} from 'lightweight-charts';

const TV = {
  bg: '#131722',
  grid: '#1e222d',
  text: '#d1d4dc',
  up: '#26a69a',
  down: '#ef5350',
};

export const PLOT_PALETTE = ['#2962ff', '#ff6d00', '#2e7d32', '#9c27b0', '#00bcd4', '#fdd835', '#e91e63', '#5d4037'];

export function createBaseChart(container: HTMLElement, options?: Record<string, unknown>): IChartApi {
  return createChart(container, {
    layout: { background: { type: ColorType.Solid, color: TV.bg }, textColor: TV.text },
    grid: { vertLines: { color: TV.grid }, horzLines: { color: TV.grid } },
    rightPriceScale: { borderColor: '#485c7b' },
    timeScale: { borderColor: '#485c7b', timeVisible: true, secondsVisible: false },
    crosshair: { mode: CrosshairMode.Normal },
    ...options,
  });
}

export function createCandleSeries(chart: IChartApi, paneIndex?: number): ISeriesApi<'Candlestick'> {
  const opts = {
    upColor: TV.up, downColor: TV.down,
    borderDownColor: TV.down, borderUpColor: TV.up,
    wickDownColor: TV.down, wickUpColor: TV.up,
  };
  return paneIndex !== undefined
    ? chart.addSeries(CandlestickSeries, opts, paneIndex)
    : chart.addSeries(CandlestickSeries, opts);
}

export function createVolumeSeries(chart: IChartApi, paneIndex?: number): ISeriesApi<'Histogram'> {
  const opts = { priceFormat: { type: 'volume' as const }, priceScaleId: '' };
  const series = paneIndex !== undefined
    ? chart.addSeries(HistogramSeries, opts, paneIndex)
    : chart.addSeries(HistogramSeries, opts);
  series.priceScale().applyOptions({ scaleMargins: { top: 0.1, bottom: 0.1 } });
  return series;
}

export function createLineSeries(chart: IChartApi, name: string, color: string, paneIndex?: number): ISeriesApi<'Line'> {
  const opts = {
    color,
    lineWidth: 2 as LineWidth,
    priceLineVisible: false,
    lastValueVisible: true,
    title: name,
  };
  return paneIndex !== undefined
    ? chart.addSeries(LineSeries, opts, paneIndex)
    : chart.addSeries(LineSeries, opts);
}
