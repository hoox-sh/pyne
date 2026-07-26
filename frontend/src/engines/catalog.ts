/**
 * Built-in calculation engines for AXIS (Solid path).
 * Uses the Solid store for endpoint / config — not legacy state.js.
 */

import type { EnginePlugin, RunResult } from '../plugins/types';
import { store } from '../store';
import { registry } from '../plugins/registry';

function resolveConfig(
  schema: EnginePlugin['configSchema'],
  config?: Record<string, unknown>,
): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, def] of Object.entries(schema || {})) {
    out[k] = def && 'default' in def ? def.default : undefined;
  }
  for (const [k, v] of Object.entries(config || {})) {
    if (v !== undefined) out[k] = v;
  }
  return out;
}

/** Ensure a URL is a real zip/wheel, not SPA HTML fallback (micropip BadZipFile). */
async function assertZipAsset(url: string, label: string): Promise<void> {
  const res = await fetch(url, { method: 'GET', signal: AbortSignal.timeout(30_000) });
  if (!res.ok) {
    throw new Error(`${label} missing: HTTP ${res.status} at ${url}`);
  }
  const ct = (res.headers.get('content-type') || '').toLowerCase();
  if (ct.includes('text/html')) {
    throw new Error(
      `${label} returned HTML (SPA fallback) at ${url} — deploy public/vendor and public/pyodide into dist/`,
    );
  }
  const buf = new Uint8Array(await res.arrayBuffer());
  // ZIP local file header magic: PK\x03\x04
  if (buf.length < 4 || buf[0] !== 0x50 || buf[1] !== 0x4b) {
    const head = new TextDecoder().decode(buf.slice(0, 32));
    throw new Error(
      `${label} is not a zip/wheel at ${url} (got ${buf.length} bytes, starts with ${JSON.stringify(head)})`,
    );
  }
}

export const serverEngine: EnginePlugin = {
  id: 'server',
  name: 'Server-Side',
  kind: 'engine',
  builtIn: true,
  description:
    'Sends the script + bars to the configured backend (Flask or Cloudflare Worker) and renders its response.',
  capabilities: { needsNetwork: true },
  configSchema: {
    endpoint: { type: 'string', default: 'http://localhost:5002', label: 'Backend URL' },
    mode: {
      type: 'select',
      options: ['interpret', 'compile'],
      default: 'interpret',
      label: 'Execution mode',
    },
  },
  async isReady() {
    const endpoint = (store.endpoint || this.configSchema!.endpoint.default as string).replace(/\/$/, '');
    try {
      const res = await fetch(`${endpoint}/`, {
        method: 'GET',
        signal: AbortSignal.timeout(8_000),
      });
      return res.ok;
    } catch {
      return false;
    }
  },
  async run({ script, bars, config, signal }) {
    const endpoint = (
      (config?.endpoint as string) ||
      store.endpoint ||
      (this.configSchema!.endpoint.default as string)
    ).replace(/\/$/, '');
    const cfg = resolveConfig(this.configSchema, { ...(config || {}), endpoint });
    const mode = String(cfg.mode || 'interpret');
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    const t0 = performance.now();
    const timeoutMs = Math.min(
      180_000,
      Math.max(60_000, 30_000 + (bars?.length || 0) * 80),
    );
    try {
      const res = await fetch(`${endpoint}/run?mode=${encodeURIComponent(mode)}`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ script, data: bars }),
        signal: signal ?? AbortSignal.timeout(timeoutMs),
      });
      const payload = await res.json().catch(() => ({ status: 'error', message: 'invalid JSON' }));
      if (!res.ok || payload.status === 'error') {
        return {
          status: 'error',
          plots: [],
          events: [],
          series: {},
          error: payload.message || `HTTP ${res.status}`,
          meta: { ms: performance.now() - t0 },
        } satisfies RunResult;
      }
      return {
        status: 'success',
        plots: payload.plots || [],
        series: payload.series || {},
        events: payload.events || [],
        drawings: payload.drawings || [],
        meta: {
          ...(payload.meta || {}),
          ms: performance.now() - t0,
          mode: payload.mode,
          script_id: payload.script_id,
          run_id: payload.run_id,
          overlay: payload.meta?.overlay ?? true,
          script_name: payload.meta?.script_name || 'plot',
          plot_meta: payload.plot_meta || {},
        },
      } satisfies RunResult;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      return {
        status: 'error',
        plots: [],
        events: [],
        series: {},
        error: msg,
        meta: { ms: performance.now() - t0 },
      } satisfies RunResult;
    }
  },
};

