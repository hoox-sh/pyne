/**
 * Unified plugin contracts for AXIS (PR1).
 * All kinds share PluginBase; active selection lives in the Solid store.
 */

import type { Bar } from '../store/types';
import type { LogLevel } from '../store/types';

export type PluginKind =
  | 'source'
  | 'stream'
  | 'engine'
  | 'storage'
  | 'component';

export interface FieldSchema {
  type: 'string' | 'number' | 'boolean' | 'select';
  default?: string | number | boolean;
  label?: string;
  description?: string;
  placeholder?: string;
  min?: number;
  max?: number;
  step?: number;
  options?: string[];
}

export type ConfigSchema = Record<string, FieldSchema>;

export interface PluginCapabilities {
  offline?: boolean;
  needsAuth?: boolean;
  needsNetwork?: boolean;
  needsProxy?: boolean;
}

export interface PluginBase {
  id: string;
  name: string;
  kind: PluginKind;
  description?: string;
  version?: string;
  builtIn?: boolean;
  configSchema?: ConfigSchema;
  capabilities?: PluginCapabilities;
  init?(ctx: PluginContext): Promise<void> | void;
  dispose?(): Promise<void> | void;
}

export interface PluginContext {
  getConfig(): Record<string, unknown>;
  setStatus(msg: string, level?: LogLevel): void;
  host: {
    fetch?: typeof fetch;
  };
}

/** Registry key: `${kind}:${id}` */
export function pluginKey(kind: PluginKind, id: string): string {
  return `${kind}:${id}`;
}

// --- Source ---

export interface SourceOpts {
  symbol: string;
  interval: string;
  limit?: number;
  config?: Record<string, unknown>;
}

export interface SourcePlugin extends PluginBase {
  kind: 'source';
  fetchHistorical(opts: SourceOpts): Promise<Bar[]>;
  searchSymbols?(query: string, config?: Record<string, unknown>): Promise<string[]>;
}

// --- Stream ---

export interface StreamOpts {
  symbol: string;
  interval: string;
  config?: Record<string, unknown>;
  lastBar?: Bar | null;
  onBar: (b: Bar) => void;
  onError: (e: Error) => void;
  onStatus: (s: { state: 'open' | 'closed' | 'reconnecting' | string; url?: string; detail?: string }) => void;
}

export interface StreamPlugin extends PluginBase {
  kind: 'stream';
  start(opts: StreamOpts): () => void;
}

// --- Engine ---

export interface RunResult {
  status: 'success' | 'error';
  plots: (number | null)[];
  series?: Record<string, (number | null)[]>;
  events: Array<{
    time: number;
    type: string;
    id?: string;
    price?: number;
    dir?: string;
    [k: string]: unknown;
  }>;
  /** Pine line/label/box objects from interpret runtime */
  drawings?: Array<Record<string, unknown>>;
  error?: string;
  meta?: {
    mode?: string;
    script_id?: string;
    run_id?: string;
    ms?: number;
    count?: number;
    overlay?: boolean;
    script_name?: string;
    [k: string]: unknown;
  };
}

export interface EngineOpts {
  script: string;
  bars: Bar[];
  config?: Record<string, unknown>;
  signal?: AbortSignal;
}

export interface EnginePlugin extends PluginBase {
  kind: 'engine';
  isReady(): Promise<boolean>;
  run(opts: EngineOpts): Promise<RunResult>;
}

// --- Storage (PR2 — interface reserved) ---

export interface ScriptMeta {
  id: string;
  name: string;
  description?: string;
  path?: string;
  updatedAt: number;
  createdAt?: number;
  revision?: string;
  tags?: string[];
}

export interface ScriptDocument extends ScriptMeta {
  content: string;
}

export interface SyncResult {
  ok: boolean;
  message?: string;
  revision?: string;
  conflicts?: Array<{ id: string; localRev?: string; remoteRev?: string }>;
}

export interface StorageStatus {
  connected: boolean;
  dirty?: boolean;
  lastSyncAt?: number;
  branch?: string;
  remote?: string;
  error?: string;
}

export interface StoragePlugin extends PluginBase {
  kind: 'storage';
  list(opts?: { prefix?: string; config?: Record<string, unknown> }): Promise<ScriptMeta[]>;
  read(id: string, config?: Record<string, unknown>): Promise<ScriptDocument>;
  write(doc: ScriptDocument, config?: Record<string, unknown>): Promise<ScriptMeta>;
  remove(id: string, config?: Record<string, unknown>): Promise<void>;
  saveDraft?(doc: { content: string; name?: string }, config?: Record<string, unknown>): Promise<void>;
  loadDraft?(config?: Record<string, unknown>): Promise<{ content: string; name?: string } | null>;
  sync?(direction: 'push' | 'pull' | 'both', config?: Record<string, unknown>): Promise<SyncResult>;
  getStatus?(config?: Record<string, unknown>): Promise<StorageStatus>;
}

// --- Component (phase 2 — reserved) ---

export interface ComponentPlugin extends PluginBase {
  kind: 'component';
  slots: Array<'manager-tab' | 'results-tab' | 'topbar-action' | 'settings-section'>;
  mount(slot: string, el: HTMLElement, api: Record<string, unknown>): () => void;
}

export type AnyPlugin =
  | SourcePlugin
  | StreamPlugin
  | EnginePlugin
  | StoragePlugin
  | ComponentPlugin;

export interface PluginSummaryItem {
  id: string;
  name: string;
  description: string;
  builtIn?: boolean;
}

export interface RegistrySummary {
  sources: PluginSummaryItem[];
  streams: PluginSummaryItem[];
  engines: PluginSummaryItem[];
  storages: PluginSummaryItem[];
}
