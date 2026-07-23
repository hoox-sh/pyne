// Symbol autocomplete.  Wraps the symbol <input> in a combo-box that
// fetches /exchangeInfo from Binance (or any provider the user configures)
// and offers fuzzy matches.  Cached for an hour in localStorage.

const CACHE_KEY = 'pynescript.superchart.symbols.v1';
const CACHE_TTL_MS = 60 * 60 * 1000;
const DEFAULT_BASE = 'https://api.binance.com';

function loadCache() {
    try {
        const c = JSON.parse(localStorage.getItem(CACHE_KEY) || 'null');
        if (c && Date.now() - c.ts < CACHE_TTL_MS) return c.symbols;
    } catch (_) { /* ignore */ }
    return null;
}
function saveCache(symbols) {
    try { localStorage.setItem(CACHE_KEY, JSON.stringify({ ts: Date.now(), symbols })); } catch (_) { /* ignore */ }
}

async function fetchSymbols(base = DEFAULT_BASE) {
    const res = await fetch(`${base}/api/v3/exchangeInfo`, { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return (data.symbols || [])
        .filter((s) => s.status === 'TRADING' && s.isSpotTradingAllowed !== false)
        .map((s) => ({
            symbol: s.symbol,
            base: s.baseAsset,
            quote: s.quoteAsset,
            display: `${s.base}/${s.quote}`,
        }));
}

function rank(query, list) {
    const q = query.toUpperCase();
    const out = [];
    for (const s of list) {
        if (s.symbol === q) { out.push({ s, score: 0 }); continue; }
        if (s.base === q) { out.push({ s, score: 1 }); continue; }
        if (s.symbol.startsWith(q)) { out.push({ s, score: 2 }); continue; }
        if (s.base.startsWith(q)) { out.push({ s, score: 3 }); continue; }
        if (s.symbol.includes(q) || s.base.includes(q)) { out.push({ s, score: 4 }); continue; }
    }
    out.sort((a, b) => a.score - b.score);
    return out.slice(0, 12).map((o) => o.s);
}

let popover = null;
let active = 0;
let items = [];
let inputEl = null;
let lastQuery = '';

function close() {
    if (popover) { popover.remove(); popover = null; }
    document.removeEventListener('mousedown', outsideClick);
    document.removeEventListener('keydown', keyHandler, true);
}

function outsideClick(e) {
    if (!popover) return;
    if (popover.contains(e.target) || e.target === inputEl) return;
    close();
}

function keyHandler(e) {
    if (!popover) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); move(1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); move(-1); }
    else if (e.key === 'Enter' && items[active]) { e.preventDefault(); pick(items[active]); }
    else if (e.key === 'Escape') { close(); }
}

function move(delta) {
    if (!items.length) return;
    active = (active + delta + items.length) % items.length;
    render();
}

function pick(item) {
    if (!inputEl) return;
    inputEl.value = item.symbol;
    inputEl.dispatchEvent(new Event('change'));
    close();
}

function render() {
    if (!popover) return;
    popover.innerHTML = items.map((s, i) => `
        <div class="ac-item ${i === active ? 'is-active' : ''}" data-i="${i}">
            <strong>${s.symbol}</strong>
            <span class="ac-quote">${s.display}</span>
        </div>
    `).join('') || '<div class="ac-empty">No matches</div>';
    for (const el of popover.querySelectorAll('.ac-item')) {
        el.addEventListener('mousedown', (e) => { e.preventDefault(); pick(items[+el.dataset.i]); });
    }
}

async function ensurePopover() {
    if (popover) return popover;
    popover = document.createElement('div');
    popover.className = 'ac-popover';
    document.body.appendChild(popover);
    document.addEventListener('mousedown', outsideClick);
    document.addEventListener('keydown', keyHandler, true);
    return popover;
}

function position(input) {
    if (!popover) return;
    const r = input.getBoundingClientRect();
    popover.style.left = `${r.left + window.scrollX}px`;
    popover.style.top = `${r.bottom + window.scrollY + 2}px`;
    popover.style.width = `${r.width}px`;
}

export async function attachSymbolAutocomplete(input, onPick) {
    inputEl = input;
    let symbols = loadCache();
    if (!symbols) {
        try { symbols = await fetchSymbols(); saveCache(symbols); }
        catch (_) { symbols = []; }
    }
    input.addEventListener('focus', () => show(input, ''));
    input.addEventListener('input', () => show(input, input.value));
    input.addEventListener('blur', () => setTimeout(close, 200));

    async function show(el_, q) {
        if (q === lastQuery && popover) { position(el_); return; }
        lastQuery = q;
        if (!symbols) return;
        items = q ? rank(q, symbols) : symbols.slice(0, 12);
        active = 0;
        if (!items.length) { close(); return; }
        await ensurePopover();
        render();
        position(el_);
    }

    if (onPick) {
        const origDispatch = input.dispatchEvent.bind(input);
        input.addEventListener('change', () => onPick(input.value));
    }
}
