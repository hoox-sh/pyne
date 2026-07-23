# SuperChart Lite — Modular PWA Design (2026-07-23)

## Goal
Promote the existing static prototype into a **fully modular PWA** that runs the
real Pine Script evaluator client-side **and/or** on a **Cloudflare Worker
backend**, with swappable **data sources** and **live datastreams** — no
hard-coded providers, no fixed deployment target.

## Why
- The current `frontend/` is a single static page with hard-coded Binance
  fetch + a single `fetch /run` call against the Flask backend.
- The user wants "no border or restriction" — the app must work offline, with
  any data provider, on any backend (local Flask OR Cloudflare Pages + Worker),
  with calculation on either side.
- The Python evaluator is large; running it in the browser via Pyodide gives
  full Pine Script v6 parity without a server roundtrip.

## Architecture

```
┌─────────────────────────── Browser (PWA) ─────────────────────────────┐
│  Service Worker · manifest.webmanifest · offline cache               │
│  UI: lightweight-charts + CodeMirror 6 + tabs                         │
│                                                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────────┐    │
│  │ Sources  │  │ Streams  │  │ Engines  │  │ Storage (localStorage│   │
│  │ (history)│  │ (live)   │  │ (calc)   │  │  + IDB for offline)  │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────────────────┘    │
│       │             │              │                                    │
│       ▼             ▼              ▼                                    │
│  registry-driven, all plugins share the same contract                 │
└───────────────────────────────────────────────────────────────────────┘
            │                                            │
            ▼ (only if engine=server OR stream=remote)   ▼
┌─────────────────────────── Backend (pluggable) ───────────────────────┐
│  Local Flask `make run`      OR      Cloudflare Pages + Worker        │
│  (existing, dev only)                 • Pages: static PWA             │
│                                       • Worker: /api/run, /api/stream│
│                                       • Durable Object: live session  │
│                                       • KV: API keys, usage meter     │
│                                       • D1: persistent runs/scripts   │
│                                       • R2: indicator bundle cache    │
│                                       • WebSocket Hibernation (DO)    │
└───────────────────────────────────────────────────────────────────────┘
```

## Plugin contracts (registry)

Every plugin is `{ id, name, kind, description, configSchema, factory }`.
Three kinds:

### `Source` (historical OHLCV)
```ts
interface Source {
  id: string;
  name: string;
  kind: 'source';
  description: string;
  configSchema: JSONSchema;     // shown in top-bar config popover
  fetchHistorical(opts: {
    symbol: string; interval: string; limit?: number;
    config: Record<string, unknown>;
  }): Promise<Bar[]>;            // Bar = {time, open, high, low, close, volume?}
}
```

### `Stream` (live tick / bar push)
```ts
interface Stream {
  id: string;
  kind: 'stream';
  start(opts: { symbol, interval, config, onBar(bar) }): () => void; // returns stop
}
```

### `Engine` (calculate)
```ts
interface Engine {
  id: 'server' | 'pyodide' | string;
  kind: 'engine';
  isReady(): Promise<boolean>;
  run(opts: { script: string; bars: Bar[]; config }): Promise<RunResult>;
}
type RunResult = {
  status: 'success' | 'error';
  plots: (number|null)[];
  series?: Record<string, (number|null)[]>;
  events: StrategyEvent[];
  metrics?: Record<string, number|string>;
  error?: string;
  meta?: { mode?: string; script_id?: string; run_id?: string; ms?: number };
};
```

## Shipped plugins (initial set)

| Kind     | id            | Notes |
|----------|---------------|-------|
| Source   | `binance-rest`| `https://api.binance.com/api/v3/klines` |
| Source   | `mock-walk`   | Random-walk synthesis (offline fallback) |
| Source   | `csv-upload`  | User-uploaded CSV/JSON |
| Stream   | `binance-ws`  | `wss://stream.binance.com:9443/ws/<sym>@kline_<tf>` |
| Stream   | `mock-poll`   | Synthesizes incremental bars (no network) |
| Stream   | `none`        | Paused |
| Engine   | `server`      | `POST {endpoint}/run`; works against Flask or CF Worker |
| Engine   | `pyodide`     | Loads pynescript wheel via Pyodide CDN, runs `Runtime().run()` in-browser |

