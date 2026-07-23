// Chart + equity pane wrapper. Owns the lightweight-charts instances.

const TV = {
    bg: '#131722',
    grid: '#1e222d',
    text: '#d1d4dc',
    up: '#26a69a',
    down: '#ef5350',
};
const PLOT_PALETTE = ['#2962ff', '#ff6d00', '#2e7d32', '#9c27b0', '#00bcd4', '#fdd835', '#e91e63', '#5d4037'];

let mainChart = null;
let candleSeries = null;
let overlaySeries = [];
let equityChart = null;
let equitySeries = null;
let ro = null;

export function initChart({ chartEl, equityEl, equityPaneEl }) {
    if (typeof LightweightCharts === 'undefined') {
        throw new Error('lightweight-charts not loaded');
    }
    mainChart = LightweightCharts.createChart(chartEl, {
        layout: { background: { type: 'solid', color: TV.bg }, textColor: TV.text },
        grid: { vertLines: { color: TV.grid }, horzLines: { color: TV.grid } },
        crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
        rightPriceScale: { borderColor: '#485c7b' },
        timeScale: { borderColor: '#485c7b', timeVisible: true, secondsVisible: false },
    });
    candleSeries = mainChart.addCandlestickSeries({
        upColor: TV.up, downColor: TV.down, borderDownColor: TV.down, borderUpColor: TV.up,
        wickDownColor: TV.down, wickUpColor: TV.up,
    });

    equityChart = LightweightCharts.createChart(equityEl, {
        layout: { background: { type: 'solid', color: TV.bg }, textColor: TV.text },
        grid: { vertLines: { color: TV.grid }, horzLines: { color: TV.grid } },
        timeScale: { borderColor: '#485c7b', timeVisible: true, secondsVisible: false },
        rightPriceScale: { borderColor: '#485c7b' },
    });
    equitySeries = equityChart.addAreaSeries({
        lineColor: '#2962ff', topColor: 'rgba(41, 98, 255, 0.4)',
        bottomColor: 'rgba(41, 98, 255, 0.0)', lineWidth: 2,
    });

    ro = new ResizeObserver(() => {
        if (mainChart) {
            const r = chartEl.getBoundingClientRect();
            mainChart.applyOptions({ width: r.width, height: r.height });
        }
        if (equityChart && !equityPaneEl.hidden) {
            const r = equityEl.getBoundingClientRect();
            equityChart.applyOptions({ width: r.width, height: r.height });
        }
    });
    ro.observe(chartEl);
    ro.observe(equityEl);
    return { mainChart, candleSeries, equitySeries, equityChart };
}

export function setOhlcv(bars) {
    if (!candleSeries) return;
    const norm = (b) => ({
        time: typeof b.time === 'number' ? b.time : Math.floor(new Date(b.time).getTime() / 1000),
        open: Number(b.open), high: Number(b.high), low: Number(b.low), close: Number(b.close),
        volume: b.volume !== undefined ? Number(b.volume) : undefined,
    });
    const data = bars.map(norm).filter((b) => Number.isFinite(b.time) && Number.isFinite(b.open));
    candleSeries.setData(data);
    mainChart.timeScale().fitContent();
    return data;
}

export function appendBar(bar) {
    const t = typeof bar.time === 'number' ? bar.time : Math.floor(new Date(bar.time).getTime() / 1000);
    const point = { time: t, open: +bar.open, high: +bar.high, low: +bar.low, close: +bar.close };
    try { candleSeries.update(point); } catch (_) { /* ignore */ }
    return point;
}

export function setMarkers(markers) {
    if (!candleSeries) return;
    try { candleSeries.setMarkers(markers); } catch (_) { /* ignore */ }
}

export function clearOverlays() {
    for (const s of overlaySeries) {
        try { mainChart.removeSeries(s); } catch (_) { /* ignore */ }
    }
    overlaySeries = [];
}

export function addOverlayLine(name, points) {
    const series = mainChart.addLineSeries({
        color: PLOT_PALETTE[overlaySeries.length % PLOT_PALETTE.length],
        lineWidth: 2, priceLineVisible: false, lastValueVisible: true, title: name,
    });
    series.setData(points);
    overlaySeries.push(series);
    return series;
}

export function setEquityPane(visible) {
    const pane = document.getElementById('equity-pane');
    if (pane) pane.hidden = !visible;
}

export function setEquityCurve(points) {
    if (!equitySeries) return;
    try { equitySeries.setData(points); equityChart.timeScale().fitContent(); } catch (_) { /* ignore */ }
}

export function getLastBar() {
    // last bar from the candle series
    try {
        const data = candleSeries.dataByIndex ? null : null; // lightweight-charts doesn't expose this directly
    } catch (_) { /* ignore */ }
    return null;
}
