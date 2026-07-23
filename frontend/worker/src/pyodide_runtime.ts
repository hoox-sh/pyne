// In-Worker Python runtime via Pyodide.
//
// Status: scaffold only.  When `PYODIDE_IN_WORKER=enabled` is set, we lazy-
// load Pyodide from R2 (or the jsDelivr CDN as a dev fallback), mount the
// pynescript wheel from R2, and translate the `/api/run` request into a
// `pynescript.backend.runtime.Runtime().run(script, bars)` call.
//
// Until the wheel upload pipeline is implemented (see RUNTIME.md), this
// returns 503 with a clear hint.

import type { Env } from './index';

let pyReady: Promise<unknown> | null = null;

async function ensurePyodide(_env: Env): Promise<unknown> {
    if (pyReady) return pyReady;
    pyReady = (async () => {
        // Two ways to boot Pyodide in a Worker:
        //   1. `workerd-pyodide` (workerd-native, fastest).
        //   2. Load from CDN at module init (simpler, slower cold start).
        // We use the CDN approach here and let the deploy pipeline swap it
        // for workerd-native in production.
        const indexURL = 'https://cdn.jsdelivr.net/pyodide/v0.26.2/full/';
        const { loadPyodide } = await import(/* @vite-ignore */ `${indexURL}pyodide.js`);
        const py = await (loadPyodide as (opts: { indexURL: string }) => Promise<unknown>)({ indexURL });
        // Stub: in production, load the wheel from R2.
        // await (py as { runPythonAsync: (s: string) => Promise<void> }).runPythonAsync(`
        //     import micropip
        //     await micropip.install('https://r2.example.com/pynescript-0.x.whl')
        // `);
        return py;
    })();
    return pyReady;
}

export async function tryRunInWorker(script: string, bars: unknown[], env: Env): Promise<unknown | null> {
    if (env.PYODIDE_IN_WORKER !== 'enabled') return null;
    try {
        const py = await ensurePyodide(env);
        // @ts-expect-error - Pyodide dynamic
        const json = await py.runPythonAsync(`run_script(${JSON.stringify(script)}, ${JSON.stringify(bars)})`);
        return JSON.parse(json as string);
    } catch (err) {
        return { status: 'error', error: err instanceof Error ? err.message : String(err) };
    }
}
