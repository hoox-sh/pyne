/**
 * Dynamic plugin loader for AXIS.
 * Loads ES modules from URL; registers source/stream/engine plugins; persists URL list.
 */

import { registerDynamicSource, unregisterDynamicSource, listDynamicSourceIds } from '../sources/catalog';
import { registerDynamicStream, unregisterDynamicStream } from '../streams/catalog';
import { registerDynamicEngine, unregisterDynamicEngine } from '../engines/catalog';
import { ensureBuiltins } from './bootstrap';
import { appendLog } from '../store';
import type { EnginePlugin, SourcePlugin, StreamPlugin } from './types';

export const PLUGINS_KEY = 'pynescript.axis.plugins.v1';
const LEGACY_PLUGINS_KEY = 'pynescript.superchart.plugins.v1';

export type InstalledPlugin = {
  url: string;
  id: string;
  name: string;
  kind: string;
  description?: string;
};

function readInstalled(): InstalledPlugin[] {
  try {
    const raw =
      localStorage.getItem(PLUGINS_KEY) || localStorage.getItem(LEGACY_PLUGINS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeInstalled(list: InstalledPlugin[]) {
  try {
    localStorage.setItem(PLUGINS_KEY, JSON.stringify(list));
  } catch {
    /* ignore */
  }
}

export function getInstalledPlugins(): InstalledPlugin[] {
  return readInstalled();
}

function asPlugin(mod: unknown): Record<string, unknown> | null {
  if (!mod || typeof mod !== 'object') return null;
  const m = mod as Record<string, unknown>;
  const p = (m.default || m.plugin || m) as Record<string, unknown>;
  if (!p || typeof p !== 'object') return null;
  return p;
}

/** Map legacy Vite-dev paths to production static paths under public/plugins/. */
export function normalizePluginUrl(url: string): string {
  let href = url.trim();
  if (!href) return href;
  // /src/plugins/foo.js → /plugins/foo.js (dev-only path never ships in dist)
  href = href.replace(/(^|\/)src\/plugins\//, '$1plugins/');
  // Drop accidental example- prefix double paths
  return href;
}

export async function loadPluginFromUrl(url: string): Promise<InstalledPlugin> {
  ensureBuiltins();
  const href = normalizePluginUrl(url);
  if (!href) throw new Error('URL required');

  const mod = await import(/* @vite-ignore */ href);
  const p = asPlugin(mod);
  if (!p) throw new Error('Module did not export a plugin object');

  const id = String(p.id || '');
  const name = String(p.name || id);
  const kind = String(p.kind || '');
  const description = p.description ? String(p.description) : '';

  if (!id || !kind) throw new Error('Plugin needs id and kind');

  if (kind === 'source') {
    if (typeof p.fetchHistorical !== 'function') {
      throw new Error('Source plugin needs fetchHistorical()');
    }
    registerDynamicSource(p as unknown as SourcePlugin);
  } else if (kind === 'stream') {
    if (typeof p.start !== 'function') throw new Error('Stream plugin needs start()');
    registerDynamicStream(p as unknown as StreamPlugin);
  } else if (kind === 'engine') {
    if (typeof p.run !== 'function') throw new Error('Engine plugin needs run()');
    registerDynamicEngine(p as unknown as EnginePlugin);
  } else if (kind === 'storage') {
    throw new Error('Custom storage plugins via URL are not supported yet (use built-in local/cloud)');
  } else {
    throw new Error(`Unknown plugin kind: ${kind}`);
  }

  const entry: InstalledPlugin = { url: href, id, name, kind, description };
  const list = readInstalled().filter((x) => x.url !== href && !(x.kind === kind && x.id === id));
  list.push(entry);
  writeInstalled(list);
  appendLog('ok', `Loaded plugin ${name} (${kind})`, 'plugins');
  return entry;
}

export function removePlugin(id: string, kind?: string) {
  const list = readInstalled();
  const entry = kind
    ? list.find((x) => x.id === id && x.kind === kind)
    : list.find((x) => x.id === id);
  const resolvedKind = kind || entry?.kind;

  if (resolvedKind === 'source') unregisterDynamicSource(id);
  else if (resolvedKind === 'stream') unregisterDynamicStream(id);
  else if (resolvedKind === 'engine') unregisterDynamicEngine(id);
  else {
    // Kind unknown — try all
    unregisterDynamicSource(id);
    unregisterDynamicStream(id);
    unregisterDynamicEngine(id);
  }

  writeInstalled(
    list.filter((x) => !(x.id === id && (!kind || x.kind === kind))),
  );
  appendLog('info', `Removed plugin ${id}`, 'plugins');
}

/** Re-import all saved plugin URLs (call on app boot). */
export async function restoreInstalledPlugins(): Promise<void> {
  ensureBuiltins();
  const list = readInstalled();
  for (const item of list) {
    try {
      await loadPluginFromUrl(item.url);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      appendLog('error', `Failed to restore ${item.url}: ${msg}`, 'plugins');
    }
  }
  if (list.length) {
    appendLog(
      'info',
      `Restored ${list.length} installed plugin URL(s) (${listDynamicSourceIds().length} dynamic sources)`,
      'plugins',
    );
  }
}