Users can add more via `state.plugins.register({...})` in the console, or
via a `plugins/<id>.js` ES module loaded with a top-bar button.

## Cloudflare Worker (`worker/`)

A separate `worker/` directory with `wrangler.toml`, deployable via
`wrangler pages deploy` (or `wrangler deploy` for a standalone Worker). It
exposes:
- `POST /api/run`            — proxies to the same `Runtime` Python module via
  Pyodide (Worker-side) OR calls a configured external backend URL.
- `GET  /api/historical`     — KV-cached + D1-recorded, fallback to ccxt/binance.
- `GET  /api/stream`         — WebSocket upgrade → Durable Object session.
- `POST /api/keys`           — Admin-only; creates API keys stored in KV.
- `GET  /api/usage`          — Per-key meter (KV counters, Workers Analytics
  Engine for telemetry).

The worker is **optional**. The PWA works fully against the local Flask
backend, or against a hosted CF Worker, or fully offline (mock sources + 
Pyodide engine).

## Files

```
frontend/
  index.html               (now also references manifest + registers SW)
  style.css
  manifest.webmanifest     (NEW)
  sw.js                    (NEW — cache-first static, network-first /api)
  icon-192.png  icon-512.png  (NEW — generated placeholder)
  src/
    main.js                (NEW — bootstraps UI + registry)
    state.js               (NEW — central state, persisted via storage.js)
    chart.js               (NEW — extracted chart code)
    pine-editor.js         (existing, unchanged)
    storage.js             (existing, moved into src/)
    ui/
      topbar.js            (NEW — sources/streams/engines/endpoint pickers)
      editor.js            (NEW — wraps pine-editor)
      results.js           (NEW — tab rendering)
      status.js            (NEW — status bar)
      icons.js             (NEW — inline SVG icons)
    sources/
      index.js             (NEW — registry)
      binance-rest.js
      mock-walk.js
      csv-upload.js
    streams/
      index.js
      binance-ws.js
      mock-poll.js
      none.js
    engines/
      index.js
      server.js
      pyodide.js
  worker/                  (NEW)
    wrangler.toml
    package.json
    tsconfig.json
    src/
      index.ts             (router)
      runtime.ts           (pyodide OR external proxy)
      keys.ts
      durable-objects/
        session.ts         (live WebSocket session)
      kv.ts
      d1.ts
Makefile                   (add build-cf, deploy-cf, dev-cf targets)
README.md                  (update architecture section)
```

## PWA behaviour
- `manifest.webmanifest` with `start_url: /`, `display: standalone`,
  theme color `#131722`, background `#131722`, two icon sizes.
- `sw.js` registered on load. Strategies:
  - Static (`/`, `/style.css`, `/src/*`, CDN bundles) → cache-first.
  - `/api/*` (when hitting the CF endpoint) → network-first, fall back to
    cache. Falls through to a 503 page if both fail and no engine=pyodide.
- App is **fully usable offline** when source=`mock-walk` and engine=`pyodide`.
  Live stream goes to `mock-poll` in that mode.

## Backwards compatibility
- Existing `frontend/script.js`, `pine-editor.js`, `storage.js` keep their
  public API; `script.js` becomes a thin entry that delegates to `src/`.
- Existing backend endpoints (`/run`, `/auth/validate`, etc.) unchanged.
- All current demos + the backend run path keep working.

## Out of scope (explicitly)
- Cloudflare Access / OAuth login (deferred; localStorage keys only).
- Vectorize embeddings / similarity search for indicators (deferred).
- Browser-Streaming for the evaluator (Pyodide first; revisit Workers AI later).
- A plugin marketplace / registry server (registry is client-side only).

## Verification plan
1. `make test` still passes (Python).
2. `make run-frontend` serves the PWA; `manifest.webmanifest` returns 200;
   `sw.js` registers (DevTools → Application → Service Workers).
3. With engine=`server` + source=`binance-rest`: load + run a demo → plots
   appear, events show, equity curve populates.
4. With engine=`pyodide` + source=`mock-walk`: same demo runs **offline**
   (DevTools → Network → Offline) and produces the same plots.
5. `make build-cf` produces a deployable `worker/` bundle; `make deploy-cf`
   (dry-run) succeeds against a placeholder CF account (if `CLOUDFLARE_API_TOKEN`
   is set).
