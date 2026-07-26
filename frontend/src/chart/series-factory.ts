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

/** Void canvas + Hell Flieder brand — matches index.css tokens */
export const TV = {
  bg: '#0a0b10',
  panel: '#111218',
  elev: '#171821',
  grid: 'rgba(140, 130, 180, 0.07)',
  text: '#c8cad4',
  textDim: '#8b8e9c',
  up: '#5ecf8a',
  down: '#e85d4c',
  border: '#3a3d4a',
  flieder: '#c4b0f0',
  fliederSoft: 'rgba(196, 176, 240, 0.38)',
  green: '#8ef5a8',
  orange: '#e8a03a',
};

/** Plot colors: Hell Flieder, lightgreen, orange, then muted fillers */
export const PLOT_PALETTE = [
  '#c4b0f0',
  '#8ef5a8',
  '#e8a03a',
  '#6ec8d4',
  '#a78be6',
  '#5ecf8a',
  '#e85d4c',
  '#8b8e9c',
];

export function createBaseChart(container: HTMLElement, options?: Record<string, unknown>): IChartApi {
  return createChart(container, {
    layout: {
      background: { type: ColorType.Solid, color: TV.bg },
      textColor: TV.textDim,
      fontSize: 11,
      attributionLogo: false,
    },
    grid: {
      vertLines: { color: TV.grid },
      horzLines: { color: TV.grid },
    },
    rightPriceScale: {
      borderColor: TV.border,
      borderVisible: true,
      textColor: TV.textDim,
      entireTextOnly: false,
      minimumWidth: 54,
      scaleMargins: { top: 0.06, bottom: 0.06 },
    },
    leftPriceScale: {
      visible: false,
      borderColor: TV.border,
    },
    timeScale: {
      borderColor: TV.border,
      borderVisible: true,
      timeVisible: true,
      secondsVisible: false,
      ticksVisible: true,
    },
    crosshair: {
      mode: CrosshairMode.Normal,
      vertLine: {
        color: TV.fliederSoft,
        width: 1 as LineWidth,
        style: 2,
        labelBackgroundColor: TV.elev,
      },
      horzLine: {
        color: TV.fliederSoft,
        width: 1 as LineWidth,
        style: 2,
        labelBackgroundColor: TV.elev,
      },
    },
    handleScroll: { vertTouchDrag: true },
    ...options,
  });
}

export function createCandleSeries(chart: IChartApi, paneIndex?: number): ISeriesApi<'Candlestick'> {
  const opts = {
    upColor: TV.up,
    downColor: TV.down,
    borderDownColor: TV.down,
    borderUpColor: TV.up,
    wickDownColor: TV.down,
    wickUpColor: TV.up,
    lastValueVisible: true,
    priceLineVisible: true,
    priceLineColor: TV.fliederSoft,
    priceLineWidth: 1 as LineWidth,
    priceLineStyle: 2,
  };
  const series = paneIndex !== undefined
    ? chart.addSeries(CandlestickSeries, opts, paneIndex)
    : chart.addSeries(CandlestickSeries, opts);
  chart.priceScale('right').applyOptions({
    borderColor: TV.border,
    textColor: TV.textDim,
  });
  return series;
}

export function createVolumeSeries(chart: IChartApi, paneIndex?: number): ISeriesApi<'Histogram'> {
  const opts = {
    priceFormat: { type: 'volume' as const },
    priceScaleId: '',
    lastValueVisible: false,
    priceLineVisible: false,
  };
  const series = paneIndex !== undefined
    ? chart.addSeries(HistogramSeries, opts, paneIndex)
    : chart.addSeries(HistogramSeries, opts);
  series.priceScale().applyOptions({
    scaleMargins: { top: 0.72, bottom: 0 },
    borderVisible: false,
  });
  return series;
}

export function createLineSeries(chart: IChartApi, name: string, color: string, paneIndex?: number): ISeriesApi<'Line'> {
  const opts = {
    color,
    lineWidth: 2 as LineWidth,
    priceLineVisible: false,
    lastValueVisible: true,
    title: name,
    crosshairMarkerVisible: true,
    crosshairMarkerRadius: 3,
    crosshairMarkerBorderColor: TV.bg,
    crosshairMarkerBackgroundColor: color,
  };
  return paneIndex !== undefined
    ? chart.addSeries(LineSeries, opts, paneIndex)
    : chart.addSeries(LineSeries, opts);
}
