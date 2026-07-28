// Copyright (C) 2024-2026 jango_blockchained
//
// This file is part of pynescript.
//
// pynescript is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// pynescript is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
//
// SPDX-License-Identifier: AGPL-3.0-or-later

/**
 * Unified plugin registry — single source of truth for all plugin kinds.
 */

import type {
  AnyPlugin,
  ComponentPlugin,
  EnginePlugin,
  PluginKind,
  RegistrySummary,
  SourcePlugin,
  StoragePlugin,
  StreamPlugin,
} from './types';

type Listener = (event: { type: 'registered' | 'unregistered'; kind: PluginKind; id: string }) => void;

function summarize(p: { id: string; name: string; description?: string; builtIn?: boolean }) {
  return {
    id: p.id,
    name: p.name,
    description: p.description || '',
    builtIn: p.builtIn,
  };
}

export class PluginRegistry {
  private _sources = new Map<string, SourcePlugin>();
  private _streams = new Map<string, StreamPlugin>();
  private _engines = new Map<string, EnginePlugin>();
  private _storages = new Map<string, StoragePlugin>();
  private _components = new Map<string, ComponentPlugin>();
  private _listeners = new Set<Listener>();
  /** Preserve registration order within each kind */
  private _sourceOrder: string[] = [];
  private _streamOrder: string[] = [];
  private _engineOrder: string[] = [];
  private _storageOrder: string[] = [];

  on(listener: Listener): () => void {
    this._listeners.add(listener);
    return () => this._listeners.delete(listener);
  }

  private _emit(type: 'registered' | 'unregistered', kind: PluginKind, id: string) {
    for (const l of this._listeners) {
      try {
        l({ type, kind, id });
      } catch {
        /* ignore listener errors */
      }
    }
  }

  private _setOrdered(order: string[], id: string) {
    if (!order.includes(id)) order.push(id);
  }

  private _removeOrdered(order: string[], id: string) {
    const i = order.indexOf(id);
    if (i >= 0) order.splice(i, 1);
  }

  // --- Source ---
  registerSource(source: SourcePlugin): this {
    this._assertSource(source);
    const isNew = !this._sources.has(source.id);
    this._sources.set(source.id, source);
    if (isNew) this._setOrdered(this._sourceOrder, source.id);
    this._emit('registered', 'source', source.id);
    return this;
  }

  getSource(id: string): SourcePlugin | undefined {
    return this._sources.get(id);
  }

  listSources(): SourcePlugin[] {
    return this._sourceOrder.map((id) => this._sources.get(id)!).filter(Boolean);
  }

  unregisterSource(id: string, opts?: { allowBuiltIn?: boolean }): boolean {
    const p = this._sources.get(id);
    if (!p) return false;
    if (p.builtIn && !opts?.allowBuiltIn) return false;
    this._sources.delete(id);
    this._removeOrdered(this._sourceOrder, id);
    this._emit('unregistered', 'source', id);
    return true;
  }

  // --- Stream ---
  registerStream(stream: StreamPlugin): this {
    this._assertStream(stream);
    const isNew = !this._streams.has(stream.id);
    this._streams.set(stream.id, stream);
    if (isNew) this._setOrdered(this._streamOrder, stream.id);
    this._emit('registered', 'stream', stream.id);
    return this;
  }

  getStream(id: string): StreamPlugin | undefined {
    return this._streams.get(id);
  }

  listStreams(): StreamPlugin[] {
    return this._streamOrder.map((id) => this._streams.get(id)!).filter(Boolean);
  }

  unregisterStream(id: string, opts?: { allowBuiltIn?: boolean }): boolean {
    const p = this._streams.get(id);
    if (!p) return false;
    if (p.builtIn && !opts?.allowBuiltIn) return false;
    this._streams.delete(id);
    this._removeOrdered(this._streamOrder, id);
    this._emit('unregistered', 'stream', id);
    return true;
  }

  // --- Engine ---
  registerEngine(engine: EnginePlugin): this {
    this._assertEngine(engine);
    const isNew = !this._engines.has(engine.id);
    this._engines.set(engine.id, engine);
    if (isNew) this._setOrdered(this._engineOrder, engine.id);
    this._emit('registered', 'engine', engine.id);
    return this;
  }

  getEngine(id: string): EnginePlugin | undefined {
    return this._engines.get(id);
  }

  listEngines(): EnginePlugin[] {
    return this._engineOrder.map((id) => this._engines.get(id)!).filter(Boolean);
  }

  unregisterEngine(id: string, opts?: { allowBuiltIn?: boolean }): boolean {
    const p = this._engines.get(id);
    if (!p) return false;
    if (p.builtIn && !opts?.allowBuiltIn) return false;
    this._engines.delete(id);
    this._removeOrdered(this._engineOrder, id);
    this._emit('unregistered', 'engine', id);
    return true;
  }

