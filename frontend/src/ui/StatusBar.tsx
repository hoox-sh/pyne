import { Component } from 'solid-js';
import { store, setStore, persist } from '../store';
import { Icons } from './icons';

const STATUS_COLORS: Record<string, string> = {
  ready: 'text-accent-2',
  loading: 'text-orange',
  running: 'text-accent',
  error: 'text-red',
  connected: 'text-accent-2',
  disconnected: 'text-text-faint',
};

export const StatusBar: Component = () => {
  const color = () => STATUS_COLORS[store.status] || 'text-text-dim';

  return (
    <div class="flex items-center gap-2 px-2.5 py-0.5 bg-bg-panel border-t-2 border-border text-[11px] text-text-dim min-h-[22px] flex-shrink-0">
      <span class={`flex items-center gap-1.5 min-w-0 ${color()}`}>
        {store.status === 'running' && <Icons.loader size={12} class="animate-spin text-accent" />}
        {store.status === 'error' && <Icons.alert size={12} class="text-red" />}
        {store.status === 'ready' && <Icons.activity size={12} class="text-accent-2" />}
        {store.status === 'loading' && <Icons.loader size={12} class="animate-spin text-orange" />}
        <span class="truncate">{store.statusMessage}</span>
      </span>
      <span class="flex-1" />

      <button
        type="button"
        class={`sc-btn sc-btn-ghost px-1.5 py-0 text-[10px] inline-flex items-center gap-1 ${
          store.logsPanel.open ? 'text-accent' : ''
        }`}
        title="Toggle system logs"
        onClick={() => {
          setStore('logsPanel', 'open', !store.logsPanel.open);
          persist();
        }}
      >
        <Icons.scrollText size={12} />
        <span class="font-mono">{store.logs.length}</span>
      </button>

      <span
        class={`inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider ${
          store.engine === 'pyodide' ? 'text-accent-2' : 'text-accent-3'
        }`}
        title={
          store.engine === 'pyodide'
            ? 'Client engine (offline-ready)'
            : `Server engine · ${store.endpoint}`
        }
      >
        {store.engine === 'pyodide' ? (
          <Icons.activity size={11} />
        ) : (
          <Icons.wifi size={11} />
        )}
        {store.engine === 'pyodide' ? 'local' : 'server'}
      </span>
      <span
        class="text-[10px] font-mono text-text-faint max-w-[120px] truncate"
        title={`Source: ${store.source}`}
      >
        {store.source}
      </span>
      <span class="text-text-faint font-mono text-[10px] tracking-tight">
        {store.bars.length} bars · {store.scripts.length} ind · {store.panes.length} panes
        {store.lastRunMs != null && ` · ${store.lastRunMs.toFixed(0)}ms`}
      </span>
    </div>
  );
};
