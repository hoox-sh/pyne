/**
 * Tests for the unified TypeScript plugin registry (PR1).
 * Run: `bun test frontend/tests/plugin-registry.test.ts`
 */

import { describe, expect, it, beforeEach } from 'bun:test';
import { PluginRegistry, registry } from '../src/plugins/registry';
import {
  ensureSourcesRegistered,
  _resetSourceRegistrationFlag,
  mockWalk,
  binanceRest,
  csvUpload,
  listSources,
  registerDynamicSource,
  unregisterDynamicSource,
} from '../src/sources/catalog';
import {
  ensureStreamsRegistered,
  _resetStreamRegistrationFlag,
  mockPollStream,
  listStreams,
  registerDynamicStream,
} from '../src/streams/catalog';
import {
  ensureEnginesRegistered,
  _resetEngineRegistrationFlag,
  serverEngine,
  listEngines,
  registerDynamicEngine,
} from '../src/engines/catalog';
import { setUploadedBars, clearUploadedBars } from '../src/sources/upload-store';
import { _resetBootstrapFlag, ensureBuiltins } from '../src/plugins/bootstrap';
import { _resetStorageRegistrationFlag, listStorages } from '../src/storage/catalog';

beforeEach(() => {
  registry.clear();
  _resetSourceRegistrationFlag();
  _resetStreamRegistrationFlag();
  _resetEngineRegistrationFlag();
  _resetStorageRegistrationFlag();
  _resetBootstrapFlag();
  clearUploadedBars();
});

describe('PluginRegistry', () => {
  it('rejects a Source without fetchHistorical', () => {
    expect(() =>
      registry.registerSource({ id: 'bad', name: 'Bad', kind: 'source' } as never),
    ).toThrow(/fetchHistorical/);
  });

  it('rejects a Source with the wrong kind', () => {
    expect(() =>
      registry.registerSource({
        id: 'x',
        name: 'X',
        kind: 'stream',
        start: () => () => {},
      } as never),
    ).toThrow(/kind must be 'source'/);
  });

  it('rejects a Stream without start', () => {
    expect(() =>
      registry.registerStream({ id: 's', name: 'S', kind: 'stream' } as never),
    ).toThrow(/start/);
  });

  it('rejects an Engine without run', () => {
    expect(() =>
      registry.registerEngine({ id: 'e', name: 'E', kind: 'engine' } as never),
    ).toThrow(/run/);
  });

  it('lists registered plugins in registration order', () => {
    registry
      .registerSource(mockWalk)
      .registerSource(binanceRest)
      .registerStream(mockPollStream)
      .registerEngine(serverEngine);
    expect(registry.listSources().map((s) => s.id)).toEqual(['mock-walk', 'binance-rest']);
    expect(registry.listStreams().map((s) => s.id)).toEqual(['mock-poll']);
    expect(registry.listEngines().map((e) => e.id)).toEqual(['server']);
  });

  it('getSource/getStream/getEngine round-trip', () => {
    registry.registerSource(mockWalk).registerStream(mockPollStream).registerEngine(serverEngine);
    expect(registry.getSource('mock-walk')?.name).toBe('Mock Walk');
    expect(registry.getStream('mock-poll')?.id).toBe('mock-poll');
    expect(registry.getEngine('server')?.id).toBe('server');
    expect(registry.getSource('missing')).toBeUndefined();
  });

  it('summary() includes all kinds', () => {
    registry.registerSource(mockWalk).registerEngine(serverEngine);
    const s = registry.summary();
    expect(s.sources).toHaveLength(1);
    expect(s.engines).toHaveLength(1);
    expect(s.streams).toHaveLength(0);
    expect(s.storages).toHaveLength(0);
    expect(s.sources[0]).toEqual({
      id: 'mock-walk',
      name: 'Mock Walk',
      description: expect.any(String),
      builtIn: true,
    });
  });

  it('new PluginRegistry() instances are independent', () => {
    const r1 = new PluginRegistry();
    const r2 = new PluginRegistry();
    r1.registerSource(mockWalk);
    expect(r1.listSources()).toHaveLength(1);
    expect(r2.listSources()).toHaveLength(0);
  });

  it('does not unregister built-in plugins by default', () => {
    registry.registerSource(mockWalk);
    expect(registry.unregisterSource('mock-walk')).toBe(false);
    expect(registry.getSource('mock-walk')).toBeDefined();
    expect(registry.unregisterSource('mock-walk', { allowBuiltIn: true })).toBe(true);
  });

  it('register() dispatches by kind', () => {
    registry.register(mockWalk);
    registry.register(serverEngine);
    expect(registry.listSources()).toHaveLength(1);
    expect(registry.listEngines()).toHaveLength(1);
  });

  it('emits registered events', () => {
    const events: string[] = [];
    const off = registry.on((e) => events.push(`${e.type}:${e.kind}:${e.id}`));
    registry.registerSource(mockWalk);
    expect(events).toContain('registered:source:mock-walk');
    off();
  });
});

