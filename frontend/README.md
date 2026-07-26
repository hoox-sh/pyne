# frontend/ — AXIS (PWA)

**AXIS** (formerly SuperChart Lite) — open charting PWA for Pine Script™.
**Installable PWA**, **fully pluggable**, runs against a local Flask backend,
a Cloudflare Worker, or **fully offline** with the in-browser Pyodide engine.

**Icons:** [Lucide](https://lucide.dev) via `lucide-solid` (tree-shakable stroke
icons, ISC). Wrapper: `src/ui/icons.tsx`.

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

**Primary path is Vite + Solid** (this is what ships on the VPS demo):

```bash
cd frontend && bun install && bun run dev   # Vite on :3000 (proxies /run → :5002)
# production: bun run build && python3 axis_pwa_server.py   # serves dist/ on :8081
```

```bash
# Terminal 1 — backend
make run              # Flask on :5002 (uses the existing pynescript runtime)

# Terminal 2 — PWA (Vite)
cd frontend && bun run dev
```

### Legacy static path (not recommended)

`style.css`, `main.js`, `server.ts`, and root-level `index.html` without Vite
are the pre-Solid SuperChart shell. They still use older TV-blue tokens in places
and are kept only for smoke tests / offline static serving. Prefer `bun run dev`
or `dist/` from `bun run build`. Do not treat the legacy shell as the product UI.
See **`LEGACY.md`**.

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
- **VPS demo**: PWA `http://162.254.38.194:8081` · Pro API
  `http://162.254.38.194:5002` (systemd `axis-pwa` + `pynescript-api`).
  Solid store default endpoint points at that API host.
- **Cloudflare Worker**: deploy `worker/` with `make deploy-cf`. The Worker
  exposes `/api/run`, `/api/stream`, `/api/keys`, etc. and proxies to the
  pynescript Python runtime via Pyodide on the Worker side. See
  `worker/README.md`.

## CORS (AXIS browser origin → Pro API)

The Pro API (`backend/app.py`) uses `flask-cors` with origins from
`ALLOWED_ORIGINS` (comma-separated). Defaults include
`https://pynescript.ai`, `https://app.pynescript.ai`, and a localhost regex.

For the public AXIS demo the VPS unit sets:

```ini
# /etc/systemd/system/pynescript-api.service
Environment=ALLOWED_ORIGINS=*
```

That reflects any browser `Origin` (including `http://162.254.38.194:8081`).
For production, prefer an explicit list, e.g.:

```bash
ALLOWED_ORIGINS=http://162.254.38.194:8081,https://your-pages-host.example,^https?://(localhost|127\.0\.0\.1)(:\d+)?$
```

Smoke:

```bash
curl -sS -D- -o /dev/null -X OPTIONS http://162.254.38.194:5002/run \
  -H "Origin: http://162.254.38.194:8081" \
  -H "Access-Control-Request-Method: POST"
# expect Access-Control-Allow-Origin echoing the Origin

curl -sS -X POST http://162.254.38.194:5002/run \
  -H "Content-Type: application/json" \
  -H "Origin: http://162.254.38.194:8081" \
  -d '{"script":"//@version=5\nindicator(\"t\")\nplot(close)","data":[{"time":1,"open":1,"high":1,"low":1,"close":1,"volume":1}]}'
```

## PWA

- Manifest at `manifest.webmanifest` (void theme `#0a0b10`, icons 192/512).
- Service Worker at `sw.js` registered on first load. Cache-first for the
  app shell, network-first for `/api/*`, fallback to a 503 JSON for offline
  API calls (the `pyodide` engine keeps the app fully usable offline).
- Install prompt: in Chrome/Edge, look for the install icon in the URL bar.

## Persistence (localStorage)

`pynescript.axis.v1` holds (migrates automatically from `pynescript.superchart.v*`):

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
