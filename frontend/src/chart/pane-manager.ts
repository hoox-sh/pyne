import {
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type SeriesMarker,
  type UTCTimestamp,
} from 'lightweight-charts';
import {
  createBaseChart,
  createLineSeries,
  createAreaSeries,
  PLOT_PALETTE,
  TV,
} from './series-factory';
import type { Bar } from '../store/types';
import { resizePane } from '../store';
import type { TradeMarker } from '../results/events';

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
  /** LWC v5 markers plugin attached to the price candle series */
  private candleMarkers: ISeriesMarkersPluginApi<UTCTimestamp> | null = null;

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
    // Horizontal resize handle above this pane (except first)
    if (this.panes.size > 0) {
      this.attachPaneResizeHandle(id);
    }

    const div = document.createElement('div');
    div.id = `pane-${id}`;
    div.className = 'relative';
    div.dataset.paneId = id;
    if (height) {
      div.style.height = `${height}px`;
      div.style.flex = '0 0 auto';
    } else {
      div.style.flex = '1 1 auto';
    }
    div.style.minHeight = type === 'volume' ? '72px' : '48px';
    div.style.background = '#0a0b10';

    const labelEl = document.createElement('span');
    labelEl.className =
      'absolute top-1 left-2 text-[10px] text-text-dim uppercase tracking-wider z-10 pointer-events-none bg-bg-base/90 px-1.5 py-0.5 border border-border-soft';
    labelEl.textContent = label;
    div.appendChild(labelEl);

    this.container.appendChild(div);

    const chart = createBaseChart(div, {
      timeScale:
        type === 'volume' || type === 'indicator' || type === 'equity'
          ? { visible: false, borderColor: '#3a3d4a', borderVisible: false }
          : undefined,
      rightPriceScale:
        type === 'volume'
          ? { borderColor: '#3a3d4a', scaleMargins: { top: 0.15, bottom: 0.02 }, minimumWidth: 54 }
          : type === 'equity'
            ? { borderColor: TV.border, scaleMargins: { top: 0.1, bottom: 0.05 }, minimumWidth: 54 }
            : undefined,
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
    document.getElementById(`pane-handle-${id}`)?.remove();
    this.panes.delete(id);
  }

  /**
   * Drag handle above `belowId` — resizes the pane above by changing pixel heights.
   */
  private attachPaneResizeHandle(belowId: string) {
    const handle = document.createElement('div');
    handle.id = `pane-handle-${belowId}`;
    handle.className = 'sc-pane-resize-handle';
    handle.title = 'Drag to resize panes';
    handle.setAttribute('role', 'separator');
    handle.setAttribute('aria-orientation', 'horizontal');

    let dragging = false;
    let startY = 0;
    let aboveStart = 0;
    let belowStart = 0;
    let aboveEl: HTMLElement | null = null;
    let belowEl: HTMLElement | null = null;

    handle.addEventListener('pointerdown', (e) => {
      e.preventDefault();
      belowEl = document.getElementById(`pane-${belowId}`);
      // Previous sibling pane element (skip handles)
      let prev = handle.previousElementSibling as HTMLElement | null;
      while (prev && !prev.id?.startsWith('pane-')) {
        prev = prev.previousElementSibling as HTMLElement | null;
      }
      aboveEl = prev;
      if (!aboveEl || !belowEl) return;
      dragging = true;
      startY = e.clientY;
      aboveStart = aboveEl.getBoundingClientRect().height;
      belowStart = belowEl.getBoundingClientRect().height;
      handle.setPointerCapture(e.pointerId);
      document.body.style.cursor = 'row-resize';
      document.body.style.userSelect = 'none';
    });

    handle.addEventListener('pointermove', (e) => {
      if (!dragging || !aboveEl || !belowEl) return;
      const dy = e.clientY - startY;
      const minAbove = 48;
      const minBelow = belowEl.dataset.paneId === 'volume' ? 72 : 48;
      let newAbove = aboveStart + dy;
      let newBelow = belowStart - dy;
      if (newAbove < minAbove) {
        newBelow -= minAbove - newAbove;
        newAbove = minAbove;
      }
      if (newBelow < minBelow) {
        newAbove -= minBelow - newBelow;
        newBelow = minBelow;
      }
      if (newAbove < minAbove || newBelow < minBelow) return;

      aboveEl.style.flex = '0 0 auto';
      belowEl.style.flex = '0 0 auto';
      aboveEl.style.height = `${newAbove}px`;
      belowEl.style.height = `${newBelow}px`;

      const aboveId = aboveEl.id.replace(/^pane-/, '');
      this.resize(aboveId, newAbove);
      this.resize(belowId, newBelow);
    });

    const endDrag = (e: PointerEvent) => {
      if (!dragging) return;
      dragging = false;
      try {
        handle.releasePointerCapture(e.pointerId);
      } catch {
        /* ignore */
      }
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      // Persist heights into store
      if (aboveEl && belowEl) {
        const aboveId = aboveEl.id.replace(/^pane-/, '');
        const ah = aboveEl.getBoundingClientRect().height;
        const bh = belowEl.getBoundingClientRect().height;
        resizePane(aboveId, Math.round(ah));
        resizePane(belowId, Math.round(bh));
      }
    };
    handle.addEventListener('pointerup', endDrag);
    handle.addEventListener('pointercancel', endDrag);

    this.container.appendChild(handle);
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
    // Include equity so trade curve tracks price/volume range
    const panes = this.getAllPanes().filter((p) => p.visible);
    if (panes.length < 2) return;
    const src = panes[0].chart;
    for (let i = 1; i < panes.length; i++) {
      const target = panes[i].chart;
      src.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (this.suppressSync || !range) return;
        this.suppressSync = true;
        try {
          target.timeScale().setVisibleLogicalRange(range);
        } finally {
          this.suppressSync = false;
        }
      });
    }
  }

  /**
   * Attach or update entry/exit markers on the price candle series (LWC v5).
   */
  setTradeMarkers(markers: TradeMarker[]) {
    const pricePane = this.panes.get('price');
    const candle = pricePane?.series['candle'];
    if (!candle) return;

    const seriesMarkers: SeriesMarker<UTCTimestamp>[] = markers.map((m) => ({
      time: m.time as UTCTimestamp,
      position: m.position,
      color: m.color,
      shape: m.shape,
      text: m.text,
    }));

    if (!this.candleMarkers) {
      this.candleMarkers = createSeriesMarkers(candle, seriesMarkers);
    } else {
      this.candleMarkers.setMarkers(seriesMarkers);
    }
  }

  clearTradeMarkers() {
    if (this.candleMarkers) {
      this.candleMarkers.setMarkers([]);
    }
  }

  /**
   * Show / hide equity pane and set area series data.
   * Creates the pane on first use (height 100px).
   */
  setEquityCurve(points: { time: number; value: number }[]) {
    if (!points.length) {
      this.hideEquityPane();
      return;
    }

    let pane = this.panes.get('equity');
    if (!pane) {
      pane = this.createPane('equity', 'equity', 'Equity', 100);
      pane.series['equity'] = createAreaSeries(pane.chart, 'Equity', TV.indigo);
      this.syncTimeScales();
    } else {
      this.setVisible('equity', true);
      if (!pane.series['equity']) {
        pane.series['equity'] = createAreaSeries(pane.chart, 'Equity', TV.indigo);
      }
    }

    pane.series['equity'].setData(
      points.map((p) => ({ time: p.time as UTCTimestamp, value: p.value })),
    );
  }

  hideEquityPane() {
    const pane = this.panes.get('equity');
    if (!pane) return;
    if (pane.series['equity']) {
      try {
        pane.series['equity'].setData([]);
      } catch {
        /* ignore */
      }
    }
    this.setVisible('equity', false);
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
        time: bar.time as UTCTimestamp,
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close,
      });
      // Tint last-price line to bar direction
      try {
        const up = bar.close >= bar.open;
        pricePane.series['candle'].applyOptions({
          priceLineColor: up ? 'rgba(94, 207, 138, 0.55)' : 'rgba(232, 93, 76, 0.55)',
        });
      } catch {
        /* ignore */
      }
    }
    const volPane = this.panes.get('volume');
    if (volPane?.series['volume']) {
      volPane.series['volume'].update({
        time: bar.time as UTCTimestamp,
        value: bar.volume ?? 0,
        color: bar.close >= bar.open ? 'rgba(94, 207, 138, 0.45)' : 'rgba(232, 93, 76, 0.45)',
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
    this.candleMarkers = null;
    for (const pane of this.getAllPanes()) {
      this.destroyPane(pane.id);
    }
  }
}
