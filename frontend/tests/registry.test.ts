// Bun tests for the plugin registry.
// Run with: `bun test frontend/tests/registry.test.ts`

import { describe, expect, it, beforeEach } from 'bun:test';
import { registry, Registry } from '../src/registry.js';
import { binanceRest, mockWalk, csvUpload } from '../src/sources/index.js';
import { binanceWs, mockPoll, none } from '../src/streams/index.js';
import { serverEngine, pyodideEngine } from '../src/engines/index.js';

beforeEach(() => {
    registry.clear();
});

describe('Registry', () => {
    it('rejects a Source without fetchHistorical', () => {
        expect(() => registry.registerSource({ id: 'bad', name: 'Bad', kind: 'source' }))
            .toThrow(/fetchHistorical/);
    });

    it('rejects a Source with the wrong kind', () => {
        expect(() => registry.registerSource({ id: 'x', name: 'X', kind: 'stream', start: () => () => {} }))
            .toThrow(/kind must be 'source'/);
    });

    it('rejects a Stream without start', () => {
        expect(() => registry.registerStream({ id: 's', name: 'S', kind: 'stream' }))
            .toThrow(/start/);
    });

    it('rejects an Engine without run', () => {
        expect(() => registry.registerEngine({ id: 'e', name: 'E', kind: 'engine' }))
            .toThrow(/run/);
    });

    it('lists registered plugins in registration order', () => {
        registry
            .registerSource(mockWalk)
            .registerSource(binanceRest)
            .registerStream(binanceWs)
            .registerEngine(serverEngine);
        expect(registry.listSources().map((s) => s.id)).toEqual(['mock-walk', 'binance-rest']);
        expect(registry.listStreams().map((s) => s.id)).toEqual(['binance-ws']);
        expect(registry.listEngines().map((e) => e.id)).toEqual(['server']);
    });

    it('getSource/getStream/getEngine round-trip', () => {
        registry.registerSource(mockWalk).registerStream(none).registerEngine(pyodideEngine);
        expect(registry.getSource('mock-walk')?.name).toBe('Mock Walk');
        expect(registry.getStream('none')?.id).toBe('none');
        expect(registry.getEngine('pyodide')?.id).toBe('pyodide');
        expect(registry.getSource('missing')).toBeUndefined();
    });

    it('summary() returns a serializable shape', () => {
        registry.registerSource(mockWalk).registerEngine(serverEngine);
        const s = registry.summary();
        expect(s.sources).toHaveLength(1);
        expect(s.engines).toHaveLength(1);
        expect(s.streams).toHaveLength(0);
        expect(s.sources[0]).toEqual({ id: 'mock-walk', name: 'Mock Walk', description: expect.any(String) });
    });

    it('new Registry() instances are independent', () => {
        const r1 = new Registry();
        const r2 = new Registry();
        r1.registerSource(mockWalk);
        expect(r1.listSources()).toHaveLength(1);
        expect(r2.listSources()).toHaveLength(0);
    });
});

describe('Built-in plugins', () => {
    it('mock-walk returns N bars and is deterministic with a seed', async () => {
        const bars = await mockWalk.fetchHistorical({ symbol: 'TEST', interval: '1d', config: { limit: 50, seed: 42 } });
        expect(bars.length).toBe(50);
        expect(bars[0]).toMatchObject({ open: expect.any(Number), high: expect.any(Number), low: expect.any(Number), close: expect.any(Number) });
        // First generated bar is the oldest — its open equals the start price.
        expect(bars[0].open).toEqual(100);
        // Deterministic seed → same close at every index.
        const bars2 = await mockWalk.fetchHistorical({ symbol: 'TEST', interval: '1d', config: { limit: 50, seed: 42 } });
        for (let i = 0; i < bars.length; i++) {
            expect(bars[i].close).toEqual(bars2[i].close);
        }
    });

    it('csv-upload fails when no bars are stashed', async () => {
        await expect(csvUpload.fetchHistorical({ symbol: 'X', interval: '1d', config: {} })).rejects.toThrow(/No uploaded file/);
    });

    it('csv-upload returns stashed bars', async () => {
        const bars = [{ time: 1, open: 1, high: 1, low: 1, close: 1 }];
        const out = await csvUpload.fetchHistorical({ symbol: 'X', interval: '1d', config: { bars } });
        expect(out).toBe(bars);
    });

    it('none stream returns a no-op stop', () => {
        const stop = none.start({ symbol: 'X', interval: '1d' });
        expect(typeof stop).toBe('function');
        stop();
    });

    it('mock-poll stream emits at least one bar within a few ticks', async () => {
        const bars: any[] = [];
        let resolveDone: () => void;
        const done = new Promise<void>((r) => { resolveDone = r; });
        const stop = mockPoll.start({
            symbol: 'BTCUSDT',
            interval: '1m',
            lastBar: { time: Math.floor(Date.now() / 1000) - 60, open: 100, high: 101, low: 99, close: 100 },
            onBar: (b) => { bars.push(b); if (bars.length >= 2) resolveDone(); },
            config: { tickMs: 50, volatility: 0.01 },
        });
        try {
            await Promise.race([done, new Promise((r) => setTimeout(r, 500))]);
            expect(bars.length).toBeGreaterThanOrEqual(1);
            expect(bars[0]).toMatchObject({ open: expect.any(Number), close: expect.any(Number) });
        } finally {
            stop();
        }
    });

    it('server engine returns a structured error on network failure', async () => {
        const result = await serverEngine.run({ script: 'plot(close)', bars: [{ time: 1, open: 1, high: 1, low: 1, close: 1 }], config: { endpoint: 'http://127.0.0.1:1' } });
        expect(result.status).toBe('error');
        expect(result.error).toBeDefined();
    });
});
