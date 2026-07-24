// Chart wrapper around lightweight-charts.
// Supports a main price pane, a volume histogram sub-pane, an indicator
// sub-pane (used for `overlay=false` plots), and an equity pane for the
// strategy tester. Each pane gets its own `IChartApi` so the time scales
// stay independent — main/indicator panes share a logical "time axis"
// through `setVisibleRange` syncing.

const TV = {
    bg: '#131722',
    grid: '#1e222d',
    text: '#d1d4dc',
    up: '#26a69a',
    down: '#ef5350',
};
const PLOT_PALETTE = ['#2962ff', '#ff6d00', '#2e7d32', '#9c27b0', '#00bcd4', '#fdd835', '#e91e63', '#5d4037'];

let ro = null;

// Pane state: each entry holds the lightweight-charts instance + helpers.
const panes = {
    main: { chart: null, candle: null, overlays: [] },
    volume: { chart: null, hist: null },
    indicator: { chart: null, overlays: [], visible: false },
    equity: { chart: null, area: null },
};

function commonOptions() {
    return {
        layout: { background: { type: 'solid', color: TV.bg }, textColor: TV.text },
        grid: { vertLines: { color: TV.grid }, horzLines: { color: TV.grid } },
        rightPriceScale: { borderColor: '#485c7b' },
        timeScale: { borderColor: '#485c7b', timeVisible: true, secondsVisible: false },
    };
}

export function initChart({ mainEl, volumeEl, indicatorEl, equityEl }) {
    if (typeof LightweightCharts === 'undefined') throw new Error('lightweight-charts not loaded');

    // Main price pane
    panes.main.chart = LightweightCharts.createChart(mainEl, {
        ...commonOptions(),
        crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
    });
    panes.main.candle = panes.main.chart.addCandlestickSeries({
        upColor: TV.up, downColor: TV.down, borderDownColor: TV.down, borderUpColor: TV.up,
        wickDownColor: TV.down, wickUpColor: TV.up,
    });

    // Volume sub-pane
    panes.volume.chart = LightweightCharts.createChart(volumeEl, {
        ...commonOptions(),
        timeScale: { visible: false, borderColor: '#485c7b' },
    });
    panes.volume.hist = panes.volume.chart.addHistogramSeries({
        priceFormat: { type: 'volume' },
        priceScaleId: '',
        color: TV.up,
    });
    panes.volume.hist.priceScale().applyOptions({ scaleMargins: { top: 0.1, bottom: 0.1 } });

    // Indicator sub-pane (hidden until a run produces overlay=false plots)
    panes.indicator.chart = LightweightCharts.createChart(indicatorEl, {
        ...commonOptions(),
        crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
    });

    // Equity pane
    panes.equity.chart = LightweightCharts.createChart(equityEl, commonOptions());
    panes.equity.area = panes.equity.chart.addAreaSeries({
        lineColor: '#2962ff', topColor: 'rgba(41, 98, 255, 0.4)',
        bottomColor: 'rgba(41, 98, 255, 0.0)', lineWidth: 2,
    });

    // Resize observer
    ro = new ResizeObserver(() => fitAll());
    ro.observe(mainEl);
    ro.observe(volumeEl);
    ro.observe(indicatorEl);
    ro.observe(equityEl);

    // Sync time scale of volume + indicator with the main chart.
    let suppress = false;
    const sync = (src, dst) => {
        src.timeScale().subscribeVisibleLogicalRangeChange((range) => {
            if (suppress || !range) return;
            suppress = true;
            try { dst.timeScale().setVisibleLogicalRange(range); } finally { suppress = false; }
        });
    };
    sync(panes.main.chart, panes.volume.chart);
    sync(panes.main.chart, panes.indicator.chart);
    // Equity chart intentionally NOT synced — it has far fewer points
}

function fitAll() {
    // Resize each chart to its container
    for (const [key, sel] of [
        ['main', '#chart'],
        ['volume', '#volume-chart'],
        ['indicator', '#indicator-chart'],
        ['equity', '#equity-chart'],
    ]) {
        const el = document.querySelector(sel);
        if (el && panes[key]?.chart) {
            const r = el.getBoundingClientRect();
            panes[key].chart.applyOptions({ width: r.width, height: r.height });
        }
    }
}

// --- Data setters --------------------------------------------------------

