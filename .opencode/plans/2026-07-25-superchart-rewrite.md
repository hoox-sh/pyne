# SuperChart Lite Full Rewrite — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the SuperChart Lite PWA from vanilla JS to SolidJS + Lightweight Charts v5.2 with dynamic multi-pane support, live re-run on each bar, indicator panel, and multi-exchange streams.

**Architecture:** SolidJS SPA with fine-grained reactivity, single LWC v5.2 chart instance using native multi-pane API (`addSeries` with `paneIndex`, `PaneApi`, resizable separators), Vite build, Tailwind CSS v4 styling, CodeMirror 6 editor.

**Tech Stack:** SolidJS, Lightweight Charts v5.2, Vite, TypeScript, Tailwind CSS v4, CodeMirror 6, Bun (test runner)

---

## File Structure

```
frontend/
  vite.config.ts              — Vite config with SolidJS plugin + tailwindcss v4
  tsconfig.json               — TypeScript strict config
  package.json                — Dependencies: solid-js, lightweight-charts, @codemirror/*, tailwindcss
  index.html                  — Entry point (minimal, just <div id="app">)
  src/
    index.tsx                 — SolidJS render bootstrap
    index.css                 — Tailwind CSS entry + theme variables
    app.tsx                   — Root layout component
    store/
      index.ts                — createStore with persist middleware
      types.ts                — State type definitions
    chart/
      ChartHost.tsx           — Single LWC v5.2 chart container component
      pane-manager.ts         — Creates/destroys panes via paneIndex + moveToPane
      series-factory.ts       — LineSeries, HistogramSeries, CandlestickSeries factories
      crosshair-sync.ts       — Synced crosshair across panes
    editor/
      PineEditor.tsx          — CodeMirror 6 wrapper component
      pine-language.ts        — Custom PineScript language support
      tabbed-editor.tsx       — Multi-tab editor with persistence
    indicators/
      runner.ts               — Script execution (server + pyodide engines)
      IndicatorPanel.tsx      — Right sidebar indicator management UI
      IndicatorCard.tsx       — Single indicator card (toggle, colors, remove)
    streams/
      multiplex.ts            — Multi-exchange stream manager
      binance.ts              — Binance WS + REST
    ui/
      Topbar.tsx              — Toolbar (symbol, interval, live, theme, engine)
      StatusBar.tsx           — Bottom status bar
      SettingsDialog.tsx      — Settings modal
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/index.html`
- Create: `frontend/src/index.tsx`
- Create: `frontend/src/index.css`
- Create: `frontend/src/app.tsx`
- Create: `frontend/src/store/types.ts`
- Create: `frontend/src/store/index.ts`

- [ ] **Step 1: Initialize project**

```bash
cd frontend
bun init -y
bun add solid-js lightweight-charts
bun add -d @types/bun vite vite-plugin-solid typescript tailwindcss@4 @tailwindcss/vite
```

- [ ] **Step 2: Create `vite.config.ts`**

```ts
import { defineConfig } from 'vite';
import solid from 'vite-plugin-solid';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [solid(), tailwindcss()],
  build: {
    outDir: 'dist',
    target: 'esnext',
  },
  server: {
    port: 3000,
    proxy: {
      '/run': 'http://localhost:5002',
    },
  },
});
```

- [ ] **Step 3: Create `tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ESNext",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "jsx": "preserve",
    "jsxImportSource": "solid-js",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "outDir": "./dist",
    "rootDir": "./src",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist"]
}
```

- [ ] **Step 4: Create `index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>SuperChart Lite</title>
  <meta name="theme-color" content="#131722" />
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/index.tsx"></script>
</body>
</html>
```

- [ ] **Step 5: Create `src/index.tsx`**

```tsx
import { render } from 'solid-js/web';
import { App } from './app';
import './index.css';

const root = document.getElementById('app');
if (root) render(() => <App />, root);
```

- [ ] **Step 6: Create `src/index.css`**

```css
@import "tailwindcss";

@theme {
  --color-bg-base: #131722;
  --color-bg-panel: #1e222d;
  --color-bg-elev: #2a2e39;
  --color-bg-hover: #363a45;
  --color-border: #363c4e;
  --color-border-soft: #2a2e39;
  --color-text: #d1d4dc;
  --color-text-dim: #787b86;
  --color-text-faint: #5d606b;
  --color-accent: #2962ff;
  --color-accent-hover: #2979ff;
  --color-green: #26a69a;
  --color-red: #ef5350;
  --color-yellow: #ffb300;
  --color-purple: #9c27b0;
}

html, body {
  margin: 0;
  padding: 0;
  height: 100%;
  overflow: hidden;
}
```

- [ ] **Step 7: Create `src/app.tsx`**

```tsx
import { Component } from 'solid-js';

export const App: Component = () => {
  return (
    <div class="h-screen flex flex-col bg-bg-base text-text">
      <div class="flex-1 flex items-center justify-center text-text-dim">
        SuperChart Lite — loading…
      </div>
    </div>
  );
};
```

- [ ] **Step 8: Create `src/store/types.ts`**

```ts
export interface Bar {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

export interface Pane {
  id: string;
  type: 'price' | 'volume' | 'indicator' | 'equity';
  height: number;
  order: number;
  visible: boolean;
  label?: string;
}

export interface Indicator {
  id: string;
  name: string;
  code: string;
  paneId: string;
  visible: boolean;
  plots: Record<string, { color: string }>;
}

export interface AppState {
  bars: Bar[];
  symbol: string;
  interval: string;
  exchange: string;
  engine: string;
  endpoint: string;

  scripts: Indicator[];
  panes: Pane[];

  live: {
    active: boolean;
    needsRerun: boolean;
    lastBarTime: number;
  };

  theme: 'dark' | 'light';
  editor: { open: boolean; width: number };
  indicatorPanel: { open: boolean };
  stream: { status: 'connected' | 'disconnected' | 'error' };
}
```

