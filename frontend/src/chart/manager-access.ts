/**
 * Imperative chart manager access without Solid UI imports.
 * Lets runner / streams / load-symbol work in unit tests without Lucide/Solid DOM.
 */

import type { PaneManager } from './pane-manager';
import { DrawingLayer } from './drawing-layer';
import { createCandleSeries, createVolumeSeries, TV } from './series-factory';
import { store, setDrawings } from '../store';
import type { Bar } from '../store/types';

let manager: PaneManager | undefined;
let drawingLayer: DrawingLayer | undefined;

export function getManager(): PaneManager | undefined {
  return manager;
}

export function setManager(m: PaneManager | undefined) {
  manager = m;
}

export function getDrawingLayer(): DrawingLayer | undefined {
  return drawingLayer;
}

export function setDrawingLayer(layer: DrawingLayer | undefined) {
  drawingLayer = layer;
}

function ensureDrawingLayer() {
  if (!manager || drawingLayer) return;
  const pricePane = manager.getPane('price');
  const candle = pricePane?.series['candle'];
  if (!pricePane || !candle) return;
  const el = typeof document !== 'undefined' ? document.getElementById('pane-price') : null;
  if (!el) return;

  drawingLayer = new DrawingLayer(el, pricePane.chart, candle as never);
  drawingLayer.setDrawings(store.drawings);
  drawingLayer.setTool(store.drawingTool);
  drawingLayer.setOnChange((list) => setDrawings(list));
}

export function setDataToChart(bars: Bar[]) {
  if (!manager) return;
  const pricePane = manager.getPane('price');
  const volPane = manager.getPane('volume');

  manager.clearTradeMarkers();

  if (pricePane && !pricePane.series['candle']) {
    pricePane.series['candle'] = createCandleSeries(pricePane.chart);
  }
  if (pricePane?.series['candle']) {
    pricePane.series['candle'].setData(
      bars.map((b) => ({
        time: b.time as never,
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
      })),
    );
    const last = bars[bars.length - 1];
    if (last) {
      const up = last.close >= last.open;
      pricePane.series['candle'].applyOptions({
        priceLineColor: up ? TV.up : TV.down,
      });
    }
    pricePane.chart.timeScale().fitContent();
  }

  if (volPane && !volPane.series['volume']) {
    volPane.series['volume'] = createVolumeSeries(volPane.chart);
  }
  if (volPane?.series['volume']) {
    volPane.series['volume'].setData(
      bars.map((b) => ({
        time: b.time as never,
        value: b.volume ?? 0,
        color: b.close >= b.open ? 'rgba(94, 207, 138, 0.45)' : 'rgba(232, 93, 76, 0.45)',
      })),
    );
  }

  ensureDrawingLayer();
  drawingLayer?.setDrawings(store.drawings);
}

export { getActiveDrawingLayer } from './drawing-layer';
