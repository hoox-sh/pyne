/**
 * Live stream plugins for AXIS.
 */

import type { Bar } from '../store/types';

export interface StreamPlugin {
  id: string;
  name: string;
  description: string;
  start(opts: {
    symbol: string;
    interval: string;
    onBar: (bar: Bar) => void;
    onStatus: (status: { state: string; detail?: string }) => void;
    onError: (err: Error) => void;
    lastBar?: Bar | null;
  }): () => void;
}

const INTERVAL_MAP: Record<string, string> = {
  '1m': '1m',
  '5m': '5m',
  '15m': '15m',
  '1h': '1h',
  '4h': '4h',
  '1d': '1d',
  '1w': '1w',
};

function intervalToSec(iv: string): number {
  const m = /^(\d+)([mhdw])$/.exec(iv || '');
  if (!m) return 86400;
  const n = parseInt(m[1], 10);
  const mult: Record<string, number> = { m: 60, h: 3600, d: 86400, w: 604800 };
  return n * (mult[m[2]] || 86400);
}

export const binanceStream: StreamPlugin = {
  id: 'binance-ws',
  name: 'Binance WebSocket',
  description: 'Real-time klines via wss://stream.binance.com',
  start({ symbol, interval, onBar, onStatus, onError }) {
    const wsInterval = INTERVAL_MAP[interval] || interval;
    const url = `wss://stream.binance.com:9443/ws/${symbol.toLowerCase()}@kline_${wsInterval}`;
    let ws: WebSocket;
    try {
      ws = new WebSocket(url);
    } catch (e) {
      onError(e instanceof Error ? e : new Error(String(e)));
      return () => {};
    }

    ws.onopen = () => onStatus({ state: 'open', detail: url });
    ws.onerror = () => onError(new Error('WebSocket error'));
    ws.onclose = () => onStatus({ state: 'closed' });

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data as string);
        const k = data.k;
        if (!k) return;
        onBar({
          time: Math.floor(k.t / 1000),
          open: +k.o,
          high: +k.h,
          low: +k.l,
          close: +k.c,
          volume: +k.v,
        });
      } catch {
        /* ignore */
      }
    };

    return () => {
      try {
        ws.close();
      } catch {
        /* ignore */
      }
    };
  },
};

/** Offline live feed — synthesizes bars on a timer. */
export const mockPollStream: StreamPlugin = {
  id: 'mock-poll',
  name: 'Mock Poll',
  description: 'Synthetic live bars (offline). Good with Mock Walk source.',
  start({ interval, onBar, onStatus, lastBar }) {
    const step = intervalToSec(interval);
    let cur: Bar = lastBar
      ? { ...lastBar }
      : {
          time: Math.floor(Date.now() / 1000) - step,
          open: 100,
          high: 101,
          low: 99,
          close: 100,
          volume: 100,
        };

    onStatus({ state: 'open', detail: 'mock-poll' });

    const tick = () => {
      const now = Math.floor(Date.now() / 1000);
      // Align to interval slots
      const slot = Math.floor(now / step) * step;
      const drift = (Math.random() - 0.48) * cur.close * 0.008;
      if (slot === cur.time) {
        // Update open bar
        const close = Math.max(0.01, cur.close + drift);
        cur = {
          ...cur,
          high: Math.max(cur.high, close, cur.open),
          low: Math.min(cur.low, close, cur.open),
          close,
          volume: (cur.volume ?? 0) + Math.random() * 50,
        };
      } else {
        // New bar
        const open = cur.close;
        const close = Math.max(0.01, open + drift);
        cur = {
          time: slot,
          open,
          high: Math.max(open, close),
          low: Math.min(open, close),
          close,
          volume: 50 + Math.random() * 200,
        };
      }
      onBar({ ...cur });
    };

    // Immediate tick so live feels responsive
    tick();
    const id = setInterval(tick, 1000);
    return () => {
      clearInterval(id);
      onStatus({ state: 'closed' });
    };
  },
};

