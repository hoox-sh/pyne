// Copyright (C) 2024-2026 jango_blockchained
//
// This file is part of pynescript.
//
// pynescript is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// pynescript is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
//
// SPDX-License-Identifier: AGPL-3.0-or-later

// Results panel — Trades & Events, Plots, Metrics, Raw JSON tabs.

function el(id) { return document.getElementById(id); }

const refs = {};

function flashCopied(btn) {
    btn.classList.add('copied');
    const orig = btn.innerHTML;
    btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
    setTimeout(() => {
        btn.innerHTML = orig;
        btn.classList.remove('copied');
    }, 1200);
}

function getPanelTextContent(panelId) {
    const panel = document.getElementById(panelId);
    if (!panel) return '';
    // Get text content, but skip the copy button text
    const clone = panel.cloneNode(true);
    const btn = clone.querySelector('.btn-copy-panel');
    if (btn) btn.remove();
    return (clone.textContent || '').trim();
}

async function copyPanel(name) {
    const panelIds = {
        trades: 'tab-trades',
        strategy: 'tab-strategy',
        plots: 'tab-plots',
        metrics: 'tab-metrics',
        raw: 'tab-raw',
    };
    const panelId = panelIds[name];
    if (!panelId) return;

    // For raw JSON, prefer the pre content
    let text;
    if (name === 'raw') {
        const pre = document.getElementById('raw-json');
        text = pre?.textContent || '';
    } else if (name === 'trades') {
        text = getPanelTextContent(panelId);
        // Format as structured text
        const lines = text.split('\n').map(l => l.trim()).filter(Boolean);
        text = lines.join('\n');
    } else {
        text = getPanelTextContent(panelId);
    }

    if (!text) return;
    try {
        await navigator.clipboard.writeText(text);
        const btn = document.querySelector(`.btn-copy-panel[data-copy="${name}"]`);
        if (btn) flashCopied(btn);
    } catch { /* no-op */ }
}

