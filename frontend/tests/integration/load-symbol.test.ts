/**
 * loadSymbolData integration with mock-walk.
 */

import '../setup';
import { describe, expect, it, beforeEach } from 'bun:test';
import { registry } from '../../src/plugins/registry';
import { ensureBuiltins, _resetBootstrapFlag } from '../../src/plugins/bootstrap';
import { _resetSourceRegistrationFlag } from '../../src/sources/catalog';
import { _resetStreamRegistrationFlag } from '../../src/streams/catalog';
import { _resetEngineRegistrationFlag } from '../../src/engines/catalog';
import { _resetStorageRegistrationFlag } from '../../src/storage/catalog';
import { setStore, store, clearLogs } from '../../src/store';
import { loadSymbolData } from '../../src/data/load-symbol';

beforeEach(() => {
  registry.clear();
  _resetSourceRegistrationFlag();
  _resetStreamRegistrationFlag();
  _resetEngineRegistrationFlag();
  _resetStorageRegistrationFlag();
  _resetBootstrapFlag();
  ensureBuiltins();
  clearLogs();
  setStore('bars', []);
  setStore('source', 'mock-walk');
});

describe('loadSymbolData', () => {
  it('loads mock-walk into store', async () => {
    const ok = await loadSymbolData('ETHUSDT', '1h', 'mock-walk');
    expect(ok).toBe(true);
    expect(store.bars.length).toBeGreaterThan(0);
    expect(store.symbol).toBe('ETHUSDT');
    expect(store.interval).toBe('1h');
    expect(store.exchange).toBe('mock');
    expect(store.status).toBe('ready');
  });

  it('returns false for unknown source', async () => {
    const ok = await loadSymbolData('BTCUSDT', '1d', 'nope-source');
    expect(ok).toBe(false);
    expect(store.status).toBe('error');
  });
});
