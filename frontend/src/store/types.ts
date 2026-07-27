export interface Bar {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
  /**
   * Venue reported this candle as closed (e.g. Binance kline `k.x`).
   * Used when live.rerunOn === 'bar-close'. Not persisted.
   */
  closed?: boolean;
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
  /** Live quote poll interval in seconds (5–120) */
  refreshSec: number;
}

export interface EditorLayoutState {
  open: boolean;
  width: number;
  mode: EditorMode;
}

/** Built-in historical source ids (D1) */
export type SourceId = 'binance-rest' | 'mock-walk' | 'csv-upload' | string;

/** Active plugin selection (source/stream/engine/storage) */
export interface ActivePlugins {
  source: string;
  stream: string;
  engine: string;
  /** PR2: local | git | cloud */
  storage: string;
}

import type { Drawing, DrawingToolId } from '../chart/drawing-types';
export type { Drawing, DrawingToolId };

/** How a plane moves data (for Connection HUD badges). */
export type TransportClass = 'ws' | 'rest' | 'local' | 'broker' | 'none';

export type ConnState = 'idle' | 'connecting' | 'open' | 'degraded' | 'error' | 'closed';

export interface PlaneTelemetry {
  id: string;
  name: string;
  transport: TransportClass;
  state: ConnState;
  detail?: string;
  latencyMs?: number | null;
  lastEventAt?: number | null;
  error?: string | null;
}

export interface TickTelemetry {
  time: number;
  price: number;
  dir: 'up' | 'down' | 'flat';
  at: number;
}

export interface TelemetryState {
  source: PlaneTelemetry;
  stream: PlaneTelemetry;
  engine: PlaneTelemetry;
  storage: PlaneTelemetry;
  /** Rolling run latency samples (ms), newest last */
  runLatencySamples: number[];
  lastTick: TickTelemetry | null;
  /** Layout prefs (may be persisted via rest of store carefully) */
  hud: { compact: boolean; overlay: boolean };
}

export interface AppState {
  bars: Bar[];
  /**
   * Bumped only on full history loads (loadBars), not live appendBar.
   * ChartHost uses this so it does not full-setData on every tick.
   */
  chartDataGen: number;
  symbol: string;
  interval: string;
  exchange: string;
  /** Historical data source plugin id (mirrors activePlugins.source) */
  source: SourceId;
  engine: string;
  endpoint: string;
  /** Canonical active plugin ids */
  activePlugins: ActivePlugins;
  /** Per-plugin config keyed by `${kind}:${id}` or bare id */
  pluginsConfig: Record<string, Record<string, unknown>>;

  scripts: Indicator[];
  panes: Pane[];

  live: {
    active: boolean;
    needsRerun: boolean;
    lastBarTime: number;
    streamId: string;
    /**
     * When true, successful Load auto-starts the paired live stream.
     * Default false (no surprise sockets).
     */
    preferAfterLoad: boolean;
    /**
     * every-tick = re-run indicators on each bar update (default).
     * bar-close = only when venue marks candle closed (or bar time advances).
     */
    rerunOn: 'every-tick' | 'bar-close';
  };

  theme: 'dark' | 'light';
  editor: EditorLayoutState;
  watchlist: WatchlistState;
  indicatorPanel: { open: boolean; width: number };
  /** Bottom results / export drawer */
  resultsPanel: { open: boolean; height: number };
  /** System log drawer (collapsed by default) */
  logsPanel: { open: boolean; height: number };
  stream: { status: 'connected' | 'disconnected' | 'error' | 'connecting' };
  status: AppStatus;
  statusMessage: string;
  lastRunMs: number | null;
  /** Last script run payload for Results panel (not always persisted fully) */
  lastRun: unknown | null;
  /** In-memory system logs (not persisted) */
  logs: LogEntry[];

  /** Active interactive drawing tool */
  drawingTool: DrawingToolId;
  /** User chart drawings (persisted) */
  drawings: Drawing[];

  /** Connection / engine / datafeed telemetry (ephemeral) */
  telemetry: TelemetryState;
}
