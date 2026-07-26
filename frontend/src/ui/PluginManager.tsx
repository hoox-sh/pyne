/**
 * AXIS plugin manager — load ES module plugins from URL (D6).
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
import { Icons } from './icons';
import { persist, setStore, store } from '../store';

interface Props {
  open: boolean;
  onClose: () => void;
  /** Notify parent that source/stream lists may have changed */
  onChanged?: () => void;
}

const EXAMPLES = [
  { label: 'CoinGecko source (example)', url: '/src/plugins/example-coingecko-source.js' },
  { label: 'Tiny Pine engine (example)', url: '/src/plugins/example-tiny-pine-engine.js' },
  { label: 'CF DO stream (example)', url: '/src/plugins/example-cf-do-stream.js' },
];

export const PluginManager: Component<Props> = (props) => {
  const [url, setUrl] = createSignal('');
  const [busy, setBusy] = createSignal(false);
  const [error, setError] = createSignal('');
  const [installed, setInstalled] = createSignal<InstalledPlugin[]>(getInstalledPlugins());

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
            <span id="axis-plugins-title" class="text-sm font-semibold text-text tracking-tight inline-flex items-center gap-1.5">
              <Icons.folder size={14} />
              Plugins
            </span>
            <button class="sc-btn sc-btn-ghost px-2" onClick={props.onClose} aria-label="Close">
              <Icons.x size={14} />
            </button>
          </div>

          <div class="p-3.5 flex flex-col gap-3 overflow-auto text-[11px]">
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
                            removePlugin(p.id);
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

            <div class="grid grid-cols-2 gap-2 text-[10px] text-text-faint font-mono">
              <div class="border-2 border-border px-2 py-1">
                sources: {sources().length}
              </div>
              <div class="border-2 border-border px-2 py-1">
                streams: {streams().length}
              </div>
            </div>
          </div>

          <div class="flex items-center gap-2 px-3.5 py-2.5 border-t-2 border-border bg-bg-base">
            <div class="flex-1 text-[10px] text-text-faint">
              Plugins re-load on next visit from localStorage
            </div>
            <button
              class="sc-btn sc-btn-primary"
              onClick={() => {
                // Ensure current source still valid
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
