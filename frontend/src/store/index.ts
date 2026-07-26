import { createStore } from 'solid-js/store';
import type {
  AppState,
  Bar,
  Indicator,
  Pane,
  EditorMode,
  LogEntry,
  LogLevel,
  Drawing,
  DrawingToolId,
} from './types';

// Stable ID generation — uses timestamp prefix + counter to survive reloads
let idCounter = 0;
const uid = () => `id_${Date.now()}_${++idCounter}`;

/** Current AXIS storage key (was SuperChart). */
export const STORAGE_KEY = 'pynescript.axis.v1';
/** Legacy SuperChart keys — read once for migration. */
const LEGACY_STORAGE_KEYS = [
  'pynescript.superchart.v2',
  'pynescript.superchart.v1',
] as const;

export const EDITOR_DOC_KEY = 'pynescript.axis.editor.doc';
const LEGACY_EDITOR_DOC_KEYS = [
  'pynescript.superchart.editor.doc',
] as const;

const DEFAULT_WATCHLIST = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'ADAUSDT', 'DOGEUSDT'];

const DEFAULTS: AppState = {
  bars: [],
  symbol: 'BTCUSDT',
  interval: '1d',
  exchange: 'binance',
  source: 'binance-rest',
  engine: 'server',
  endpoint: 'http://162.254.38.194:5002',
  scripts: [],
  panes: [
    { id: 'price', type: 'price', height: 0, order: 0, visible: true, label: 'Price' },
    { id: 'volume', type: 'volume', height: 120, order: 1, visible: true, label: 'Volume' },
  ],
  live: { active: false, needsRerun: false, lastBarTime: 0, streamId: 'binance-ws' },
  theme: 'dark',
  editor: { open: true, width: 460, mode: 'docked' },
  watchlist: { open: true, width: 200, symbols: [...DEFAULT_WATCHLIST] },
  indicatorPanel: { open: false, width: 224 },
  resultsPanel: { open: false, height: 220 },
  logsPanel: { open: false, height: 160 },
  stream: { status: 'disconnected' },
  status: 'ready',
  statusMessage: 'Ready.',
  lastRunMs: null,
  lastRun: null,
  logs: [],
  drawingTool: 'cursor',
  drawings: [],
};