/** OKX public WS candle channel (books limited; trades/candles public). */
export const okxStream: StreamPlugin = {
  id: 'okx-ws',
  name: 'OKX WebSocket',
  description: 'OKX public candle channel (wss://ws.okx.com:8443/ws/v5/business).',
  start({ symbol, interval, onBar, onStatus, onError }) {
    const instId = (() => {
      const s = symbol.toUpperCase().replace(/[-_/]/g, '');
      if (s.endsWith('USDT')) return `${s.slice(0, -4)}-USDT`;
      return `${s}-USDT`;
    })();
    const barMap: Record<string, string> = {
      '1m': 'candle1m',
      '5m': 'candle5m',
      '15m': 'candle15m',
      '1h': 'candle1H',
      '4h': 'candle4H',
      '1d': 'candle1D',
      '1w': 'candle1W',
    };
    const channel = barMap[interval] || 'candle1D';
    const url = 'wss://ws.okx.com:8443/ws/v5/business';
    let ws: WebSocket;
    try {
      ws = new WebSocket(url);
    } catch (e) {
      onError(e instanceof Error ? e : new Error(String(e)));
      return () => {};
    }
    ws.onopen = () => {
      onStatus({ state: 'open', detail: url });
      ws.send(
        JSON.stringify({
          op: 'subscribe',
          args: [{ channel, instId }],
        }),
      );
    };
    ws.onerror = () => onError(new Error('OKX WebSocket error'));
    ws.onclose = () => onStatus({ state: 'closed' });
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data as string);
        const row = msg?.data?.[0];
        if (!row || !Array.isArray(row)) return;
        // [ts, o, h, l, c, vol, ...]
        onBar({
          time: Math.floor(Number(row[0]) / 1000),
          open: +row[1],
          high: +row[2],
          low: +row[3],
          close: +row[4],
          volume: +row[5],
        });
      } catch {
        /* ignore */
      }
    };
    return () => {
      try {
        ws.close();
      } catch {
        /* ignore */
      }
    };
  },
};

/** Bybit v5 public kline stream (spot). */
export const bybitStream: StreamPlugin = {
  id: 'bybit-ws',
  name: 'Bybit WebSocket',
  description: 'Bybit public kline stream (wss://stream.bybit.com/v5/public/spot).',
  start({ symbol, interval, onBar, onStatus, onError }) {
    const ivMap: Record<string, string> = {
      '1m': '1',
      '5m': '5',
      '15m': '15',
      '1h': '60',
      '4h': '240',
      '1d': 'D',
      '1w': 'W',
    };
    const iv = ivMap[interval] || 'D';
    const topic = `kline.${iv}.${symbol.toUpperCase()}`;
    const url = 'wss://stream.bybit.com/v5/public/spot';
    let ws: WebSocket;
    try {
      ws = new WebSocket(url);
    } catch (e) {
      onError(e instanceof Error ? e : new Error(String(e)));
      return () => {};
    }
    ws.onopen = () => {
      onStatus({ state: 'open', detail: topic });
      ws.send(JSON.stringify({ op: 'subscribe', args: [topic] }));
    };
    ws.onerror = () => onError(new Error('Bybit WebSocket error'));
    ws.onclose = () => onStatus({ state: 'closed' });
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data as string);
        const row = msg?.data?.[0];
        if (!row) return;
        onBar({
          time: Math.floor(Number(row.start) / 1000),
          open: +row.open,
          high: +row.high,
          low: +row.low,
          close: +row.close,
          volume: +row.volume,
        });
      } catch {
        /* ignore */
      }
    };
    return () => {
      try {
        ws.close();
      } catch {
        /* ignore */
      }
    };
  },
};

/** Coinbase Exchange ticker → 1s synthetic bar updates (public WS). */
export const coinbaseStream: StreamPlugin = {
  id: 'coinbase-ws',
  name: 'Coinbase WebSocket',
  description: 'Coinbase Exchange ticker (wss://ws-feed.exchange.coinbase.com) aggregated into live bars.',
  start({ symbol, interval, onBar, onStatus, onError, lastBar }) {
    const product = (() => {
      const s = symbol.toUpperCase().replace(/[-_/]/g, '');
      if (s.endsWith('USDT')) return `${s.slice(0, -4)}-USDT`;
      if (s.endsWith('USD')) return `${s.slice(0, -3)}-USD`;
      return `${s}-USD`;
    })();
    const step = intervalToSec(interval);
    const url = 'wss://ws-feed.exchange.coinbase.com';
    let ws: WebSocket;
    let cur: Bar | null = lastBar ? { ...lastBar } : null;
    try {
      ws = new WebSocket(url);
    } catch (e) {
      onError(e instanceof Error ? e : new Error(String(e)));
      return () => {};
    }
    ws.onopen = () => {
      onStatus({ state: 'open', detail: product });
      ws.send(
        JSON.stringify({
          type: 'subscribe',
          product_ids: [product],
          channels: ['ticker'],
        }),
      );
    };
    ws.onerror = () => onError(new Error('Coinbase WebSocket error'));
    ws.onclose = () => onStatus({ state: 'closed' });
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data as string);
        if (msg.type !== 'ticker' || msg.price == null) return;
        const price = +msg.price;
        const vol = msg.last_size != null ? +msg.last_size : 0;
        const now = Math.floor(Date.now() / 1000);
        const slot = Math.floor(now / step) * step;
        if (!cur || cur.time !== slot) {
          cur = {
            time: slot,
            open: price,
            high: price,
            low: price,
            close: price,
            volume: vol,
          };
        } else {
          cur = {
            ...cur,
            high: Math.max(cur.high, price),
            low: Math.min(cur.low, price),
            close: price,
            volume: (cur.volume ?? 0) + vol,
          };
        }
        onBar({ ...cur });
      } catch {
        /* ignore */
      }
    };
    return () => {
      try {
        ws.close();
      } catch {
        /* ignore */
      }
    };
  },
};