- [ ] **Step 9: Create `src/store/index.ts`**

```ts
import { createStore } from 'solid-js/store';
import type { AppState, Bar, Indicator, Pane } from './types';

let nextId = 1;
const uid = () => `id_${nextId++}`;

const STORAGE_KEY = 'pynescript.superchart.v2';

const DEFAULTS: AppState = {
  bars: [],
  symbol: 'BTCUSDT',
  interval: '1d',
  exchange: 'binance',
  engine: 'server',
  endpoint: 'http://162.254.38.194:5002',
  scripts: [],
  panes: [
    { id: 'price', type: 'price', height: 0, order: 0, visible: true, label: 'Price' },
    { id: 'volume', type: 'volume', height: 120, order: 1, visible: true, label: 'Volume' },
  ],
  live: { active: false, needsRerun: false, lastBarTime: 0 },
  theme: 'dark',
  editor: { open: true, width: 460 },
  indicatorPanel: { open: false },
  stream: { status: 'disconnected' },
};

function loadPersisted(): Partial<AppState> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch {}
  return {};
}

export const [store, setStore] = createStore<AppState>({
  ...DEFAULTS,
  ...loadPersisted(),
});

let persistTimer: ReturnType<typeof setTimeout> | null = null;
export function persist() {
  if (persistTimer) clearTimeout(persistTimer);
  persistTimer = setTimeout(() => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(store)); } catch {}
  }, 200);
}

export function loadBars(bars: Bar[], symbol: string, interval: string, exchange: string) {
  setStore('bars', bars);
  setStore('symbol', symbol);
  setStore('interval', interval);
  setStore('exchange', exchange);
  persist();
}

export function addIndicator(name: string, code: string, paneId: string, plots: Record<string, { color: string }>) {
  const id = uid();
  setStore('scripts', (s) => [...s, { id, name, code, paneId, visible: true, plots }]);
  persist();
  return id;
}

export function removeIndicator(id: string) {
  setStore('scripts', (s) => s.filter((ind) => ind.id !== id));
  persist();
}

export function toggleIndicator(id: string) {
  setStore('scripts', (s) => s.map((ind) => ind.id === id ? { ...ind, visible: !ind.visible } : ind));
  persist();
}

export function setIndicatorColor(id: string, plotName: string, color: string) {
  setStore('scripts', (s) => s.map((ind) =>
    ind.id === id ? { ...ind, plots: { ...ind.plots, [plotName]: { color } } } : ind
  ));
  persist();
}

export function addPane(type: Pane['type'], label?: string): string {
  const id = uid();
  const maxOrder = Math.max(...store.panes.map((p) => p.order), -1);
  setStore('panes', (p) => [...p, { id, type, height: 120, order: maxOrder + 1, visible: true, label }]);
  persist();
  return id;
}

export function removePane(id: string) {
  setStore('panes', (p) => p.filter((pane) => pane.id !== id));
  persist();
}

export function resizePane(id: string, height: number) {
  setStore('panes', (p) => p.map((pane) => pane.id === id ? { ...pane, height } : pane));
  persist();
}

export function reorderPanes(orderedIds: string[]) {
  setStore('panes', (p) =>
    p.map((pane) => ({ ...pane, order: orderedIds.indexOf(pane.id) }))
      .sort((a, b) => a.order - b.order)
  );
  persist();
}

export function appendBar(bar: Bar) {
  setStore('bars', (b) => [...b, bar]);
  setStore('live', 'lastBarTime', bar.time);
  setStore('live', 'needsRerun', true);
  persist();
}

export function setLive(active: boolean) {
  setStore('live', 'active', active);
  persist();
}

export function toggleTheme() {
  const next = store.theme === 'dark' ? 'light' : 'dark';
  setStore('theme', next);
  document.documentElement.setAttribute('data-theme', next);
  persist();
}
```

- [ ] **Step 10: Verify build works**

```bash
cd frontend && bun run vite build
```

- [ ] **Step 11: Commit**

```bash
git add frontend/package.json frontend/vite.config.ts frontend/tsconfig.json frontend/index.html frontend/src/
git commit -m "feat: scaffold SolidJS + Vite + Tailwind + LWC v5.2 project"
```

---

## Task 2: Chart Host + LWC v5.2 Multi-Pane

**Files:**
- Create: `frontend/src/chart/ChartHost.tsx`
- Create: `frontend/src/chart/pane-manager.ts`
- Create: `frontend/src/chart/series-factory.ts`
- Create: `frontend/src/chart/crosshair-sync.ts`

- [ ] **Step 1: Create `src/chart/series-factory.ts`**

```ts
import { createChart, IChartApi, ISeriesApi } from 'lightweight-charts';

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
    layout: { background: { type: 'solid' as const, color: TV.bg }, textColor: TV.text },
    grid: { vertLines: { color: TV.grid }, horzLines: { color: TV.grid } },
    rightPriceScale: { borderColor: '#485c7b' },
    timeScale: { borderColor: '#485c7b', timeVisible: true, secondsVisible: false },
    crosshair: { mode: 0 },
    ...options,
  });
}

export function createCandleSeries(chart: IChartApi, paneIndex?: number): ISeriesApi<'Candlestick'> {
  const LW = (window as any).LightweightCharts;
  const opts = {
    upColor: TV.up, downColor: TV.down,
    borderDownColor: TV.down, borderUpColor: TV.up,
    wickDownColor: TV.down, wickUpColor: TV.up,
  };
  return paneIndex !== undefined
    ? chart.addSeries(LW.CandlestickSeries, opts, paneIndex)
    : chart.addSeries(LW.CandlestickSeries, opts);
}

export function createVolumeSeries(chart: IChartApi, paneIndex?: number): ISeriesApi<'Histogram'> {
  const LW = (window as any).LightweightCharts;
  const opts = { priceFormat: { type: 'volume' as const }, priceScaleId: '' };
  const series = paneIndex !== undefined
    ? chart.addSeries(LW.HistogramSeries, opts, paneIndex)
    : chart.addSeries(LW.HistogramSeries, opts);
  series.priceScale().applyOptions({ scaleMargins: { top: 0.1, bottom: 0.1 } });
  return series;
}

export function createLineSeries(chart: IChartApi, name: string, color: string, paneIndex?: number): ISeriesApi<'Line'> {
  const LW = (window as any).LightweightCharts;
  const opts = { color, lineWidth: 2, priceLineVisible: false, lastValueVisible: true, title: name };
  return paneIndex !== undefined
    ? chart.addSeries(LW.LineSeries, opts, paneIndex)
    : chart.addSeries(LW.LineSeries, opts);
}
```

