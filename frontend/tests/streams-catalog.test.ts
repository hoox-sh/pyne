/**
 * Stream plugins + defaultStreamForSource.
 */

import './setup';
import { describe, expect, it, beforeEach, afterEach } from 'bun:test';
import { MockWebSocket } from './helpers/mock-ws';
import {
  mockPollStream,
  binanceStream,
  defaultStreamForSource,
  listStreams,
  getStream,
  registerDynamicStream,
  ensureStreamsRegistered,
  _resetStreamRegistrationFlag,
} from '../src/streams/catalog';
import { registry } from '../src/plugins/registry';
import { _resetBootstrapFlag } from '../src/plugins/bootstrap';

let restoreWs: (() => void) | null = null;

beforeEach(() => {
  registry.clear();
  _resetStreamRegistrationFlag();
  _resetBootstrapFlag();
  ensureStreamsRegistered();
  restoreWs = MockWebSocket.install();
});

afterEach(() => {
  restoreWs?.();
  restoreWs = null;
});

describe('defaultStreamForSource', () => {
  it('maps sources to streams', () => {
    expect(defaultStreamForSource('mock-walk')).toBe('mock-poll');
    expect(defaultStreamForSource('csv-upload')).toBe('mock-poll');
    expect(defaultStreamForSource('okx-rest')).toBe('okx-ws');
    expect(defaultStreamForSource('bybit-rest')).toBe('bybit-ws');
    expect(defaultStreamForSource('coinbase-rest')).toBe('coinbase-ws');
    expect(defaultStreamForSource('binance-rest')).toBe('binance-ws');
  });
});

describe('streams catalog', () => {
  it('lists built-ins including binance and mock', () => {
    const ids = listStreams().map((s) => s.id);
    expect(ids).toContain('binance-ws');
    expect(ids).toContain('mock-poll');
    expect(getStream('binance-ws')).toBeDefined();
  });

  it('mock-poll emits bars', async () => {
    const bars: unknown[] = [];
    const stop = mockPollStream.start({
      symbol: 'BTCUSDT',
      interval: '1m',
      lastBar: { time: Math.floor(Date.now() / 1000) - 60, open: 100, high: 101, low: 99, close: 100 },
      onBar: (b) => bars.push(b),
      onError: () => {},
      onStatus: () => {},
      config: { tickMs: 20 },
    });
    await new Promise((r) => setTimeout(r, 80));
    stop();
    expect(bars.length).toBeGreaterThanOrEqual(1);
  });

  it('binance-ws opens and parses kline message', async () => {
    const bars: unknown[] = [];
    let opened = false;
    const stop = binanceStream.start({
      symbol: 'BTCUSDT',
      interval: '1m',
      onBar: (b) => bars.push(b),
      onError: () => {},
      onStatus: (s) => {
        if (s.state === 'open') opened = true;
      },
    });
    await new Promise((r) => setTimeout(r, 20));
    expect(MockWebSocket.instances.length).toBeGreaterThanOrEqual(1);
    const ws = MockWebSocket.instances[MockWebSocket.instances.length - 1];
    ws.push({
      k: {
        t: 1_700_000_000_000,
        o: '1',
        h: '2',
        l: '0.5',
        c: '1.5',
        v: '10',
      },
    });
    expect(opened).toBe(true);
    expect(bars.length).toBe(1);
    stop();
  });

  it('registerDynamicStream', () => {
    registerDynamicStream({
      id: 'dyn-stream',
      name: 'D',
      kind: 'stream',
      start: () => () => {},
    });
    expect(getStream('dyn-stream')).toBeDefined();
  });
});
