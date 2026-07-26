/**
 * Resolve the currently selected source / stream / engine / storage plugins.
 */

import { store } from '../store';
import { registry } from './registry';
import { ensureBuiltins } from './bootstrap';
import { pluginKey, type EnginePlugin, type SourcePlugin, type StoragePlugin, type StreamPlugin } from './types';

function pluginConfig(kind: string, id: string): Record<string, unknown> {
  const configs = store.pluginsConfig || {};
  return (
    configs[pluginKey(kind as 'source', id)] ||
    configs[id] ||
    {}
  );
}

export function getActiveSourceId(): string {
  return store.activePlugins?.source || store.source || 'binance-rest';
}

export function getActiveStreamId(): string {
  return store.activePlugins?.stream || store.live?.streamId || 'binance-ws';
}

export function getActiveEngineId(): string {
  return store.activePlugins?.engine || store.engine || 'server';
}

export function getActiveStorageId(): string {
  return store.activePlugins?.storage || 'local';
}

export function getActiveSource(): SourcePlugin {
  ensureBuiltins();
  const id = getActiveSourceId();
  const p = registry.getSource(id) || registry.getSource('binance-rest');
  if (!p) throw new Error(`No source plugin registered (wanted ${id})`);
  return p;
}

export function getActiveStream(): StreamPlugin {
  ensureBuiltins();
  const id = getActiveStreamId();
  const p = registry.getStream(id) || registry.getStream('binance-ws');
  if (!p) throw new Error(`No stream plugin registered (wanted ${id})`);
  return p;
}

export function getActiveEngine(): EnginePlugin {
  ensureBuiltins();
  const id = getActiveEngineId();
  const p = registry.getEngine(id) || registry.getEngine('server');
  if (!p) throw new Error(`No engine plugin registered (wanted ${id})`);
  return p;
}

/** Active storage plugin (defaults to local). */
export function getActiveStorage(): StoragePlugin | undefined {
  ensureBuiltins();
  const id = getActiveStorageId();
  return registry.getStorage(id) || registry.getStorage('local');
}

export function getActiveSourceConfig(): Record<string, unknown> {
  return pluginConfig('source', getActiveSourceId());
}

export function getActiveStreamConfig(): Record<string, unknown> {
  return pluginConfig('stream', getActiveStreamId());
}

export function getActiveEngineConfig(): Record<string, unknown> {
  const base = pluginConfig('engine', getActiveEngineId());
  // Surface store.endpoint into server engine config by default
  if (getActiveEngineId() === 'server' && store.endpoint) {
    return { endpoint: store.endpoint, ...base };
  }
  return base;
}
