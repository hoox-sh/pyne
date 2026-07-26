// LEGACY — SuperChart Lite / pre-Solid main entry.
//
// The product UI is the Vite + Solid app: `src/index.tsx` → `src/app.tsx`.
// This file powers the old static shell only (tests/server, offline archives).
// Do not add features here; extend ChartHost / Topbar / store instead.
//
// Wires the registry, state, top bar, editor, chart, results, status, and
// the Service Worker. Everything is plugin-driven.

import './registry-bootstrap.js';
import { initState, getState } from './state.js';
import { registry } from './registry.js';
import { initTopbar, setLiveIndicator } from './ui/topbar.js';
import { setStatus } from './ui/status.js';
import { initResults, renderResults } from './ui/results.js';
import { initPineEditor, getScript, setScript, focusEditor } from '../pine-editor.js';
import { TabbedEditor } from './ui/tabbed-editor.js';
import { initChart, setOhlcv, appendBar, setMarkers, clearOverlays, addOverlayLine,
         setEquityPane, setEquityCurve, setTimeRange } from './chart.js';
import { openSettings } from './ui/settings.js';
import { pyodideEngine } from './engines/index.js';
import { initWatchlist } from './ui/watchlist.js';
import { applyHashState, watchHashState } from './state-hash.js';
import { openManager, initManager } from './ui/manager.js';
import { attachSymbolAutocomplete } from './ui/symbol-autocomplete.js';

let bars = [];            // current OHLCV array
let liveStop = null;      // cleanup for current live stream
let editor;               // TabbedEditor instance, set during bootstrap()

const DEMOS = {
    'rsi-overlay': `//@version=5
// RSI mean-reversion, plotted on the main chart
strategy("RSI Overlay", overlay=true, default_qty_type=strategy.percent_of_equity, default_qty_value=10)

length   = input.int(14, "RSI Length", minval=2, maxval=100)
oversold = input.float(30, "Oversold", minval=1, maxval=50)
overbought = input.float(70, "Overbought", minval=50, maxval=99)

rsi = ta.rsi(close, length)

if (rsi < oversold)
    strategy.entry("Long", strategy.long)

if (rsi > overbought)
    strategy.close("Long")

plot(rsi * 0.01, "RSI scaled", color=color.new(color.purple, 50))
`,
    'rsi-subpane': `//@version=5
// RSI sub-pane (overlay=false) — the traditional layout
strategy("RSI SubPane", overlay=false, default_qty_type=strategy.percent_of_equity, default_qty_value=10)

length   = input.int(14, "RSI Length", minval=2, maxval=100)
oversold = input.float(30, "Oversold", minval=1, maxval=50)
overbought = input.float(70, "Overbought", minval=50, maxval=99)

rsi = ta.rsi(close, length)

if (rsi < oversold)
    strategy.entry("Long", strategy.long)

if (rsi > overbought)
    strategy.close("Long")

plot(rsi, "RSI")
hline(oversold,   "Oversold",   color=color.green)
hline(overbought, "Overbought", color=color.red)
`,
    'sma-crossover': `//@version=5
// SMA crossover indicator
strategy("SMA Cross", overlay=true, default_qty_type=strategy.percent_of_equity, default_qty_value=100)

fast = input.int(9, "Fast", minval=2, maxval=100)
slow = input.int(21, "Slow", minval=2, maxval=200)

fastMA = ta.sma(close, fast)
slowMA = ta.sma(close, slow)

if (ta.crossover(fastMA, slowMA))
    strategy.entry("Long", strategy.long)

if (ta.crossunder(fastMA, slowMA))
    strategy.close("Long")

plot(fastMA, "Fast", color=color.orange)
plot(slowMA, "Slow", color=color.blue)
`,
    'macd': `//@version=5
// MACD indicator with signal line
indicator("MACD", overlay=false)

fastLen   = input.int(12, "Fast Length")
slowLen   = input.int(26, "Slow Length")
signalLen = input.int(9,  "Signal Length")

[macdLine, signalLine, histLine] = ta.macd(close, fastLen, slowLen, signalLen)

plot(macdLine,   "MACD",   color=color.blue)
plot(signalLine, "Signal", color=color.orange)
plot(histLine,   "Histogram", color=histLine >= 0 ? color.green : color.red, style=plot.style_columns)
`,
    'bollinger': `//@version=5
// Bollinger Bands
indicator("Bollinger Bands", overlay=true)

length = input.int(20, "Length")
mult   = input.float(2.0, "StdDev", step=0.1)

basis = ta.sma(close, length)
dev   = mult * ta.stdev(close, length)

upper = basis + dev
lower = basis - dev

plot(basis, "Basis", color=color.orange)
plot(upper, "Upper", color=color.blue)
plot(lower, "Lower", color=color.blue)
fill(plot(upper), plot(lower), color=color.new(color.blue, 90))
`,
    'client-side-demo': `//@version=5
// Tiny client-side demo — works with the Pyodide engine + sma/rsi builtins
indicator("Client SMA", overlay=true)
length = input.int(20, "Length", minval=2)
plot(ta.sma(close, length), "SMA")
`,
};

