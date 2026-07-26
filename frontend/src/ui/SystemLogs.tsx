/**
 * Collapsible system log strip — copyable, void chrome, Lucide icons.
 */

import { Component, For, Show, createEffect, createSignal } from 'solid-js';
import { store, setStore, persist, clearLogs } from '../store';
import type { LogEntry } from '../store/types';
import { Icons } from './icons';

function formatTs(ts: number): string {
  const d = new Date(ts);
  return d.toISOString().slice(11, 23); // HH:mm:ss.sss
}

function levelClass(level: LogEntry['level']): string {
  switch (level) {
    case 'error':
      return 'text-red';
    case 'ok':
      return 'text-accent-2';
    case 'warn':
      return 'text-orange';
    default:
      return 'text-text-dim';
  }
}

function logsAsText(logs: LogEntry[]): string {
  return logs
    .map((l) => `${formatTs(l.ts)}\t${l.level.toUpperCase()}\t[${l.source || 'system'}]\t${l.message}`)
    .join('\n');
}

export const SystemLogs: Component = () => {
  const [copied, setCopied] = createSignal(false);
  let listRef: HTMLDivElement | undefined;

  createEffect(() => {
    // Auto-scroll when expanded and logs grow
    void store.logs.length;
    if (store.logsPanel.open && listRef) {
      listRef.scrollTop = listRef.scrollHeight;
    }
  });

  const toggle = () => {
    setStore('logsPanel', 'open', !store.logsPanel.open);
    persist();
  };

  const copyAll = async () => {
    const text = logsAsText(store.logs);
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      /* ignore */
    }
  };

  const copyLine = async (entry: LogEntry) => {
    const text = `${formatTs(entry.ts)}\t${entry.level}\t${entry.message}`;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 800);
    } catch {
      /* ignore */
    }
  };

  const last = () => store.logs[store.logs.length - 1];

  return (
    <div class="flex flex-col border-t-2 border-border bg-bg-panel flex-shrink-0">
      {/* Collapsed header / toggle row */}
      <div class="flex items-center gap-1.5 px-2 py-0.5 min-h-[24px]">
        <button
          type="button"
          class="sc-btn sc-btn-ghost px-1.5 py-0.5 text-[10px] inline-flex items-center gap-1"
          onClick={toggle}
          title={store.logsPanel.open ? 'Collapse system logs' : 'Expand system logs'}
          aria-expanded={store.logsPanel.open}
        >
          <Icons.scrollText size={13} />
          <span class="uppercase tracking-wider text-text-dim">Logs</span>
          <span class="text-text-faint font-mono">({store.logs.length})</span>
          {store.logsPanel.open ? <Icons.chevronDown size={12} /> : <Icons.chevronUp size={12} />}
        </button>

        <Show when={!store.logsPanel.open && last()}>
          <button
            type="button"
            class={`flex-1 min-w-0 text-left text-[10px] font-mono truncate px-1 ${levelClass(last()!.level)}`}
            title="Click to expand"
            onClick={toggle}
          >
            <span class="text-text-faint mr-1.5">{formatTs(last()!.ts)}</span>
            {last()!.message}
          </button>
        </Show>
        <Show when={!store.logsPanel.open && !last()}>
          <span class="flex-1 text-[10px] text-text-faint px-1">No log entries yet</span>
        </Show>
        <Show when={store.logsPanel.open}>
          <div class="flex-1" />
        </Show>

        <Show when={copied()}>
          <span class="text-[10px] text-accent-2 inline-flex items-center gap-0.5">
            <Icons.check size={12} /> Copied
          </span>
        </Show>

        <button
          type="button"
          class="sc-btn sc-btn-ghost px-1.5 py-0.5"
          title="Copy all logs"
          disabled={!store.logs.length}
          onClick={copyAll}
        >
          <Icons.copy size={13} />
        </button>
        <button
          type="button"
          class="sc-btn sc-btn-ghost px-1.5 py-0.5"
          title="Clear logs"
          disabled={!store.logs.length}
          onClick={() => clearLogs()}
        >
          <Icons.x size={13} />
        </button>
      </div>

      {/* Expanded body */}
      <Show when={store.logsPanel.open}>
        <div
          ref={listRef}
          class="overflow-auto border-t border-border-soft font-mono text-[10px] bg-bg-base"
          style={{ height: `${Math.max(80, store.logsPanel.height - 28)}px` }}
        >
          <Show
            when={store.logs.length > 0}
            fallback={
              <div class="p-3 text-text-faint uppercase tracking-wider">Waiting for system events…</div>
            }
          >
            <For each={store.logs}>
              {(entry) => (
                <div
                  class="group flex items-start gap-2 px-2 py-0.5 border-b border-border-soft/50 hover:bg-bg-hover/60"
                  onDblClick={() => copyLine(entry)}
                  title="Double-click to copy line"
                >
                  <span class="text-text-faint w-[72px] flex-shrink-0 select-none">
                    {formatTs(entry.ts)}
                  </span>
                  <span
                    class={`w-10 flex-shrink-0 uppercase select-none ${levelClass(entry.level)}`}
                  >
                    {entry.level}
                  </span>
                  <span class="text-text-faint w-14 flex-shrink-0 truncate select-none">
                    {entry.source}
                  </span>
                  <span class={`flex-1 min-w-0 break-all ${levelClass(entry.level)}`}>
                    {entry.message}
                  </span>
                  <button
                    type="button"
                    class="sc-btn sc-btn-ghost px-1 py-0 opacity-0 group-hover:opacity-100"
                    title="Copy line"
                    onClick={() => copyLine(entry)}
                  >
                    <Icons.copy size={11} />
                  </button>
                </div>
              )}
            </For>
          </Show>
        </div>
      </Show>
    </div>
  );
};