type PyodideLike = {
  loadPackage: (name: string) => Promise<void>;
  pyimport: (name: string) => { install: (url: string, keep?: boolean) => Promise<void> };
  runPythonAsync: (code: string) => Promise<void>;
  runPython: (code: string) => string;
};

declare global {
  interface Window {
    loadPyodide?: (opts: { indexURL: string }) => Promise<PyodideLike>;
  }
}

/** Self-hosted Pyodide (public/pyodide/v0.26.2 — ~14MB, no CDN required). */
export const LOCAL_PYODIDE_VERSION = '0.26.2';
export const LOCAL_PYODIDE_INDEX = `/pyodide/v${LOCAL_PYODIDE_VERSION}/`;

/** Absolute indexURL with trailing slash (relative paths resolve against location.origin). */
export function resolvePyodideIndexUrl(configured?: string): string {
  const raw = (configured || LOCAL_PYODIDE_INDEX).trim() || LOCAL_PYODIDE_INDEX;
  if (/^https?:\/\//i.test(raw)) {
    return raw.endsWith('/') ? raw : `${raw}/`;
  }
  const origin = typeof location !== 'undefined' ? location.origin : '';
  const path = raw.startsWith('/') ? raw : `/${raw}`;
  const withSlash = path.endsWith('/') ? path : `${path}/`;
  return `${origin}${withSlash}`;
}

function pyodidePluginConfig(): Record<string, unknown> {
  const configs = store.pluginsConfig || {};
  return (configs['engine:pyodide'] || configs.pyodide || {}) as Record<string, unknown>;
}

/** Prefetch core Pyodide assets into HTTP cache (wasm + stdlib are the heavy bits). */
export function prefetchPyodideAssets(indexUrl?: string): void {
  if (typeof document === 'undefined') return;
  const base = resolvePyodideIndexUrl(indexUrl);
  const files = [
    'pyodide.js',
    'pyodide.asm.js',
    'pyodide.asm.wasm',
    'python_stdlib.zip',
    'pyodide-lock.json',
    'micropip-0.6.0-py3-none-any.whl',
    'packaging-23.2-py3-none-any.whl',
  ];
  for (const f of files) {
    const href = `${base}${f}`;
    if (document.querySelector(`link[data-axis-pyodide="${f}"]`)) continue;
    const link = document.createElement('link');
    link.rel = f.endsWith('.js') ? 'modulepreload' : 'prefetch';
    link.href = href;
    link.as = f.endsWith('.wasm') ? 'fetch' : f.endsWith('.js') ? 'script' : 'fetch';
    link.crossOrigin = 'anonymous';
    link.dataset.axisPyodide = f;
    document.head.appendChild(link);
  }
  // Also warm vendor wheels + runtime (same-origin)
  if (typeof location !== 'undefined') {
    const origin = location.origin;
    for (const path of [
      '/vendor/pynescript-0.2.0-py3-none-any.whl',
      '/vendor/antlr4_python3_runtime-4.13.2-py3-none-any.whl',
      '/pyodide/pynescript_runtime.py',
    ]) {
      void fetch(`${origin}${path}`, { method: 'GET', credentials: 'same-origin' }).catch(() => {});
    }
  }
}

/**
 * Preload full Pyodide + pynescript runtime in the background.
 * Safe to call multiple times; shares the same ensure promise.
 */
export function preloadPyodide(): Promise<unknown> {
  prefetchPyodideAssets();
  return pyodideEngine._ensure().catch((err: unknown) => {
    // Soft-fail: preload must not break the app if assets are missing
    console.warn('[axis] pyodide preload failed', err);
    return null;
  });
}

