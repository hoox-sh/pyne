# frontend/ — pynescript SuperChart Lite (prototype)

Lightweight browser clone of a TradingView-style chart + integrated Pine Script editor.

**Current status (MVP slice)**

- Candlestick chart powered by TradingView `lightweight-charts`
- Split layout: chart | **CodeMirror 6** Pine editor (syntax highlight + line numbers)
- Load data: Binance public (with fallback), CSV/JSON upload
- "Load RSI Strategy" demo buttons (`overlay=true` / `overlay=false`)
- Run via backend `POST /run` (full pynescript evaluator + strategy events)
- Visualization: plot() on main or sub-pane (`overlay=`) + strategy trade markers on price
- Tabs: Trades & Events, Plots, Metrics, Raw JSON
- Keyboard: Ctrl/Cmd + Enter runs the script
- Fully static ES modules — serve with `make run-frontend` (HTTP required for CM6 CDN)
- **CDNs**: lightweight-charts (jsDelivr/unpkg) + CodeMirror 6 packages (esm.sh). Offline/file:// falls back where possible.
- **localStorage**: auto-saves script + symbol/TF + mode + API key; 💾 Save / Reset saved
- **Equity pane**: strategy capital curve under the chart after Run
- **Local / Cloud stub**: toggle badge → API key bar → `Authorization: Bearer` + `/auth/validate` + usage

## Local dev (recommended)

```bash
# Terminal 1
make run          # backend API on :5002 (needs no extra deps for basic use)

# Terminal 2
make run-frontend # or: python -m http.server 8081 --directory frontend
# then open http://localhost:8081
```

Direct file open will still let you use the Pine editor, Run button (demo mode), data upload, and Live stream (datafeed simulation).

## Live data & datafeed integration
- "▶ Live" button starts a real-time candle stream (Binance WS) that behaves like `CCXTProDataFeed.watch_ohlcv`.
- Falls back to in-memory MockDataFeed simulation (from `src/pynescript/util/datafeed.py`).
- Historical data goes through backend `/data/historical` which uses `pynescript.util.data.get_provider` (ccxt supported when installed).
- The Python `datafeed` module powers server-side realtime for the evaluator (`request.*`, strategy runs).

## Editor

- `pine-editor.js` — CodeMirror 6 host + Pine `StreamLanguage` (keywords/types/`ta.*`/`strategy.*`)
- TV-dark theme; Tab indent; search/history/fold via CM defaults
- If esm.sh is blocked, falls back to a plain textarea

## Persistence (`storage.js`)

Browser `localStorage` key `pynescript.superchart.v1`:

| Field | Purpose |
|-------|---------|
| `script` | Pine source |
| `symbol` / `interval` | Last market selection |
| `mode` | `local` \| `cloud` |
| `apiKey` | Stored **only in this browser** (dev convenience) |

## Local vs Cloud

| Mode | Behavior |
|------|----------|
| **Local** | Free `POST /run`, no key |
| **Cloud** | Requires API key; sends `Authorization: Bearer …`; validates via `/auth/validate`; shows `/auth/usage` when available |

Create a key (dev): `POST /auth/create_key` with admin token configured.

## Future (per plan)

- Richer Pine language (full grammar / completions from builtin_metadata)
- Real modular pay-as-you-go metering on `/run`
- Persistent "cloud runner" sessions (CF Durable Objects)
- Self data streams / WebSocket feeds
- Full CF Pages + Workers deployment using pine-worker
- Optional Vite packaging for offline vendor bundles
