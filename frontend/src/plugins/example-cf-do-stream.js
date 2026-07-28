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

// Live datastream that proxies through a Cloudflare Worker Durable Object.
// The Worker hosts a `SessionDO` that opens one upstream Binance kline WS
// per (symbol, interval) and fans it out to N clients.
//
// This means: only ONE outbound connection to Binance per session, no
// matter how many browser tabs are watching the same symbol.  Useful for
// scaling past the ~5-connection per-domain browser limit on WS.
//
// Requires the endpoint to be set to a CF Worker URL that has the DO
// binding enabled (see frontend/worker/wrangler.toml).

const cfStream = {
    id: 'cf-do',
    name: 'Cloudflare DO Relay',
    kind: 'stream',
    description: 'WebSocket relay through a Cloudflare Durable Object. One upstream per session, multiple clients. Requires a Worker endpoint.',
    configSchema: {
        endpoint: { type: 'string', default: '', label: 'Worker wss:// or https:// URL (empty = disabled)' },
    },
    start({ symbol, interval, onBar, onError, onStatus, config, lastBar }) {
        const cfg = { ...this.configSchema, ...(config || {}) };
        if (!cfg.endpoint) {
            onError?.(new Error('Cloudflare DO stream requires an endpoint URL (set in Settings).'));
            return () => {};
        }
        const base = cfg.endpoint.replace(/^http/, 'ws').replace(/\/$/, '');
        const url = `${base}/api/stream?session=${encodeURIComponent(symbol + '@' + interval)}&symbol=${symbol}&interval=${interval}`;
        let ws;
        try { ws = new WebSocket(url); }
        catch (e) { onError?.(e); return () => {}; }
        ws.addEventListener('open', () => onStatus?.({ state: 'open', url }));
        ws.addEventListener('close', () => onStatus?.({ state: 'closed' }));
        ws.addEventListener('error', () => onError?.(new Error('WebSocket error')));
        ws.addEventListener('message', (ev) => {
            try {
                const msg = JSON.parse(ev.data);
                if (msg.type === 'status' || msg.type === 'error') return;
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
            } catch (_) { /* ignore parse */ }
        });
        // Send initial heartbeat so the DO can broadcast status.
        setTimeout(() => {
            if (ws.readyState === 1) ws.send(JSON.stringify({ action: 'ping' }));
        }, 100);
        return () => { try { ws.close(); } catch (_) { /* ignore */ } };
    },
};

export default cfStream;