- [ ] **Step 2: Create `src/chart/pane-manager.ts`**

```ts
import { IChartApi, ISeriesApi } from 'lightweight-charts';
import { createBaseChart, createCandleSeries, createVolumeSeries, PLOT_PALETTE } from './series-factory';
import type { Bar } from '../store/types';

export interface ManagedPane {
  id: string;
  type: string;
  chart: IChartApi;
  series: Record<string, ISeriesApi<any>>;
  visible: boolean;
  label: string;
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

    const pane: ManagedPane = { id, type, chart, series: {}, visible: true, label };
    this.panes.set(id, pane);

    const ro = new ResizeObserver(() => {
      const rect = div.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        chart.applyOptions({ width: rect.width, height: rect.height });
      }
    });
    ro.observe(div);

    return pane;
  }

  destroyPane(id: string) {
    const pane = this.panes.get(id);
    if (!pane) return;
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
    const panes = this.getAllPanes().filter((p) => p.type !== 'equity');
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
    series.setData(data);
    pane.series[`overlay_${name}`] = series;
    return series;
  }
}
```

- [ ] **Step 3: Create `src/chart/crosshair-sync.ts`**

```ts
import { IChartApi, ISeriesApi } from 'lightweight-charts';

export interface CrosshairData {
  time: any;
  point: { x: number; y: number } | null;
  seriesData: Map<ISeriesApi<any>, any>;
}

export function syncCrosshair(panes: IChartApi[], onMove: (data: CrosshairData) => void) {
  for (const chart of panes) {
    chart.subscribeCrosshairMove((param) => {
      if (!param.time || !param.point) {
        onMove({ time: null, point: null, seriesData: new Map() });
        return;
      }
      onMove({ time: param.time, point: param.point, seriesData: param.seriesData as Map<ISeriesApi<any>, any> });
    });
  }
}
```

- [ ] **Step 4: Create `src/chart/ChartHost.tsx`**

```tsx
import { Component, onMount, onCleanup } from 'solid-js';
import { PaneManager } from './pane-manager';
import { store } from '../store';
import type { Bar } from '../store/types';

let containerRef: HTMLDivElement;
let manager: PaneManager;

export function getManager(): PaneManager | undefined {
  return manager;
}

export function setDataToChart(bars: Bar[]) {
  if (!manager) return;
  const pricePane = manager.getPane('price');
  const volPane = manager.getPane('volume');

  if (pricePane && !pricePane.series['candle']) {
    pricePane.series['candle'] = (window as any).LightweightCharts
      ? (window as any).LightweightCharts.CandlestickSeries
      : null;
    // Import dynamically and set up
    import('./series-factory').then(({ createCandleSeries }) => {
      if (pricePane && !pricePane.series['candle']) {
        pricePane.series['candle'] = createCandleSeries(pricePane.chart);
      }
      if (pricePane?.series['candle']) {
        pricePane.series['candle'].setData(
          bars.map((b) => ({ time: b.time, open: b.open, high: b.high, low: b.low, close: b.close }))
        );
        pricePane.chart.timeScale().fitContent();
      }
    });
  } else if (pricePane?.series['candle']) {
    pricePane.series['candle'].setData(
      bars.map((b) => ({ time: b.time, open: b.open, high: b.high, low: b.low, close: b.close }))
    );
    pricePane.chart.timeScale().fitContent();
  }

  if (volPane && !volPane.series['volume']) {
    import('./series-factory').then(({ createVolumeSeries }) => {
      if (volPane && !volPane.series['volume']) {
        volPane.series['volume'] = createVolumeSeries(volPane.chart);
      }
      if (volPane?.series['volume']) {
        volPane.series['volume'].setData(
          bars.map((b) => ({
            time: b.time, value: b.volume ?? 0,
            color: b.close >= b.open ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)',
          }))
        );
      }
    });
  } else if (volPane?.series['volume']) {
    volPane.series['volume'].setData(
      bars.map((b) => ({
        time: b.time, value: b.volume ?? 0,
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

    if (store.bars.length) {
      setDataToChart(store.bars);
    }
  });

  onCleanup(() => {
    if (manager) {
      for (const pane of manager.getAllPanes()) {
        manager.destroyPane(pane.id);
      }
    }
  });

  return (
    <div ref={containerRef!} class="flex-1 flex flex-col min-h-0 relative">
      <div class="absolute inset-0 flex items-center justify-center text-text-dim text-sm bg-bg-base z-[5]">
        Loading chart…
      </div>
    </div>
  );
};
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/chart/
git commit -m "feat: add LWC v5.2 chart host with pane manager + multi-pane support"
```

---

## Task 3: Editor + PineScript Language

**Files:**
- Create: `frontend/src/editor/pine-language.ts`
- Create: `frontend/src/editor/PineEditor.tsx`
- Create: `frontend/src/editor/tabbed-editor.tsx`

- [ ] **Step 1: Create `src/editor/pine-language.ts`**

