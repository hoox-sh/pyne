// Tiny plugin registry. All sources/streams/engines register through here.
// A plugin is an object with `{ id, name, kind, description, ... }` where
// `kind` is one of: 'source', 'stream', 'engine'.

class Registry {
    constructor() {
        this._sources = new Map();
        this._streams = new Map();
        this._engines = new Map();
    }

    // --- Source ---
    registerSource(source) {
        this._assertSource(source);
        this._sources.set(source.id, source);
        return this;
    }
    getSource(id) { return this._sources.get(id); }
    listSources() { return [...this._sources.values()]; }

    // --- Stream ---
    registerStream(stream) {
        this._assertStream(stream);
        this._streams.set(stream.id, stream);
        return this;
    }
    getStream(id) { return this._streams.get(id); }
    listStreams() { return [...this._streams.values()]; }

    // --- Engine ---
    registerEngine(engine) {
        this._assertEngine(engine);
        this._engines.set(engine.id, engine);
        return this;
    }
    getEngine(id) { return this._engines.get(id); }
    listEngines() { return [...this._engines.values()]; }

    // --- Bulk ---
    clear() { this._sources.clear(); this._streams.clear(); this._engines.clear(); }
    summary() {
        return {
            sources: this.listSources().map((s) => ({ id: s.id, name: s.name, description: s.description })),
            streams: this.listStreams().map((s) => ({ id: s.id, name: s.name, description: s.description })),
            engines: this.listEngines().map((e) => ({ id: e.id, name: e.name, description: e.description })),
        };
    }

    _assertSource(s) {
        if (!s || typeof s !== 'object') throw new Error('source: not an object');
        if (!s.id || !s.name) throw new Error('source: id and name required');
        if (s.kind !== 'source') throw new Error(`source: kind must be 'source' (got ${s.kind})`);
        if (typeof s.fetchHistorical !== 'function') throw new Error('source: fetchHistorical() required');
    }
    _assertStream(s) {
        if (!s || typeof s !== 'object') throw new Error('stream: not an object');
        if (!s.id || !s.name) throw new Error('stream: id and name required');
        if (s.kind !== 'stream') throw new Error(`stream: kind must be 'stream' (got ${s.kind})`);
        if (typeof s.start !== 'function') throw new Error('stream: start() required');
    }
    _assertEngine(e) {
        if (!e || typeof e !== 'object') throw new Error('engine: not an object');
        if (!e.id || !e.name) throw new Error('engine: id and name required');
        if (e.kind !== 'engine') throw new Error(`engine: kind must be 'engine' (got ${e.kind})`);
        if (typeof e.run !== 'function') throw new Error('engine: run() required');
    }
}

export const registry = new Registry();
export { Registry };

// Allow plugins to be loaded later via dynamic import. Each entry is
// { id, url } — url is an ES module that default-exports a plugin object.
export async function loadPluginFromUrl(url) {
    const mod = await import(/* @vite-ignore */ url);
    const plugin = mod.default || mod.plugin || mod;
    if (!plugin || !plugin.kind) throw new Error(`Plugin at ${url} did not export a plugin object`);
    if (plugin.kind === 'source') registry.registerSource(plugin);
    else if (plugin.kind === 'stream') registry.registerStream(plugin);
    else if (plugin.kind === 'engine') registry.registerEngine(plugin);
    else throw new Error(`Plugin at ${url} has unknown kind: ${plugin.kind}`);
    return plugin;
}
