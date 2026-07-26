/**
 * AXIS plugin manager — plugins tab + script library (storage backends).
 */

import { Component, For, Show, createSignal, createMemo } from 'solid-js';
import {
  getInstalledPlugins,
  loadPluginFromUrl,
  removePlugin,
  type InstalledPlugin,
} from '../plugins/loader';
import { listSources } from '../sources/catalog';
import { listStreams } from '../streams/catalog';
import { listEngines } from '../engines/catalog';
import { listStorages } from '../storage/catalog';
import { ScriptLibraryPanel } from './ScriptLibraryPanel';
import { Icons } from './icons';
import { persist, setStore, store } from '../store';

interface Props {
  open: boolean;
  onClose: () => void;
  /** Notify parent that source/stream lists may have changed */
  onChanged?: () => void;
  getDoc?: () => string;
  setDoc?: (doc: string, name?: string) => void;
}

const EXAMPLES = [
  { label: 'CoinGecko source (example)', url: '/src/plugins/example-coingecko-source.js' },
  { label: 'Tiny Pine engine (example)', url: '/src/plugins/example-tiny-pine-engine.js' },
  { label: 'CF DO stream (example)', url: '/src/plugins/example-cf-do-stream.js' },
];

type TabId = 'plugins' | 'library';

export const PluginManager: Component<Props> = (props) => {
  const [url, setUrl] = createSignal('');
  const [busy, setBusy] = createSignal(false);
  const [error, setError] = createSignal('');
  const [installed, setInstalled] = createSignal<InstalledPlugin[]>(getInstalledPlugins());
  const [tab, setTab] = createSignal<TabId>('plugins');

  const refresh = () => {
    setInstalled(getInstalledPlugins());
    props.onChanged?.();
  };

  const load = async (href?: string) => {
    const u = (href || url()).trim();
    if (!u) return;
    setBusy(true);
    setError('');
    try {
      await loadPluginFromUrl(u);
      setUrl('');
      refresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const sources = createMemo(() => listSources());
  const streams = createMemo(() => listStreams());
  const engines = createMemo(() => listEngines());
  const storages = createMemo(() => listStorages());

  const onBackdrop = (e: MouseEvent) => {
    if (e.target === e.currentTarget) props.onClose();
  };

  return (
    <Show when={props.open}>
      <div
        class="fixed inset-0 bg-black/75 flex items-center justify-center z-[1000] p-4"
        onClick={onBackdrop}
        role="presentation"
      >
        <div
          class="bg-bg-panel border-2 border-border w-[min(560px,calc(100vw-32px))] max-h-[calc(100vh-64px)] flex flex-col shadow-[0_16px_48px_rgba(0,0,0,0.6)]"
          role="dialog"
          aria-modal="true"
          aria-labelledby="axis-plugins-title"
        >
          <div class="h-0.5 w-full bg-accent flex-shrink-0" />
          <div class="flex items-center justify-between px-3.5 py-2.5 border-b-2 border-border">
            <span
              id="axis-plugins-title"
              class="text-sm font-semibold text-text tracking-tight inline-flex items-center gap-1.5"
            >
              <Icons.folder size={14} />
              Manager
            </span>
            <button class="sc-btn sc-btn-ghost px-2" onClick={props.onClose} aria-label="Close">
              <Icons.x size={14} />
            </button>
          </div>

          <div class="flex border-b-2 border-border flex-shrink-0" role="tablist">
            <button
              role="tab"
              aria-selected={tab() === 'plugins'}
              class={`flex-1 px-3 py-2 text-[11px] font-medium border-b-2 -mb-[2px] ${
                tab() === 'plugins'
                  ? 'border-b-accent text-text'
                  : 'border-b-transparent text-text-dim hover:text-text'
              }`}
              onClick={() => setTab('plugins')}
            >
              Plugins
            </button>
            <button
              role="tab"
              aria-selected={tab() === 'library'}
              class={`flex-1 px-3 py-2 text-[11px] font-medium border-b-2 -mb-[2px] ${
                tab() === 'library'
                  ? 'border-b-accent text-text'
                  : 'border-b-transparent text-text-dim hover:text-text'
              }`}
              onClick={() => setTab('library')}
            >
              Script Library
            </button>
          </div>

          <div class="p-3.5 flex flex-col gap-3 overflow-auto text-[11px] min-h-0 flex-1">
            <Show when={tab() === 'plugins'}>
              <div class="flex flex-col gap-1">
                <label class="text-[10px] text-text-dim uppercase tracking-wider">Load from URL</label>
                <div class="flex gap-1.5">
                  <input
                    class="sc-input flex-1 min-w-0 font-mono text-[11px]"
                    placeholder="https://…/my-source.js or /src/plugins/…"
                    value={url()}
                    onInput={(e) => setUrl(e.currentTarget.value)}
                    onKeyDown={(e) => e.key === 'Enter' && load()}
                  />
                  <button
                    class="sc-btn sc-btn-primary inline-flex items-center gap-1"
                    disabled={busy() || !url().trim()}
                    onClick={() => load()}
                  >
                    {busy() ? <Icons.loader size={13} class="animate-spin" /> : <Icons.download size={13} />}
                    Load
                  </button>
                </div>
                <Show when={error()}>
                  <p class="text-red font-mono text-[10px]">{error()}</p>
                </Show>
              </div>

              <div>
                <div class="text-[10px] text-text-dim uppercase tracking-wider mb-1">Examples</div>
                <div class="flex flex-col gap-1">
                  <For each={EXAMPLES}>
                    {(ex) => (
                      <button
                        class="sc-btn sc-btn-ghost text-left text-[10px] font-mono justify-start"
                        onClick={() => {
                          setUrl(ex.url);
                          load(ex.url);
                        }}
                      >
                        {ex.label}
                      </button>
                    )}
                  </For>
                </div>
              </div>

              <div>
                <div class="text-[10px] text-text-dim uppercase tracking-wider mb-1">
                  Installed ({installed().length})
                </div>
                <Show
                  when={installed().length > 0}
                  fallback={<div class="text-text-faint p-2">No dynamic plugins yet.</div>}
                >
                  <ul class="flex flex-col gap-1">
                    <For each={installed()}>
                      {(p) => (
                        <li class="flex items-center gap-2 border-2 border-border bg-bg-elev px-2 py-1.5">
                          <div class="flex-1 min-w-0">
                            <div class="text-text font-medium">{p.name}</div>
                            <div class="text-text-faint font-mono text-[10px] truncate">
                              {p.kind} · {p.id}
                            </div>
                            <div class="text-text-faint font-mono text-[9px] truncate" title={p.url}>
                              {p.url}
                            </div>
                          </div>
                          <button
                            class="sc-btn sc-btn-ghost px-1.5"
                            title="Remove"
                            onClick={() => {
                              removePlugin(p.id, p.kind);
                              refresh();
                            }}
                          >
                            <Icons.x size={13} />
                          </button>
                        </li>
                      )}
                    </For>
                  </ul>
                </Show>
              </div>

              <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[10px] text-text-faint font-mono">
                <div class="border-2 border-border px-2 py-1">sources: {sources().length}</div>
                <div class="border-2 border-border px-2 py-1">streams: {streams().length}</div>
                <div class="border-2 border-border px-2 py-1">engines: {engines().length}</div>
                <div class="border-2 border-border px-2 py-1">storage: {storages().length}</div>
              </div>
            </Show>

            <Show when={tab() === 'library'}>
              <ScriptLibraryPanel getDoc={props.getDoc} setDoc={props.setDoc} />
            </Show>
          </div>

          <div class="flex items-center gap-2 px-3.5 py-2.5 border-t-2 border-border bg-bg-base">
            <div class="flex-1 text-[10px] text-text-faint">
              {tab() === 'plugins'
                ? 'Plugins re-load on next visit from localStorage'
                : `Scripts: ${store.activePlugins?.storage || 'local'} backend`}
            </div>
            <button
              class="sc-btn sc-btn-primary"
              onClick={() => {
                if (!listSources().some((s) => s.id === store.source)) {
                  setStore('source', 'binance-rest');
                  persist();
                }
                props.onClose();
              }}
            >
              Done
            </button>
          </div>
        </div>
      </div>
    </Show>
  );
};
