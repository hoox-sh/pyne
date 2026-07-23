# frontend/ — SuperChart Lite (PWA)

A modular TradingView-style chart + Pine Script editor. **Installable PWA**,
**fully pluggable**, runs against a local Flask backend, a Cloudflare Worker,
or **fully offline** with the in-browser Pyodide engine.

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
│  (dev only)                            • Pages: static PWA             │
│                                        • Worker: /api/run, /api/stream│
│                                        • Durable Object: live session  │
│                                        • KV: API keys, usage meter     │
│                                        • D1: persistent runs/scripts   │
│                                        • R2: indicator bundle cache    │
│                                        • WebSocket Hibernation (DO)    │
└───────────────────────────────────────────────────────────────────────┘
```

## Plugin contract

Every plugin is an object with `{ id, name, kind, description, configSchema, ... }`.

```ts
// kind: 'source'  — historical OHLCV
interface Source {
  fetchHistorical({ symbol, interval, config }): Promise<Bar[]>
}

// kind: 'stream'  — live tick / bar push
interface Stream {
  start({ symbol, interval, onBar, onError, onStatus, config }): () => void  // returns stop
}

// kind: 'engine'  — calculate Pine
interface Engine {
  isReady(): Promise<boolean>
  run({ script, bars, config }): Promise<RunResult>
}

type RunResult = {
  status: 'success' | 'error',
  plots: (number|null)[],
  series?: Record<string, (number|null)[]>,
  events: any[],
  meta?: { mode?, script_id?, run_id?, ms? },
  error?: string,
}
```

## Built-in plugins

| Kind   | id            | Source                           |
|--------|---------------|----------------------------------|
| Source | `binance-rest`| `https://api.binance.com/...`    |
| Source | `mock-walk`   | pure-synthetic random walk       |
| Source | `csv-upload`  | user-uploaded file               |
| Stream | `binance-ws`  | `wss://stream.binance.com/...`   |
| Stream | `mock-poll`   | synthetic poll (offline)         |
| Stream | `none`        | paused                           |
| Engine | `server`      | `POST {endpoint}/run`            |
| Engine | `pyodide`     | in-browser Python (Pyodide)      |

Add a new plugin: drop a file in `frontend/src/plugins/<id>.js` that
default-exports the plugin object, then import + register it in
`src/registry-bootstrap.js`. Or load at runtime from the DevTools console:

```js
import { loadPluginFromUrl } from './src/registry.js';
await loadPluginFromUrl('https://example.com/my-plugin.js');
```

## Local dev

```bash
# Terminal 1 — backend
make run              # Flask on :5002 (uses the existing pynescript runtime)

# Terminal 2 — PWA
make run-frontend     # python -m http.server 8081 --directory frontend
# open http://localhost:8081
```

For an **offline-first** demo: set `Source = Mock Walk`, `Stream = Mock Poll`,
`Engine = Client-Side (Pyodide)`. Disable network in DevTools — Run still works.

## File map

```
frontend/
  index.html                  PWA shell
  style.css                   TV-dark + light themes
  manifest.webmanifest        PWA manifest (installable)
  sw.js                       Service Worker (offline cache)
  assets/
    icon-192.png
    icon-512.png
    icon-maskable-512.png
  pine-editor.js              CodeMirror 6 + Pine StreamLanguage
  storage.js                  localStorage helpers (legacy)
  src/
    main.js                   bootstrap, wires UI + registry
    state.js                  central persisted state
    registry.js               plugin registry + loadPluginFromUrl
    registry-bootstrap.js     registers built-in plugins
    chart.js                  lightweight-charts wrapper (main / volume / indicator / equity)
    ui/
      topbar.js               engine/source/stream/endpoint/symbol/...
      results.js              5-tab results panel (Trades, Strategy, Plots, Metrics, Raw)
      status.js               status bar
      settings.js             generic configSchema-driven settings dialog
      manager.js              plugin manager + script library + theme
      symbol-autocomplete.js  Binance symbol autocomplete
    sources/
      index.js                binance-rest, mock-walk, csv-upload
    streams/
      index.js                binance-ws, mock-poll, none
    engines/
      index.js                server, pyodide (Python in browser)
    plugins/                  example plugins (load via Manager)
      example-coingecko-source.js
      example-tiny-pine-engine.js
      example-cf-do-stream.js
      README.md               contract + how-to
  worker/                     Cloudflare Pages + Worker (see worker/README.md)
```

## Backend targets

- **Local Flask**: existing `make run` on `:5002`. PWA talks to it directly
  (CORS handled by the backend). Default endpoint is `http://localhost:5002`.
- **Cloudflare Worker**: deploy `worker/` with `make deploy-cf`. The Worker
  exposes `/api/run`, `/api/stream`, `/api/keys`, etc. and proxies to the
  pynescript Python runtime via Pyodide on the Worker side. See
  `worker/README.md`.

## PWA

- Manifest at `manifest.webmanifest` (theme `#2962ff`, icons 192/512).
- Service Worker at `sw.js` registered on first load. Cache-first for the
  app shell, network-first for `/api/*`, fallback to a 503 JSON for offline
  API calls (the `pyodide` engine keeps the app fully usable offline).
- Install prompt: in Chrome/Edge, look for the install icon in the URL bar.

## Persistence (localStorage)

`pynescript.superchart.v1` holds:

| Field          | Purpose                              |
|----------------|--------------------------------------|
| `script`       | Last Pine source                     |
| `symbol`/`interval` | Last market selection            |
| `engine`       | `server` or `pyodide`                |
| `source`       | `binance-rest`/`mock-walk`/`csv-upload` |
| `stream`       | `binance-ws`/`mock-poll`/`none`      |
| `endpoint`     | Backend URL                          |
| `mode`         | `local` or `cloud`                   |
| `apiKey`       | stored **only in this browser**      |
| `pluginsConfig`| per-plugin configuration             |

## Verification

- `make run-frontend` then open `http://localhost:8081`.
- App loads, chart shows BTC/USDT, top bar exposes Engine / Source / Stream
  pickers. DevTools → Application → Manifest + Service Workers confirms PWA.
- Engine = `pyodide` + Source = `mock-walk`: go offline (DevTools → Network
  → Offline). Click Run. Pine still executes.
