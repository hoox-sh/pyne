# SuperChart Lite — Full Rewrite Design Spec

**Date:** 2026-07-25
**Status:** Approved
**Scope:** Frontend rewrite + backend enhancements

---

## 1. Overview

Rewrite the SuperChart Lite PWA frontend (`frontend/`) from a hardcoded 4-pane layout
with static script execution into a TradingView-parity charting platform with:

- **Dynamic pane management** — add/remove/resize/reorder indicator panes
- **Live mode** — re-run Pine Script on every new bar (not just update candles)
- **Indicator panel** — UI to manage running scripts (toggle, colors, settings, remove)
- **Multi-exchange streams** — Binance, Coinbase, Kraken, OKX

Backend changes: minimal — add multi-script `/run` endpoint, `bar_index` param for
incremental runs.

---

## 2. Architecture

### 2.1 Reactive State Store (`store.js`)

Central EventTarget-based state store. All components subscribe to state slices.

```
State Shape:
{
  bars: Bar[],                    // OHLCV data
  interval: string,               // "1m", "5m", "1h", "1d", etc.
  symbol: string,                 // "BTCUSDT"
  exchange: string,               // "binance", "coinbase", "kraken", "okx"

  scripts: Indicator[],           // Running indicator scripts
  // Indicator = { id, name, code, paneId, visible, plots: {name: color}[] }

  panes: Pane[],                  // Chart pane layout
  // Pane = { id, type, height, order, visible }

  live: {
    active: boolean,
    needsRerun: boolean,
    lastBarTime: number,
  },

  theme: "dark" | "light",
  editor: { open: boolean, width: number },
  indicatorPanel: { open: boolean },

  stream: { status: "connected" | "disconnected" | "error" },
}
```

**Actions:**
- `LOAD_BARS(bars, symbol, interval, exchange)` — set historical data
- `ADD_INDICATOR(script, name)` — run script, create indicator entry
- `REMOVE_INDICATOR(id)` — remove indicator + its pane
- `TOGGLE_INDICATOR(id)` — show/hide indicator plots
- `SET_INDICATOR_COLOR(id, plotName, color)` — change plot color
- `ADD_PANE(type)` — create new pane
- `REMOVE_PANE(id)` — destroy pane
- `RESIZE_PANE(id, height)` — update pane height
- `REORDER_PANES(orderedIds)` — reorder panes
- `APPEND_BAR(bar)` — live mode: add new bar
- `SET_LIVE(active)` — toggle live mode
- `MARK_RERUN()` — set `liveNeedsRerun = true`

### 2.2 File Structure After Rewrite

```
src/
  store.js                   — State store + actions + subscriptions
  main.js                    — Bootstrap, wires components to store
  chart/
    pane-manager.js          — Creates/destroys/resizes/reorders panes
    pane.js                  — Single pane: LightweightCharts instance + series
    renderers.js             — Series factories (candle, hist, line, area)
    crosshair.js             — Synced crosshair across all panes
    overlay.js               — Add/remove/clear overlay lines + markers
  scripts/
    runner.js                — Script execution (server or pyodide)
    indicator.js             — Indicator model + result parsing
    results-panel.js         — Strategy tester + results tabs
  streams/
    multiplex.js             — Multi-exchange stream manager
    index.js                 — Built-in stream plugins (binance, coinbase, etc.)
    sources.js               — Historical data sources (REST)
  ui/
    topbar.js                — Toolbar (symbol, interval, live, theme)
    indicator-panel.js       — Indicator panel sidebar
    tabbed-editor.js         — Multi-tab code editor
    watchlist.js             — Symbol watchlist
    manager.js               — Script library + settings
  state.js                   — localStorage persistence (unchanged)
```

---

## 3. Dynamic Pane Manager

### 3.1 Pane Types

| Type | Always Present | Removable | Default Height |
|---|---|---|---|
| `price` | Yes | No | Flex (fills remaining) |
| `volume` | Yes | Yes | 120px |
| `indicator` | No | Yes | 120px |
| `equity` | No | Yes | 160px |

### 3.2 Pane Lifecycle