```ts
import { StreamLanguage, StreamParser } from '@codemirror/language';

const pineParser: StreamParser<{ inComment: boolean }> = {
  startState: () => ({ inComment: false }),
  token(stream, state) {
    if (stream.match('//@version=')) { stream.skipToEnd(); return 'meta'; }
    if (stream.match('//')) { stream.skipToEnd(); return 'comment'; }
    if (stream.match('/*')) { state.inComment = true; return 'comment'; }
    if (state.inComment) {
      if (stream.match('*/')) { state.inComment = false; return 'comment'; }
      stream.skipToEnd();
      return 'comment';
    }
    if (stream.match(/"[^"]*"/) || stream.match(/'[^']*'/)) return 'string';
    if (stream.match(/\b(indicator|strategy|plot|hline|fill|plotshape|plotchar|alertcondition)\b/)) return 'keyword';
    if (stream.match(/\b(input|int|float|bool|string|color|bar_index|close|open|high|low|volume|time|math|ta|array|matrix)\b/)) return 'variableName';
    if (stream.match(/\b(if|else|for|while|switch|true|false|na)\b/)) return 'controlKeyword';
    if (stream.match(/\b(var|varip|export|import|type|method|using)\b/)) return 'definitionKeyword';
    if (stream.match(/[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?/)) return 'number';
    if (stream.match(/[A-Z][A-Z0-9_]+/)) return 'constantName';
    if (stream.match(/[a-zA-Z_][a-zA-Z0-9_]*/)) return 'variableName';
    if (stream.match(/[+\-*/%=<>!&|^~?:]+/)) return 'operator';
    if (stream.match(/[{}()\[\],;.]/)) return 'punctuation';
    stream.next();
    return null;
  },
};

export const pineScript = StreamLanguage.define(pineParser);
```

- [ ] **Step 2: Create `src/editor/PineEditor.tsx`**

```tsx
import { Component, onMount, onCleanup } from 'solid-js';
import { EditorView, keymap, lineNumbers, highlightActiveLine, highlightActiveLineGutter } from '@codemirror/view';
import { EditorState } from '@codemirror/state';
import { defaultKeymap, indentWithTab } from '@codemirror/commands';
import { searchKeymap, highlightSelectionMatches } from '@codemirror/search';
import { autocompletion, completionKeymap } from '@codemirror/autocomplete';
import { bracketMatching } from '@codemirror/language';
import { oneDark } from '@codemirror/theme-one-dark';
import { pineScript } from './pine-language';

interface Props {
  initialDoc?: string;
  onDocChange?: (doc: string) => void;
  onRun?: () => void;
  height?: string;
}

export const PineEditor: Component<Props> = (props) => {
  let containerRef: HTMLDivElement;
  let view: EditorView;

  const getDoc = () => view?.state.doc.toString() ?? '';

  onMount(() => {
    const runKeymap = keymap.of([{
      key: 'Mod-Enter',
      run: () => { props.onRun?.(); return true; },
    }]);

    const state = EditorState.create({
      doc: props.initialDoc ?? '',
      extensions: [
        lineNumbers(),
        highlightActiveLine(),
        highlightActiveLineGutter(),
        bracketMatching(),
        highlightSelectionMatches(),
        autocompletion(),
        runKeymap,
        keymap.of([...defaultKeymap, indentWithTab, ...searchKeymap, ...completionKeymap]),
        pineScript,
        oneDark,
        EditorView.updateListener.of((update) => {
          if (update.docChanged) props.onDocChange?.(update.state.doc.toString());
        }),
        EditorView.theme({
          '&': { height: '100%' },
          '.cm-scroller': { overflow: 'auto' },
        }),
      ],
    });

    view = new EditorView({ state, parent: containerRef });
  });

  onCleanup(() => view?.destroy());

  return <div ref={containerRef!} class="h-full overflow-hidden" style={{ height: props.height || '100%' }} />;
};
```

- [ ] **Step 3: Create `src/editor/tabbed-editor.tsx`**

```tsx
import { Component, For, createSignal } from 'solid-js';
import { PineEditor } from './PineEditor';
import { store } from '../store';

interface Tab {
  id: string;
  name: string;
  doc: string;
  dirty: boolean;
}

const DEMOS: Record<string, string> = {
  'rsi-overlay': `//@version=5
strategy("RSI Overlay", overlay=true)
length = input.int(14, "RSI Length", minval=2, maxval=100)
rsi = ta.rsi(close, length)
plot(rsi * 0.01, "RSI scaled", color=color.new(color.purple, 50))
`,
  'macd': `//@version=5