async function loadHistorical() {
    const state = getState();
    const source = registry.getSource(state.get('source'));
    if (!source) {
        setStatus(`Unknown source: ${state.get('source')}`, 'error');
        return;
    }
    setStatus(`Loading via ${source.name}…`, 'busy', `${state.get('symbol')} ${state.get('interval')}`);
    try {
        const data = await source.fetchHistorical({
            symbol: state.get('symbol'),
            interval: state.get('interval'),
            config: state.get('pluginsConfig')?.[source.id] || {},
        });
        bars = setOhlcv(data) || [];
        setStatus(`Loaded ${bars.length} bars (${source.name})`, 'success', `${state.get('symbol')} ${state.get('interval')}`);
    } catch (err) {
        setStatus(`${source.name} load failed: ${err.message}`, 'error');
    }
}

async function handleUploadFile(file) {
    setStatus(`Parsing ${file.name}…`, 'busy');
    try {
        const text = await file.text();
        let parsed;
        if (file.name.endsWith('.json') || /^[\s]*[\{\[]/.test(text)) {
            parsed = JSON.parse(text);
        } else {
            parsed = parseCsv(text);
        }
        const arr = Array.isArray(parsed) ? parsed : parsed.bars || parsed.data || [];
        if (!arr.length) throw new Error('no rows');
        // Stash on state so csv-upload source can use it.
        getState().assign({ uploadedBars: arr, source: 'csv-upload' });
        // Update the source dropdown UI
        const sel = document.getElementById('source-select');
        if (sel) sel.value = 'csv-upload';
        bars = setOhlcv(arr) || [];
        setStatus(`Loaded ${bars.length} bars from ${file.name}`, 'success', file.name);
    } catch (err) {
        setStatus(`Upload failed: ${err.message}`, 'error');
    }
}

function parseCsv(text) {
    const lines = text.split(/\r?\n/).filter(Boolean);
    if (!lines.length) return [];
    const header = lines[0].split(',').map((s) => s.trim().toLowerCase());
    const idx = (name) => header.indexOf(name);
    const iT = idx('time') >= 0 ? idx('time') : idx('timestamp') >= 0 ? idx('timestamp') : idx('date');
    const iO = idx('open');
    const iH = idx('high');
    const iL = idx('low');
    const iC = idx('close');
    const iV = idx('volume');
    if (iO < 0 || iH < 0 || iL < 0 || iC < 0) {
        throw new Error('CSV needs columns: time,open,high,low,close[,volume]');
    }
    return lines.slice(1).map((line) => {
        const c = line.split(',');
        const tRaw = c[iT];
        const time = /^\d+$/.test(tRaw) ? parseInt(tRaw, 10) : Math.floor(new Date(tRaw).getTime() / 1000);
        return {
            time,
            open: parseFloat(c[iO]),
            high: parseFloat(c[iH]),
            low: parseFloat(c[iL]),
            close: parseFloat(c[iC]),
            volume: iV >= 0 ? parseFloat(c[iV]) : undefined,
        };
    });
}

function toggleLive() {
    if (liveStop) { liveStop(); liveStop = null; setLiveIndicator(false); return; }
    const state = getState();
    const stream = registry.getStream(state.get('stream'));
    if (!stream || stream.id === 'none') { setLiveIndicator(false); return; }
    setLiveIndicator(true);
    liveStop = stream.start({
        symbol: state.get('symbol'),
        interval: state.get('interval'),
        lastBar: bars[bars.length - 1],
        onBar: (b) => { appendBar(b); bars.push(b); },
        onStatus: (s) => setStatus(`Live (${stream.name}): ${s.state}`, s.state === 'open' ? 'success' : 'info'),
        onError: (e) => { setStatus(`Live error: ${e.message}`, 'error'); liveStop = null; setLiveIndicator(false); },
    });
}

async function runScript() {
    const state = getState();
    const engine = registry.getEngine(state.get('engine'));
    if (!engine) { setStatus(`Unknown engine: ${state.get('engine')}`, 'error'); return; }
    if (!bars.length) { setStatus('No market data loaded. Click Load first.', 'error'); return; }
    const script = editor ? editor.getScript() : getScript();
    if (!script.trim()) { setStatus('Editor is empty — nothing to run.', 'error'); return; }

    setStatus(`Running on ${engine.name}…`, 'busy', `bars=${bars.length}`);
    clearOverlays();
    setMarkers([]);
    setEquityPane(false);
    try {
        const result = await engine.run({ script, bars, config: {} });
        // Heuristic: detect `overlay=false` in the script so the chart can
        // route plots to the indicator sub-pane when needed.  A real
        // implementation would have the runtime return this in `meta`.
        if (!result.meta) result.meta = {};
        if (result.meta.overlay === undefined) {
            const m = /\b(strategy|indicator)\s*\(\s*["'][^"']*["']\s*,\s*[^)]*overlay\s*=\s*(true|false)/.exec(script);
            result.meta.overlay = m ? m[2] === 'true' : true;
        }
        if (result.meta.script_name === undefined) {
            const m = /\b(strategy|indicator)\s*\(\s*["']([^"']+)["']/.exec(script);
            result.meta.script_name = m ? m[2] : 'plot';
        }
        state.assign({ lastResult: result });
        applyResults(result);
        const ms = result.meta?.ms;
        setStatus(
            result.status === 'success' ? `Run complete (${engine.name})` : `Run failed: ${result.error}`,
            result.status === 'success' ? 'success' : 'error',
            `events=${(result.events || []).length} plots=${(result.plots || []).length} ${ms ? ms.toFixed(0) + 'ms' : ''}`.trim(),
        );
    } catch (err) {
        setStatus(`Run crashed: ${err.message}`, 'error');
    }
}

function applyResults(payload) {
    renderResults(payload);
    if (payload.status === 'error') return;

    const ohlcvTimes = bars.map((b) => b.time);
    const isOverlay = payload.meta?.overlay !== false;  // default true
    const pane = isOverlay ? 'main' : 'indicator';

    // Update pane label
    const lbl = document.getElementById('pane-label-indicator');
    if (lbl) lbl.textContent = payload.meta?.script_name || 'Indicator';

    // Primary plots
    const plots = payload.plots || [];
    if (plots.length) {
        const data = [];
        for (let i = 0; i < plots.length && i < ohlcvTimes.length; i++) {
            const v = plots[i];
            if (v === null || v === undefined || typeof v !== 'number' || Number.isNaN(v)) continue;
            data.push({ time: ohlcvTimes[i], value: v });
        }
        if (data.length) addOverlayLine(payload.meta?.script_name || 'plot', data, { pane });
    }
    // Multiple series → multiple overlays
    const series = payload.series || {};
    for (const k of Object.keys(series)) {
        if (k.startsWith('__')) continue;
        const arr = series[k];
        if (!Array.isArray(arr)) continue;
        const data = [];
        for (let i = 0; i < arr.length && i < ohlcvTimes.length; i++) {
            const v = arr[i];
            if (v === null || v === undefined || typeof v !== 'number' || Number.isNaN(v)) continue;
            data.push({ time: ohlcvTimes[i], value: v });
        }
        if (data.length) addOverlayLine(k, data, { pane });
    }

    // Markers (only on main pane)
    const events = payload.events || [];
    const markers = events.map((ev) => {
        const kind = (ev.type || ev.event || '').toLowerCase();
        const isEntry = kind.includes('entry');
        return {
            time: ev.time, position: isEntry ? 'belowBar' : 'aboveBar',
            color: isEntry ? '#26a69a' : '#ef5350',
            shape: isEntry ? 'arrowUp' : 'arrowDown',
            text: ev.id || kind,
        };
    }).filter((m) => Number.isFinite(m.time));
    markers.sort((a, b) => a.time - b.time);
    setMarkers(markers);

    // Equity curve
    if (events.length) {
        const eq = buildEquity(events);
        if (eq.length) {
            setEquityPane(true);
            setEquityCurve(eq);
        }
    }
}

function buildEquity(events) {
    const sorted = events.slice().sort((a, b) => (a.time || 0) - (b.time || 0));
    let equity = 10000;
    let inPos = false;
    let entryPrice = 0;
    const points = [];
    for (const ev of sorted) {
        const t = ev.time;
        const p = ev.price;
        if (t === undefined || p === undefined) continue;
        const kind = (ev.type || ev.event || '').toLowerCase();
        if (kind.includes('entry')) {
            if (!inPos) { inPos = true; entryPrice = p; }
        } else if (kind.includes('close') || kind.includes('exit')) {
            if (inPos) {
                equity *= (1 + (p - entryPrice) / entryPrice);
                inPos = false;
            }
        }
        points.push({ time: t, value: +equity.toFixed(2) });
    }
    return points;
}

function saveCurrent() {
    const s = getState().snapshot();
    getState().assign({ script: getScript() });
    setStatus('Saved.', 'success', new Date().toLocaleTimeString());
}

function resetAll() {
    if (!confirm('Reset saved state and clear editor?')) return;
    localStorage.removeItem('pynescript.superchart.v1');
    setScript(DEMOS['rsi-overlay']);
    getState().assign({
        endpoint: 'http://localhost:5002',
        engine: 'server',
        source: 'binance-rest',
        stream: 'binance-ws',
        symbol: 'BTCUSDT',
        interval: '1d',
        mode: 'local',
        apiKey: '',
        script: DEMOS['rsi-overlay'],
    });
    setStatus('Reset to defaults.', 'info');
}

function wireDemos() {
    for (const btn of document.querySelectorAll('[data-demo]')) {
        btn.addEventListener('click', () => {
            const key = btn.dataset.demo;
            if (DEMOS[key]) {
                setScript(DEMOS[key]);
                focusEditor();
                // Auto-run the script after a brief delay so CM6 can render
                setTimeout(runScript, 150);
            }
        });
    }
}

function wireSettings() {
    const btn = document.getElementById('settings-btn');
    if (!btn) return;
    btn.addEventListener('click', () => {
        const state = getState();
        const choice = prompt(
            'Configure which plugin?\n' +
            registry.listEngines().map((p, i) => `${i + 1}. ${p.name} (engine)`).join('\n') +
            '\n' +
            registry.listSources().map((p, i) => `${i + 1 + registry.listEngines().length}. ${p.name} (source)`).join('\n') +
            '\n' +
            registry.listStreams().map((p, i) => `${i + 1 + registry.listEngines().length + registry.listSources().length}. ${p.name} (stream)`).join('\n') +
            '\n\nEnter number:',
        );
        if (!choice) return;
        const n = parseInt(choice, 10);
        const engines = registry.listEngines();
        const sources = registry.listSources();
        const streams = registry.listStreams();
        const total = engines.length + sources.length + streams.length;
        if (Number.isNaN(n) || n < 1 || n > total) return;
        let plugin;
        if (n <= engines.length) plugin = engines[n - 1];
        else if (n <= engines.length + sources.length) plugin = sources[n - engines.length - 1];
        else plugin = streams[n - engines.length - sources.length - 1];
        openSettings({
            title: `${plugin.name} (${plugin.kind})`,
            schema: plugin.configSchema,
            current: state.get('pluginsConfig')?.[plugin.id] || {},
            onSave: (next) => {
                const cfg = { ...(state.get('pluginsConfig') || {}) };
                cfg[plugin.id] = next;
                state.assign({ pluginsConfig: cfg });
                setStatus(`Saved ${plugin.name} settings.`, 'success', `${Object.keys(next).length} fields`);
            },
        });
    });
}

function repopulateDropdowns() {
    const eng = document.getElementById('engine-select');
    const src = document.getElementById('source-select');
    const stm = document.getElementById('stream-select');
    const state = getState();
    function fill(sel, items, current) {
        if (!sel) return;
        const prev = sel.value;
        sel.innerHTML = '';
        for (const it of items) {
            const opt = document.createElement('option');
            opt.value = it.id; opt.textContent = it.name;
            if (it.id === current || (!current && it.id === prev)) opt.selected = true;
            sel.appendChild(opt);
        }
    }
    fill(eng, registry.listEngines(), state.get('engine'));
    fill(src, registry.listSources(), state.get('source'));
    fill(stm, registry.listStreams(), state.get('stream'));
}

function wireManager() {
    const btn = document.getElementById('manager-btn');
    if (!btn) return;
    btn.addEventListener('click', () => openManager());
    window.addEventListener('plugin-loaded', () => repopulateDropdowns());
}

function wireTimePresets() {
    for (const btn of document.querySelectorAll('.time-preset')) {
        btn.addEventListener('click', () => {
            const range = btn.dataset.range;
            setTimeRange(range);
            for (const b of document.querySelectorAll('.time-preset')) b.classList.toggle('is-active', b === btn);
            getState().assign({ timeRange: range });
        });
    }
    // Restore last selected range
    const last = getState().get('timeRange') || 'ALL';
    for (const b of document.querySelectorAll('.time-preset')) {
        if (b.dataset.range === last) b.classList.add('is-active');
    }
}

async function bootstrap() {
    // Service worker (production only — skip on file:// or dev ports without HTTPS)
    if ('serviceWorker' in navigator && location.protocol !== 'file:' && location.hostname !== 'localhost' && location.hostname !== '127.0.0.1') {
        try { await navigator.serviceWorker.register('./sw.js'); } catch (_) { /* ignore */ }
    }

    initState();
    const storedScript = getState().get('script');

    // Chart
    initChart({
        mainEl: document.getElementById('chart'),
        volumeEl: document.getElementById('volume-chart'),
        indicatorEl: document.getElementById('indicator-chart'),
        equityEl: document.getElementById('equity-chart'),
    });

    // Editor — multi-tab CodeMirror 6.  Tabs are persisted in localStorage
    // so reloading the page restores every open script.
    editor = new TabbedEditor({
        parent: document.getElementById('pine-editor'),
        onRun: () => runScript(),
        onDocChange: (src) => getState().assign({ script: src }),
        initialScript: storedScript || DEMOS['rsi-overlay'],
    });
    await editor.init();

    // UI panels
    initResults();
    initTopbar({
        onRun: runScript,
        onLoad: loadHistorical,
        onUpload: () => {},
        onUploadFile: handleUploadFile,
        onLiveToggle: toggleLive,
        onSave: saveCurrent,
        onReset: resetAll,
    });
    wireDemos();
    wireSettings();
    wireTimePresets();
    wireManager();
    initManager();  // restore theme + auto-load user plugins

    // Wire Pyodide engine progress indicator
    const progressEl = document.getElementById('engine-progress');
    if (progressEl) {
        pyodideEngine.setProgressCallback((msg) => {
            if (msg) {
                progressEl.textContent = msg;
                progressEl.hidden = false;
            } else {
                progressEl.hidden = true;
                progressEl.textContent = '';
            }
        });
    }

    // Offline indicator
    const offlineBadge = document.getElementById('offline-badge');
    function updateOnlineStatus() {
        if (offlineBadge) offlineBadge.hidden = navigator.onLine;
    }
    window.addEventListener('online', updateOnlineStatus);
    window.addEventListener('offline', updateOnlineStatus);
    updateOnlineStatus();

    // Symbol autocomplete (best-effort, no UI changes if it fails)
    try { await attachSymbolAutocomplete(document.getElementById('symbol-input')); } catch (_) { /* ignore */ }

    // Watchlist sidebar
    initWatchlist();
    window.addEventListener('watchlist-select', () => loadHistorical());

    // URL hash state sync (reads hash → state on load, pushes state → hash on change)
    const hadHash = applyHashState();
    watchHashState();
    if (hadHash) {
        // Sync UI controls with restored state
        const s = getState();
        const symEl = document.getElementById('symbol-input');
        const intEl = document.getElementById('interval-select');
        if (symEl) symEl.value = s.get('symbol') || 'BTCUSDT';
        if (intEl) intEl.value = s.get('interval') || '1d';
    }

    // Global Ctrl/Cmd+Enter
    document.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); runScript(); }
    });

    // Editor slide-in toggle
    const editorToggle = document.getElementById('editor-toggle');
    const editorSlide = document.getElementById('editor-slide');
    let editorOpen = false;

    function toggleEditor(open) {
        editorOpen = open !== undefined ? open : !editorOpen;
        editorSlide.classList.toggle('open', editorOpen);
        if (editorOpen) {
            // Reset to 460px when re-opening (in case it was resized)
            editorSlide.style.width = '';
        }
        // Trigger chart resize after transition completes
        setTimeout(() => window.dispatchEvent(new Event('resize')), 300);
    }

    if (editorToggle && editorSlide) {
        editorToggle.addEventListener('click', () => toggleEditor());
        // Editor toggle shortcut: Ctrl+\
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === '\\') { e.preventDefault(); toggleEditor(); }
        });
    }

    // Editor resize drag handle
    const resizeHandle = document.getElementById('editor-resize');
    if (resizeHandle && editorSlide) {
        let isDragging = false;
        let startX = 0;
        let startW = 0;

        resizeHandle.addEventListener('mousedown', (e) => {
            isDragging = true;
            startX = e.clientX;
            startW = editorSlide.offsetWidth;
            resizeHandle.classList.add('is-dragging');
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
        });

        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            const newW = Math.max(280, Math.min(startW + (startX - e.clientX), window.innerWidth * 0.8));
            editorSlide.style.width = `${newW}px`;
            window.dispatchEvent(new Event('resize'));
        });

        document.addEventListener('mouseup', () => {
            if (isDragging) {
                isDragging = false;
                resizeHandle.classList.remove('is-dragging');
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
            }
        });
    }

    // Initial load
    await loadHistorical();
    setStatus('Ready.', 'success', `${registry.listSources().length} src · ${registry.listEngines().length} eng · ${registry.listStreams().length} stream`);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootstrap);
} else {
    bootstrap();
}
