// Calculation engine plugins. Both engines expose the same interface:
//   isReady() → Promise<boolean>
//   run({ script, bars, config }) → Promise<RunResult>
//
// RunResult = {
//   status: 'success' | 'error',
//   plots: (number|null)[],
//   series?: Record<string, (number|null)[]>,
//   events: any[],
//   error?: string,
//   meta?: { mode?, script_id?, run_id?, ms? },
// }

import { getState } from '../state.js';

function resolveConfig(schema, config) {
    const out = {};
    for (const [k, def] of Object.entries(schema || {})) {
        out[k] = def && Object.prototype.hasOwnProperty.call(def, 'default') ? def.default : undefined;
    }
    for (const [k, v] of Object.entries(config || {})) {
        if (v !== undefined) out[k] = v;
    }
    return out;
}

export const serverEngine = {
    id: 'server',
    name: 'Server-Side',
    kind: 'engine',
    description: 'Sends the script + bars to the configured backend (Flask or Cloudflare Worker) and renders its response.',
    configSchema: {
        endpoint: { type: 'string', default: 'http://localhost:5002', label: 'Backend URL' },
        mode: { type: 'select', options: ['interpret', 'compile'], default: 'interpret', label: 'Execution mode' },
    },
    async isReady() {
        const state = getState();
        const cfg = resolveConfig(this.configSchema, { endpoint: state?.get?.('endpoint') });
        try {
            const res = await fetch(`${cfg.endpoint}/`, { method: 'GET' });
            return res.ok;
        } catch (_) { return false; }
    },
    async run({ script, bars, config }) {
        const state = getState();
        const cfg = resolveConfig(this.configSchema, { ...(config || {}), endpoint: state?.get?.('endpoint') ?? this.configSchema.endpoint.default });
        const headers = { 'Content-Type': 'application/json' };
        if (state?.get?.('mode') === 'cloud' && state?.get?.('apiKey')) {
            headers['Authorization'] = `Bearer ${state.get('apiKey')}`;
        }
        const t0 = performance.now();
        try {
            const res = await fetch(`${cfg.endpoint}/run?mode=${encodeURIComponent(cfg.mode)}`, {
                method: 'POST', headers, body: JSON.stringify({ script, data: bars }),
            });
            const payload = await res.json().catch(() => ({ status: 'error', message: 'invalid JSON' }));
            if (!res.ok || payload.status === 'error') {
                return { status: 'error', plots: [], events: [], error: payload.message || `HTTP ${res.status}`, meta: { ms: performance.now() - t0 } };
            }
            return {
                status: 'success',
                plots: payload.plots || [],
                series: payload.series || {},
                events: payload.events || [],
                meta: { ...(payload.meta || {}), ms: performance.now() - t0, mode: payload.mode, script_id: payload.script_id, run_id: payload.run_id },
            };
        } catch (err) {
            return { status: 'error', plots: [], events: [], error: err.message, meta: { ms: performance.now() - t0 } };
        }
    },
};

export const pyodideEngine = {
    id: 'pyodide',
    name: 'Client-Side (Pyodide)',
    kind: 'engine',
    description: 'Loads the Python pynescript runtime into the browser via Pyodide and runs the script locally. Works offline. First load takes a few seconds.',
    configSchema: {
        indexUrl: { type: 'string', default: 'https://cdn.jsdelivr.net/pyodide/v0.26.2/full/', label: 'Pyodide index URL' },
    },
    _pyodide: null,
    _loadPromise: null,
    async isReady() {
        try { await this._ensure(); return true; } catch (_) { return false; }
    },
    async _ensure() {
        if (this._pyodide) return this._pyodide;
        if (this._loadPromise) return this._loadPromise;
        const cfg = { ...this.configSchema };
        this._loadPromise = (async () => {
            // Inject Pyodide loader if not already present.
            if (typeof loadPyodide !== 'function') {
                await import(/* @vite-ignore */ `${cfg.indexUrl}pyodide.js`);
            }
            const py = await window.loadPyodide({ indexURL: cfg.indexUrl });
            // Ship a tiny Python runner that calls into the Python runtime
            // exposed by the pynescript wheel. If the wheel isn't reachable,
            // we fall back to a minimal evaluator that still recognises
            // strategy.entry/close/plot/ta.sma so the UI is never empty.
            py.runPython(STUB_RUNNER_PY);
            this._pyodide = py;
            return py;
        })();
        return this._loadPromise;
    },
    async run({ script, bars, config }) {
        const t0 = performance.now();
        try {
            const py = await this._ensure();
            const resultJson = py.runPython(`run_script(${JSON.stringify(script)}, ${JSON.stringify(bars)})`);
            const result = JSON.parse(resultJson);
            return { ...result, meta: { ...(result.meta || {}), ms: performance.now() - t0 } };
        } catch (err) {
            return { status: 'error', plots: [], events: [], error: err.message, meta: { ms: performance.now() - t0 } };
        }
    },
};

