// Binance REST source — klines via api.binance.com.
// Falls back silently to a synthetic walk when the network is unavailable.

function intervalToMs(iv) {
    const m = /^(\d+)([mhdw])$/.exec(iv || '');
    if (!m) return 86400 * 1000;
    const n = parseInt(m[1], 10);
    const mult = { m: 60_000, h: 3_600_000, d: 86_400_000, w: 604_800_000 }[m[2]] || 86_400_000;
    return n * mult;
}

function resolveConfig(schema, config) {
    // Merge schema defaults with user-supplied values.  Anything in
    // `config` wins; missing fields fall back to the schema's `default`.
    const out = {};
    for (const [k, def] of Object.entries(schema || {})) {
        out[k] = def && Object.prototype.hasOwnProperty.call(def, 'default') ? def.default : undefined;
    }
    for (const [k, v] of Object.entries(config || {})) {
        if (v !== undefined) out[k] = v;
    }
    return out;
}

function synthesizeWalk(n, interval, start) {
    const step = Math.floor(intervalToMs(interval) / 1000);
    const out = [];
    let price = start;
    const now = Math.floor(Date.now() / 1000);
    for (let i = n - 1; i >= 0; i--) {
        const t = now - i * step;
        const drift = (Math.random() - 0.48) * price * 0.02;
        const open = price;
        const close = Math.max(0.01, price + drift);
        const high = Math.max(open, close) + Math.random() * price * 0.005;
        const low = Math.min(open, close) - Math.random() * price * 0.005;
        out.push({ time: t, open, high, low, close, volume: 100 + Math.random() * 1000 });
        price = close;
    }
    return out;
}

export const binanceRest = {
    id: 'binance-rest',
    name: 'Binance REST',
    kind: 'source',
    description: 'Public Binance kline API (api.binance.com). Falls back to a synthetic walk if the network is unavailable.',
    configSchema: {
        baseUrl: { type: 'string', default: 'https://api.binance.com', label: 'API base URL' },
        limit: { type: 'number', default: 500, min: 50, max: 1000, label: 'Bars' },
        fallback: { type: 'boolean', default: true, label: 'Synthesize on failure' },
    },
    async fetchHistorical({ symbol, interval, config }) {
        const cfg = resolveConfig(this.configSchema, config);
        const url = `${cfg.baseUrl}/api/v3/klines?symbol=${encodeURIComponent(symbol)}&interval=${encodeURIComponent(interval)}&limit=${cfg.limit}`;
        try {
            const res = await fetch(url, {
                cache: 'no-store',
                signal: AbortSignal.timeout(15_000),
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            if (!Array.isArray(data) || !data.length) throw new Error('empty kline response');
            return data.map((d) => ({
                time: d[0] / 1000,
                open: parseFloat(d[1]),
                high: parseFloat(d[2]),
                low: parseFloat(d[3]),
                close: parseFloat(d[4]),
                volume: parseFloat(d[5]),
            }));
        } catch (err) {
            if (!cfg.fallback) throw err;
            console.warn(`[binance-rest] Network error, falling back to synthetic data: ${err.message}`);
            return synthesizeWalk(cfg.limit || 200, interval, 100);
        }
    },
};

// A synthetic-only source useful for offline work and tests.
export const mockWalk = {
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
        if (cfg.seed) {
            // Mulberry32 — small deterministic PRNG
            let s = cfg.seed >>> 0;
            const rand = () => {
                s = (s + 0x6D2B79F5) >>> 0;
                let t = s;
                t = Math.imul(t ^ (t >>> 15), t | 1);
                t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
                return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
            };
            const out = [];
            const step = Math.floor(intervalToMs(interval) / 1000);
            const now = Math.floor(Date.now() / 1000);
            let price = cfg.startPrice;
            for (let i = cfg.limit - 1; i >= 0; i--) {
                const t = now - i * step;
                const drift = (rand() - 0.48) * price * 0.02;
                const open = price;
                const close = Math.max(0.01, price + drift);
                const high = Math.max(open, close) + rand() * price * 0.005;
                const low = Math.min(open, close) - rand() * price * 0.005;
                out.push({ time: t, open, high, low, close, volume: 100 + rand() * 1000 });
                price = close;
            }
            return out;
        }
        return synthesizeWalk(cfg.limit, interval, cfg.startPrice);
    },
};

// A source that holds the last user-uploaded file. The actual file is stored
// in `state._uploadedBars` (set by the UI when the user picks a file).
import { getState } from '../state.js';
export const csvUpload = {
    id: 'csv-upload',
    name: 'CSV / JSON Upload',
    kind: 'source',
    description: 'Uses the last file the user uploaded (CSV with time,open,high,low,close[,volume] or JSON array).',
    configSchema: {},
    async fetchHistorical() {
        const state = getState();
        const bars = state?.get?.('uploadedBars');
        if (!Array.isArray(bars) || !bars.length) {
            throw new Error('No uploaded file. Use the Upload button to pick a CSV/JSON file first.');
        }
        return bars;
    },
};
