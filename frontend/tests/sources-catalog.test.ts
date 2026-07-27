/**
 * Built-in historical sources (mocked network).
 */

import './setup';
import { describe, expect, it, beforeEach, afterEach } from 'bun:test';
import { mockFetch, jsonResponse } from './helpers/mock-fetch';
import {
  binanceRest,
  mockWalk,
  csvUpload,
  okxRest,
  bybitRest,
  coinbaseRest,
  listSources,
  getSource,
  registerDynamicSource,
  unregisterDynamicSource,
  ensureSourcesRegistered,
  _resetSourceRegistrationFlag,
} from '../src/sources/catalog';
import { setUploadedBars, clearUploadedBars } from '../src/sources/upload-store';
import { registry } from '../src/plugins/registry';
import { _resetBootstrapFlag } from '../src/plugins/bootstrap';

let restoreFetch: (() => void) | null = null;

beforeEach(() => {
  registry.clear();
  _resetSourceRegistrationFlag();
  _resetBootstrapFlag();
  clearUploadedBars();
  ensureSourcesRegistered();
});

afterEach(() => {
  restoreFetch?.();
  restoreFetch = null;
});

describe('sources catalog', () => {
  it('lists built-ins', () => {
    const ids = listSources().map((s) => s.id);
    expect(ids).toContain('binance-rest');
    expect(ids).toContain('mock-walk');
    expect(getSource('mock-walk')?.name).toBe('Mock Walk');
  });

  it('mock-walk returns configured length', async () => {
    const bars = await mockWalk.fetchHistorical({
      symbol: 'X',
      interval: '1h',
      config: { limit: 20, seed: 7 },
    });
    expect(bars).toHaveLength(20);
  });

  it('csv-upload uses upload store', async () => {
    setUploadedBars([{ time: 1, open: 1, high: 2, low: 0.5, close: 1.5 }], 't.csv');
    const bars = await csvUpload.fetchHistorical({ symbol: 'X', interval: '1d' });
    expect(bars[0].close).toBe(1.5);
  });

  it('binance-rest maps klines', async () => {
    restoreFetch = mockFetch(async () =>
      jsonResponse([
        [1_700_000_000_000, '10', '12', '9', '11', '100'],
        [1_700_086_400_000, '11', '13', '10', '12', '200'],
      ]),
    );
    const bars = await binanceRest.fetchHistorical({
      symbol: 'BTCUSDT',
      interval: '1d',
      config: { fallback: false, limit: 2 },
    });
    expect(bars).toHaveLength(2);
    expect(bars[0].time).toBe(1_700_000_000);
    expect(bars[0].close).toBe(11);
  });

  it('binance-rest falls back when fallback true', async () => {
    restoreFetch = mockFetch(async () => {
      throw new Error('network down');
    });
    const bars = await binanceRest.fetchHistorical({
      symbol: 'BTCUSDT',
      interval: '1d',
      config: { fallback: true, limit: 5 },
    });
    expect(bars.length).toBeGreaterThan(0);
  });

  it('okx-rest maps candles', async () => {
    restoreFetch = mockFetch(async () =>
      jsonResponse({
        code: '0',
        data: [
          ['1700086400000', '2', '3', '1', '2.5', '50'],
          ['1700000000000', '1', '2', '0.5', '1.5', '40'],
        ],
      }),
    );
    const bars = await okxRest.fetchHistorical({
      symbol: 'BTCUSDT',
      interval: '1d',
      config: { limit: 2 },
    });
    expect(bars.length).toBe(2);
    // reversed to oldest first
    expect(bars[0].time).toBeLessThan(bars[1].time);
  });

  it('bybit-rest maps kline list', async () => {
    restoreFetch = mockFetch(async () =>
      jsonResponse({
        retCode: 0,
        result: {
          list: [
            ['1700086400000', '2', '3', '1', '2.5', '50'],
            ['1700000000000', '1', '2', '0.5', '1.5', '40'],
          ],
        },
      }),
    );
    const bars = await bybitRest.fetchHistorical({
      symbol: 'BTCUSDT',
      interval: '1d',
      config: {},
    });
    expect(bars.length).toBe(2);
  });

  it('coinbase-rest maps candles', async () => {
    restoreFetch = mockFetch(async () =>
      jsonResponse([
        [1_700_086_400, 1, 3, 2, 2.5, 10],
        [1_700_000_000, 0.5, 2, 1, 1.5, 8],
      ]),
    );
    const bars = await coinbaseRest.fetchHistorical({
      symbol: 'BTCUSD',
      interval: '1d',
      config: {},
    });
    expect(bars.length).toBe(2);
    expect(bars[0].time).toBeLessThanOrEqual(bars[1].time);
  });

  it('dynamic register/unregister', () => {
    registerDynamicSource({
      id: 'dyn-src',
      name: 'Dyn',
      kind: 'source',
      description: '',
      configSchema: {},
      async fetchHistorical() {
        return [];
      },
    });
    expect(getSource('dyn-src')).toBeDefined();
    unregisterDynamicSource('dyn-src');
    expect(listSources().find((s) => s.id === 'dyn-src')).toBeUndefined();
  });
});