indicator("MACD", overlay=false)
fastLen   = input.int(12, "Fast Length")
slowLen   = input.int(26, "Slow Length")
signalLen = input.int(9,  "Signal Length")
[macdLine, signalLine, histLine] = ta.macd(close, fastLen, slowLen, signalLen)
plot(macdLine, "MACD", color=color.blue)
plot(signalLine, "Signal", color=color.orange)
`,
};

let tabId = 0;
const newTab = (name: string, doc: string): Tab => ({
  id: `tab_${++tabId}`, name, doc, dirty: false,
});

interface Props {
  onRun?: (doc: string) => void;
}

export const TabbedEditor: Component<Props> = (props) => {
  const [tabs, setTabs] = createSignal<Tab[]>([
    newTab('Script 1', store.scripts[0]?.code || DEMOS['rsi-overlay']),
  ]);
  const [activeTab, setActiveTab] = createSignal(0);

  const addTab = () => {
    setTabs((t) => [...t, newTab(`Script ${t.length + 1}`, '')]);
    setActiveTab(tabs().length - 1);
  };

  const closeTab = (idx: number) => {
    if (tabs().length <= 1) return;
    setTabs((t) => t.filter((_, i) => i !== idx));
    if (activeTab() >= tabs().length) setActiveTab(tabs().length - 1);
  };

  const onDocChange = (doc: string) => {
    setTabs((t) => t.map((tab, i) => i === activeTab() ? { ...tab, doc, dirty: true } : tab));
  };

  return (
    <div class="flex flex-col h-full min-h-0">
      <div class="flex items-stretch bg-bg-base border-b border-border overflow-x-auto flex-shrink-0">
        <For each={tabs()}>
          {(tab, idx) => (
            <button
              class={`flex items-center gap-1.5 px-2.5 py-1 text-[11px] border-r border-border-soft cursor-pointer whitespace-nowrap select-none transition-colors ${
                idx() === activeTab()
                  ? 'bg-bg-panel text-text border-b-2 border-b-accent -mb-px'
                  : 'text-text-dim hover:bg-bg-hover hover:text-text'
              }`}
              onClick={() => setActiveTab(idx())}
            >
              {tab.dirty && <span class="inline-block w-1.5 h-1.5 rounded-full bg-yellow" />}
              <span class="max-w-[140px] overflow-hidden text-ellipsis">{tab.name}</span>
              {tabs().length > 1 && (
                <span
                  class="text-text-faint hover:text-red text-sm px-0.5 rounded hover:bg-bg-hover"
                  onClick={(e) => { e.stopPropagation(); closeTab(idx()); }}
                >
                  ×
                </span>
              )}
            </button>
          )}
        </For>
        <button
          class="text-text-dim border-none bg-transparent px-2.5 cursor-pointer text-lg hover:text-text hover:bg-bg-hover"
          onClick={addTab}
        >
          +
        </button>
      </div>
      <div class="flex-1 min-h-0 overflow-hidden relative">
        <PineEditor
          initialDoc={tabs()[activeTab()]?.doc}
          onDocChange={onDocChange}
          onRun={() => props.onRun?.(tabs()[activeTab()]?.doc)}
        />
      </div>
    </div>
  );
};
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/editor/
git commit -m "feat: add PineScript editor with CodeMirror 6 + multi-tab support"
```

---

## Task 4: Script Runner + Indicator Model

**Files:**
- Create: `frontend/src/indicators/runner.ts`
- Create: `frontend/src/indicators/IndicatorPanel.tsx`
- Create: `frontend/src/indicators/IndicatorCard.tsx`

- [ ] **Step 1: Create `src/indicators/runner.ts`**

```ts
import { store, addIndicator } from '../store';
import { getManager } from '../chart/ChartHost';
import { PLOT_PALETTE } from '../chart/series-factory';

export interface RunResult {
  status: 'success' | 'error';
  plots: (number | null)[];
  series: Record<string, (number | null)[]>;
  events: any[];
  error?: string;
  meta?: { overlay?: boolean; script_name?: string; ms?: number };
}

export async function runScript(script: string): Promise<RunResult> {
  const endpoint = store.endpoint;
  const t0 = performance.now();
  try {
    const res = await fetch(`${endpoint}/run?mode=interpret`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ script, data: store.bars }),
      signal: AbortSignal.timeout(30_000),
    });
    const payload = await res.json().catch(() => ({ status: 'error', message: 'invalid JSON' }));
    if (!res.ok || payload.status === 'error') {
      return { status: 'error', plots: [], series: {}, events: [], error: payload.message || `HTTP ${res.status}`, meta: { ms: performance.now() - t0 } };
    }
    return {
      status: 'success',
      plots: payload.plots || [],
      series: payload.series || {},
      events: payload.events || [],
      meta: { ...(payload.meta || {}), ms: performance.now() - t0, overlay: payload.meta?.overlay ?? true, script_name: payload.meta?.script_name || 'plot' },
    };
  } catch (err: any) {
    return { status: 'error', plots: [], series: {}, events: [], error: err.message, meta: { ms: performance.now() - t0 } };
  }
}

export async function runAndApply(script: string, indicatorId?: string): Promise<RunResult> {
  const result = await runScript(script);
  if (result.status === 'error') return result;

  const manager = getManager();
  if (!manager) return result;

  const overlay = result.meta?.overlay !== false;
  const paneId = overlay ? 'price' : 'indicator';
  const scriptName = result.meta?.script_name || 'plot';

  if (!overlay && !manager.getPane('indicator')) {
    const { addPane } = await import('../store');
    addPane('indicator', scriptName);
    manager.createPane('indicator', 'indicator', scriptName, 120);
    manager.syncTimeScales();
  }

  manager.removeOverlays(paneId);

  const ohlcvTimes = store.bars.map((b) => b.time);
  if (result.plots.length) {
    const data = result.plots
      .map((v, i) => (v != null && typeof v === 'number' && !isNaN(v) && ohlcvTimes[i] ? { time: ohlcvTimes[i], value: v } : null))
      .filter(Boolean) as { time: number; value: number }[];
    if (data.length) manager.addOverlayLine(paneId, scriptName, data);
  }

  for (const [k, arr] of Object.entries(result.series)) {
    if (k.startsWith('__')) continue;
    const data = (arr as (number | null)[])
      .map((v, i) => (v != null && typeof v === 'number' && !isNaN(v) && ohlcvTimes[i] ? { time: ohlcvTimes[i], value: v } : null))
      .filter(Boolean) as { time: number; value: number }[];
    if (data.length) manager.addOverlayLine(paneId, k, data);
  }

  if (indicatorId) {
    const plots: Record<string, { color: string }> = {};
    plots[scriptName] = { color: PLOT_PALETTE[0] };
    for (const k of Object.keys(result.series)) {
      plots[k] = { color: PLOT_PALETTE[Object.keys(plots).length % PLOT_PALETTE.length] };
    }
    addIndicator(scriptName, script, paneId, plots);
  }

  return result;
}
```

- [ ] **Step 2: Create `src/indicators/IndicatorCard.tsx`**