describe('Catalog → registry bridge', () => {
  it('ensureSourcesRegistered populates registry', () => {
    ensureSourcesRegistered();
    const ids = listSources().map((s) => s.id);
    expect(ids).toContain('binance-rest');
    expect(ids).toContain('mock-walk');
    expect(ids).toContain('csv-upload');
  });

  it('ensureStreamsRegistered populates registry', () => {
    ensureStreamsRegistered();
    const ids = listStreams().map((s) => s.id);
    expect(ids).toContain('binance-ws');
    expect(ids).toContain('mock-poll');
  });

  it('ensureEnginesRegistered populates registry', () => {
    ensureEnginesRegistered();
    const ids = listEngines().map((e) => e.id);
    expect(ids).toEqual(expect.arrayContaining(['server', 'pyodide']));
  });

  it('ensureBuiltins includes local storage', () => {
    ensureBuiltins();
    expect(listStorages().map((s) => s.id)).toContain('local');
  });

  it('registerDynamicSource adds a non-built-in source', () => {
    ensureSourcesRegistered();
    const n = listSources().length;
    registerDynamicSource({
      id: 'test-src',
      name: 'Test',
      kind: 'source',
      description: 'dyn',
      configSchema: {},
      async fetchHistorical() {
        return [];
      },
    });
    expect(listSources()).toHaveLength(n + 1);
    unregisterDynamicSource('test-src');
    expect(listSources().find((s) => s.id === 'test-src')).toBeUndefined();
  });

  it('registerDynamicStream and engine work', () => {
    ensureStreamsRegistered();
    ensureEnginesRegistered();
    registerDynamicStream({
      id: 'test-stream',
      name: 'T',
      kind: 'stream',
      start: () => () => {},
    });
    registerDynamicEngine({
      id: 'test-engine',
      name: 'E',
      kind: 'engine',
      async isReady() {
        return true;
      },
      async run() {
        return { status: 'success', plots: [], events: [], series: {} };
      },
    });
    expect(listStreams().some((s) => s.id === 'test-stream')).toBe(true);
    expect(listEngines().some((e) => e.id === 'test-engine')).toBe(true);
  });
});

describe('Built-in source plugins (Solid catalog)', () => {
  it('mock-walk returns N bars and is deterministic with a seed', async () => {
    const bars = await mockWalk.fetchHistorical({
      symbol: 'TEST',
      interval: '1d',
      config: { limit: 50, seed: 42 },
    });
    expect(bars.length).toBe(50);
    expect(bars[0]).toMatchObject({
      open: expect.any(Number),
      high: expect.any(Number),
      low: expect.any(Number),
      close: expect.any(Number),
    });
    expect(bars[0].open).toEqual(100);
    const bars2 = await mockWalk.fetchHistorical({
      symbol: 'TEST',
      interval: '1d',
      config: { limit: 50, seed: 42 },
    });
    for (let i = 0; i < bars.length; i++) {
      expect(bars[i].close).toEqual(bars2[i].close);
    }
  });

  it('csv-upload fails when no bars are stashed', async () => {
    await expect(csvUpload.fetchHistorical({ symbol: 'X', interval: '1d' })).rejects.toThrow(
      /No uploaded file/,
    );
  });

  it('csv-upload returns stashed bars via upload-store', async () => {
    const bars = [{ time: 1, open: 1, high: 1, low: 1, close: 1 }];
    setUploadedBars(bars, 't.csv');
    const out = await csvUpload.fetchHistorical({ symbol: 'X', interval: '1d' });
    expect(out).toEqual(bars);
  });
});

describe('Built-in engine plugins', () => {
  it('server engine returns a structured error on network failure', async () => {
    const result = await serverEngine.run({
      script: 'plot(close)',
      bars: [{ time: 1, open: 1, high: 1, low: 1, close: 1 }],
      config: { endpoint: 'http://127.0.0.1:1' },
    });
    expect(result.status).toBe('error');
    expect(result.error).toBeDefined();
  });
});
