// Copyright (C) 2024-2026 jango_blockchained
//
// This file is part of pynescript.
//
// pynescript is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// pynescript is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
//
// SPDX-License-Identifier: AGPL-3.0-or-later

import { Component, For, Show, createMemo, createSignal } from 'solid-js';
import {
  store,
  setStore,
  setStatus,
  toggleTheme,
  persist,
  setEditorOpen,
  setEditorMode,
  setActivePlugin,
  toggleIndicatorPanel,
} from '../store';
import { runAndApply } from '../indicators/runner';
import { startLive, stopLive, listStreams, defaultStreamForSource } from '../streams/multiplex';
import { loadSymbolData } from '../data/load-symbol';
import { parseOhlcvFile } from '../data/parse-bars';
import { openEditorWindow, writeSharedDoc } from '../editor/editor-bridge';
import { listSources } from '../sources/catalog';
import { listEngines, preloadPyodide } from '../engines/catalog';
import { setUploadedBars, getUploadedFileName } from '../sources/upload-store';
import { engineOptionLabel } from './plugin-badges';
import { Icons } from './icons';
import { HooxLogo } from './HooxLogo';
import { HooxLoader } from './HooxLoader';
import { WATCHLIST_INTERVALS } from '../data/watchlist-tickers';

const INTERVALS = [...WATCHLIST_INTERVALS];

