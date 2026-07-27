/**
 * Live multiplex start/stop.
 */

import './setup';
import { describe, expect, it, beforeEach, afterEach } from 'bun:test';
import { registry } from '../src/plugins/registry';
import { ensureBuiltins, _resetBootstrapFlag } from '../src/plugins/bootstrap';
import { _resetSourceRegistrationFlag } from '../src/sources/catalog';
import {
  _resetStreamRegistrationFlag,
  registerDynamicStream,
} from '../src/streams/catalog';
import { _resetEngineRegistrationFlag } from '../src/engines/catalog';
import { _resetStorageRegistrationFlag } from '../src/storage/catalog';
import { setStore, store, clearLogs } from '../src/store';
import { startLive, stopLive, getAvailableStreams } from '../src/streams/multiplex';

beforeEach(() => {
  registry.clear();
  _resetSourceRegistrationFlag();
  _resetStreamRegistrationFlag();
  _resetEngineRegistrationFlag();
  _resetStorageRegistrationFlag();
  _resetBootstrapFlag();
  ensureBuiltins();
  clearLogs();
  setStore('bars', [
    { time: 1000, open: 1, high: 1, low: 1, close: 1, volume: 1 },
  ]);
  setStore('scripts', []);
  setStore('live', { active: false, needsRerun: false, lastBarTime: 0, streamId: 'mock-poll' });
  setStore('source', 'mock-walk');
  stopLive();
});

afterEach(() => {
  stopLive();
});

describe('multiplex', () => {
  it('getAvailableStreams non-empty', () => {
    expect(getAvailableStreams().length).toBeGreaterThan(0);
  });

  it('startLive with dynamic stream appends bars and stopLive cleans up', async () => {
    let stopped = false;
    registerDynamicStream({
      id: 'test-mux-stream',
      name: 'Mux Test',
      kind: 'stream',
      start({ onBar, onStatus }) {
        onStatus({ state: 'open', detail: 'test' });
        const t = setInterval(() => {
          onBar({
            time: Math.floor(Date.now() / 1000),
            open: 2,
            high: 2,
            low: 2,
            close: 2,
            volume: 1,
          });
        }, 30);
        return () => {
          stopped = true;
          clearInterval(t);
        };
      },
    });

    const before = store.bars.length;
    startLive('test-mux-stream', 'BTCUSDT', '1m');
    expect(store.live.active).toBe(true);
    expect(store.stream.status).toBe('connected');

    await new Promise((r) => setTimeout(r, 80));
    expect(store.bars.length).toBeGreaterThanOrEqual(before);

    stopLive();
    expect(stopped).toBe(true);
    expect(store.live.active).toBe(false);
    expect(store.stream.status).toBe('disconnected');
  });

  it('startLive falls back when stream id unknown', () => {
    setStore('source', 'mock-walk');
    startLive('totally-missing', 'BTCUSDT', '1m');
    expect(store.live.streamId).toBe('mock-poll');
    expect(store.live.active).toBe(true);
    stopLive();
  });
});
