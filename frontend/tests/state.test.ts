// State tests — verify the central persisted state class (legacy path).

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
        const { initState } = await import('../src/state.js');
        const s = initState();
        expect(s.get('symbol')).toBe('BTCUSDT');
        expect(s.get('engine')).toBe('server');
        expect(s.get('mode')).toBe('local');
    });

    it('hydrates from AXIS storage key', async () => {
        localStorage.setItem('pynescript.axis.v1', JSON.stringify({ symbol: 'ETHUSDT', engine: 'pyodide' }));
        const { initState } = await import('../src/state.js?v=axis');
        const s = initState();
        expect(s.get('symbol')).toBe('ETHUSDT');
        expect(s.get('engine')).toBe('pyodide');
    });

    it('migrates SuperChart legacy key into AXIS key', async () => {
        localStorage.setItem('pynescript.superchart.v1', JSON.stringify({ symbol: 'ETHUSDT', engine: 'pyodide' }));
        const { initState } = await import('../src/state.js?v=migrate');
        const s = initState();
        expect(s.get('symbol')).toBe('ETHUSDT');
        expect(s.get('engine')).toBe('pyodide');
        expect(localStorage.getItem('pynescript.axis.v1')).toBeTruthy();
    });

    it('assign() updates state, fires change event, and persists', async () => {
        const { initState } = await import('../src/state.js?v=assign');
        const s = initState();
        let fired = 0;
        let lastDetail: any = null;
        s.addEventListener('change', (e: any) => { fired++; lastDetail = e.detail; });
        s.assign({ symbol: 'SOLUSDT' });
        expect(fired).toBe(1);
        expect(lastDetail).toEqual({ symbol: 'SOLUSDT' });
        expect(s.get('symbol')).toBe('SOLUSDT');
        const stored = JSON.parse(localStorage.getItem('pynescript.axis.v1')!);
        expect(stored.symbol).toBe('SOLUSDT');
    });

    it('resetState wipes AXIS + legacy keys and produces a fresh instance', async () => {
        localStorage.setItem('pynescript.axis.v1', JSON.stringify({ symbol: 'DOGEUSDT' }));
        localStorage.setItem('pynescript.superchart.v1', JSON.stringify({ symbol: 'OLD' }));
        const { initState, resetState, getState } = await import('../src/state.js?v=reset');
        initState();
        resetState();
        expect(localStorage.getItem('pynescript.axis.v1')).toBeNull();
        expect(localStorage.getItem('pynescript.superchart.v1')).toBeNull();
        expect(getState().get('symbol')).toBe('BTCUSDT');
    });

    it('snapshot() returns a shallow copy of the data', async () => {
        const { initState } = await import('../src/state.js?v=snap');
        const s = initState();
        const snap = s.snapshot();
        expect(snap).toEqual({
            symbol: 'BTCUSDT',
            engine: 'server',
            source: 'binance-rest',
            stream: 'binance-ws',
            interval: '1d',
            mode: 'local',
            apiKey: '',
            script: '',
            plugins: [],
            pluginsConfig: {},
            timeRange: 'ALL',
            endpoint: 'http://localhost:5002',
        });
        snap.symbol = 'MUTATED';
        expect(s.get('symbol')).toBe('BTCUSDT');  // top-level is frozen
    });
});