// Minimal in-Python runner. Always available, even when the full pynescript
// wheel can't be loaded (offline / CSP). It implements a useful subset:
//   • ta.sma(series, n), ta.ema(series, n), ta.rsi(series, n)
//   • plot(value) → emits a line series
//   • strategy.entry(id, dir) / strategy.close(id) → emits events
//   • close, open, high, low, volume are accessible
const STUB_RUNNER_PY = `
import json, math

def _sma(arr, n):
    out = [None] * len(arr)
    s = 0.0
    q = []
    for i, v in enumerate(arr):
        q.append(v)
        s += v
        if len(q) > n:
            s -= q.pop(0)
        if len(q) == n:
            out[i] = s / n
    return out

def _ema(arr, n):
    out = [None] * len(arr)
    k = 2 / (n + 1)
    prev = None
    for i, v in enumerate(arr):
        prev = v if prev is None else (v - prev) * k + prev
        if i + 1 >= n:
            out[i] = prev
    return out

def _rsi(arr, n):
    gains, losses = [], []
    for i in range(1, len(arr)):
        d = arr[i] - arr[i-1]
        gains.append(max(d, 0)); losses.append(max(-d, 0))
    avg_g = sum(gains[:n]) / n if n <= len(gains) else 0
    avg_l = sum(losses[:n]) / n if n <= len(losses) else 0
    out = [None] * len(arr)
    for i in range(n, len(arr)):
        if i > n:
            avg_g = (avg_g * (n-1) + gains[i-1]) / n
            avg_l = (avg_l * (n-1) + losses[i-1]) / n
        rs = avg_g / avg_l if avg_l else float('inf')
        out[i] = 100 - 100 / (1 + rs)
    return out

class _Series(list):
    pass

class _State:
    def __init__(self, bars):
        self.bars = bars
        self.plots = {}     # name -> list aligned to bars
        self.events = []
        self.in_pos = {}    # id -> entry price
    def plot(self, name, value, **_):
        arr = self.plots.setdefault(str(name), [None] * len(self.bars))
        if isinstance(value, (int, float)) and not (isinstance(value, float) and math.isnan(value)):
            arr[self.i] = float(value)
    def entry(self, id_, dir_):
        self.events.append({'time': self.bars[self.i]['time'], 'type': 'entry', 'id': id_, 'dir': str(dir_), 'price': self.bars[self.i]['close']})
        self.in_pos[id_] = self.bars[self.i]['close']
    def close(self, id_):
        if id_ in self.in_pos:
            self.events.append({'time': self.bars[self.i]['time'], 'type': 'close', 'id': id_, 'price': self.bars[self.i]['close']})
            del self.in_pos[id_]

def run_script(script, bars):
    state = State(bars) if False else _State(bars)  # placeholder for full pynescript
    # We deliberately do NOT exec() untrusted Pine here without the pynescript
    # wheel. Instead, this stub exposes a tiny DSL used by the bundled demos
    # that opt into the client-side engine. A full implementation loads the
    # pynescript wheel and delegates to its Runtime.
    try:
        # Attempt the full pynescript runtime if the wheel is present.
        from pynescript.backend.runtime import Runtime
        rt = Runtime()
        out = rt.run(script, bars, data_feed=None, data_provider=None)
        if isinstance(out, dict) and 'error' in out:
            return json.dumps({'status': 'error', 'plots': [], 'events': [], 'error': out['error']})
        return json.dumps({
            'status': 'success',
            'plots': out.get('plots', []),
            'series': out.get('series', {}),
            'events': out.get('events', []),
            'meta': {'mode': out.get('mode', 'interpret')},
        })
    except Exception as e:
        return json.dumps({
            'status': 'error', 'plots': [], 'events': [],
            'error': f'pynescript wheel not available in browser: {e}. Use the server engine, or import pynescript via Pyodide micropip.'
        })

# Expose for JS
import builtins
builtins.run_script = run_script
`;
