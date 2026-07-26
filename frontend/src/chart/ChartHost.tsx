import { Component, Show, createEffect, createMemo, onMount, onCleanup } from 'solid-js';
import { PaneManager } from './pane-manager';
import { createCandleSeries, createVolumeSeries, TV } from './series-factory';
import { DrawingLayer } from './drawing-layer';
import { DrawingToolbar } from './DrawingToolbar';
import { PineTableHud } from './PineTableHud';
import { store, setDrawings } from '../store';
import type { Bar } from '../store/types';

/** Imperative chart mount only — never put Solid children inside this node. */
let panesEl: HTMLDivElement | undefined;
let manager: PaneManager | undefined;
let drawingLayer: DrawingLayer | undefined;

export function getManager(): PaneManager | undefined {
  return manager;
}

export function getDrawingLayer(): DrawingLayer | undefined {
  return drawingLayer;
}

// re-export for callers that prefer ChartHost surface
export { getActiveDrawingLayer } from './drawing-layer';

function ensureDrawingLayer() {
  if (!manager || drawingLayer) return;
  const pricePane = manager.getPane('price');
  const candle = pricePane?.series['candle'];
  if (!pricePane || !candle) return;
  const el = document.getElementById('pane-price');
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

  // New OHLCV invalidates previous run overlays on price (caller re-runs if needed)
  manager.clearTradeMarkers();

  if (pricePane && !pricePane.series['candle']) {
    pricePane.series['candle'] = createCandleSeries(pricePane.chart);
  }
  if (pricePane?.series['candle']) {
    pricePane.series['candle'].setData(
      bars.map((b) => ({
        time: b.time as any,
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
      })),
    );
    // Last-value label tint: green if last bar up, coral if down
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
        time: b.time as any,
        value: b.volume ?? 0,
        color: b.close >= b.open ? 'rgba(94, 207, 138, 0.45)' : 'rgba(232, 93, 76, 0.45)',
      })),
    );
  }

  // Attach / refresh drawing layer once candles exist
  ensureDrawingLayer();
  drawingLayer?.setDrawings(store.drawings);
}

export const ChartHost: Component = () => {
  const emptyHint = createMemo(() => {
    if (store.bars.length > 0) return null;
    if (store.status === 'loading') return { title: 'Loading market data…', sub: store.statusMessage || '' };
    if (store.status === 'error') return { title: 'Could not load chart', sub: store.statusMessage || 'Try again' };
    if (store.status === 'running') return { title: 'Running script…', sub: store.statusMessage || '' };
    return {
      title: 'Load data to begin',
      sub: `${store.symbol} · ${store.interval} — press Load or pick a watchlist symbol`,
    };
  });

  onMount(() => {
    if (!panesEl) return;
    manager = new PaneManager(panesEl);

    for (const pane of store.panes) {
      manager.createPane(pane.id, pane.type, pane.label || pane.type, pane.height || undefined);
    }
    manager.syncTimeScales();
    manager.syncCrosshair(() => {});

    if (store.bars.length) {
      setDataToChart(store.bars);
    }
  });

  // Keep series in sync if bars change without going through loadSymbolData
  createEffect(() => {
    const bars = store.bars;
    if (manager && bars.length) setDataToChart(bars);
  });

  // Keep tool in sync when store changes from toolbar
  createEffect(() => {
    const tool = store.drawingTool;
    drawingLayer?.setTool(tool);
  });

  onCleanup(() => {
    if (drawingLayer) {
      drawingLayer.destroy();
      drawingLayer = undefined;
    }
    if (manager) {
      manager.dispose();
      manager = undefined;
    }
  });

  return (
    // Outer shell owns Solid children (empty overlay). PaneManager only
    // mutates the inner ref node — Solid must never reconcile that subtree
    // or it wipes LWC canvases when the empty-state <Show> flips off.
    <div class="flex-1 flex flex-col min-h-0 relative bg-bg-base">
      <div
        ref={(el) => {
          panesEl = el;
        }}
        class="flex-1 flex flex-col min-h-0"
        data-axis-panes
      />
      <Show when={store.bars.length > 0}>
        <DrawingToolbar />
        <PineTableHud />
      </Show>
      <Show when={emptyHint()}>
        {(hint) => (
          <div class="absolute inset-0 flex flex-col items-center justify-center gap-2 z-[5] pointer-events-none px-6">
            <div
              class={`text-[11px] tracking-[0.18em] uppercase font-medium ${
                store.status === 'error' ? 'text-red' : 'text-text-faint'
              }`}
            >
              {hint().title}
            </div>
            <Show when={hint().sub}>
              <div class="text-[11px] text-text-faint/80 font-mono text-center max-w-md">{hint().sub}</div>
            </Show>
            <Show when={store.status === 'loading' || store.status === 'running'}>
              <div class="mt-2 w-24 h-0.5 bg-border overflow-hidden">
                <div class="h-full w-1/2 bg-accent animate-pulse" />
              </div>
            </Show>
          </div>
        )}
      </Show>
    </div>
  );
};
