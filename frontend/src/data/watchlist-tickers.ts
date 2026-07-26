/**
 * Watchlist ticker quotes — prefer the active historical source exchange.
 */

export interface WatchTicker {
  price: number;
  change: number; // %
  source?: string;
}

function toUsdt(sym: string): string {
  const s = sym.toUpperCase().replace(/[^A-Z0-9]/g, '');
  if (s.endsWith('USDT') || s.endsWith('USD') || s.endsWith('USDC')) return s;
  return `${s}USDT`;
}

function okxInst(sym: string): string {
  const s = toUsdt(sym);
  if (s.endsWith('USDT')) return `${s.slice(0, -4)}-USDT`;
  if (s.endsWith('USD')) return `${s.slice(0, -3)}-USD`;
  return `${s}-USDT`;
}

/** Fetch 24h last + change for symbols using the active source when possible. */
export async function fetchWatchlistTickers(
  symbols: string[],
  sourceId: string,
): Promise<Record<string, WatchTicker>> {
  if (!symbols.length) return {};
  const id = (sourceId || 'binance-rest').toLowerCase();

  try {
    if (id.includes('okx')) return await fetchOkx(symbols);
    if (id.includes('bybit')) return await fetchBybit(symbols);
    if (id.includes('coinbase')) return await fetchCoinbase(symbols);
    if (id.includes('mock')) return mockTickers(symbols);
    if (id.includes('csv')) return {}; // no live quotes
    // binance-rest and default
    return await fetchBinance(symbols);
  } catch {
    // Fallback to Binance for common USDT pairs
    if (!id.includes('binance')) {
      try {
        return await fetchBinance(symbols);
      } catch {
        return {};
      }
    }
    return {};
  }
}

async function fetchBinance(symbols: string[]): Promise<Record<string, WatchTicker>> {
  const syms = symbols.map(toUsdt);
  const res = await fetch(
    `https://api.binance.com/api/v3/ticker/24hr?symbols=${JSON.stringify(syms)}`,
  );
  if (!res.ok) throw new Error(`binance ${res.status}`);
  const data = (await res.json()) as Array<{
    symbol: string;
    lastPrice: string;
    priceChangePercent: string;
  }>;
  const next: Record<string, WatchTicker> = {};
  for (const t of data) {
    // Map back to original key if present
    const orig = symbols.find((s) => toUsdt(s) === t.symbol) || t.symbol;
    next[orig] = {
      price: parseFloat(t.lastPrice),
      change: parseFloat(t.priceChangePercent),
      source: 'binance',
    };
  }
  return next;
}

async function fetchOkx(symbols: string[]): Promise<Record<string, WatchTicker>> {
  const res = await fetch('https://www.okx.com/api/v5/market/tickers?instType=SPOT');
  if (!res.ok) throw new Error(`okx ${res.status}`);
  const body = (await res.json()) as {
    data?: Array<{ instId: string; last: string; sodUtc0?: string; open24h?: string }>;
  };
  const byId = new Map((body.data || []).map((t) => [t.instId, t]));
  const next: Record<string, WatchTicker> = {};
  for (const sym of symbols) {
    const inst = okxInst(sym);
    const t = byId.get(inst);
    if (!t) continue;
    const last = parseFloat(t.last);
    const open = parseFloat(t.open24h || t.sodUtc0 || String(last));
    const change = open ? ((last - open) / open) * 100 : 0;
    next[sym] = { price: last, change, source: 'okx' };
  }
  return next;
}

async function fetchBybit(symbols: string[]): Promise<Record<string, WatchTicker>> {
  const res = await fetch('https://api.bybit.com/v5/market/tickers?category=spot');
  if (!res.ok) throw new Error(`bybit ${res.status}`);
  const body = (await res.json()) as {
    result?: { list?: Array<{ symbol: string; lastPrice: string; price24hPcnt: string }> };
  };
  const bySym = new Map((body.result?.list || []).map((t) => [t.symbol, t]));
  const next: Record<string, WatchTicker> = {};
  for (const sym of symbols) {
    const key = toUsdt(sym);
    const t = bySym.get(key);
    if (!t) continue;
    next[sym] = {
      price: parseFloat(t.lastPrice),
      change: parseFloat(t.price24hPcnt) * 100, // fraction → %
      source: 'bybit',
    };
  }
  return next;
}

async function fetchCoinbase(symbols: string[]): Promise<Record<string, WatchTicker>> {
  // Coinbase product ids like BTC-USD
  const next: Record<string, WatchTicker> = {};
  await Promise.all(
    symbols.slice(0, 12).map(async (sym) => {
      const base = toUsdt(sym).replace(/USDT$/, '').replace(/USD$/, '');
      const product = `${base}-USD`;
      try {
        const res = await fetch(`https://api.exchange.coinbase.com/products/${product}/ticker`);
        if (!res.ok) return;
        const t = (await res.json()) as { price?: string };
        const price = parseFloat(t.price || '0');
        if (!price) return;
        // 24h stats
        let change = 0;
        try {
          const s = await fetch(`https://api.exchange.coinbase.com/products/${product}/stats`);
          if (s.ok) {
            const st = (await s.json()) as { open?: string; last?: string };
            const open = parseFloat(st.open || '0');
            const last = parseFloat(st.last || String(price));
            if (open) change = ((last - open) / open) * 100;
          }
        } catch {
          /* ignore */
        }
        next[sym] = { price, change, source: 'coinbase' };
      } catch {
        /* ignore */
      }
    }),
  );
  return next;
}

function mockTickers(symbols: string[]): Record<string, WatchTicker> {
  const next: Record<string, WatchTicker> = {};
  for (const sym of symbols) {
    const seed = [...sym].reduce((a, c) => a + c.charCodeAt(0), 0);
    const price = 50 + (seed % 200) + Math.random() * 2;
    const change = (Math.random() - 0.5) * 6;
    next[sym] = { price, change, source: 'mock' };
  }
  return next;
}

export const WATCHLIST_INTERVALS = ['1m', '5m', '15m', '1h', '4h', '1d', '1w'] as const;

export const WATCHLIST_REFRESH_OPTIONS = [
  { value: 5, label: '5s' },
  { value: 15, label: '15s' },
  { value: 30, label: '30s' },
  { value: 60, label: '60s' },
] as const;
