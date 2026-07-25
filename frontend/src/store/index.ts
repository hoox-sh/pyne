import { createStore } from 'solid-js/store';
import type { AppState, Bar, Indicator, Pane } from './types';

// Stable ID generation — uses timestamp prefix + counter to survive reloads
let idCounter = 0;
const uid = () => `id_${Date.now()}_${++idCounter}`;

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
  live: { active: false, needsRerun: false, lastBarTime: 0, streamId: 'binance-ws' },
  theme: 'dark',
  editor: { open: true, width: 460 },
  indicatorPanel: { open: false },
  stream: { status: 'disconnected' },
  status: 'ready',
  statusMessage: 'Ready.',
  lastRunMs: null,
};

function loadPersisted(): Partial<AppState> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      // Ensure new fields exist on old persisted state
      return { ...DEFAULTS, ...parsed, live: { ...DEFAULTS.live, ...parsed.live } };
    }
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

export function setStatus(status: AppState['status'], message?: string) {
  setStore('status', status);
  if (message !== undefined) setStore('statusMessage', message);
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
