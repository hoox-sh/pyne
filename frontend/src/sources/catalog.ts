/**
 * Built-in historical data sources for AXIS.
 * Used by Solid load path; legacy registry can keep its own JS copies.
 */

import type { Bar } from '../store/types';
import { getUploadedBars } from './upload-store';

export type SourceConfigSchema = Record<
  string,
  { type: string; default?: unknown; label?: string; min?: number; max?: number }
>;

export interface SourcePlugin {
  id: string;
  name: string;
  kind: 'source';
  description: string;
  configSchema: SourceConfigSchema;
  fetchHistorical: (args: {
    symbol: string;
    interval: string;
    config?: Record<string, unknown>;
  }) => Promise<Bar[]>;
}

function intervalToMs(iv: string): number {
  const m = /^(\d+)([mhdw])$/.exec(iv || '');
  if (!m) return 86400 * 1000;
  const n = parseInt(m[1], 10);
  const mult: Record<string, number> = {
    m: 60_000,
    h: 3_600_000,
    d: 86_400_000,
    w: 604_800_000,
  };
  return n * (mult[m[2]] || 86_400_000);
}

function resolveConfig(
  schema: SourceConfigSchema,
  config?: Record<string, unknown>,
): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, def] of Object.entries(schema || {})) {
    out[k] = def && 'default' in def ? def.default : undefined;
  }
  for (const [k, v] of Object.entries(config || {})) {
    if (v !== undefined) out[k] = v;
  }
  return out;
}

function synthesizeWalk(n: number, interval: string, start: number): Bar[] {
  const step = Math.floor(intervalToMs(interval) / 1000);
  const out: Bar[] = [];
  let price = start;
  const now = Math.floor(Date.now() / 1000);
  for (let i = n - 1; i >= 0; i--) {
    const t = now - i * step;
    const drift = (Math.random() - 0.48) * price * 0.02;
    const open = price;
    const close = Math.max(0.01, price + drift);
    const high = Math.max(open, close) + Math.random() * price * 0.005;
    const low = Math.min(open, close) - Math.random() * price * 0.005;
    out.push({
      time: t,
      open,
      high,
      low,
      close,
      volume: 100 + Math.random() * 1000,
    });
    price = close;
  }
  return out;
}

