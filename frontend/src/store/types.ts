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

export type AppStatus = 'ready' | 'loading' | 'running' | 'error' | 'connected' | 'disconnected';

export type LogLevel = 'info' | 'ok' | 'warn' | 'error';

export interface LogEntry {
  id: string;
  ts: number;
  level: LogLevel;
  message: string;
  source?: string;
}

/** docked = right sidebar; popout = external window/tab owns the editor UI */
export type EditorMode = 'docked' | 'popout';

export interface WatchlistState {
  open: boolean;
  width: number;
  symbols: string[];
}

export interface EditorLayoutState {
  open: boolean;
  width: number;
  mode: EditorMode;
}

/** Built-in historical source ids (D1) */
export type SourceId = 'binance-rest' | 'mock-walk' | 'csv-upload' | string;

export interface AppState {
  bars: Bar[];
  symbol: string;
  interval: string;
  exchange: string;
  /** Historical data source plugin id */
  source: SourceId;
  engine: string;
  endpoint: string;

  scripts: Indicator[];
  panes: Pane[];

  live: {
    active: boolean;
    needsRerun: boolean;
    lastBarTime: number;
    streamId: string;
  };

  theme: 'dark' | 'light';
  editor: EditorLayoutState;
  watchlist: WatchlistState;
  indicatorPanel: { open: boolean; width: number };
  /** Bottom results / export drawer */
  resultsPanel: { open: boolean; height: number };
  /** System log drawer (collapsed by default) */
  logsPanel: { open: boolean; height: number };
  stream: { status: 'connected' | 'disconnected' | 'error' };
  status: AppStatus;
  statusMessage: string;
  lastRunMs: number | null;
  /** Last script run payload for Results panel (not always persisted fully) */
  lastRun: unknown | null;
  /** In-memory system logs (not persisted) */
  logs: LogEntry[];
}
