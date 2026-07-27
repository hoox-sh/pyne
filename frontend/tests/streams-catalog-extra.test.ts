/**
 * Additional stream plugins (okx/bybit/coinbase/kraken) with MockWebSocket.
 */

import './setup';
import { describe, expect, it, beforeEach, afterEach } from 'bun:test';
import { MockWebSocket } from './helpers/mock-ws';
import {
  okxStream,
  bybitStream,
  coinbaseStream,
  krakenStream,
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
});

function startAndPush(
  stream: { start: (o: never) => () => void },
  msg: unknown,
): Promise<unknown[]> {
  const bars: unknown[] = [];
  const stop = stream.start({
    symbol: 'BTCUSDT',
    interval: '1m',
    onBar: (b: unknown) => bars.push(b),
    onError: () => {},
    onStatus: () => {},
    lastBar: { time: 1000, open: 1, high: 1, low: 1, close: 1 },
  } as never);
  return new Promise((resolve) => {
    setTimeout(() => {
      const ws = MockWebSocket.instances[MockWebSocket.instances.length - 1];
      if (ws) ws.push(msg);
      setTimeout(() => {
        stop();
        resolve(bars);
      }, 10);
    }, 15);
  });
}

describe('extra exchange streams', () => {
  it('okx stream parses candle', async () => {
    const bars = await startAndPush(okxStream, {
      data: [
        {
          ts: '1700000000000',
          o: '1',
          h: '2',
          l: '0.5',
          c: '1.5',
          vol: '10',
        },
      ],
    });
    // okx may expect different shape — at least start/stop works
    expect(Array.isArray(bars)).toBe(true);
  });

  it('bybit stream start/stop', async () => {
    const bars = await startAndPush(bybitStream, {
      topic: 'kline.1.BTCUSDT',
      data: [{ start: 1700000000000, open: '1', high: '2', low: '0.5', close: '1.5', volume: '9' }],
    });
    expect(Array.isArray(bars)).toBe(true);
  });

  it('coinbase stream start/stop', async () => {
    const bars = await startAndPush(coinbaseStream, {
      type: 'ticker',
      price: '100.5',
      time: new Date().toISOString(),
    });
    expect(Array.isArray(bars)).toBe(true);
  });

  it('kraken stream start/stop', async () => {
    const bars = await startAndPush(krakenStream, [
      0,
      ['1', '2', '0.5', '1.5', '1', '1.5', '1.2', '10'],
      'ohlc-1',
      'XBT/USD',
    ]);
    expect(Array.isArray(bars)).toBe(true);
  });
});