export function initResults() {
    refs.trades = el('tab-trades');
    refs.strategy = el('tab-strategy');
    refs.plots = el('tab-plots');
    refs.metrics = el('tab-metrics');
    refs.raw = el('tab-raw');
    refs.rawJson = el('raw-json');
    for (const tab of document.querySelectorAll('.tab')) {
        tab.addEventListener('click', () => activateTab(tab.dataset.tab));
    }
    // Wire copy buttons
    for (const btn of document.querySelectorAll('.btn-copy-panel')) {
        const name = btn.dataset.copy;
        if (name) btn.addEventListener('click', () => copyPanel(name));
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

function buildStrategyReport(events) {
    // Walk the events stream and pair entries with subsequent closes.
    // Returns { trades: [...], stats: {...} }.
    const sorted = (events || []).slice().sort((a, b) => (a.time || 0) - (b.time || 0));
    const open = new Map(); // id -> { entry price, entry time, dir }
    const trades = [];
    for (const ev of sorted) {
        const t = ev.time;
        const p = ev.price;
        if (t === undefined || p === undefined) continue;
        const kind = (ev.type || ev.event || '').toLowerCase();
        const id = ev.id || '_default';
        if (kind.includes('entry')) {
            const dir = (ev.dir || kind).toString().toLowerCase();
            open.set(id, { entry: p, time: t, dir });
        } else if (kind.includes('close') || kind.includes('exit')) {
            const o = open.get(id);
            if (o) {
                const pnl = (p - o.entry) * (o.dir.includes('short') ? -1 : 1);
                const pnlPct = pnl / o.entry;
                trades.push({ id, dir: o.dir, entryTime: o.time, entry: o.entry, exitTime: t, exit: p, pnl, pnlPct });
                open.delete(id);
            }
        }
    }

    const wins = trades.filter((t) => t.pnl > 0);
    const losses = trades.filter((t) => t.pnl <= 0);
    const totalPnl = trades.reduce((s, t) => s + t.pnl, 0);
    const grossProfit = wins.reduce((s, t) => s + t.pnl, 0);
    const grossLoss = Math.abs(losses.reduce((s, t) => s + t.pnl, 0));
    const winRate = trades.length ? (wins.length / trades.length) * 100 : 0;
    const profitFactor = grossLoss > 0 ? grossProfit / grossLoss : grossProfit > 0 ? Infinity : 0;
    const avgTrade = trades.length ? totalPnl / trades.length : 0;
    const avgWin = wins.length ? grossProfit / wins.length : 0;
    const avgLoss = losses.length ? -grossLoss / losses.length : 0;

    // Max drawdown on the equity curve.
    let equity = 0, peak = 0, maxDD = 0;
    for (const t of trades) {
        equity += t.pnl;
        if (equity > peak) peak = equity;
        const dd = (peak - equity) / Math.max(1, Math.abs(peak) + 1);
        if (dd > maxDD) maxDD = dd;
    }
    return {
        trades,
        stats: { totalPnl, winRate, profitFactor, avgTrade, avgWin, avgLoss, maxDD, wins: wins.length, losses: losses.length, trades: trades.length },
    };
}

function formatPct(n) {
    if (!Number.isFinite(n)) return '—';
    return (n * 100).toFixed(2) + '%';
}

function formatMoney(n) {
    if (!Number.isFinite(n)) return '—';
    return (n >= 0 ? '+' : '') + n.toFixed(2);
}

function renderStrategy(payload) {
    if (!refs.strategy) return;
    if (payload.error) {
        refs.strategy.innerHTML = `<div class="empty">Error: ${escapeHtml(payload.error)}</div>`;
        return;
    }
    const events = payload.events || [];
    if (!events.length) {
        refs.strategy.innerHTML = '<div class="empty">No events. This is the Strategy Tester — it analyses strategy.entry/close events.</div>';
        return;
    }
    const { trades, stats } = buildStrategyReport(events);
    if (!trades.length) {
        refs.strategy.innerHTML = `<div class="empty">${events.length} events but no closed trades yet (positions still open or only entries).</div>`;
        return;
    }

    const summary = `
        <div class="metric-grid metric-grid-wide">
            <div class="metric metric-big"><span class="metric-label">Net P&amp;L</span><span class="metric-value ${stats.totalPnl >= 0 ? 'pos' : 'neg'}">${formatMoney(stats.totalPnl)}</span></div>
            <div class="metric metric-big"><span class="metric-label">Win Rate</span><span class="metric-value">${stats.winRate.toFixed(1)}%</span></div>
            <div class="metric metric-big"><span class="metric-label"># Trades</span><span class="metric-value">${stats.trades}</span></div>
            <div class="metric metric-big"><span class="metric-label">Profit Factor</span><span class="metric-value">${Number.isFinite(stats.profitFactor) ? stats.profitFactor.toFixed(2) : '∞'}</span></div>
            <div class="metric metric-big"><span class="metric-label">Avg Trade</span><span class="metric-value ${stats.avgTrade >= 0 ? 'pos' : 'neg'}">${formatMoney(stats.avgTrade)}</span></div>
            <div class="metric metric-big"><span class="metric-label">Max Drawdown</span><span class="metric-value neg">${(stats.maxDD * 100).toFixed(2)}%</span></div>
        </div>`;

    const rows = trades.map((t) => {
        const t1 = new Date(t.entryTime * 1000).toISOString().slice(0, 10);
        const t2 = new Date(t.exitTime * 1000).toISOString().slice(0, 10);
        return `<tr>
            <td>${escapeHtml(t.id)}</td>
            <td>${escapeHtml(t.dir)}</td>
            <td>${t1}</td>
            <td>${t.entry.toFixed(2)}</td>
            <td>${t2}</td>
            <td>${t.exit.toFixed(2)}</td>
            <td class="${t.pnl >= 0 ? 'pos' : 'neg'}">${formatMoney(t.pnl)}</td>
            <td class="${t.pnlPct >= 0 ? 'pos' : 'neg'}">${formatPct(t.pnlPct)}</td>
        </tr>`;
    }).join('');

    refs.strategy.innerHTML = `${summary}
        <div class="strategy-table-wrap">
        <table class="strategy-table">
            <thead><tr>
                <th>ID</th><th>Dir</th><th>Entry date</th><th>Entry</th>
                <th>Exit date</th><th>Exit</th><th>P&amp;L</th><th>%</th>
            </tr></thead>
            <tbody>${rows}</tbody>
        </table>
        </div>`;
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
        if (refs.strategy) refs.strategy.innerHTML = '<div class="empty">Run a strategy to see the tester.</div>';
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

    // Strategy tester
    renderStrategy(payload);
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
