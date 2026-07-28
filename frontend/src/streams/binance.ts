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
