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

// Live datastream plugins. All streams expose a `start({ symbol, interval,
// onBar, onError, onStatus })` function that returns a `stop()` cleanup
// function. The engine is responsible for connecting/disconnecting on
// symbol/interval changes.

function intervalToMs(iv) {
    const m = /^(\d+)([mhdw])$/.exec(iv || '');
    if (!m) return 86400 * 1000;
    const n = parseInt(m[1], 10);
    const mult = { m: 60_000, h: 3_600_000, d: 86_400_000, w: 604_800_000 }[m[2]] || 86_400_000;
    return n * mult;
}

function resolveConfig(schema, config) {
    const out = {};
    for (const [k, def] of Object.entries(schema || {})) {
        out[k] = def && Object.prototype.hasOwnProperty.call(def, 'default') ? def.default : undefined;
    }
    for (const [k, v] of Object.entries(config || {})) {
        if (v !== undefined) out[k] = v;
    }
    return out;
}

export const binanceWs = {
    id: 'binance-ws',
    name: 'Binance WebSocket',
    kind: 'stream',
    description: 'wss://stream.binance.com:9443 — kline stream for one symbol+interval. Real-time updates.',
    configSchema: {
        wsBase: { type: 'string', default: 'wss://stream.binance.com:9443', label: 'WS base URL' },
    },
    start({ symbol, interval, onBar, onError, onStatus, config }) {
        const cfg = resolveConfig(this.configSchema, config);
        const url = `${cfg.wsBase}/ws/${symbol.toLowerCase()}@kline_${interval}`;
        let ws;
        try { ws = new WebSocket(url); }
        catch (e) { onError?.(e); return () => {}; }

        ws.addEventListener('open', () => onStatus?.({ state: 'open', url }));
        ws.addEventListener('close', () => onStatus?.({ state: 'closed' }));
        ws.addEventListener('error', () => onError?.(new Error('WebSocket error')));
        ws.addEventListener('message', (ev) => {
            try {
                const msg = JSON.parse(ev.data);
                const k = msg.k;
                if (!k) return;
                onBar?.({
                    time: Math.floor(k.t / 1000),
                    open: parseFloat(k.o),
                    high: parseFloat(k.h),
                    low: parseFloat(k.l),
                    close: parseFloat(k.c),
                    volume: parseFloat(k.v),
                });
            } catch (e) { /* ignore parse */ }
        });

        return () => { try { ws.close(); } catch (_) { /* ignore */ } };
    },
};

// Synthetic poll — generates one new bar every `tickMs` ms by random-walking
// the close price. Useful for offline demos and tests.
export const mockPoll = {
    id: 'mock-poll',
    name: 'Mock Poll',
    kind: 'stream',
    description: 'Synthesizes a new bar at a fixed interval. No network. Perfect for offline demos.',
    configSchema: {
        tickMs: { type: 'number', default: 1000, min: 100, label: 'Tick (ms)' },
        volatility: { type: 'number', default: 0.005, min: 0, max: 0.5, label: 'Volatility' },
    },
    start({ interval, onBar, onError, onStatus, config, lastBar }) {
        const cfg = resolveConfig(this.configSchema, config);
        const step = Math.floor(intervalToMs(interval) / 1000);
        let cur = lastBar ? { ...lastBar } : null;
        if (cur) {
            // Advance to next slot if needed
            const now = Math.floor(Date.now() / 1000);
            while (cur.time + step <= now) cur = nextBar(cur, step, cfg.volatility);
            onBar?.(cur);
        }
        const handle = setInterval(() => {
            if (!cur) return;
            cur = nextBar(cur, step, cfg.volatility);
            onBar?.(cur);
        }, cfg.tickMs);
        onStatus?.({ state: 'open', url: 'mock://poll' });

        return () => {
            clearInterval(handle);
            onStatus?.({ state: 'closed' });
        };

        function nextBar(prev, step, vol) {
            const drift = (Math.random() - 0.5) * 2 * prev.close * vol;
            const open = prev.close;
            const close = Math.max(0.01, open + drift);
            return {
                time: prev.time + step,
                open,
                high: Math.max(open, close) + Math.random() * prev.close * vol * 0.5,
                low: Math.min(open, close) - Math.random() * prev.close * vol * 0.5,
                close,
                volume: 100 + Math.random() * 1000,
            };
        }
    },
};

export const none = {
    id: 'none',
    name: 'No Live Stream',
    kind: 'stream',
    description: 'Historical data only. No live updates.',
    configSchema: {},
    start() {
        return () => {};
    },
};
