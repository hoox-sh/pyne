/**
 * Live re-run path: multiplex marks needsRerun and schedules silent runner.
 */
import './../setup';
import { describe, expect, it, beforeEach, afterEach, mock } from 'bun:test';
import { registry } from '../../src/plugins/registry';
import { _resetBootstrapFlag, ensureBuiltins } from '../../src/plugins/bootstrap';
import { _resetSourceRegistrationFlag } from '../../src/sources/catalog';
import { _resetStreamRegistrationFlag } from '../../src/streams/catalog';
import { _resetEngineRegistrationFlag } from '../../src/engines/catalog';
import { _resetStorageRegistrationFlag } from '../../src/storage/catalog';
import {
  store,
  setStore,
  loadBars,
  setLive,
  setActivePlugin,
} from '../../src/store';
import { startLive, stopLive, defaultStreamForSource } from '../../src/streams/multiplex';
import { SAMPLE_BARS } from '../fixtures/bars';

beforeEach(() => {
  registry.clear();
  _resetSourceRegistrationFlag();
  _resetStreamRegistrationFlag();
  _resetEngineRegistrationFlag();
  _resetStorageRegistrationFlag();
  _resetBootstrapFlag();
  ensureBuiltins();
  loadBars(SAMPLE_BARS.slice(0, 5), 'BTCUSDT', '1m', 'mock');
  setActivePlugin('source', 'mock-walk');
  setActivePlugin('stream', 'mock-poll');
  setActivePlugin('engine', 'server');
  setStore('endpoint', 'http://run.test');
  setStore('scripts', [
    {
      id: 'ind1',
      name: 'SMA',
      code: '//@version=5\nindicator("x")\nplot(close)',
      paneId: 'price',
      visible: true,
      plots: {},
    },
  ]);
});

afterEach(() => {
  stopLive();
  setLive(false);
});

describe('live re-run integration', () => {
  it('startLive with mock-poll sets live.active and can stop cleanly', async () => {
    // Avoid real network on silent re-run
    const originalFetch = globalThis.fetch;
    globalThis.fetch = mock(async () =>
      new Response(
        JSON.stringify({
          status: 'success',
          plots: [1, 2, 3],
          series: {},
          events: [],
          meta: { script_name: 'x', overlay: true, ms: 1 },
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    ) as typeof fetch;

    try {
      await startLive('mock-poll');
      expect(store.live.active).toBe(true);
      expect(store.live.streamId).toBe('mock-poll');
      // Allow one poll tick
      await new Promise((r) => setTimeout(r, 50));
      stopLive();
      expect(store.live.active).toBe(false);
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it('default mock source prefers mock-poll stream plugin', () => {
    expect(defaultStreamForSource('mock-walk')).toMatch(/mock/);
    expect(defaultStreamForSource('binance-rest')).toMatch(/binance|none|ws/i);
  });
});
