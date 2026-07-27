/**
 * Live re-run debounce when indicators are visible.
 */

import './setup';
import { describe, expect, it, beforeEach, afterEach } from 'bun:test';
import { mockFetch, jsonResponse } from './helpers/mock-fetch';
import { registry } from '../src/plugins/registry';
import { ensureBuiltins, _resetBootstrapFlag } from '../src/plugins/bootstrap';
import { _resetSourceRegistrationFlag } from '../src/sources/catalog';
import { _resetStreamRegistrationFlag, registerDynamicStream } from '../src/streams/catalog';
import { _resetEngineRegistrationFlag } from '../src/engines/catalog';
import { _resetStorageRegistrationFlag } from '../src/storage/catalog';
import { setStore, setActivePlugin, clearLogs, store } from '../src/store';
import { startLive, stopLive } from '../src/streams/multiplex';
import { SAMPLE_BARS } from './fixtures/bars';

let restoreFetch: (() => void) | null = null;
let runCount = 0;

beforeEach(() => {
  registry.clear();
  _resetSourceRegistrationFlag();
  _resetStreamRegistrationFlag();
  _resetEngineRegistrationFlag();
  _resetStorageRegistrationFlag();
  _resetBootstrapFlag();
  ensureBuiltins();
  clearLogs();
  runCount = 0;
  setStore('bars', SAMPLE_BARS);
  setStore('endpoint', 'http://run.test:5002');
  setActivePlugin('engine', 'server');
  setStore('scripts', [
    {
      id: 'ind1',
      name: 't',
      code: 'plot(close)',
      paneId: 'price',
      visible: true,
      plots: {},
    },
  ]);
  setStore('live', { active: false, needsRerun: false, lastBarTime: 0, streamId: 'x' });
  restoreFetch = mockFetch(async () => {
    runCount += 1;
    return jsonResponse({
      status: 'success',
      plots: SAMPLE_BARS.map(() => 1),
      series: {},
      events: [],
      meta: {},
    });
  });
  stopLive();
});

afterEach(() => {
  stopLive();
  restoreFetch?.();
});

describe('multiplex scheduleRerun', () => {
  it('re-runs visible indicators after live bars (debounced)', async () => {
    registerDynamicStream({
      id: 'rerun-stream',
      name: 'R',
      kind: 'stream',
      start({ onBar, onStatus }) {
        onStatus({ state: 'open' });
        onBar({
          time: Math.floor(Date.now() / 1000),
          open: 1,
          high: 1,
          low: 1,
          close: 1,
          volume: 1,
        });
        const t = setInterval(() => {
          onBar({
            time: Math.floor(Date.now() / 1000),
            open: 1,
            high: 1,
            low: 1,
            close: 1,
            volume: 1,
          });
        }, 50);
        return () => clearInterval(t);
      },
    });

    startLive('rerun-stream', 'BTCUSDT', '1m');
    expect(store.live.active).toBe(true);
    await new Promise((r) => setTimeout(r, 600));
    expect(runCount).toBeGreaterThanOrEqual(1);
    stopLive();
  });
});