function readLocalStorage(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

/** Prefer AXIS key; fall back to SuperChart keys and migrate. */
function loadRawState(): string | null {
  const current = readLocalStorage(STORAGE_KEY);
  if (current) return current;
  for (const legacy of LEGACY_STORAGE_KEYS) {
    const raw = readLocalStorage(legacy);
    if (raw) {
      try {
        localStorage.setItem(STORAGE_KEY, raw);
      } catch {}
      return raw;
    }
  }
  return null;
}

function migrateEditorDoc() {
  if (readLocalStorage(EDITOR_DOC_KEY)) return;
  for (const legacy of LEGACY_EDITOR_DOC_KEYS) {
    const raw = readLocalStorage(legacy);
    if (raw) {
      try {
        localStorage.setItem(EDITOR_DOC_KEY, raw);
      } catch {}
      return;
    }
  }
}

migrateEditorDoc();

function loadPersisted(): Partial<AppState> {
  try {
    const raw = loadRawState();
    if (raw) {
      const parsed = JSON.parse(raw);
      return {
        ...DEFAULTS,
        ...parsed,
        live: { ...DEFAULTS.live, ...parsed.live },
        editor: { ...DEFAULTS.editor, ...parsed.editor },
        watchlist: {
          ...DEFAULTS.watchlist,
          ...parsed.watchlist,
          symbols: parsed.watchlist?.symbols?.length
            ? parsed.watchlist.symbols
            : DEFAULTS.watchlist.symbols,
        },
        indicatorPanel: { ...DEFAULTS.indicatorPanel, ...parsed.indicatorPanel },
        resultsPanel: { ...DEFAULTS.resultsPanel, ...parsed.resultsPanel },
        logsPanel: { ...DEFAULTS.logsPanel, ...parsed.logsPanel, open: false },
        // Do not hydrate lastRun / logs from storage
        lastRun: null,
        logs: [],
        drawingTool: 'cursor',
        drawings: Array.isArray(parsed.drawings) ? parsed.drawings : [],
      };
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
    try {
      // Omit bars + lastRun + logs from persistence (size); keep layout prefs
      const { bars: _b, lastRun: _r, logs: _l, ...rest } = store as AppState & {
        bars: unknown;
        lastRun: unknown;
        logs: unknown;
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(rest));
    } catch {}
  }, 200);
}

const MAX_LOGS = 500;

function statusToLevel(status: AppState['status']): LogLevel {
  if (status === 'error') return 'error';
  if (status === 'ready' || status === 'connected') return 'ok';
  if (status === 'loading' || status === 'running') return 'info';
  return 'warn';
}

export function appendLog(level: LogLevel, message: string, source = 'system') {
  const entry: LogEntry = {
    id: uid(),
    ts: Date.now(),
    level,
    message,
    source,
  };
  setStore('logs', (logs) => {
    const next = [...logs, entry];
    return next.length > MAX_LOGS ? next.slice(next.length - MAX_LOGS) : next;
  });
}

export function clearLogs() {
  setStore('logs', []);
}

export function setLastRun(result: unknown) {
  setStore('lastRun', result as never);
  if (result && typeof result === 'object' && result !== null && 'meta' in result) {
    const ms = (result as { meta?: { ms?: number } }).meta?.ms;
    if (typeof ms === 'number') setStore('lastRunMs', ms);
  }
}

export function setStatus(status: AppState['status'], message?: string) {
  setStore('status', status);
  if (message !== undefined) {
    setStore('statusMessage', message);
    appendLog(statusToLevel(status), message, status);
  }
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

/**
 * Append or update the latest bar (live klines update the open bar in place).
 * Does not persist every tick — bars stay in memory only.
 */
export function appendBar(bar: Bar) {
  setStore('bars', (b) => {
    if (b.length && b[b.length - 1].time === bar.time) {
      const next = b.slice();
      next[next.length - 1] = bar;
      return next;
    }
    // Cap history growth during long live sessions
    const next = b.length > 5000 ? b.slice(b.length - 4000) : b.slice();
    next.push(bar);
    return next;
  });
  setStore('live', 'lastBarTime', bar.time);
  setStore('live', 'needsRerun', true);
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

/* ── Layout helpers ─────────────────────────────────────────────── */

export function setEditorWidth(width: number) {
  const w = Math.min(Math.max(width, 280), Math.floor(window.innerWidth * 0.8));
  setStore('editor', 'width', w);
  persist();
}

export function setWatchlistWidth(width: number) {
  const w = Math.min(Math.max(width, 140), 360);
  setStore('watchlist', 'width', w);
  persist();
}

export function setIndicatorWidth(width: number) {
  const w = Math.min(Math.max(width, 160), 400);
  setStore('indicatorPanel', 'width', w);
  persist();
}

export function setEditorOpen(open: boolean) {
  setStore('editor', 'open', open);
  persist();
}

export function setEditorMode(mode: EditorMode) {
  setStore('editor', 'mode', mode);
  if (mode === 'popout') setStore('editor', 'open', false);
  persist();
}

export function setWatchlistOpen(open: boolean) {
  setStore('watchlist', 'open', open);
  persist();
}

export function addWatchlistSymbol(symbol: string) {
  const sym = symbol.toUpperCase().trim();
  if (!sym || store.watchlist.symbols.includes(sym)) return;
  setStore('watchlist', 'symbols', (s) => [...s, sym]);
  persist();
}

export function removeWatchlistSymbol(symbol: string) {
  setStore('watchlist', 'symbols', (s) => s.filter((x) => x !== symbol));
  persist();
}

export function saveEditorDoc(doc: string) {
  try { localStorage.setItem(EDITOR_DOC_KEY, doc); } catch {}
}

export function loadEditorDoc(): string {
  try { return localStorage.getItem(EDITOR_DOC_KEY) || ''; } catch { return ''; }
}

export function setDrawingTool(tool: DrawingToolId) {
  setStore('drawingTool', tool);
  // tool choice is session-ish; still persist so toolbar restores
  persist();
}

export function setDrawings(drawings: Drawing[]) {
  setStore('drawings', drawings);
  persist();
}

export function clearDrawings() {
  setStore('drawings', []);
  persist();
}

/** Sync store from layer after delete-selected (layer owns selection). */
export function deleteSelectedDrawing(current: Drawing[]) {
  setStore('drawings', current);
  persist();
}
