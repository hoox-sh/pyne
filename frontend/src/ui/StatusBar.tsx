import { Component, Show, createMemo } from 'solid-js';
import { store, setStore, persist } from '../store';
import { Icons } from './icons';
import type { RunResult } from '../indicators/runner';
import { buildStrategyReport, formatMoney } from '../results/strategy';
import { getEngine } from '../engines/catalog';
import { getStorage } from '../storage/catalog';

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

  const strategySummary = createMemo(() => {
    const r = store.lastRun as RunResult | null;
    if (!r?.events?.length) return null;
    const rep = buildStrategyReport(r.events as never[], store.bars);
    if (!rep.stats.trades) return null;
    return rep.stats;
  });

  const engineMeta = createMemo(() => {
    const eng = getEngine(store.engine);
    return {
      id: store.engine,
      name: eng?.name || store.engine,
      offline: !!eng?.capabilities?.offline,
      needsNet: !!eng?.capabilities?.needsNetwork,
    };
  });

  const storageId = () => store.activePlugins?.storage || 'local';
  const storageMeta = createMemo(() => {
    const s = getStorage(storageId());
    return { id: storageId(), name: s?.name || storageId() };
  });

  return (
    <div
      class="flex items-center gap-2 px-2.5 py-0.5 bg-bg-panel border-t-2 border-border text-[11px] text-text-dim min-h-[22px] flex-shrink-0"
      data-testid="axis-statusbar"
      role="status"
    >
      <span class={`flex items-center gap-1.5 min-w-0 ${color()}`} data-testid="axis-status-message">
        {store.status === 'running' && <Icons.loader size={12} class="animate-spin text-accent" />}
        {store.status === 'error' && <Icons.alert size={12} class="text-red" />}
        {store.status === 'ready' && <Icons.activity size={12} class="text-accent-2" />}
        {store.status === 'loading' && <Icons.loader size={12} class="animate-spin text-orange" />}
        <span class="truncate">{store.statusMessage}</span>
      </span>
      <span class="flex-1" />

      <Show when={strategySummary()}>
        {(stats) => (
          <span
            class={`text-[10px] font-mono tracking-tight tabular-nums ${
              stats().totalPnl >= 0 ? 'text-accent-2' : 'text-red'
            }`}
            title="Closed trades from last run"
          >
            {stats().trades} trades · {formatMoney(stats().totalPnl)}
          </span>
        )}
      </Show>

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
        class={`inline-flex items-center gap-1 text-[10px] font-mono tracking-tight ${
          engineMeta().offline ? 'text-accent-2' : 'text-accent-3'
        }`}
        title={
          engineMeta().offline
            ? `${engineMeta().name} · offline-capable`
            : `${engineMeta().name} · ${store.endpoint}`
        }
      >
        {engineMeta().offline ? <Icons.activity size={11} /> : <Icons.wifi size={11} />}
        <span class="max-w-[90px] truncate">{engineMeta().id}</span>
      </span>

      <span
        class="text-[10px] font-mono text-text-faint max-w-[72px] truncate"
        title={`Storage: ${storageMeta().name}`}
      >
        ⧉ {storageMeta().id}
      </span>

      <span
        class="text-[10px] font-mono text-text-faint max-w-[100px] truncate"
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
