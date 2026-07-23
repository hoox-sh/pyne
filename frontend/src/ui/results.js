// Results panel — Trades & Events, Plots, Metrics, Raw JSON tabs.

function el(id) { return document.getElementById(id); }

const refs = {};

export function initResults() {
    refs.trades = el('tab-trades');
    refs.plots = el('tab-plots');
    refs.metrics = el('tab-metrics');
    refs.raw = el('tab-raw');
    refs.rawJson = el('raw-json');
    for (const tab of document.querySelectorAll('.tab')) {
        tab.addEventListener('click', () => activateTab(tab.dataset.tab));
    }
    return refs;
}

function activateTab(name) {
    for (const tab of document.querySelectorAll('.tab')) {
        tab.classList.toggle('tab-active', tab.dataset.tab === name);
    }
    for (const panel of document.querySelectorAll('.tab-panel')) {
        panel.classList.toggle('tab-panel-active', panel.id === `tab-${name}`);
    }
}

function escapeHtml(s) {
    return String(s ?? '').replace(/[&<>"']/g, (c) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
}

function formatNum(n) {
    if (n === null || n === undefined) return '—';
    if (typeof n !== 'number' || Number.isNaN(n)) return '—';
    if (Math.abs(n) >= 1e6) return n.toExponential(2);
    return n.toFixed(Math.abs(n) >= 100 ? 2 : 4);
}

export function renderResults(payload) {
    if (!refs.trades) initResults();

    if (!payload) {
        refs.trades.innerHTML = '<div class="empty">Run a script to see events.</div>';
        refs.plots.innerHTML = '<div class="empty">Run a script to see plots.</div>';
        refs.metrics.innerHTML = '<div class="empty">Run a script to see metrics.</div>';
        refs.rawJson.textContent = '';
        return;
    }

    // Trades & events
    const events = payload.events || [];
    if (payload.error) {
        refs.trades.innerHTML = `<div class="empty">Error: ${escapeHtml(payload.error)}</div>`;
    } else if (!events.length) {
        refs.trades.innerHTML = '<div class="empty">No strategy events in this run.</div>';
    } else {
        const rows = events.map((ev) => {
            const t = ev.time ? new Date(ev.time * 1000).toISOString().slice(0, 16).replace('T', ' ') : '-';
            const kind = (ev.type || ev.event || '?').toString();
            const sym = ev.id || ev.symbol || '';
            const price = ev.price !== undefined ? Number(ev.price).toFixed(2) : '-';
            const detail = JSON.stringify(ev).slice(0, 120);
            return `<li class="event-item">
                <span class="event-time">${t}</span>
                <span class="event-type ${kind.toLowerCase()}">${escapeHtml(kind)}</span>
                <span class="event-symbol">${escapeHtml(sym)}</span>
                <span class="event-detail" title="${escapeHtml(detail)}">${escapeHtml(detail)}</span>
                <span class="event-price">${price}</span>
            </li>`;
        }).join('');
        refs.trades.innerHTML = `<ul class="event-list">${rows}</ul>`;
    }

    // Plots
    const plots = payload.plots || [];
    const series = payload.series || {};
    const plotKeys = Object.keys(series).filter((k) => !k.startsWith('__'));
    if (payload.error) {
        refs.plots.innerHTML = `<div class="empty">Error: ${escapeHtml(payload.error)}</div>`;
    } else if (plotKeys.length) {
        const rows = plotKeys.map((k, i) => {
            const arr = series[k];
            const last = Array.isArray(arr) ? arr[arr.length - 1] : null;
            const len = Array.isArray(arr) ? arr.length : 0;
            return `<div class="metric">
                <span class="metric-label">● ${escapeHtml(k)}</span>
                <span class="metric-value">${len} pts · last ${formatNum(last)}</span>
            </div>`;
        }).join('');
        refs.plots.innerHTML = `<div class="metric-grid">${rows}</div>`;
    } else if (plots.length) {
        const nonNull = plots.filter((v) => v !== null && v !== undefined).length;
        const last = [...plots].reverse().find((v) => v !== null && v !== undefined);
        refs.plots.innerHTML = `<div class="metric-grid">
            <div class="metric"><span class="metric-label">plot_0</span><span class="metric-value">${nonNull}/${plots.length} pts</span></div>
            <div class="metric"><span class="metric-label">last</span><span class="metric-value">${formatNum(last)}</span></div>
        </div>`;
    } else {
        refs.plots.innerHTML = '<div class="empty">No plots in this run.</div>';
    }

    // Metrics
    const metrics = deriveMetrics(payload);
    if (payload.error) {
        refs.metrics.innerHTML = `<div class="empty">Error: ${escapeHtml(payload.error)}</div>`;
    } else if (metrics.length) {
        const rows = metrics.map((m) => `<div class="metric">
            <span class="metric-label">${escapeHtml(m.label)}</span>
            <span class="metric-value">${escapeHtml(m.value)}</span>
        </div>`).join('');
        refs.metrics.innerHTML = `<div class="metric-grid">${rows}</div>`;
    } else {
        refs.metrics.innerHTML = '<div class="empty">No metrics available.</div>';
    }

    // Raw JSON
    try { refs.rawJson.textContent = JSON.stringify(payload, null, 2); }
    catch (_) { refs.rawJson.textContent = String(payload); }
}

function deriveMetrics(payload) {
    if (payload.error) return [];
    const events = payload.events || [];
    const m = [];
    const meta = payload.meta || {};
    m.push({ label: 'bars processed', value: String(meta.count ?? '—') });
    m.push({ label: 'events', value: String(events.length) });
    const entries = events.filter((e) => /entry/i.test(e.type || e.event || '')).length;
    const exits = events.filter((e) => /close|exit/i.test(e.type || e.event || '')).length;
    m.push({ label: 'entries', value: String(entries) });
    m.push({ label: 'exits', value: String(exits) });
    if (meta.mode) m.push({ label: 'mode', value: meta.mode });
    if (meta.script_id) m.push({ label: 'script_id', value: meta.script_id.slice(0, 12) });
    if (meta.run_id) m.push({ label: 'run_id', value: meta.run_id.slice(0, 8) });
    if (typeof meta.ms === 'number') m.push({ label: 'ms', value: meta.ms.toFixed(1) });
    return m;
}
