import type { IChartApi, ISeriesApi, UTCTimestamp } from 'lightweight-charts';
import { createBaseChart, createCandleSeries, createVolumeSeries, createLineSeries, PLOT_PALETTE } from './series-factory';
import type { Bar } from '../store/types';

export interface ManagedPane {
  id: string;
  type: string;
  chart: IChartApi;
  series: Record<string, ISeriesApi<any>>;
  visible: boolean;
  label: string;
  resizeObserver: ResizeObserver | null;
}

export class PaneManager {
  private panes: Map<string, ManagedPane> = new Map();
  private container: HTMLElement;
  private suppressSync = false;

  constructor(container: HTMLElement) {
    this.container = container;
  }

  getPane(id: string): ManagedPane | undefined {
    return this.panes.get(id);
  }

  getAllPanes(): ManagedPane[] {
    return Array.from(this.panes.values());
  }

  createPane(id: string, type: string, label: string, height?: number): ManagedPane {
    const div = document.createElement('div');
    div.id = `pane-${id}`;
    div.className = 'relative';
    if (height) div.style.height = `${height}px`;
    else div.style.flex = '1 1 auto';
    div.style.minHeight = '0';

    const labelEl = document.createElement('span');
    labelEl.className = 'absolute top-1 left-2 text-[10px] text-text-dim uppercase tracking-wider z-10 pointer-events-none bg-bg-base/70 px-1.5 py-0.5 rounded';
    labelEl.textContent = label;
    div.appendChild(labelEl);

    this.container.appendChild(div);

    const chart = createBaseChart(div, {
      timeScale: type === 'volume' ? { visible: false, borderColor: '#485c7b' } : undefined,
    });

    const ro = new ResizeObserver(() => {
      const rect = div.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        chart.applyOptions({ width: rect.width, height: rect.height });
      }
    });
    ro.observe(div);

    const pane: ManagedPane = { id, type, chart, series: {}, visible: true, label, resizeObserver: ro };
    this.panes.set(id, pane);

    return pane;
  }

  destroyPane(id: string) {
    const pane = this.panes.get(id);
    if (!pane) return;
    // Disconnect ResizeObserver to prevent memory leak
    if (pane.resizeObserver) {
      pane.resizeObserver.disconnect();
    }
    pane.chart.remove();
    const el = document.getElementById(`pane-${id}`);
    el?.remove();
    this.panes.delete(id);
  }

  setVisible(id: string, visible: boolean) {
    const pane = this.panes.get(id);
    if (!pane) return;
    pane.visible = visible;
    const el = document.getElementById(`pane-${id}`);
    if (el) el.style.display = visible ? '' : 'none';
    if (visible) {
      const rect = el?.getBoundingClientRect();
      if (rect) pane.chart.applyOptions({ width: rect.width, height: rect.height });
    }
  }

  setLabel(id: string, label: string) {
    const pane = this.panes.get(id);
    if (pane) pane.label = label;
    const el = document.getElementById(`pane-${id}`);
    const labelEl = el?.querySelector('span');
    if (labelEl) labelEl.textContent = label;
  }

  resize(id: string, height: number) {
    const el = document.getElementById(`pane-${id}`);
    if (el) el.style.height = `${height}px`;
    const pane = this.panes.get(id);
    if (pane) {
      const rect = el?.getBoundingClientRect();
      if (rect) pane.chart.applyOptions({ width: rect.width, height: height });
    }
  }

  syncTimeScales() {
    const panes = this.getAllPanes().filter((p) => p.type !== 'equity' && p.visible);
    if (panes.length < 2) return;
    const src = panes[0].chart;
    for (let i = 1; i < panes.length; i++) {
      src.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (this.suppressSync || !range) return;
        this.suppressSync = true;
        try { panes[i].chart.timeScale().setVisibleLogicalRange(range); } finally { this.suppressSync = false; }
      });
    }
  }

  syncCrosshair(onMove: (data: { time: any; point: { x: number; y: number } | null; seriesData: Map<ISeriesApi<any>, any> }) => void) {
    for (const pane of this.getAllPanes()) {
      pane.chart.subscribeCrosshairMove((param) => {
        if (!param.time || !param.point) {
          onMove({ time: null, point: null, seriesData: new Map() });
          return;
        }
        onMove({ time: param.time, point: param.point, seriesData: param.seriesData as Map<ISeriesApi<any>, any> });
      });
    }
  }

  fitContent() {
    const pricePane = this.panes.get('price');
    if (pricePane) pricePane.chart.timeScale().fitContent();
  }

  setData(paneId: string, seriesKey: string, data: any[]) {
    const pane = this.panes.get(paneId);
    if (!pane) return;
    const series = pane.series[seriesKey];
    if (series) series.setData(data);
  }

  appendBar(bar: Bar) {
    const pricePane = this.panes.get('price');
    if (pricePane?.series['candle']) {
      pricePane.series['candle'].update({
        time: bar.time, open: bar.open, high: bar.high, low: bar.low, close: bar.close,
      });
    }
    const volPane = this.panes.get('volume');
    if (volPane?.series['volume']) {
      volPane.series['volume'].update({
        time: bar.time, value: bar.volume ?? 0,
        color: bar.close >= bar.open ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)',
      });
    }
  }

  removeOverlays(paneId: string) {
    const pane = this.panes.get(paneId);
    if (!pane) return;
    const overlays = Object.keys(pane.series).filter((k) => k.startsWith('overlay_'));
    for (const k of overlays) {
      try { pane.chart.removeSeries(pane.series[k]); } catch {}
      delete pane.series[k];
    }
  }

  addOverlayLine(paneId: string, name: string, data: { time: number; value: number }[], color?: string) {
    const pane = this.panes.get(paneId);
    if (!pane) return;
    const overlayCount = Object.keys(pane.series).filter((k) => k.startsWith('overlay_')).length;
    const c = color || PLOT_PALETTE[overlayCount % PLOT_PALETTE.length];
    const series = createLineSeries(pane.chart, name, c);
    series.setData(data.map((d) => ({ time: d.time as UTCTimestamp, value: d.value })));
    pane.series[`overlay_${name}`] = series;
    return series;
  }

  dispose() {
    for (const pane of this.getAllPanes()) {
      this.destroyPane(pane.id);
    }
  }
}
