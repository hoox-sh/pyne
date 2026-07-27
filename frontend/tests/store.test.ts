/**
 * Solid store mutators + persist.
 * Run: bun test frontend/tests/store.test.ts
 */

import './setup';
import { describe, expect, it, beforeEach } from 'bun:test';
import {
  store,
  setStore,
  persist,
  setActivePlugin,
  appendLog,
  clearLogs,
  setLastRun,
  setStatus,
  loadBars,
  addIndicator,
  removeIndicator,
  toggleIndicator,
  setIndicatorColor,
  addPane,
  removePane,
  resizePane,
  reorderPanes,
  appendBar,
  setLive,
  toggleTheme,
  setEditorWidth,
  setWatchlistWidth,
  setIndicatorWidth,
  setEditorOpen,
  setEditorMode,
  setWatchlistOpen,
  setIndicatorPanelOpen,
  toggleIndicatorPanel,
  addWatchlistSymbol,
  removeWatchlistSymbol,
  setWatchlistRefreshSec,
  saveEditorDoc,
  loadEditorDoc,
  setDrawingTool,
  setDrawings,
  clearDrawings,
  deleteSelectedDrawing,
  STORAGE_KEY,
  EDITOR_DOC_KEY,
} from '../src/store';
import { SAMPLE_BARS, makeBars } from './fixtures/bars';

function resetStoreBasics() {
  clearLogs();
  setStore('bars', []);
  setStore('scripts', []);
  setStore('panes', [
    { id: 'price', type: 'price', height: 0, order: 0, visible: true, label: 'Price' },
    { id: 'volume', type: 'volume', height: 120, order: 1, visible: true, label: 'Volume' },
  ]);
  setStore('symbol', 'BTCUSDT');
  setStore('interval', '1d');
  setStore('exchange', 'binance');
  setStore('source', 'binance-rest');
  setStore('engine', 'server');
  setStore('activePlugins', {
    source: 'binance-rest',
    stream: 'binance-ws',
    engine: 'server',
    storage: 'local',
  });
  setStore('live', { active: false, needsRerun: false, lastBarTime: 0, streamId: 'binance-ws' });
  setStore('theme', 'dark');
  setStore('editor', { open: true, width: 460, mode: 'docked' });
  setStore('watchlist', {
    open: true,
    width: 200,
    symbols: ['BTCUSDT'],
    refreshSec: 15,
  });
  setStore('status', 'ready');
  setStore('statusMessage', 'Ready.');
  setStore('lastRun', null);
  setStore('lastRunMs', null);
  setStore('drawingTool', 'cursor');
  setStore('drawings', []);
  localStorage.removeItem(STORAGE_KEY);
}

beforeEach(() => {
  resetStoreBasics();
});

describe('setActivePlugin', () => {
  it('syncs flat fields for source/engine/stream', () => {
    setActivePlugin('source', 'mock-walk');
    expect(store.source).toBe('mock-walk');
    expect(store.activePlugins.source).toBe('mock-walk');

    setActivePlugin('engine', 'pyodide');
    expect(store.engine).toBe('pyodide');
    expect(store.activePlugins.engine).toBe('pyodide');

    setActivePlugin('stream', 'mock-poll');
    expect(store.live.streamId).toBe('mock-poll');
    expect(store.activePlugins.stream).toBe('mock-poll');

    setActivePlugin('storage', 'cloud');
    expect(store.activePlugins.storage).toBe('cloud');
  });
});

describe('logs and status', () => {
  it('appendLog and clearLogs', () => {
    appendLog('info', 'hello', 'test');
    expect(store.logs.length).toBeGreaterThanOrEqual(1);
    expect(store.logs[store.logs.length - 1].message).toBe('hello');
    clearLogs();
    expect(store.logs).toEqual([]);
  });

  it('setStatus writes message and logs', () => {
    clearLogs();
    setStatus('error', 'boom');
    expect(store.status).toBe('error');
    expect(store.statusMessage).toBe('boom');
    expect(store.logs.some((l) => l.message === 'boom')).toBe(true);
  });

  it('setLastRun captures meta.ms', () => {
    setLastRun({ status: 'success', plots: [], events: [], meta: { ms: 42.5 } });
    expect(store.lastRunMs).toBe(42.5);
  });
});

