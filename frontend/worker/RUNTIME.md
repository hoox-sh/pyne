# RUNTIME.md — In-Worker Python via Pyodide

**Status:** planned, not yet implemented.

## Goal

Run the Python pynescript runtime **inside the Cloudflare Worker**, removing
the dependency on an external Flask service. This unlocks a fully-CF
deployment (Pages + Worker + KV + D1 + R2) with no other infrastructure.

## Plan

1. **Bundle the pynescript wheel.** Build a single-file wheel for
   `pynescript` (and its antlr4 runtime, asdl, etc.) stripped of the
   LSP-only parts. Upload to R2 under `bundles/pynescript-0.x.y-py3-none-any.whl`.
2. **Load Pyodide in the Worker.** The
   [pyodide-port](https://github.com/hoodmane/pyodide-port) project ships a
   `worker.js` that runs Pyodide in a WebAssembly Worker. We can use
   `@cloudflare/workers-py` or vendor the loader. Pin the Pyodide version
   in `wrangler.toml` and upload the index to R2 for offline boot.
3. **Bridge `Runtime().run()`.** Expose a small TS wrapper that calls
   `pyodide.runPythonAsync("from pynescript.backend.runtime import Runtime; r = Runtime()")`
   and forwards `run(script, bars, ...)` requests to it. The result is
   serialised via `json.dumps(...)` and returned as the Worker's response.
4. **Cache the wheel in module memory.** Use `env.BUNDLES.get(key)` plus
   `caches.default` so subsequent runs in the same isolate avoid re-fetching.
5. **Cold start budget.** Pyodide boot is ~3 s on first run; cache the
   `globals` dict across invocations using module-level state.

## Constraints

- Worker CPU time limit: 30 s (paid plan). Pine evaluation of 500 bars
  should fit in well under 1 s of CPU.
- Worker memory: 128 MB. Pyodide itself is ~30 MB; the pynescript wheel
  is ~5 MB. Comfortable.
- Network: Worker → R2 calls are free; calls to external APIs are metered.

## Roll-out

Behind a feature flag: when `RUNTIME_MODE=in-worker` is set, the Worker
runs the script itself. Otherwise it proxies to `EXTERNAL_BACKEND`. This
lets us A/B test in production.