1. **Create:** `ADD_PANE(type)` → allocate `<div>`, call `LightweightCharts.createChart()`,
   insert into DOM at correct order
2. **Destroy:** `REMOVE_PANE(id)` → call `chart.remove()`, remove DOM element, free memory
3. **Resize:** Draggable dividers between panes. Mouse drag → update `pane.height` in state →
   `chart.applyOptions({ height })` → DOM resize
4. **Reorder:** Drag pane header → update `pane.order` in state → re-sort DOM elements
5. **Visibility:** Toggle pane visibility without destroying (preserves chart state)

### 3.3 Time Scale Sync

All panes except `equity` sync their time scale to the `price` pane via
`subscribeVisibleLogicalRangeChange`. A `suppress` flag prevents infinite recursion
when syncing.

### 3.4 Pane Header

Each sub-pane shows a header bar with:
- Script name (click to rename)
- Visibility toggle (eye icon)
- Color dots for each plot
- Settings gear (future)
- Remove button (×)
- Drag handle (for reorder)

---

## 4. Live Mode (Re-run on Each Bar)

### 4.1 Flow

```
Stream plugin receives new bar
    → dispatch('APPEND_BAR', bar)
    → dispatch('MARK_RERUN')
    → Debouncer (300ms) fires if needsRerun
        → For each visible indicator:
            → POST /run { script, data: bars[] }
            → Parse response → overlay lines + markers
            → Update chart series
        → dispatch('MARK_RERUN', false)
```

### 4.2 Backend Changes

**Endpoint:** `POST /run` (already exists)

Changes:
- Accept `scripts` array (multiple scripts in one request) — **optional optimization**
- Add `bar_index` param: if provided, backend can skip re-computing bars before that index
- Response unchanged: `{ plots, series, events, meta }`

**New endpoint:** `POST /run/batch` (optional)
```json
// Request
{
  "scripts": [
    { "id": "ind_1", "code": "plot(ta.rsi(close, 14))" },
    { "id": "ind_2", "code": "plot(ta.sma(close, 50))" }
  ],
  "data": [ { "time": ..., "open": ..., ... } ]
}

// Response
{
  "results": {
    "ind_1": { "plots": [...], "series": {...}, "events": [...] },
    "ind_2": { "plots": [...], "series": {...}, "events": [...] }
  }
}
```

### 4.3 Performance

- Only re-run **visible** indicators (hidden ones are skipped)
- 300ms debounce prevents hammering on fast timeframes (1s, 5s)
- On 1m timeframe: ~1 bar/min → re-run is cheap
- Consider caching: if bars haven't changed since last run, skip

### 4.4 Stream Plugins

| Stream | Transport | Symbol Format | Interval Param |
|---|---|---|---|
| Binance WS | `wss://stream.binance.com:9443/ws/{symbol}@kline_{interval}` | `BTCUSDT` | `1m`, `5m`, `1h` |
| Coinbase WS | `wss://ws-feed.exchange.coinbase.com` (subscribe matches) | `BTC-USD` | `1m`, `5m`, `1h` |
| Kraken WS | `wss://ws.kraken.com/v2` (OHLC channel) | `XBT/USD` | `1`, `5`, `60` |
| OKX WS | `wss://ws.okx.com:8443/ws/v5/public` (candle channel) | `BTC-USDT` | `1m`, `5m`, `1H` |

Each stream plugin normalizes bars to `{ time, open, high, low, close, volume }`.

---

## 5. Indicator Panel

### 5.1 UI

Collapsible sidebar panel (right side of chart), toggled from toolbar.

```
┌─ Indicators ──────────────────────┐
│ 👁 RSI SubPane          🎨  ×    │
│   ├─ RSI (14)        ● #purple   │
│   └─ Oversold (30)   ● #green    │
│   └─ Overbought (70) ● #red      │
│                                   │
│ 👁 SMA Cross            🎨  ×    │
│   ├─ fastMA (9)       ● #blue    │
│   └─ slowMA (21)      ● #orange  │
│                                   │
│            [+ Add Indicator]      │
└────────────────────────────────────┘
```

### 5.2 Actions