```tsx
import { Component, For } from 'solid-js';
import type { Indicator } from '../store/types';
import { toggleIndicator, removeIndicator } from '../store';
import { getManager } from '../chart/ChartHost';

interface Props {
  indicator: Indicator;
}

export const IndicatorCard: Component<Props> = (props) => {
  const toggle = () => toggleIndicator(props.indicator.id);
  const remove = () => {
    const manager = getManager();
    if (manager) {
      manager.removeOverlays(props.indicator.paneId);
      if (props.indicator.paneId !== 'price' && props.indicator.paneId !== 'volume') {
        manager.destroyPane(props.indicator.paneId);
      }
    }
    removeIndicator(props.indicator.id);
  };

  return (
    <div class="bg-bg-elev rounded border border-border-soft p-2.5 mb-2">
      <div class="flex items-center justify-between mb-1.5">
        <div class="flex items-center gap-2">
          <button
            class={`w-5 h-5 rounded text-xs flex items-center justify-center ${
              props.indicator.visible ? 'bg-accent/20 text-accent' : 'bg-bg-hover text-text-dim'
            }`}
            onClick={toggle}
          >
            {props.indicator.visible ? '👁' : '👁‍🗨'}
          </button>
          <span class="text-xs font-semibold text-text">{props.indicator.name}</span>
        </div>
        <button class="text-text-faint hover:text-red text-xs px-1 rounded hover:bg-bg-hover" onClick={remove}>
          ×
        </button>
      </div>
      <div class="flex flex-col gap-0.5">
        <For each={Object.entries(props.indicator.plots)}>
          {([name, { color }]) => (
            <div class="flex items-center gap-2 text-[11px] text-text-dim">
              <span class="inline-block w-2 h-2 rounded-full flex-shrink-0" style={{ background: color }} />
              <span>{name}</span>
            </div>
          )}
        </For>
      </div>
    </div>
  );
};
```

- [ ] **Step 3: Create `src/indicators/IndicatorPanel.tsx`**

```tsx
import { Component, For, Show } from 'solid-js';
import { store } from '../store';
import { IndicatorCard } from './IndicatorCard';

export const IndicatorPanel: Component = () => {
  return (
    <Show when={store.indicatorPanel.open}>
      <div class="w-56 bg-bg-panel border-l border-border flex flex-col flex-shrink-0 overflow-hidden">
        <div class="px-2.5 py-1.5 border-b border-border text-[11px] text-text-dim uppercase tracking-wider font-semibold">
          Indicators
        </div>
        <div class="flex-1 overflow-y-auto p-2">
          <Show
            when={store.scripts.length > 0}
            fallback={<div class="text-text-faint text-[11px] italic p-2">No indicators running.</div>}
          >
            <For each={store.scripts}>
              {(ind) => <IndicatorCard indicator={ind} />}
            </For>
          </Show>
        </div>
      </div>
    </Show>
  );
};
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/indicators/
git commit -m "feat: add script runner, indicator model, and indicator panel UI"
```

---

## Task 5: App Layout + Topbar + Status

**Files:**
- Create: `frontend/src/ui/Topbar.tsx`
- Create: `frontend/src/ui/StatusBar.tsx`
- Modify: `frontend/src/app.tsx`

- [ ] **Step 1: Create `src/ui/Topbar.tsx`**

```tsx
import { Component, For, createSignal } from 'solid-js';
import { store, setStore, toggleTheme, persist } from '../store';
import { getManager, setDataToChart } from '../chart/ChartHost';
import { runAndApply } from '../indicators/runner';

const SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT'];
const INTERVALS = ['1m', '5m', '15m', '1h', '4h', '1d', '1w'];

export const Topbar: Component<{ onToggleEditor: () => void; onToggleIndicatorPanel: () => void; editorRef: { getDoc: () => string } }> = (props) => {
  const [liveRunning, setLiveRunning] = createSignal(false);

  const loadHistorical = async () => {
    try {
      const res = await fetch(`https://api.binance.com/api/v3/klines?symbol=${store.symbol}&interval=${store.interval}&limit=500`);
      const raw = await res.json();
      const bars = raw.map((k: any[]) => ({
        time: Math.floor(k[0] / 1000),
        open: +k[1], high: +k[2], low: +k[3], close: +k[4], volume: +k[5],
      }));
      const { loadBars } = await import('../store');
      loadBars(bars, store.symbol, store.interval, store.exchange);
      const manager = getManager();
      if (manager) {
        setDataToChart(bars);
        manager.fitContent();
      }
    } catch (err) {
      console.error('Load failed:', err);
    }
  };

  const onRun = async () => {
    const doc = props.editorRef.getDoc();
    if (!doc?.trim()) return;
    await runAndApply(doc, 'new');
  };

  const toggleLive = () => {
    const next = !liveRunning();
    setLiveRunning(next);
    const { setLive } = require('../store');
    setLive(next);
  };

  return (
    <header class="flex items-center gap-3 px-2.5 py-1.5 bg-bg-panel border-b border-border flex-shrink-0 min-h-[40px]">
      <div class="font-semibold text-sm text-text mr-2">SuperChart Lite</div>

      <label class="text-[11px] text-text-dim uppercase tracking-wider">Symbol</label>
      <select
        class="bg-bg-elev text-text border border-border rounded px-2 py-1 text-xs outline-none focus:border-accent min-w-[80px]"
        value={store.symbol}
        onChange={(e) => { setStore('symbol', e.currentTarget.value); persist(); }}
      >
        <For each={SYMBOLS}>{(s) => <option value={s}>{s}</option>}</For>
      </select>

      <label class="text-[11px] text-text-dim uppercase tracking-wider">Interval</label>
      <select
        class="bg-bg-elev text-text border border-border rounded px-2 py-1 text-xs outline-none focus:border-accent min-w-[60px]"
        value={store.interval}
        onChange={(e) => { setStore('interval', e.currentTarget.value); persist(); }}
      >
        <For each={INTERVALS}>{(i) => <option value={i}>{i}</option>}</For>
      </select>

      <button class="bg-bg-elev text-text border border-border rounded px-2.5 py-1 text-xs cursor-pointer hover:bg-bg-hover" onClick={loadHistorical}>
        Load
      </button>

      <button
        class={`bg-bg-elev text-text border border-border rounded px-2.5 py-1 text-xs cursor-pointer hover:bg-bg-hover flex items-center gap-1.5 ${liveRunning() ? 'border-green text-green' : ''}`}
        onClick={toggleLive}
      >
        <span class={`inline-block w-2 h-2 rounded-full ${liveRunning() ? 'bg-green animate-pulse' : 'bg-text-faint'}`} />
        Live
      </button>

      <div class="flex-1" />

      <button class="bg-bg-elev text-text border border-border rounded px-2.5 py-1 text-xs cursor-pointer hover:bg-bg-hover" onClick={onRun}>
        ▶ Run
      </button>

      <button class="text-text-dim hover:text-text text-xs cursor-pointer bg-transparent border-none px-1.5" onClick={props.onToggleEditor}>
        📝 Editor
      </button>

      <button class="text-text-dim hover:text-text text-xs cursor-pointer bg-transparent border-none px-1.5" onClick={props.onToggleIndicatorPanel}>
        📊 Indicators
      </button>

      <button class="text-text-dim hover:text-text text-xs cursor-pointer bg-transparent border-none px-1.5" onClick={toggleTheme}>
        {store.theme === 'dark' ? '☀' : '🌙'}
      </button>
    </header>
  );
};
```

- [ ] **Step 2: Create `src/ui/StatusBar.tsx`**

```tsx
import { Component } from 'solid-js';
import { store } from '../store';

