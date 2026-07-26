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
            const res = await fetch(`${cfg.endpoint}/`, {
                method: 'GET',
                signal: AbortSignal.timeout(30_000),
            });
            return res.ok;
        } catch (_) { return false; }
    },
    async run({ script, bars, config }) {
        const state = getState();
        const endpoint = config?.endpoint || state?.get?.('endpoint') || this.configSchema.endpoint.default;
        const cfg = resolveConfig(this.configSchema, { ...(config || {}), endpoint });
        const headers = { 'Content-Type': 'application/json' };
        if (state?.get?.('mode') === 'cloud' && state?.get?.('apiKey')) {
            headers['Authorization'] = `Bearer ${state.get('apiKey')}`;
        }
        const t0 = performance.now();
        try {
            const res = await fetch(`${cfg.endpoint}/run?mode=${encodeURIComponent(cfg.mode)}`, {
                method: 'POST', headers, body: JSON.stringify({ script, data: bars }),
                signal: AbortSignal.timeout(30_000),
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
    _progressCallback: null,
    setProgressCallback(cb) { this._progressCallback = cb; },
    _emitProgress(msg) { if (this._progressCallback) this._progressCallback(msg); },
    async isReady() {
        try { await this._ensure(); return true; } catch (_) { return false; }
    },
    async _ensure() {
        if (this._pyodide) return this._pyodide;
        if (this._loadPromise) return this._loadPromise;
        const self = this;
        const cfg = resolveConfig(this.configSchema, {});
        // Overall timeout: 90s should be plenty for CDN + wheel + runtime
        const TIMEOUT_MS = 90_000;
        const timer = setTimeout(() => {
            self._loadPromise = null;
            self._emitProgress('');
        }, TIMEOUT_MS);
        this._loadPromise = (async () => {
            try {
                const origin = location.origin;
                self._emitProgress('Loading Pyodide runtime…');
                // Inject Pyodide loader if not already present.
                if (typeof loadPyodide !== 'function') {
                    try {
                        await import(/* @vite-ignore */ `${cfg.indexUrl}pyodide.js`);
                    } catch (e) {
                        clearTimeout(timer);
                        throw new Error(`Failed to load Pyodide from CDN: ${e.message}. Check your internet connection.`);
                    }
                }
                self._emitProgress('Initialising Pyodide…');
                const timeoutPy = AbortSignal.timeout(TIMEOUT_MS - 10_000);
                const py = await window.loadPyodide({ indexURL: cfg.indexUrl, signal: timeoutPy });

                self._emitProgress('Installing micropip…');
                await py.loadPackage('micropip');

                self._emitProgress('Installing pynescript…');
                const micropip = py.pyimport('micropip');
                const wheelUrl = `${origin}/vendor/pynescript-0.2.0-py3-none-any.whl`;
                const antlrUrl = `${origin}/vendor/antlr4_python3_runtime-4.13.2-py3-none-any.whl`;
                // Guard against SPA HTML fallback → micropip BadZipFile
                const wheelRes = await fetch(wheelUrl);
                if (!wheelRes.ok) {
                    throw new Error(`pynescript wheel missing: HTTP ${wheelRes.status} at ${wheelUrl}`);
                }
                const wheelCt = (wheelRes.headers.get('content-type') || '').toLowerCase();
                if (wheelCt.includes('text/html')) {
                    throw new Error(
                        `pynescript wheel returned HTML (SPA fallback) at ${wheelUrl} — deploy public/vendor into dist/`,
                    );
                }
                try {
                    await micropip.install(wheelUrl, false);
                } catch (e) {
                    throw new Error(`Failed to load pynescript wheel from ${origin}: ${e.message}`);
                }
                try {
                    const antlrRes = await fetch(antlrUrl);
                    if (antlrRes.ok && !(antlrRes.headers.get('content-type') || '').includes('text/html')) {
                        await micropip.install(antlrUrl, false);
                    } else {
                        await micropip.install('antlr4-python3-runtime>=4.13.1');
                    }
                } catch (e) {
                    throw new Error(`Failed to install antlr4: ${e.message}. Check /vendor or internet.`);
                }

                self._emitProgress('Loading Pine runtime…');
                const runtimeResp = await fetch(`${origin}/pyodide/pynescript_runtime.py`);
                if (!runtimeResp.ok) throw new Error(`Failed to load pynescript_runtime.py: HTTP ${runtimeResp.status}`);
                const runtimePy = await runtimeResp.text();
                if (runtimePy.trimStart().startsWith('<!')) {
                    throw new Error(`pynescript_runtime.py returned HTML — deploy public/pyodide into dist/`);
                }
                await py.runPythonAsync(runtimePy);

                self._emitProgress('');
                clearTimeout(timer);
                self._pyodide = py;
                return py;
            } catch (err) {
                self._loadPromise = null;
                self._emitProgress('');
                clearTimeout(timer);
                throw err;
            }
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
            return { status: 'error', plots: [], series: {}, events: [], error: err.message, meta: { ms: performance.now() - t0 } };
        }
    },
};