describe('bars and indicators', () => {
  it('loadBars sets symbol/interval/exchange', () => {
    loadBars(SAMPLE_BARS, 'ETHUSDT', '1h', 'binance');
    expect(store.bars).toHaveLength(SAMPLE_BARS.length);
    expect(store.symbol).toBe('ETHUSDT');
    expect(store.interval).toBe('1h');
  });

  it('appendBar updates same time then appends new', () => {
    loadBars(SAMPLE_BARS, 'BTCUSDT', '1d', 'binance');
    const last = store.bars[store.bars.length - 1];
    appendBar({ ...last, close: 999 });
    expect(store.bars[store.bars.length - 1].close).toBe(999);
    expect(store.live.needsRerun).toBe(true);

    appendBar({
      time: last.time + 100,
      open: 1,
      high: 1,
      low: 1,
      close: 1,
      volume: 1,
    });
    expect(store.bars[store.bars.length - 1].time).toBe(last.time + 100);
  });

  it('indicator CRUD', () => {
    const id = addIndicator('RSI', 'plot(1)', 'price', { RSI: { color: '#f00' } });
    expect(store.scripts.some((s) => s.id === id)).toBe(true);
    toggleIndicator(id);
    expect(store.scripts.find((s) => s.id === id)?.visible).toBe(false);
    setIndicatorColor(id, 'RSI', '#0f0');
    expect(store.scripts.find((s) => s.id === id)?.plots.RSI.color).toBe('#0f0');
    removeIndicator(id);
    expect(store.scripts.some((s) => s.id === id)).toBe(false);
  });
});

describe('panes', () => {
  it('add/remove/resize/reorder', () => {
    const id = addPane('indicator', 'Ind');
    expect(store.panes.some((p) => p.id === id)).toBe(true);
    resizePane(id, 200);
    expect(store.panes.find((p) => p.id === id)?.height).toBe(200);
    const ids = store.panes.map((p) => p.id).reverse();
    reorderPanes(ids);
    expect(store.panes[0].id).toBe(ids[0]);
    removePane(id);
    expect(store.panes.some((p) => p.id === id)).toBe(false);
  });
});

describe('layout helpers', () => {
  it('clamps widths and toggles editor/watchlist', () => {
    setEditorWidth(100);
    expect(store.editor.width).toBe(280);
    setEditorWidth(99999);
    expect(store.editor.width).toBeLessThanOrEqual(Math.floor(1280 * 0.8));

    setWatchlistWidth(50);
    expect(store.watchlist.width).toBe(140);
    setIndicatorWidth(50);
    expect(store.indicatorPanel.width).toBe(160);

    setEditorOpen(false);
    expect(store.editor.open).toBe(false);
    setEditorMode('popout');
    expect(store.editor.mode).toBe('popout');
    expect(store.editor.open).toBe(false);
    setWatchlistOpen(false);
    expect(store.watchlist.open).toBe(false);

    setIndicatorPanelOpen(false);
    expect(store.indicatorPanel.open).toBe(false);
    toggleIndicatorPanel();
    expect(store.indicatorPanel.open).toBe(true);
    toggleIndicatorPanel();
    expect(store.indicatorPanel.open).toBe(false);
  });

  it('watchlist symbols and refresh clamp', () => {
    addWatchlistSymbol('ethusdt');
    expect(store.watchlist.symbols).toContain('ETHUSDT');
    addWatchlistSymbol('ETHUSDT'); // no-op duplicate
    removeWatchlistSymbol('ETHUSDT');
    expect(store.watchlist.symbols).not.toContain('ETHUSDT');

    setWatchlistRefreshSec(1);
    expect(store.watchlist.refreshSec).toBe(5);
    setWatchlistRefreshSec(999);
    expect(store.watchlist.refreshSec).toBe(120);
  });

  it('theme toggle', () => {
    const before = store.theme;
    toggleTheme();
    expect(store.theme).not.toBe(before);
    toggleTheme();
    expect(store.theme).toBe(before);
  });

  it('setLive', () => {
    setLive(true);
    expect(store.live.active).toBe(true);
  });
});

describe('editor doc + drawings', () => {
  it('save/load editor doc', () => {
    saveEditorDoc('plot(close)');
    expect(loadEditorDoc()).toBe('plot(close)');
    expect(localStorage.getItem(EDITOR_DOC_KEY)).toBe('plot(close)');
  });

  it('drawings set/clear/delete', () => {
    setDrawingTool('trend');
    expect(store.drawingTool).toBe('trend');
    const d = [{ id: 'd1' }] as never[];
    setDrawings(d);
    expect(store.drawings).toHaveLength(1);
    deleteSelectedDrawing([]);
    expect(store.drawings).toEqual([]);
    setDrawings(d);
    clearDrawings();
    expect(store.drawings).toEqual([]);
  });
});

describe('persist', () => {
  it('writes AXIS key without bars/logs/lastRun', async () => {
    loadBars(makeBars(3), 'BTCUSDT', '1d', 'binance');
    appendLog('info', 'x');
    setLastRun({ status: 'success', plots: [], events: [] });
    setStore('symbol', 'SOLUSDT');
    persist();
    await new Promise((r) => setTimeout(r, 250));
    const raw = localStorage.getItem(STORAGE_KEY);
    expect(raw).toBeTruthy();
    const parsed = JSON.parse(raw!);
    expect(parsed.symbol).toBe('SOLUSDT');
    expect(parsed.bars).toBeUndefined();
    expect(parsed.logs).toBeUndefined();
    expect(parsed.lastRun).toBeUndefined();
  });
});