export const StatusBar: Component = () => {
  return (
    <div class="flex items-center px-2.5 py-0.5 bg-bg-panel border-t border-border text-[11px] text-text-dim min-h-[24px] flex-shrink-0">
      <span>Ready.</span>
      <span class="flex-1" />
      <span class="text-text-faint font-mono text-[11px]">
        {store.bars.length} bars · {store.scripts.length} indicators · {store.panes.length} panes
      </span>
    </div>
  );
};
```

- [ ] **Step 3: Update `src/app.tsx`**

```tsx
import { Component, createSignal, onMount } from 'solid-js';
import { Topbar } from './ui/Topbar';
import { StatusBar } from './ui/StatusBar';
import { ChartHost, setDataToChart } from './chart/ChartHost';
import { TabbedEditor } from './editor/tabbed-editor';
import { IndicatorPanel } from './indicators/IndicatorPanel';
import { store, setStore, persist } from './store';

export const App: Component = () => {
  const [editorOpen, setEditorOpen] = createSignal(true);
  const [indicatorPanelOpen, setIndicatorPanelOpen] = createSignal(false);
  let editorRef = { getDoc: () => '' };

  onMount(() => {
    document.documentElement.setAttribute('data-theme', store.theme);
  });

  return (
    <div class="h-screen flex flex-col bg-bg-base text-text overflow-hidden">
      <Topbar
        onToggleEditor={() => setEditorOpen((o) => !o)}
        onToggleIndicatorPanel={() => {
          const next = !indicatorPanelOpen();
          setIndicatorPanelOpen(next);
          setStore('indicatorPanel', 'open', next);
          persist();
        }}
        editorRef={editorRef}
      />

      <div class="flex-1 flex min-h-0 overflow-hidden">
        {editorOpen() && (
          <div class="w-[460px] min-w-[280px] bg-bg-panel border-r border-border flex flex-col flex-shrink-0 overflow-hidden">
            <div class="flex-1 min-h-0 overflow-hidden">
              <TabbedEditor onRun={(doc) => {}} />
            </div>
          </div>
        )}

        <div class="flex-1 flex min-w-0 min-h-0 overflow-hidden">
          <ChartHost />
          <IndicatorPanel />
        </div>
      </div>

      <StatusBar />
    </div>
  );
};
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/ui/ frontend/src/app.tsx
git commit -m "feat: add topbar, status bar, and main app layout"
```

---

## Task 6: Live Mode + Stream Manager

**Files:**
- Create: `frontend/src/streams/multiplex.ts`
- Create: `frontend/src/streams/binance.ts`

- [ ] **Step 1: Create `src/streams/binance.ts`**

```ts
import type { Bar } from '../store/types';

export interface StreamPlugin {
  id: string;
  name: string;
  start(opts: {
    symbol: string;
    interval: string;
    onBar: (bar: Bar) => void;
    onStatus: (status: { state: string }) => void;
    onError: (err: Error) => void;
  }): () => void;
}

const INTERVAL_MAP: Record<string, string> = {
  '1m': '1m', '5m': '5m', '15m': '15m', '1h': '1h', '4h': '4h', '1d': '1d', '1w': '1w',
};

export const binanceStream: StreamPlugin = {
  id: 'binance-ws',
  name: 'Binance WebSocket',
  start({ symbol, interval, onBar, onStatus, onError }) {
    const wsInterval = INTERVAL_MAP[interval] || interval;
    const url = `wss://stream.binance.com:9443/ws/${symbol.toLowerCase()}@kline_${wsInterval}`;
    const ws = new WebSocket(url);

    ws.onopen = () => onStatus({ state: 'open' });
    ws.onerror = () => onError(new Error('WebSocket error'));
    ws.onclose = () => onStatus({ state: 'closed' });

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        const k = data.k;
        if (!k) return;
        const bar: Bar = {
          time: Math.floor(k.t / 1000),
          open: +k.o, high: +k.h, low: +k.l, close: +k.c, volume: +k.v,
        };
        onBar(bar);
      } catch {}
    };

    return () => ws.close();
  },
};
```

- [ ] **Step 2: Create `src/streams/multiplex.ts`**

```ts
import type { Bar } from '../store/types';
import type { StreamPlugin } from './binance';
import { binanceStream } from './binance';
import { appendBar, setLive, store } from '../store';
import { getManager } from '../chart/ChartHost';
import { runScript } from '../indicators/runner';

