import { Component } from 'solid-js';
import { store } from '../store';

const STATUS_COLORS: Record<string, string> = {
  ready: 'text-green',
  loading: 'text-yellow',
  running: 'text-accent',
  error: 'text-red',
  connected: 'text-green',
  disconnected: 'text-text-faint',
};

export const StatusBar: Component = () => {
  const color = STATUS_COLORS[store.status] || 'text-text-dim';

  return (
    <div class="flex items-center px-2.5 py-0.5 bg-bg-panel border-t border-border text-[11px] text-text-dim min-h-[24px] flex-shrink-0">
      <span class={`flex items-center gap-1.5 ${color}`}>
        {store.status === 'running' && <span class="inline-block w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />}
        {store.status === 'error' && <span class="inline-block w-1.5 h-1.5 rounded-full bg-red" />}
        {store.statusMessage}
      </span>
      <span class="flex-1" />
      <span class="text-text-faint font-mono text-[11px]">
        {store.bars.length} bars · {store.scripts.length} indicators · {store.panes.length} panes
        {store.lastRunMs != null && ` · ${store.lastRunMs.toFixed(0)}ms`}
      </span>
    </div>
  );
};
