// Watchlist sidebar component.
// Shows a list of symbols with live prices (fetched from Binance).
// Clicking a symbol loads its chart data.

import { getState } from '../state.js';

const DEFAULT_SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'ADAUSDT', 'DOGEUSDT'];

let _symbols = [];
let _prices = {};   // symbol → { price, change }
let _timer = null;

function el(id) { return document.getElementById(id); }

function renderWatchlist() {
    const body = el('watchlist-body');
    if (!body) return;
    const current = (getState().get('symbol') || 'BTCUSDT').toUpperCase();
    body.innerHTML = '';
    for (const sym of _symbols) {
        const item = document.createElement('div');
        item.className = 'watchlist-item' + (sym === current ? ' is-active' : '');
        item.dataset.symbol = sym;

        const info = _prices[sym] || {};
        const price = info.price != null ? Number(info.price).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—';
        const change = info.change != null ? (info.change >= 0 ? '+' : '') + info.change.toFixed(2) + '%' : '';
        const changeClass = info.change != null ? (info.change >= 0 ? 'positive' : 'negative') : '';

        item.innerHTML = `
            <span class="watchlist-symbol">${sym}</span>
            <span style="display:flex;align-items:center;gap:6px;">
                <span class="watchlist-price">${price}</span>
                ${change ? `<span class="watchlist-change ${changeClass}">${change}</span>` : ''}
                <span class="watchlist-remove" title="Remove ${sym}">×</span>
            </span>
        `;

        item.addEventListener('click', (e) => {
            if (e.target.classList.contains('watchlist-remove')) return;
            selectSymbol(sym);
        });

        item.querySelector('.watchlist-remove').addEventListener('click', (e) => {
            e.stopPropagation();
            removeSymbol(sym);
        });

        body.appendChild(item);
    }
}

async function fetchPrices() {
    if (_symbols.length === 0) return;
    try {
        const syms = _symbols.map(s => s.toLowerCase());
        const res = await fetch(`https://api.binance.com/api/v3/ticker/24hr?symbols=${JSON.stringify(syms)}`);
        if (!res.ok) return;
        const data = await res.json();
        for (const t of data) {
            _prices[t.symbol] = {
                price: parseFloat(t.lastPrice),
                change: parseFloat(t.priceChangePercent),
            };
        }
        renderWatchlist();
    } catch (_) { /* offline or rate-limited — ignore */ }
}

function selectSymbol(sym) {
    sym = sym.toUpperCase();
    getState().assign({ symbol: sym });
    el('symbol-input').value = sym;
    renderWatchlist();
    // Trigger a reload by dispatching a custom event
    window.dispatchEvent(new CustomEvent('watchlist-select', { detail: { symbol: sym } }));
}

function addSymbol(sym) {
    sym = sym.toUpperCase().trim();
    if (!sym || _symbols.includes(sym)) return;
    _symbols.push(sym);
    persistSymbols();
    fetchPrices();
    renderWatchlist();
}

function removeSymbol(sym) {
    _symbols = _symbols.filter(s => s !== sym);
    persistSymbols();
    renderWatchlist();
}

function persistSymbols() {
    try { localStorage.setItem('watchlist_symbols', JSON.stringify(_symbols)); } catch (_) {}
}

function loadSymbols() {
    try {
        const raw = localStorage.getItem('watchlist_symbols');
        if (raw) { _symbols = JSON.parse(raw); return; }
    } catch (_) {}
    _symbols = [...DEFAULT_SYMBOLS];
}

export function initWatchlist() {
    loadSymbols();
    renderWatchlist();

    // Add-symbol input
    const addInput = el('watchlist-add');
    if (addInput) {
        addInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                const v = addInput.value.trim();
                if (v) { addSymbol(v); addInput.value = ''; }
            }
        });
    }

    // Sidebar toggle — always starts visible, collapse is transient
    const toggleBtn = el('sidebar-toggle');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', () => {
            document.querySelector('.layout').classList.toggle('sidebar-collapsed');
        });
        // Never start collapsed — watchlist should always be visible on load.
        document.querySelector('.layout')?.classList.remove('sidebar-collapsed');
        localStorage.removeItem('sidebar_collapsed');
    }

    // Sync: when symbol changes externally, re-render
    getState().addEventListener('change', () => renderWatchlist());

    // Fetch prices immediately and every 30s
    fetchPrices();
    _timer = setInterval(fetchPrices, 30_000);
}

export function destroyWatchlist() {
    if (_timer) { clearInterval(_timer); _timer = null; }
}