const STREAMS: StreamPlugin[] = [binanceStream];

let currentStop: (() => void) | null = null;
let rerunTimer: ReturnType<typeof setTimeout> | null = null;

export function getAvailableStreams(): StreamPlugin[] {
  return STREAMS;
}

export function startLive(streamId: string, symbol: string, interval: string) {
  stopLive();
  const stream = STREAMS.find((s) => s.id === streamId);
  if (!stream) return;

  const stop = stream.start({
    symbol,
    interval,
    onBar: (bar: Bar) => {
      appendBar(bar);
      const manager = getManager();
      if (manager) manager.appendBar(bar);
      if (store.live.active) scheduleRerun();
    },
    onStatus: (s) => console.log('[stream]', s.state),
    onError: (e) => { console.error('[stream]', e); stopLive(); },
  });

  currentStop = stop;
  setLive(true);
}

export function stopLive() {
  if (currentStop) { currentStop(); currentStop = null; }
  setLive(false);
  if (rerunTimer) { clearTimeout(rerunTimer); rerunTimer = null; }
}

function scheduleRerun() {
  if (rerunTimer) return;
  rerunTimer = setTimeout(async () => {
    rerunTimer = null;
    for (const ind of store.scripts) {
      if (!ind.visible) continue;
      await runScript(ind.code);
    }
  }, 300);
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/streams/
git commit -m "feat: add live stream manager with debounced re-run"
```

---

## Task 7: Polish + Responsive + Testing

**Files:**
- Create: `frontend/src/ui/SettingsDialog.tsx`
- Test: `frontend/tests/chart.test.ts`

- [ ] **Step 1: Create `src/ui/SettingsDialog.tsx`**

```tsx
import { Component, createSignal, Show } from 'solid-js';
import { store, setStore, persist } from '../store';

interface Props {
  open: boolean;
  onClose: () => void;
}

export const SettingsDialog: Component<Props> = (props) => {
  const [endpoint, setEndpoint] = createSignal(store.endpoint);
  const [engine, setEngine] = createSignal(store.engine);

  const save = () => {
    setStore('endpoint', endpoint());
    setStore('engine', engine());
    persist();
    props.onClose();
  };

  return (
    <Show when={props.open}>
      <div class="fixed inset-0 bg-black/55 flex items-center justify-center z-[1000] backdrop-blur-[2px]">
        <div class="bg-bg-panel border border-border rounded-md w-[min(540px,calc(100vw-32px))] max-h-[calc(100vh-64px)] flex flex-col shadow-[0_10px_30px_rgba(0,0,0,0.4)]">
          <div class="flex items-center justify-between px-3.5 py-2.5 border-b border-border">
            <span class="text-sm font-semibold text-text">Settings</span>
            <button class="text-text-dim hover:text-text text-xs bg-transparent border-none cursor-pointer" onClick={props.onClose}>×</button>
          </div>
          <div class="p-3.5 flex flex-col gap-2.5 overflow-auto">
            <div class="flex flex-col gap-1">
              <label class="text-xs text-text-dim uppercase tracking-wider">Backend Endpoint</label>
              <input
                class="bg-bg-elev text-text border border-border rounded px-2 py-1.5 text-sm font-mono outline-none focus:border-accent"
                value={endpoint()}
                onInput={(e) => setEndpoint(e.currentTarget.value)}
              />
            </div>
            <div class="flex flex-col gap-1">
              <label class="text-xs text-text-dim uppercase tracking-wider">Engine</label>
              <select
                class="bg-bg-elev text-text border border-border rounded px-2 py-1.5 text-sm outline-none focus:border-accent"
                value={engine()}
                onChange={(e) => setEngine(e.currentTarget.value)}
              >
                <option value="server">Server-Side</option>
                <option value="pyodide">Client-Side (Pyodide)</option>
              </select>
            </div>
          </div>
          <div class="flex items-center gap-2 px-3.5 py-2.5 border-t border-border bg-bg-base rounded-b-md">
            <div class="flex-1" />
            <button class="bg-bg-elev text-text border border-border rounded px-3 py-1 text-xs cursor-pointer hover:bg-bg-hover" onClick={props.onClose}>
              Cancel
            </button>
            <button class="bg-accent border border-accent text-white rounded px-3 py-1 text-xs cursor-pointer font-medium hover:bg-accent-hover" onClick={save}>
              Save
            </button>
          </div>
        </div>
      </div>
    </Show>
  );
};
```

- [ ] **Step 2: Write a basic test**

```ts
// frontend/tests/chart.test.ts
import { describe, it, expect } from 'bun:test';

describe('PaneManager', () => {
  it('can be imported', async () => {
    const { PaneManager } = await import('../src/chart/pane-manager');
    expect(PaneManager).toBeDefined();
  });
});

describe('Store', () => {
  it('has default state', async () => {
    const { store } = await import('../src/store');
    expect(store.symbol).toBe('BTCUSDT');
    expect(store.interval).toBe('1d');
  });
});
```

- [ ] **Step 3: Run tests**

```bash
cd frontend && bun test
```

- [ ] **Step 4: Verify full build**

```bash
cd frontend && bun run vite build
```

- [ ] **Step 5: Commit**

```bash
git add frontend/
git commit -m "feat: complete SuperChart Lite rewrite with SolidJS + LWC v5.2"
```

---

## Execution Handoff

**Plan complete and saved to `.opencode/plans/2026-07-25-superchart-rewrite.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
