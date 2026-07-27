/**
 * Persist / hydrate shape for AXIS store key.
 */
import './../setup';
import { describe, expect, it, beforeEach } from 'bun:test';
import {
  store,
  setStore,
  persist,
  loadBars,
  setActivePlugin,
  appendLog,
  STORAGE_KEY,
} from '../../src/store';
import { SAMPLE_BARS } from '../fixtures/bars';

beforeEach(() => {
  localStorage.clear();
  loadBars(SAMPLE_BARS.slice(0, 3), 'ETHUSDT', '5m', 'mock');
  setActivePlugin('source', 'mock-walk');
  setActivePlugin('engine', 'pyodide');
  setStore('endpoint', 'http://persist.test:5002');
  appendLog('info', 'should not persist', 'test');
});

describe('persist hydrate', () => {
  it('writes AXIS key without bars/logs/lastRun', async () => {
    persist();
    // persist() is debounced 200ms
    await new Promise((r) => setTimeout(r, 250));
    const raw = localStorage.getItem(STORAGE_KEY);
    expect(raw).toBeTruthy();
    const parsed = JSON.parse(raw!);
    expect(parsed.symbol).toBe('ETHUSDT');
    expect(parsed.interval).toBe('5m');
    expect(parsed.endpoint).toBe('http://persist.test:5002');
    expect(parsed.activePlugins?.engine || parsed.engine).toBeTruthy();
    expect(parsed.bars).toBeUndefined();
    expect(parsed.logs).toBeUndefined();
    expect(parsed.lastRun).toBeUndefined();
  });

  it('round-trips layout and plugin selection fields', async () => {
    setStore('editor', 'width', 420);
    setStore('watchlist', 'open', true);
    setStore('theme', 'light');
    persist();
    await new Promise((r) => setTimeout(r, 250));
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY)!);
    expect(parsed.editor?.width).toBe(420);
    expect(parsed.theme).toBe('light');
    // store still holds bars in memory
    expect(store.bars.length).toBeGreaterThan(0);
  });
});