  // --- Storage (PR2) ---
  registerStorage(storage: StoragePlugin): this {
    this._assertStorage(storage);
    const isNew = !this._storages.has(storage.id);
    this._storages.set(storage.id, storage);
    if (isNew) this._setOrdered(this._storageOrder, storage.id);
    this._emit('registered', 'storage', storage.id);
    return this;
  }

  getStorage(id: string): StoragePlugin | undefined {
    return this._storages.get(id);
  }

  listStorages(): StoragePlugin[] {
    return this._storageOrder.map((id) => this._storages.get(id)!).filter(Boolean);
  }

  unregisterStorage(id: string, opts?: { allowBuiltIn?: boolean }): boolean {
    const p = this._storages.get(id);
    if (!p) return false;
    if (p.builtIn && !opts?.allowBuiltIn) return false;
    this._storages.delete(id);
    this._removeOrdered(this._storageOrder, id);
    this._emit('unregistered', 'storage', id);
    return true;
  }

  // --- Component (phase 2) ---
  registerComponent(component: ComponentPlugin): this {
    if (!component?.id || component.kind !== 'component') {
      throw new Error("component: id and kind 'component' required");
    }
    if (typeof component.mount !== 'function') throw new Error('component: mount() required');
    this._components.set(component.id, component);
    this._emit('registered', 'component', component.id);
    return this;
  }

  getComponent(id: string): ComponentPlugin | undefined {
    return this._components.get(id);
  }

  listComponents(): ComponentPlugin[] {
    return [...this._components.values()];
  }

  // --- Bulk ---
  clear(): void {
    this._sources.clear();
    this._streams.clear();
    this._engines.clear();
    this._storages.clear();
    this._components.clear();
    this._sourceOrder = [];
    this._streamOrder = [];
    this._engineOrder = [];
    this._storageOrder = [];
  }

  summary(): RegistrySummary {
    return {
      sources: this.listSources().map(summarize),
      streams: this.listStreams().map(summarize),
      engines: this.listEngines().map(summarize),
      storages: this.listStorages().map(summarize),
    };
  }

  register(plugin: AnyPlugin): this {
    switch (plugin.kind) {
      case 'source':
        return this.registerSource(plugin);
      case 'stream':
        return this.registerStream(plugin);
      case 'engine':
        return this.registerEngine(plugin);
      case 'storage':
        return this.registerStorage(plugin);
      case 'component':
        return this.registerComponent(plugin);
      default:
        throw new Error(`Unknown plugin kind: ${(plugin as AnyPlugin).kind}`);
    }
  }

  unregister(kind: PluginKind, id: string, opts?: { allowBuiltIn?: boolean }): boolean {
    switch (kind) {
      case 'source':
        return this.unregisterSource(id, opts);
      case 'stream':
        return this.unregisterStream(id, opts);
      case 'engine':
        return this.unregisterEngine(id, opts);
      case 'storage':
        return this.unregisterStorage(id, opts);
      case 'component': {
        if (!this._components.has(id)) return false;
        this._components.delete(id);
        this._emit('unregistered', 'component', id);
        return true;
      }
      default:
        return false;
    }
  }

  private _assertSource(s: SourcePlugin) {
    if (!s || typeof s !== 'object') throw new Error('source: not an object');
    if (!s.id || !s.name) throw new Error('source: id and name required');
    if (s.kind !== 'source') throw new Error(`source: kind must be 'source' (got ${s.kind})`);
    if (typeof s.fetchHistorical !== 'function') throw new Error('source: fetchHistorical() required');
  }

  private _assertStream(s: StreamPlugin) {
    if (!s || typeof s !== 'object') throw new Error('stream: not an object');
    if (!s.id || !s.name) throw new Error('stream: id and name required');
    if (s.kind !== 'stream') throw new Error(`stream: kind must be 'stream' (got ${s.kind})`);
    if (typeof s.start !== 'function') throw new Error('stream: start() required');
  }

  private _assertEngine(e: EnginePlugin) {
    if (!e || typeof e !== 'object') throw new Error('engine: not an object');
    if (!e.id || !e.name) throw new Error('engine: id and name required');
    if (e.kind !== 'engine') throw new Error(`engine: kind must be 'engine' (got ${e.kind})`);
    if (typeof e.run !== 'function') throw new Error('engine: run() required');
  }

  private _assertStorage(s: StoragePlugin) {
    if (!s || typeof s !== 'object') throw new Error('storage: not an object');
    if (!s.id || !s.name) throw new Error('storage: id and name required');
    if (s.kind !== 'storage') throw new Error(`storage: kind must be 'storage' (got ${s.kind})`);
    if (typeof s.list !== 'function') throw new Error('storage: list() required');
    if (typeof s.read !== 'function') throw new Error('storage: read() required');
    if (typeof s.write !== 'function') throw new Error('storage: write() required');
    if (typeof s.remove !== 'function') throw new Error('storage: remove() required');
  }
}

/** Shared singleton used by Solid AXIS path */
export const registry = new PluginRegistry();