export function setOhlcv(bars) {
    if (!panes.main.candle || !panes.volume.hist) return [];
    const norm = (b) => ({
        time: typeof b.time === 'number' ? b.time : Math.floor(new Date(b.time).getTime() / 1000),
        open: Number(b.open), high: Number(b.high), low: Number(b.low), close: Number(b.close),
        volume: b.volume !== undefined ? Number(b.volume) : undefined,
    });
    const data = bars.map(norm).filter((b) => Number.isFinite(b.time) && Number.isFinite(b.open));
    panes.main.candle.setData(data);
    panes.volume.hist.setData(data.map((b) => ({
        time: b.time,
        value: b.volume ?? 0,
        color: b.close >= b.open ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)',
    })));
    panes.main.chart.timeScale().fitContent();
    return data;
}

export function appendBar(bar) {
    const t = typeof bar.time === 'number' ? bar.time : Math.floor(new Date(bar.time).getTime() / 1000);
    const point = { time: t, open: +bar.open, high: +bar.high, low: +bar.low, close: +bar.close };
    try { panes.main.candle.update(point); } catch (err) { console.warn('[chart] appendBar/main:', err.message); }
    if (bar.volume !== undefined) {
        try { panes.volume.hist.update({
            time: t, value: +bar.volume,
            color: point.close >= point.open ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)',
        }); } catch (err) { console.warn('[chart] appendBar/vol:', err.message); }
    }
    return point;
}

export function setMarkers(markers) {
    if (!panes.main.candle) return;
    try { panes.main.candle.setMarkers(markers); } catch (err) { console.warn('[chart] setMarkers:', err.message); }
}

export function clearOverlays() {
    for (const pane of [panes.main, panes.indicator]) {
        for (const s of pane.overlays) {
            try { pane.chart.removeSeries(s); } catch (err) { console.warn('[chart] clearOverlays:', err.message); }
        }
        pane.overlays = [];
    }
    setIndicatorVisible(false);
}

export function addOverlayLine(name, points, opts = {}) {
    const target = opts.pane === 'indicator' && panes.indicator.chart ? panes.indicator : panes.main;
    if (target === panes.indicator) setIndicatorVisible(true);
    const color = opts.color || PLOT_PALETTE[target.overlays.length % PLOT_PALETTE.length];
    const series = target.chart.addLineSeries({
        color, lineWidth: opts.lineWidth ?? 2, priceLineVisible: false, lastValueVisible: true, title: name,
    });
    series.setData(points);
    target.overlays.push(series);
    return series;
}

export function setEquityPane(visible) {
    const pane = document.getElementById('equity-pane');
    if (pane) pane.hidden = !visible;
}

export function setEquityCurve(points) {
    if (!panes.equity.area) return;
    try { panes.equity.area.setData(points); panes.equity.chart.timeScale().fitContent(); } catch (err) { console.warn('[chart] setEquityCurve:', err.message); }
}

function setIndicatorVisible(visible) {
    const el = document.getElementById('indicator-pane');
    if (!el) return;
    el.hidden = !visible;
    panes.indicator.visible = visible;
    // Force a resize after CSS unhide so the chart knows its new size.
    if (visible) {
        setTimeout(() => {
            const r = document.getElementById('indicator-chart')?.getBoundingClientRect();
            if (r) panes.indicator.chart.applyOptions({ width: r.width, height: r.height });
        }, 30);
    }
}

// --- Time scale helpers -------------------------------------------------

const RANGE_DAYS = { '1D': 1, '5D': 5, '1M': 30, '3M': 90, '6M': 180, '1Y': 365 };
const SEC_PER_DAY = 86400;

export function setTimeRange(range) {
    if (!panes.main.chart) return;
    if (range === 'ALL') { panes.main.chart.timeScale().fitContent(); return; }
    if (range === 'YTD') {
        const now = Math.floor(Date.now() / 1000);
        const startOfYear = Math.floor(new Date(new Date().getFullYear(), 0, 1).getTime() / 1000);
        panes.main.chart.timeScale().setVisibleRange({ from: startOfYear, to: now });
        return;
    }
    const days = RANGE_DAYS[range];
    if (!days) return;
    const now = Math.floor(Date.now() / 1000);
    panes.main.chart.timeScale().setVisibleRange({ from: now - days * SEC_PER_DAY, to: now });
}
