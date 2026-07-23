// State tests — verify the central persisted state class.

import { describe, expect, it, beforeEach } from 'bun:test';

// We need a clean localStorage between tests.
class MemoryStorage {
    store = new Map<string, string>();
    getItem(k: string) { return this.store.get(k) ?? null; }
    setItem(k: string, v: string) { this.store.set(k, v); }
    removeItem(k: string) { this.store.delete(k); }
    clear() { this.store.clear(); }
}

beforeEach(() => {
    (globalThis as any).localStorage = new MemoryStorage();
});

describe('State', () => {
    it('returns defaults when localStorage is empty', async () => {
        const { initState, getState } = await import('../src/state.js');
        const s = initState();
        expect(s.get('symbol')).toBe('BTCUSDT');
        expect(s.get('engine')).toBe('server');
        expect(s.get('mode')).toBe('local');
    });

    it('hydrates from localStorage', async () => {
        localStorage.setItem('pynescript.superchart.v1', JSON.stringify({ symbol: 'ETHUSDT', engine: 'pyodide' }));
        // Re-import to get a fresh module instance.
        const { initState, getState } = await import('../src/state.js?v=2');
        const s = initState();
        expect(s.get('symbol')).toBe('ETHUSDT');
        expect(s.get('engine')).toBe('pyodide');
    });

    it('assign() updates state, fires change event, and persists', async () => {
        const { initState, getState } = await import('../src/state.js?v=3');
        const s = initState();
        let fired = 0;
        let lastDetail: any = null;
        s.addEventListener('change', (e: any) => { fired++; lastDetail = e.detail; });
        s.assign({ symbol: 'SOLUSDT' });
        expect(fired).toBe(1);
        expect(lastDetail).toEqual({ symbol: 'SOLUSDT' });
        expect(s.get('symbol')).toBe('SOLUSDT');
        const stored = JSON.parse(localStorage.getItem('pynescript.superchart.v1')!);
        expect(stored.symbol).toBe('SOLUSDT');
    });

    it('resetState wipes localStorage and produces a fresh instance', async () => {
        localStorage.setItem('pynescript.superchart.v1', JSON.stringify({ symbol: 'DOGEUSDT' }));
        const { initState, resetState, getState } = await import('../src/state.js?v=4');
        initState();
        resetState();
        expect(localStorage.getItem('pynescript.superchart.v1')).toBeNull();
        expect(getState().get('symbol')).toBe('BTCUSDT');
    });

    it('snapshot() returns a shallow copy of the data', async () => {
        const { initState, getState } = await import('../src/state.js?v=5');
        const s = initState();
        const snap = s.snapshot();
        expect(snap).toEqual({ symbol: 'BTCUSDT', engine: 'server', source: 'binance-rest', stream: 'binance-ws', interval: '1d', mode: 'local', apiKey: '', script: '', plugins: [], pluginsConfig: {}, timeRange: 'ALL', endpoint: 'http://localhost:5002' });
        snap.symbol = 'MUTATED';
        expect(s.get('symbol')).toBe('BTCUSDT');  // top-level is frozen
    });
});