export const binanceRest: SourcePlugin = {
  id: 'binance-rest',
  name: 'Binance REST',
  kind: 'source',
  description:
    'Public Binance kline API (api.binance.com). Falls back to a synthetic walk if the network is unavailable.',
  configSchema: {
    baseUrl: { type: 'string', default: 'https://api.binance.com', label: 'API base URL' },
    limit: { type: 'number', default: 500, min: 50, max: 1000, label: 'Bars' },
    fallback: { type: 'boolean', default: true, label: 'Synthesize on failure' },
  },
  async fetchHistorical({ symbol, interval, config }) {
    const cfg = resolveConfig(this.configSchema, config);
    const baseUrl = String(cfg.baseUrl || 'https://api.binance.com');
    const limit = Number(cfg.limit) || 500;
    const url = `${baseUrl}/api/v3/klines?symbol=${encodeURIComponent(symbol)}&interval=${encodeURIComponent(interval)}&limit=${limit}`;
    try {
      const res = await fetch(url, {
        cache: 'no-store',
        signal: AbortSignal.timeout(15_000),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (!Array.isArray(data) || !data.length) throw new Error('empty kline response');
      return data.map((d: number[]) => ({
        time: d[0] / 1000,
        open: parseFloat(String(d[1])),
        high: parseFloat(String(d[2])),
        low: parseFloat(String(d[3])),
        close: parseFloat(String(d[4])),
        volume: parseFloat(String(d[5])),
      }));
    } catch (err: unknown) {
      if (!cfg.fallback) throw err;
      const msg = err instanceof Error ? err.message : String(err);
      console.warn(`[binance-rest] Network error, falling back to synthetic data: ${msg}`);
      return synthesizeWalk(limit || 200, interval, 100);
    }
  },
};

export const mockWalk: SourcePlugin = {
  id: 'mock-walk',
  name: 'Mock Walk',
  kind: 'source',
  description: 'Pure-synthetic random walk. Always available; deterministic seed optional.',
  configSchema: {
    seed: { type: 'number', default: 0, label: 'Seed (0 = random)' },
    startPrice: { type: 'number', default: 100, label: 'Start price' },
    limit: { type: 'number', default: 500, min: 50, max: 5000, label: 'Bars' },
  },
  async fetchHistorical({ interval, config }) {
    const cfg = resolveConfig(this.configSchema, config);
    const limit = Number(cfg.limit) || 500;
    const startPrice = Number(cfg.startPrice) || 100;
    const seed = Number(cfg.seed) || 0;
    if (seed) {
      let s = seed >>> 0;
      const rand = () => {
        s = (s + 0x6d2b79f5) >>> 0;
        let t = s;
        t = Math.imul(t ^ (t >>> 15), t | 1);
        t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
      };
      const out: Bar[] = [];
      const step = Math.floor(intervalToMs(interval) / 1000);
      const now = Math.floor(Date.now() / 1000);
      let price = startPrice;
      for (let i = limit - 1; i >= 0; i--) {
        const t = now - i * step;
        const drift = (rand() - 0.48) * price * 0.02;
        const open = price;
        const close = Math.max(0.01, price + drift);
        const high = Math.max(open, close) + rand() * price * 0.005;
        const low = Math.min(open, close) - rand() * price * 0.005;
        out.push({
          time: t,
          open,
          high,
          low,
          close,
          volume: 100 + rand() * 1000,
        });
        price = close;
      }
      return out;
    }
    return synthesizeWalk(limit, interval, startPrice);
  },
};

export const csvUpload: SourcePlugin = {
  id: 'csv-upload',
  name: 'CSV / JSON Upload',
  kind: 'source',
  description:
    'Uses the last file the user uploaded (CSV with time,open,high,low,close[,volume] or JSON array).',
  configSchema: {},
  async fetchHistorical() {
    const bars = getUploadedBars();
    if (!Array.isArray(bars) || !bars.length) {
      throw new Error('No uploaded file. Use Upload to pick a CSV/JSON file first.');
    }
    return bars;
  },
};

/** Map AXIS intervals to OKX bar codes */
function okxBar(interval: string): string {
  const m: Record<string, string> = {
    '1m': '1m',
    '5m': '5m',
    '15m': '15m',
    '1h': '1H',
    '4h': '4H',
    '1d': '1D',
    '1w': '1W',
  };
  return m[interval] || '1D';
}

/** BTCUSDT → BTC-USDT for OKX/Coinbase-style ids */
function dashPair(symbol: string, quote = 'USDT'): string {
  const s = symbol.toUpperCase().replace(/[-_/]/g, '');
  if (s.endsWith(quote)) return `${s.slice(0, -quote.length)}-${quote}`;
  if (s.endsWith('USD')) return `${s.slice(0, -3)}-USD`;
  return `${s}-${quote}`;
}

function bybitInterval(interval: string): string {
  const m: Record<string, string> = {
    '1m': '1',
    '5m': '5',
    '15m': '15',
    '1h': '60',
    '4h': '240',
    '1d': 'D',
    '1w': 'W',
  };
  return m[interval] || 'D';
}

export const okxRest: SourcePlugin = {
  id: 'okx-rest',
  name: 'OKX REST',
  kind: 'source',
  description: 'Public OKX candlesticks (www.okx.com). Symbol like BTCUSDT → BTC-USDT.',
  configSchema: {
    limit: { type: 'number', default: 300, min: 50, max: 300, label: 'Bars' },
  },
  async fetchHistorical({ symbol, interval, config }) {
    const cfg = resolveConfig(this.configSchema, config);
    const limit = Math.min(300, Number(cfg.limit) || 300);
    const instId = dashPair(symbol, 'USDT');
    const url = `https://www.okx.com/api/v5/market/candles?instId=${encodeURIComponent(instId)}&bar=${okxBar(interval)}&limit=${limit}`;
    const res = await fetch(url, { cache: 'no-store', signal: AbortSignal.timeout(15_000) });
    if (!res.ok) throw new Error(`OKX HTTP ${res.status}`);
    const json = await res.json();
    if (json.code !== '0' || !Array.isArray(json.data)) {
      throw new Error(json.msg || 'OKX empty response');
    }
    // OKX returns newest first: [ts, o, h, l, c, vol, ...]
    const bars: Bar[] = json.data
      .map((d: string[]) => ({
        time: Math.floor(Number(d[0]) / 1000),
        open: parseFloat(d[1]),
        high: parseFloat(d[2]),
        low: parseFloat(d[3]),
        close: parseFloat(d[4]),
        volume: parseFloat(d[5]),
      }))
      .reverse();
    if (!bars.length) throw new Error('OKX returned no candles');
    return bars;
  },
};

export const bybitRest: SourcePlugin = {
  id: 'bybit-rest',
  name: 'Bybit REST',
  kind: 'source',
  description: 'Public Bybit v5 spot klines (api.bybit.com).',
  configSchema: {
    limit: { type: 'number', default: 500, min: 50, max: 1000, label: 'Bars' },
  },
  async fetchHistorical({ symbol, interval, config }) {
    const cfg = resolveConfig(this.configSchema, config);
    const limit = Number(cfg.limit) || 500;
    const sym = symbol.toUpperCase().replace(/[-_/]/g, '');
    const url = `https://api.bybit.com/v5/market/kline?category=spot&symbol=${encodeURIComponent(sym)}&interval=${bybitInterval(interval)}&limit=${limit}`;
    const res = await fetch(url, { cache: 'no-store', signal: AbortSignal.timeout(15_000) });
    if (!res.ok) throw new Error(`Bybit HTTP ${res.status}`);
    const json = await res.json();
    const list = json?.result?.list;
    if (json.retCode !== 0 || !Array.isArray(list)) {
      throw new Error(json.retMsg || 'Bybit empty response');
    }
    // newest first
    const bars: Bar[] = list
      .map((d: string[]) => ({
        time: Math.floor(Number(d[0]) / 1000),
        open: parseFloat(d[1]),
        high: parseFloat(d[2]),
        low: parseFloat(d[3]),
        close: parseFloat(d[4]),
        volume: parseFloat(d[5]),
      }))
      .reverse();
    if (!bars.length) throw new Error('Bybit returned no candles');
    return bars;
  },
};

export const coinbaseRest: SourcePlugin = {
  id: 'coinbase-rest',
  name: 'Coinbase REST',
  kind: 'source',
  description: 'Coinbase Exchange public candles. Symbol BTCUSDT → BTC-USD.',
  configSchema: {
    granularity: { type: 'number', default: 0, label: 'Override granularity (sec, 0=auto)' },
  },
  async fetchHistorical({ symbol, interval }) {
    const product = dashPair(symbol.replace(/USDT$/i, 'USD'), 'USD');
    const granMap: Record<string, number> = {
      '1m': 60,
      '5m': 300,
      '15m': 900,
      '1h': 3600,
      '4h': 14400,
      '1d': 86400,
      '1w': 604800,
    };
    const gran = granMap[interval] || 86400;
    // Coinbase returns max 300 candles; request last window
    const end = Math.floor(Date.now() / 1000);
    const start = end - gran * 280;
    const url = `https://api.exchange.coinbase.com/products/${encodeURIComponent(product)}/candles?granularity=${gran}&start=${new Date(start * 1000).toISOString()}&end=${new Date(end * 1000).toISOString()}`;
    const res = await fetch(url, { cache: 'no-store', signal: AbortSignal.timeout(15_000) });
    if (!res.ok) throw new Error(`Coinbase HTTP ${res.status}`);
    const data = await res.json();
    if (!Array.isArray(data) || !data.length) throw new Error('Coinbase empty response');
    // [time, low, high, open, close, volume] newest first
    const bars: Bar[] = data
      .map((d: number[]) => ({
        time: Number(d[0]),
        low: Number(d[1]),
        high: Number(d[2]),
        open: Number(d[3]),
        close: Number(d[4]),
        volume: Number(d[5]),
      }))
      .sort((a, b) => a.time - b.time);
    return bars;
  },
};

/** Built-in sources in UI order */
export const BUILTIN_SOURCES: SourcePlugin[] = [
  binanceRest,
  okxRest,
  bybitRest,
  coinbaseRest,
  mockWalk,
  csvUpload,
];

const byId = new Map(BUILTIN_SOURCES.map((s) => [s.id, s]));
const dynamicSources: SourcePlugin[] = [];

export function getSource(id: string): SourcePlugin | undefined {
  return byId.get(id) || dynamicSources.find((s) => s.id === id);
}

export function listSources(): SourcePlugin[] {
  return [...BUILTIN_SOURCES, ...dynamicSources];
}

/** Register a runtime plugin source (D6). */
export function registerDynamicSource(source: SourcePlugin): void {
  if (!source?.id || source.kind !== 'source') {
    throw new Error('Invalid source plugin');
  }
  if (typeof source.fetchHistorical !== 'function') {
    throw new Error('Source must implement fetchHistorical');
  }
  const idx = dynamicSources.findIndex((s) => s.id === source.id);
  if (idx >= 0) dynamicSources[idx] = source;
  else dynamicSources.push(source);
  byId.set(source.id, source);
}

export function unregisterDynamicSource(id: string): void {
  const i = dynamicSources.findIndex((s) => s.id === id);
  if (i >= 0) dynamicSources.splice(i, 1);
  if (!BUILTIN_SOURCES.some((s) => s.id === id)) byId.delete(id);
}

export function listDynamicSourceIds(): string[] {
  return dynamicSources.map((s) => s.id);
}
