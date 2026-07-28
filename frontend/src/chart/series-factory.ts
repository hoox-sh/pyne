// Copyright (C) 2024-2026 jango_blockchained
//
// This file is part of pynescript.
//
// pynescript is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// pynescript is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
//
// SPDX-License-Identifier: AGPL-3.0-or-later

import {
  createChart,
  ColorType,
  CrosshairMode,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  AreaSeries,
  type IChartApi,
  type ISeriesApi,
  type LineWidth,
} from 'lightweight-charts';

/** Void canvas + void indigo brand — matches landing pack + index.css tokens */
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
  /** hoox void pack accent oklch(0.74 0.16 277) */
  indigo: '#939fff',
  indigoSoft: 'rgba(147, 159, 255, 0.38)',
  /** @deprecated use indigo */
  flieder: '#939fff',
  /** @deprecated use indigoSoft */
  fliederSoft: 'rgba(147, 159, 255, 0.38)',
  green: '#8ef5a8',
  orange: '#e8a03a',
};

/** Plot colors: void indigo, lightgreen, orange, then muted fillers */
export const PLOT_PALETTE = [
  '#939fff',
  '#8ef5a8',
  '#e8a03a',
  '#6ec8d4',
  '#a7b4ff',
  '#5ecf8a',
  '#e85d4c',
  '#8b8e9c',
];

/**
 * Fixed right price-scale width shared by every pane so plot areas share the
 * same right edge (price labels, 0–100 indicators, volume, equity).
 */
export const RIGHT_PRICE_SCALE_WIDTH = 72;

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
      minimumWidth: RIGHT_PRICE_SCALE_WIDTH,
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
      // Never auto-scroll when a live bar is appended / updated
      shiftVisibleRangeOnNewBar: false,
      allowShiftVisibleRangeOnWhitespaceReplacement: false,
      rightBarStaysOnScroll: true,
    },
    crosshair: {
      mode: CrosshairMode.Normal,
      vertLine: {
        color: TV.indigoSoft,
        width: 1 as LineWidth,
        style: 2,
        labelBackgroundColor: TV.elev,
      },
      horzLine: {
        color: TV.indigoSoft,
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
    priceLineColor: TV.indigoSoft,
    priceLineWidth: 1 as LineWidth,
    priceLineStyle: 2,
  };
  const series = paneIndex !== undefined
    ? chart.addSeries(CandlestickSeries, opts, paneIndex)
    : chart.addSeries(CandlestickSeries, opts);
  chart.priceScale('right').applyOptions({
    borderColor: TV.border,
    textColor: TV.textDim,
    minimumWidth: RIGHT_PRICE_SCALE_WIDTH,
  });
  return series;
}

export function createVolumeSeries(chart: IChartApi, paneIndex?: number): ISeriesApi<'Histogram'> {
  // Use the main right scale (same width as price pane) so chart edges align
  const opts = {
    priceFormat: { type: 'volume' as const },
    priceScaleId: 'right',
    lastValueVisible: true,
    priceLineVisible: false,
  };
  const series = paneIndex !== undefined
    ? chart.addSeries(HistogramSeries, opts, paneIndex)
    : chart.addSeries(HistogramSeries, opts);
  chart.priceScale('right').applyOptions({
    scaleMargins: { top: 0.12, bottom: 0.02 },
    borderVisible: true,
    borderColor: TV.border,
    textColor: TV.textDim,
    minimumWidth: RIGHT_PRICE_SCALE_WIDTH,
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

/** Equity curve — void indigo fill on void canvas */
export function createAreaSeries(
  chart: IChartApi,
  name: string,
  color = TV.indigo,
  paneIndex?: number,
): ISeriesApi<'Area'> {
  const opts = {
    lineColor: color,
    topColor: 'rgba(147, 159, 255, 0.28)',
    bottomColor: 'rgba(147, 159, 255, 0.02)',
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
    ? chart.addSeries(AreaSeries, opts, paneIndex)
    : chart.addSeries(AreaSeries, opts);
}
