import { Component, onMount, onCleanup } from 'solid-js';
import { PaneManager } from './pane-manager';
import { createCandleSeries, createVolumeSeries } from './series-factory';
import { store } from '../store';
import type { Bar } from '../store/types';

let containerRef!: HTMLDivElement;
let manager: PaneManager;

export function getManager(): PaneManager | undefined {
  return manager;
}

export function setDataToChart(bars: Bar[]) {
  if (!manager) return;
  const pricePane = manager.getPane('price');
  const volPane = manager.getPane('volume');

  if (pricePane && !pricePane.series['candle']) {
    pricePane.series['candle'] = createCandleSeries(pricePane.chart);
  }
  if (pricePane?.series['candle']) {
    pricePane.series['candle'].setData(
      bars.map((b) => ({ time: b.time as any, open: b.open, high: b.high, low: b.low, close: b.close }))
    );
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
        color: b.close >= b.open ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)',
      }))
    );
  }
}

export const ChartHost: Component = () => {
  onMount(() => {
    manager = new PaneManager(containerRef);

    for (const pane of store.panes) {
      manager.createPane(pane.id, pane.type, pane.label || pane.type, pane.height || undefined);
    }
    manager.syncTimeScales();
    manager.syncCrosshair(() => {}); // Subscribe for future crosshair tooltip use

    if (store.bars.length) {
      setDataToChart(store.bars);
    }
  });

  onCleanup(() => {
    if (manager) {
      manager.dispose();
    }
  });

  return (
    <div ref={containerRef!} class="flex-1 flex flex-col min-h-0 relative">
      <div class="absolute inset-0 flex items-center justify-center text-text-dim text-sm bg-bg-base z-[5]">
        {store.bars.length === 0 ? 'Load data to begin' : 'Loading chart…'}
      </div>
    </div>
  );
};
