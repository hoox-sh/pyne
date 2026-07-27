import { Component, Show, createEffect, createMemo, onMount, onCleanup } from 'solid-js';
import { PaneManager } from './pane-manager';
import { DrawingToolbar } from './DrawingToolbar';
import { PineTableHud } from './PineTableHud';
import { store } from '../store';
import {
  getManager,
  setManager,
  getDrawingLayer,
  setDrawingLayer,
  setDataToChart,
  getActiveDrawingLayer,
} from './manager-access';

export {
  getManager,
  getDrawingLayer,
  setDataToChart,
  getActiveDrawingLayer,
} from './manager-access';

/** Imperative chart mount only — never put Solid children inside this node. */
let panesEl: HTMLDivElement | undefined;

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
    const manager = new PaneManager(panesEl);
    setManager(manager);

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
    if (getManager() && bars.length) setDataToChart(bars);
  });

  // Keep tool in sync when store changes from toolbar
  createEffect(() => {
    const tool = store.drawingTool;
    getDrawingLayer()?.setTool(tool);
  });

  onCleanup(() => {
    const drawingLayer = getDrawingLayer();
    if (drawingLayer) {
      drawingLayer.destroy();
      setDrawingLayer(undefined);
    }
    const manager = getManager();
    if (manager) {
      manager.dispose();
      setManager(undefined);
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