export const Topbar: Component<{
  onToggleEditor: () => void;
  onToggleWatchlist: () => void;
  onOpenSettings: () => void;
  onOpenPlugins?: () => void;
  /** Bump when plugin catalog changes */
  catalogTick?: number;
  editorRef: { getDoc: () => string };
}> = (props) => {
  const sources = createMemo(() => {
    void props.catalogTick;
    return listSources();
  });
  const streams = createMemo(() => {
    void props.catalogTick;
    return listStreams();
  });
  const engines = createMemo(() => {
    void props.catalogTick;
    return listEngines();
  });
  const [loading, setLoading] = createSignal(false);
  const [uploadLabel, setUploadLabel] = createSignal(getUploadedFileName() || '');
  let fileInput: HTMLInputElement | undefined;

  const loadHistorical = async () => {
    if (loading()) return;
    setLoading(true);
    try {
      await loadSymbolData(store.symbol, store.interval, store.source);
    } finally {
      setLoading(false);
    }
  };

  const onSourceChange = (id: string) => {
    setActivePlugin('source', id);
    // Align default live stream with source (mock → mock-poll)
    const streamId = defaultStreamForSource(id);
    setActivePlugin('stream', streamId);
    // CSV needs a file first — nudge the picker
    if (id === 'csv-upload' && !getUploadedFileName()) {
      fileInput?.click();
    }
  };

  const onFilePicked = async (e: Event) => {
    const input = e.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    setLoading(true);
    try {
      const bars = await parseOhlcvFile(file);
      setUploadedBars(bars, file.name);
      setUploadLabel(file.name);
      setStore('source', 'csv-upload');
      persist();
      await loadSymbolData(store.symbol, store.interval, 'csv-upload');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatus('error', `Upload failed: ${msg}`);
    } finally {
      setLoading(false);
      // allow re-selecting the same file
      input.value = '';
    }
  };

  const onRun = async () => {
    const doc = props.editorRef.getDoc();
    if (!doc?.trim()) return;
    await runAndApply(doc);
  };

  const toggleLive = () => {
    const next = !store.live.active;
    if (next) {
      const streamId = store.live.streamId || defaultStreamForSource(store.source);
      startLive(streamId, store.symbol, store.interval);
    } else {
      stopLive();
    }
  };

  const detachEditor = (mode: 'popup' | 'tab') => {
    const doc = props.editorRef.getDoc?.() || '';
    writeSharedDoc(doc);
    setEditorMode('popout');
    setEditorOpen(false);
    openEditorWindow(mode);
  };

  const sourceNeedsSymbol = () => store.source !== 'csv-upload' && store.source !== 'mock-walk';

  return (
    <header
      class="flex items-center gap-2.5 px-2.5 py-1 bg-bg-panel border-b-2 border-border flex-shrink-0 min-h-[36px] flex-wrap"
      data-testid="axis-topbar"
    >
      <div
        class="flex items-center gap-1.5 mr-1.5 min-w-0"
        data-testid="axis-brand"
        title="HOOX · AXIS"
      >
        <HooxLogo size="xs" class="text-text flex-shrink-0" data-testid="axis-hoox-logo" />
        <div class="font-semibold text-sm text-text tracking-tight leading-none">
          AXIS
          <span class="text-text-faint font-normal text-[11px] ml-1.5">chart</span>
        </div>
      </div>

      <button
        class={`sc-btn sc-btn-ghost px-2 text-[11px] inline-flex items-center gap-1 ${store.watchlist.open ? 'text-accent' : ''}`}
        onClick={props.onToggleWatchlist}
        title="Toggle watchlist"
      >
        <Icons.list size={14} />
        List
      </button>

      <label class="text-[10px] text-text-dim uppercase tracking-wider">Source</label>
      <select
        class="sc-input min-w-[120px]"
        data-testid="axis-select-source"
        value={store.source}
        onChange={(e) => onSourceChange(e.currentTarget.value)}
        title={sources().find((s) => s.id === store.source)?.description || 'Historical data source'}
      >
        <For each={sources()}>{(s) => <option value={s.id}>{s.name}</option>}</For>
      </select>

      <Show when={store.source === 'csv-upload'}>
        <button
          class="sc-btn sc-btn-ghost px-2 text-[11px] max-w-[160px] inline-flex items-center gap-1"
          title={uploadLabel() || 'Upload CSV or JSON OHLCV'}
          onClick={() => fileInput?.click()}
        >
          <Icons.upload size={13} />
          <span class="truncate">{uploadLabel() || 'Upload…'}</span>
        </button>
        <input
          ref={fileInput}
          type="file"
          accept=".csv,.json,text/csv,application/json"
          class="hidden"
          onChange={onFilePicked}
        />
      </Show>

      <Show when={sourceNeedsSymbol()}>
        <label class="text-[10px] text-text-dim uppercase tracking-wider" for="axis-symbol">
          Symbol
        </label>
        <input
          id="axis-symbol"
          class="sc-input min-w-[96px] font-mono uppercase focus-visible:border-accent"
          value={store.symbol}
          spellcheck={false}
          autocomplete="off"
          onChange={(e) => {
            setStore('symbol', e.currentTarget.value.toUpperCase());
            persist();
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') loadHistorical();
          }}
          onBlur={() => {
            // Reload if symbol was edited without Enter
            if (store.symbol && store.bars.length === 0) void loadHistorical();
          }}
          title="Symbol · Enter to load"
        />
      </Show>

      <Show when={store.source !== 'csv-upload'}>
        <label class="text-[10px] text-text-dim uppercase tracking-wider" for="axis-interval">
          Interval
        </label>
        <select
          id="axis-interval"
          class="sc-input min-w-[56px] focus-visible:border-accent"
          value={store.interval}
          title="Bar interval · reloads chart"
          onChange={(e) => {
            const next = e.currentTarget.value;
            setStore('interval', next);
            persist();
            // Auto-reload so interval changes always paint
            if (store.source !== 'csv-upload') {
              void loadSymbolData(store.symbol, next, store.source);
            }
          }}
        >
          <For each={INTERVALS}>{(i) => <option value={i}>{i}</option>}</For>
        </select>
      </Show>

      <button
        class={`sc-btn inline-flex items-center gap-1 ${loading() ? 'opacity-50' : ''}`}
        onClick={loadHistorical}
        disabled={loading()}
        data-testid="axis-btn-load"
        title={
          store.source === 'csv-upload'
            ? 'Reload last uploaded file'
            : `Load bars from ${store.source}`
        }
      >
        {loading() ? <HooxLoader size="xs" /> : <Icons.download size={13} />}
        {loading() ? 'Loading…' : 'Load'}
      </button>

      <label class="text-[10px] text-text-dim uppercase tracking-wider">Engine</label>
      <select
        class="sc-input min-w-[120px] max-w-[180px]"
        data-testid="axis-select-engine"
        value={store.engine}
        onChange={(e) => {
          const id = e.currentTarget.value;
          setActivePlugin('engine', id);
          // Kick self-hosted Pyodide load as soon as the user selects it
          if (id === 'pyodide') void preloadPyodide();
        }}
        title={engines().find((en) => en.id === store.engine)?.description || 'Calculation engine'}
      >
        <For each={engines()}>
          {(en) => (
            <option value={en.id} title={en.description}>
              {engineOptionLabel(en)}
            </option>
          )}
        </For>
      </select>

      <label class="text-[10px] text-text-dim uppercase tracking-wider">Stream</label>
      <select
        class="sc-input min-w-[110px]"
        value={store.live.streamId}
        disabled={store.live.active}
        onChange={(e) => {
          setActivePlugin('stream', e.currentTarget.value);
        }}
        title="Live data stream (disabled while Live is on)"
      >
        <For each={streams()}>{(s) => <option value={s.id}>{s.name}</option>}</For>
      </select>

      <button
        class={`sc-btn inline-flex items-center gap-1.5 ${
          store.live.active ? 'border-accent-2 text-accent-2' : ''
        }`}
        onClick={toggleLive}
        title={store.live.active ? 'Stop live stream' : 'Start live stream'}
      >
        {store.live.active ? (
          <Icons.wifi size={13} class="text-accent-2" />
        ) : (
          <Icons.wifiOff size={13} />
        )}
        {store.live.active ? 'Live' : 'Live'}
      </button>

      <div class="flex-1" />

      <button
        class="sc-btn sc-btn-primary inline-flex items-center gap-1"
        onClick={onRun}
        data-testid="axis-btn-run"
        title="Run (or use detached editor)"
      >
        <Icons.play size={13} />
        Run
      </button>

      <button
        class={`sc-btn sc-btn-ghost px-2 inline-flex items-center gap-1 ${
          store.editor.open && store.editor.mode === 'docked' ? 'text-accent' : ''
        }`}
        onClick={props.onToggleEditor}
        title="Toggle docked editor"
      >
        <Icons.panelRight size={13} />
        Editor
        {store.editor.mode === 'popout' && (
          <span class="text-orange ml-0.5 text-[10px]">ext</span>
        )}
      </button>

      <button
        class="sc-btn sc-btn-ghost px-1.5"
        title="Detach editor to window"
        onClick={() => detachEditor('popup')}
      >
        <Icons.popout size={13} />
      </button>
      <button
        class="sc-btn sc-btn-ghost px-1.5"
        title="Open editor in new tab"
        onClick={() => detachEditor('tab')}
      >
        <Icons.externalLink size={13} />
      </button>

      <button
        type="button"
        class={`sc-btn sc-btn-ghost px-2 inline-flex items-center gap-1 ${
          store.indicatorPanel.open ? 'text-accent' : ''
        }`}
        onClick={() => toggleIndicatorPanel()}
        title="Toggle indicator list"
        aria-pressed={store.indicatorPanel.open}
        data-testid="axis-btn-indicators"
      >
        <Icons.activity size={13} />
        Indicators
      </button>

      <button
        class={`sc-btn sc-btn-ghost px-2 inline-flex items-center gap-1 ${store.resultsPanel.open ? 'text-accent' : ''}`}
        title="Results & export"
        data-testid="axis-btn-results"
        onClick={() => {
          setStore('resultsPanel', 'open', !store.resultsPanel.open);
          persist();
        }}
      >
        <Icons.scrollText size={13} />
        Results
      </button>

      <button
        class="sc-btn sc-btn-ghost px-2"
        onClick={() => props.onOpenPlugins?.()}
        title="Plugins"
        data-testid="axis-btn-plugins"
        aria-label="Open plugin manager"
      >
        <Icons.folder size={14} />
      </button>

      <button
        class="sc-btn sc-btn-ghost px-2"
        onClick={props.onOpenSettings}
        title="Settings"
        data-testid="axis-btn-settings"
        aria-label="Open settings"
      >
        <Icons.settings size={14} />
      </button>

      <button
        class="sc-btn sc-btn-ghost px-2 focus-visible:border-accent"
        onClick={toggleTheme}
        title={store.theme === 'dark' ? 'Switch to light (soft void lift)' : 'Switch to dark void'}
        aria-label="Toggle color theme"
      >
        {store.theme === 'dark' ? <Icons.sun size={14} /> : <Icons.moon size={14} />}
      </button>
    </header>
  );
};
