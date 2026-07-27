/**
 * Active plugin resolution.
 */

import './setup';
import { describe, expect, it, beforeEach } from 'bun:test';
import { registry } from '../src/plugins/registry';
import { ensureBuiltins, _resetBootstrapFlag } from '../src/plugins/bootstrap';
import { _resetSourceRegistrationFlag } from '../src/sources/catalog';
import { _resetStreamRegistrationFlag } from '../src/streams/catalog';
import { _resetEngineRegistrationFlag } from '../src/engines/catalog';
import { _resetStorageRegistrationFlag } from '../src/storage/catalog';
import { setStore, setActivePlugin } from '../src/store';
import {
  getActiveSourceId,
  getActiveStreamId,
  getActiveEngineId,
  getActiveStorageId,
  getActiveSource,
  getActiveStream,
  getActiveEngine,
  getActiveStorage,
  getActiveSourceConfig,
  getActiveStreamConfig,
  getActiveEngineConfig,
} from '../src/plugins/active';

beforeEach(() => {
  registry.clear();
  _resetSourceRegistrationFlag();
  _resetStreamRegistrationFlag();
  _resetEngineRegistrationFlag();
  _resetStorageRegistrationFlag();
  _resetBootstrapFlag();
  ensureBuiltins();
  setActivePlugin('source', 'binance-rest');
  setActivePlugin('stream', 'binance-ws');
  setActivePlugin('engine', 'server');
  setActivePlugin('storage', 'local');
  setStore('pluginsConfig', {});
  setStore('endpoint', 'http://example.test:5002');
});

describe('active ids', () => {
  it('reads activePlugins with fallbacks', () => {
    expect(getActiveSourceId()).toBe('binance-rest');
    expect(getActiveStreamId()).toBe('binance-ws');
    expect(getActiveEngineId()).toBe('server');
    expect(getActiveStorageId()).toBe('local');
  });

  it('resolves plugin objects', () => {
    expect(getActiveSource().id).toBe('binance-rest');
    expect(getActiveStream().id).toBe('binance-ws');
    expect(getActiveEngine().id).toBe('server');
    expect(getActiveStorage()?.id).toBe('local');
  });

  it('falls back when id missing from registry', () => {
    setStore('activePlugins', 'source', 'does-not-exist');
    setStore('source', 'does-not-exist');
    expect(getActiveSource().id).toBe('binance-rest');
  });
});

describe('active config', () => {
  it('merges pluginsConfig by kind:id and bare id', () => {
    setStore('pluginsConfig', {
      'source:binance-rest': { limit: 100 },
      'binance-ws': { wsBase: 'wss://x' },
    });
    expect(getActiveSourceConfig().limit).toBe(100);
    expect(getActiveStreamConfig().wsBase).toBe('wss://x');
  });

  it('injects endpoint for server engine', () => {
    setActivePlugin('engine', 'server');
    const cfg = getActiveEngineConfig();
    expect(cfg.endpoint).toBe('http://example.test:5002');
  });

  it('does not force endpoint for pyodide', () => {
    setActivePlugin('engine', 'pyodide');
    setStore('pluginsConfig', { 'engine:pyodide': { indexUrl: 'https://cdn.example/' } });
    const cfg = getActiveEngineConfig();
    expect(cfg.indexUrl).toBe('https://cdn.example/');
    // pyodide has no endpoint in schema — endpoint only if schema has endpoint field
    // current code injects only for endpoint schema or id server
    expect(cfg.endpoint).toBeUndefined();
  });
});
