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

// Example plugin: a custom historical source backed by the public
// CoinGecko API.  Demonstrates the `Source` plugin contract.
//
// To load this in the running PWA:
//   1. Open Manager → Plugins tab.
//   2. Paste the URL of this file (or use the Plugins README for self-
//      hosting instructions).
//   3. The new source appears in the Source dropdown.

const COINGECKO_IDS = {
    BTC: 'bitcoin', ETH: 'ethereum', SOL: 'solana', XRP: 'ripple',
    ADA: 'cardano', DOGE: 'dogecoin', AVAX: 'avalanche-2', DOT: 'polkadot',
    LINK: 'chainlink', MATIC: 'matic-network', LTC: 'litecoin', BCH: 'bitcoin-cash',
};

const VS_CURRENCY = 'usd';

function intervalToDays(interval) {
    const m = /^(\d+)([mhdw])$/.exec(interval || '');
    if (!m) return 1;
    const n = parseInt(m[1], 10);
    const mult = { m: 1 / 1440, h: 1 / 24, d: 1, w: 7 }[m[2]] || 1;
    return n * mult;
}

const coingeckoSource = {
    id: 'coingecko',
    name: 'CoinGecko',
    kind: 'source',
    description: 'Public CoinGecko API (no key required). Limited to common coins; ~10-30 calls/minute.',
    configSchema: {
        baseUrl: { type: 'string', default: 'https://api.coingecko.com/api/v3', label: 'API base URL' },
        vsCurrency: { type: 'string', default: 'usd', label: 'Quote currency' },
    },
    async fetchHistorical({ symbol, interval, config }) {
        const cfg = { ...this.configSchema, ...(config || {}) };
        const coin = COINGECKO_IDS[symbol.toUpperCase()] || symbol.toLowerCase();
        const days = Math.max(1, Math.min(365, Math.ceil(intervalToDays(interval) * 200)));
        const url = `${cfg.baseUrl}/coins/${coin}/market_chart?vs_currency=${cfg.vsCurrency}&days=${days}&interval=${interval === '1d' ? 'daily' : 'hourly'}`;
        const res = await fetch(url, { cache: 'no-store' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        const prices = json.prices || [];
        const volumes = json.total_volumes || [];
        if (!prices.length) throw new Error('empty response from CoinGecko');
        // CoinGecko returns [timestamp_ms, price] pairs.  Synthesize OHLC from
        // consecutive prices (the public endpoint doesn't give candles).
        const out = [];
        for (let i = 0; i < prices.length; i++) {
            const [t, c] = prices[i];
            const next = prices[i + 1]?.[1] ?? c;
            const prev = prices[i - 1]?.[1] ?? c;
            const open = prev, close = c;
            out.push({
                time: Math.floor(t / 1000),
                open, high: Math.max(open, close, next) * 1.001,
                low: Math.min(open, close, next) * 0.999,
                close,
                volume: volumes[i]?.[1] || 0,
            });
        }
        return out;
    },
};

export default coingeckoSource;
