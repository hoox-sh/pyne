import type { Bar } from '../store/types';

export interface StreamPlugin {
  id: string;
  name: string;
  start(opts: {
    symbol: string;
    interval: string;
    onBar: (bar: Bar) => void;
    onStatus: (status: { state: string }) => void;
    onError: (err: Error) => void;
  }): () => void;
}

const INTERVAL_MAP: Record<string, string> = {
  '1m': '1m', '5m': '5m', '15m': '15m', '1h': '1h', '4h': '4h', '1d': '1d', '1w': '1w',
};

export const binanceStream: StreamPlugin = {
  id: 'binance-ws',
  name: 'Binance WebSocket',
  start({ symbol, interval, onBar, onStatus, onError }) {
    const wsInterval = INTERVAL_MAP[interval] || interval;
    const url = `wss://stream.binance.com:9443/ws/${symbol.toLowerCase()}@kline_${wsInterval}`;
    const ws = new WebSocket(url);

    ws.onopen = () => onStatus({ state: 'open' });
    ws.onerror = () => onError(new Error('WebSocket error'));
    ws.onclose = () => onStatus({ state: 'closed' });

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        const k = data.k;
        if (!k) return;
        const bar: Bar = {
          time: Math.floor(k.t / 1000),
          open: +k.o, high: +k.h, low: +k.l, close: +k.c, volume: +k.v,
        };
        onBar(bar);
      } catch {}
    };

    return () => ws.close();
  },
};