/** Kraken public OHLC channel. */
export const krakenStream: StreamPlugin = {
  id: 'kraken-ws',
  name: 'Kraken WebSocket',
  description: 'Kraken public OHLC (wss://ws.kraken.com/).',
  start({ symbol, interval, onBar, onStatus, onError }) {
    const pair = (() => {
      const s = symbol.toUpperCase().replace(/[-_/]/g, '');
      // Kraken uses XBT for BTC on many pairs
      let base = s;
      let quote = 'USD';
      if (s.endsWith('USDT')) {
        base = s.slice(0, -4);
        quote = 'USDT';
      } else if (s.endsWith('USD')) {
        base = s.slice(0, -3);
        quote = 'USD';
      }
      if (base === 'BTC') base = 'XBT';
      return `${base}/${quote}`;
    })();
    const ivMap: Record<string, number> = {
      '1m': 1,
      '5m': 5,
      '15m': 15,
      '1h': 60,
      '4h': 240,
      '1d': 1440,
      '1w': 10080,
    };
    const intervalMin = ivMap[interval] || 1440;
    const url = 'wss://ws.kraken.com/';
    let ws: WebSocket;
    try {
      ws = new WebSocket(url);
    } catch (e) {
      onError(e instanceof Error ? e : new Error(String(e)));
      return () => {};
    }
    ws.onopen = () => {
      onStatus({ state: 'open', detail: pair });
      ws.send(
        JSON.stringify({
          event: 'subscribe',
          pair: [pair],
          subscription: { name: 'ohlc', interval: intervalMin },
        }),
      );
    };
    ws.onerror = () => onError(new Error('Kraken WebSocket error'));
    ws.onclose = () => onStatus({ state: 'closed' });
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data as string);
        // [channelID, [time, etime, o, h, l, c, vwap, volume, count], "ohlc-*", "PAIR"]
        if (!Array.isArray(msg) || !Array.isArray(msg[1])) return;
        const row = msg[1];
        if (row.length < 8) return;
        onBar({
          time: Math.floor(Number(row[1])), // etime
          open: +row[2],
          high: +row[3],
          low: +row[4],
          close: +row[5],
          volume: +row[7],
        });
      } catch {
        /* ignore */
      }
    };
    return () => {
      try {
        ws.close();
      } catch {
        /* ignore */
      }
    };
  },
};

export const BUILTIN_STREAMS: StreamPlugin[] = [
  binanceStream,
  okxStream,
  bybitStream,
  coinbaseStream,
  krakenStream,
  mockPollStream,
];
const dynamicStreams: StreamPlugin[] = [];

export function getStream(id: string): StreamPlugin | undefined {
  return BUILTIN_STREAMS.find((s) => s.id === id) || dynamicStreams.find((s) => s.id === id);
}

export function listStreams(): StreamPlugin[] {
  return [...BUILTIN_STREAMS, ...dynamicStreams];
}

export function registerDynamicStream(stream: StreamPlugin): void {
  if (!stream?.id || typeof stream.start !== 'function') throw new Error('Invalid stream plugin');
  const i = dynamicStreams.findIndex((s) => s.id === stream.id);
  if (i >= 0) dynamicStreams[i] = stream;
  else dynamicStreams.push(stream);
}

/** Pick a sensible stream for the current historical source. */
export function defaultStreamForSource(sourceId: string): string {
  if (sourceId === 'mock-walk' || sourceId === 'csv-upload') return 'mock-poll';
  if (sourceId === 'okx-rest') return 'okx-ws';
  if (sourceId === 'bybit-rest') return 'bybit-ws';
  if (sourceId === 'coinbase-rest') return 'coinbase-ws';
  if (sourceId === 'kraken-rest') return 'kraken-ws';
  return 'binance-ws';
}