export const pyodideEngine: EnginePlugin & {
  _pyodide: PyodideLike | null;
  _loadPromise: Promise<PyodideLike> | null;
  _ensure: () => Promise<PyodideLike>;
} = {
  id: 'pyodide',
  name: 'Client-Side (Pyodide)',
  kind: 'engine',
  builtIn: true,
  description:
    'Runs Pine in the browser via self-hosted Pyodide (~14MB from this origin). Preloads on idle; no CDN required after deploy.',
  capabilities: { offline: true, needsNetwork: false },
  configSchema: {
    indexUrl: {
      type: 'string',
      default: LOCAL_PYODIDE_INDEX,
      label: 'Pyodide index URL (default: self-hosted /pyodide/v0.26.2/)',
    },
  },
  _pyodide: null,
  _loadPromise: null,
  async isReady() {
    try {
      await this._ensure();
      return true;
    } catch {
      return false;
    }
  },
  async _ensure() {
    if (this._pyodide) return this._pyodide;
    if (this._loadPromise) return this._loadPromise;
    const self = this;
    const cfg = resolveConfig(this.configSchema, pyodidePluginConfig());
    const indexUrl = resolvePyodideIndexUrl(String(cfg.indexUrl || LOCAL_PYODIDE_INDEX));
    this._loadPromise = (async () => {
      const origin = typeof location !== 'undefined' ? location.origin : '';
      prefetchPyodideAssets(indexUrl);

      if (typeof window !== 'undefined' && typeof window.loadPyodide !== 'function') {
        await import(/* @vite-ignore */ `${indexUrl}pyodide.js`);
      }
      if (typeof window === 'undefined' || typeof window.loadPyodide !== 'function') {
        throw new Error('loadPyodide not available');
      }
      const py = await window.loadPyodide({ indexURL: indexUrl });
      // micropip + packaging served from same self-hosted index
      await py.loadPackage('micropip');
      const micropip = py.pyimport('micropip');

      // Local wheels under /vendor (public/ → dist). Validate before micropip
      // so SPA HTML fallbacks surface as clear errors instead of BadZipFile.
      const wheelUrl = `${origin}/vendor/pynescript-0.2.0-py3-none-any.whl`;
      const antlrUrl = `${origin}/vendor/antlr4_python3_runtime-4.13.2-py3-none-any.whl`;
      await assertZipAsset(wheelUrl, 'pynescript wheel');
      try {
        await micropip.install(wheelUrl, false);
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        throw new Error(`Failed to install pynescript wheel from ${wheelUrl}: ${msg}`);
      }
      try {
        await assertZipAsset(antlrUrl, 'antlr4 wheel');
        await micropip.install(antlrUrl, false);
      } catch {
        try {
          await micropip.install('antlr4-python3-runtime>=4.13.1');
        } catch {
          /* may already be present via wheel deps */
        }
      }

      const runtimeUrl = `${origin}/pyodide/pynescript_runtime.py`;
      const runtimeResp = await fetch(runtimeUrl);
      if (!runtimeResp.ok) {
        throw new Error(`Failed to load pynescript_runtime.py: HTTP ${runtimeResp.status} (${runtimeUrl})`);
      }
      const runtimeCt = runtimeResp.headers.get('content-type') || '';
      const runtimePy = await runtimeResp.text();
      if (runtimeCt.includes('text/html') || runtimePy.trimStart().startsWith('<!')) {
        throw new Error(
          `pynescript_runtime.py returned HTML instead of Python — is ${runtimeUrl} deployed under dist/pyodide/?`,
        );
      }
      await py.runPythonAsync(runtimePy);
      self._pyodide = py;
      return py;
    })().catch((err) => {
      self._loadPromise = null;
      throw err;
    });
    return this._loadPromise;
  },
  async run({ script, bars }) {
    const t0 = performance.now();
    try {
      const py = await this._ensure();
      const resultJson = py.runPython(
        `run_script(${JSON.stringify(script)}, ${JSON.stringify(bars)})`,
      );
      const result = JSON.parse(resultJson) as RunResult;
      return {
        ...result,
        series: result.series || {},
        events: result.events || [],
        meta: { ...(result.meta || {}), ms: performance.now() - t0 },
      };
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      return {
        status: 'error',
        plots: [],
        series: {},
        events: [],
        error: msg,
        meta: { ms: performance.now() - t0 },
      };
    }
  },
};

export const BUILTIN_ENGINES: EnginePlugin[] = [serverEngine, pyodideEngine];

let registered = false;

export function ensureEnginesRegistered(): void {
  if (registered) return;
  registered = true;
  for (const e of BUILTIN_ENGINES) {
    if (!registry.getEngine(e.id)) {
      registry.registerEngine(e);
    }
  }
}

export function getEngine(id: string): EnginePlugin | undefined {
  ensureEnginesRegistered();
  return registry.getEngine(id);
}

export function listEngines(): EnginePlugin[] {
  ensureEnginesRegistered();
  return registry.listEngines();
}

export function registerDynamicEngine(engine: EnginePlugin): void {
  ensureEnginesRegistered();
  if (!engine?.id || engine.kind !== 'engine') throw new Error('Invalid engine plugin');
  if (typeof engine.run !== 'function') throw new Error('Engine must implement run()');
  registry.registerEngine({ ...engine, builtIn: engine.builtIn ?? false });
}

export function unregisterDynamicEngine(id: string): boolean {
  ensureEnginesRegistered();
  return registry.unregisterEngine(id);
}

export function listDynamicEngineIds(): string[] {
  ensureEnginesRegistered();
  return registry.listEngines().filter((e) => !e.builtIn).map((e) => e.id);
}

/** @internal test helper */
export function _resetEngineRegistrationFlag() {
  registered = false;
}