| Action | Behavior |
|---|---|
| 👁 Toggle | Show/hide all plots from this indicator |
| 🎨 Color | Click color dot → color picker → update plot color |
| × Remove | Remove indicator, its pane, and all overlays |
| Drag handle | Reorder indicators (reorder panes) |
| [+ Add Indicator] | Opens editor, user writes script, clicks Run |

### 5.3 State

Each indicator in `state.scripts[]`:
```js
{
  id: "ind_1",
  name: "RSI SubPane",
  code: "// @version=5\n...",
  paneId: "pane_2",
  visible: true,
  plots: {
    "RSI": { color: "#9C27B0" },
    "Oversold": { color: "#4CAF50" },
    "Overbought": { color: "#F44336" }
  }
}
```

---

## 6. Multi-Exchange Streams

### 6.1 Exchange Stream Plugins

Each exchange is a separate stream plugin registered in the registry.

```js
// streams/binance.js
export const binanceWsStream = {
  id: 'binance-ws',
  name: 'Binance WebSocket',
  kind: 'stream',
  configSchema: { ... },
  async start({ symbol, interval, onBar, onStatus, onError }) {
    const ws = new WebSocket(`wss://stream.binance.com:9443/ws/${symbol.toLowerCase()}@kline_${interval}`);
    ws.onmessage = (e) => {
      const k = JSON.parse(e.data).k;
      onBar({ time: k.t/1000, open: +k.o, high: +k.h, low: +k.l, close: +k.c, volume: +k.v });
    };
    return () => ws.close();
  }
};
```

### 6.2 Symbol Mapping

| Exchange | BTC Symbol | Format |
|---|---|---|
| Binance | BTCUSDT | `{base}{quote}` no separator |
| Coinbase | BTC-USD | `{base}-{quote}` dash separator |
| Kraken | XBT/USD | `{base}/{quote}` slash, XBT for BTC |
| OKX | BTC-USDT | `{base}-{quote}` dash separator |

### 6.3 Historical Data Sources

Each exchange also provides a REST historical data source plugin:

```js
// sources/binance-rest.js (already exists)
// sources/coinbase-rest.js (new)
// sources/kraken-rest.js (new)
// sources/okx-rest.js (new)
```

### 6.4 User Flow

1. Settings → "Exchange" dropdown → select exchange
2. Symbol autocomplete refreshes to exchange-specific symbols
3. Live mode connects to selected exchange's WS
4. Historical data fetches from selected exchange's REST API

---

## 7. Backend Changes

### 7.1 Multi-Script `/run/batch` Endpoint

```python
@app.route("/run/batch", methods=["POST"])
def run_batch():
    """Run multiple scripts on the same data in one request."""
    data = request.get_json()
    scripts = data["scripts"]  # [{id, code}, ...]
    bars = data["data"]
    
    results = {}
    for s in scripts:
        runtime = Runtime()
        result = runtime.run(s["code"], bars, ...)
        results[s["id"]] = result
    
    return jsonify({"results": results})
```

### 7.2 `bar_index` Param for Incremental Runs

```python
@app.route("/run", methods=["POST"])
def run_pine_script():
    data = request.get_json()
    script = data["script"]
    bars = data["data"]
    bar_index = data.get("bar_index", 0)  # NEW: skip bars before this index
    
    # Only evaluate from bar_index onwards
    runtime = Runtime()
    result = runtime.run(script, bars, bar_start=bar_index)
    ...
```

---

## 8. Implementation Order

1. **Store + Pane Manager** — core state + dynamic panes
2. **Script Runner + Indicator Model** — run scripts, parse results, manage indicators
3. **Indicator Panel UI** — sidebar with toggle/color/remove
4. **Live Mode** — stream integration + debounced re-run
5. **Multi-Exchange** — exchange plugins + symbol mapping
6. **Backend batch endpoint** — optional optimization

---

## 9. Testing Strategy

- Each component is testable in isolation (state store, pane manager, runner)
- Integration tests: load bars → run script → verify overlays appear
- Live mode tests: simulate bar arrival → verify script re-runs
- Pane tests: add/remove/resize → verify DOM + chart instances
- Use existing `bun:test` framework in `frontend/tests/`
