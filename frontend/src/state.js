// Central, persisted state for AXIS (formerly SuperChart Lite).
// One source of truth — every UI module reads/writes through here.
// Prefer Solid store (`src/store/`) for the Vite app; this module serves the legacy path.

const STORAGE_KEY = 'pynescript.axis.v1';
const LEGACY_STORAGE_KEYS = [
    'pynescript.superchart.v2',
    'pynescript.superchart.v1',
];

const DEFAULT_STATE = Object.freeze({
    endpoint: 'http://localhost:5002',
    engine: 'server',           // 'server' | 'pyodide' | <custom>
    source: 'binance-rest',     // 'binance-rest' | 'mock-walk' | 'csv-upload' | <custom>
    stream: 'binance-ws',       // 'binance-ws' | 'mock-poll' | 'none' | <custom>
    symbol: 'BTCUSDT',
    interval: '1d',
    mode: 'local',              // 'local' | 'cloud'
    apiKey: '',
    script: '',
    plugins: [],                // [{id, kind, name, source:'inline'|'url'}]
    pluginsConfig: {},          // { '<pluginId>': { ...user-set fields from configSchema } }
    timeRange: 'ALL',
});

let _savedData = null; // in-memory cache to avoid reading localStorage on every assign

function readKey(key) {
    try {
        return localStorage.getItem(key);
    } catch (_) {
        return null;
    }
}

function load() {
    if (_savedData) return _savedData;
    try {
        let raw = readKey(STORAGE_KEY);
        if (!raw) {
            for (const legacy of LEGACY_STORAGE_KEYS) {
                raw = readKey(legacy);
                if (raw) {
                    try { localStorage.setItem(STORAGE_KEY, raw); } catch (_) { /* quota */ }
                    break;
                }
            }
        }
        if (!raw) return null;
        const parsed = JSON.parse(raw);
        _savedData = parsed && typeof parsed === 'object' ? parsed : null;
        return _savedData;
    } catch (_) {
        return null;
    }
}

function save(partial) {
    try {
        const prev = _savedData || {};
        const next = { ...prev, ...partial };
        // Only stamp savedAt for explicit saves (not every keystroke or trivial state flush)
        _savedData = next;
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
        return next;
    } catch (_) { /* quota */ }
}

class State extends EventTarget {
    constructor(initial = {}) {
        super();
        this._data = { ...DEFAULT_STATE, ...initial };
        Object.freeze(this._data); // immutable at the top level; nested updates use assign()
    }

    get(key) { return key ? this._data[key] : this._data; }

    assign(partial) {
        if (!partial || typeof partial !== 'object' || !Object.keys(partial).length) return;
        const next = { ...this._data, ...partial };
        this._data = Object.freeze(next);
        save(next);
        this.dispatchEvent(new CustomEvent('change', { detail: partial }));
    }

    snapshot() { return { ...this._data }; }

    /** Explicitly persist with savedAt timestamp (not triggered on every keystroke). */
    persist() {
        const stamped = { ...this._data, savedAt: Date.now() };
        this._data = Object.freeze(stamped);
        save(stamped);
    }
}

let _state = null;
export function getState() { return _state; }
export function initState() {
    if (_state) return _state;
    const stored = load();
    _state = new State(stored || {});
    return _state;
}
export function resetState() {
    localStorage.removeItem(STORAGE_KEY);
    for (const legacy of LEGACY_STORAGE_KEYS) {
        try { localStorage.removeItem(legacy); } catch (_) { /* */ }
    }
    _savedData = null;
    _state = new State();
    return _state;
}

export { STORAGE_KEY };
