/**
 * Script library UI — list / load / save / delete against the active storage plugin.
 */

import { Component, For, Show, createSignal, createEffect } from 'solid-js';
import type { ScriptMeta } from '../plugins/types';
import {
  listScripts,
  readScript,
  writeScript,
  removeScript,
  exportLibraryJson,
  importLibraryJson,
  getStorageStatus,
} from '../storage/service';
import { listStorages } from '../storage/catalog';
import { setActivePlugin, store, setStore, persist, appendLog, setStatus } from '../store';
import { pluginKey } from '../plugins/types';
import { Icons } from './icons';

function cloudCfg(): { endpoint: string; apiKey: string } {
  const pc = store.pluginsConfig || {};
  const c = (pc[pluginKey('storage', 'cloud')] || pc['cloud'] || {}) as Record<string, unknown>;
  return {
    endpoint: String(c.endpoint || store.endpoint || 'http://127.0.0.1:8787'),
    apiKey: String(c.apiKey || ''),
  };
}

function saveCloudCfg(endpoint: string, apiKey: string) {
  const key = pluginKey('storage', 'cloud');
  setStore('pluginsConfig', key, { endpoint: endpoint.replace(/\/$/, ''), apiKey });
  persist();
}

export interface ScriptLibraryPanelProps {
  /** Current editor buffer (for Save) */
  getDoc?: () => string;
  /** Load script into editor */
  setDoc?: (doc: string, name?: string) => void;
  /** Optional: called after load so host can mark tab clean */
  onLoaded?: (meta: ScriptMeta, content: string) => void;
}

export const ScriptLibraryPanel: Component<ScriptLibraryPanelProps> = (props) => {
  const [items, setItems] = createSignal<ScriptMeta[]>([]);
  const [busy, setBusy] = createSignal(false);
  const [error, setError] = createSignal('');
  const [name, setName] = createSignal('');
  const [desc, setDesc] = createSignal('');
  const [statusLine, setStatusLine] = createSignal('');
  const [cloudEndpoint, setCloudEndpoint] = createSignal(cloudCfg().endpoint);
  const [cloudKey, setCloudKey] = createSignal(cloudCfg().apiKey);
  let fileInput: HTMLInputElement | undefined;

  const storages = () => listStorages();
  const isCloud = () => (store.activePlugins?.storage || 'local') === 'cloud';

  const refresh = async () => {
    setBusy(true);
    setError('');
    try {
      const list = await listScripts();
      setItems(list);
      const st = await getStorageStatus();
      const backend = store.activePlugins?.storage || 'local';
      setStatusLine(
        `${backend}${st.remote ? ` · ${st.remote}` : ''}${st.connected ? '' : ' · offline'} · ${list.length} script(s)`,
      );
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  createEffect(() => {
    // Refresh on mount and when storage backend changes
    void store.activePlugins?.storage;
    if (isCloud()) {
      const c = cloudCfg();
      setCloudEndpoint(c.endpoint);
      setCloudKey(c.apiKey);
    }
    void refresh();
  });

  const onSave = async () => {
    const n = name().trim();
    if (!n) {
      setError('Name is required');
      return;
    }
    const content = props.getDoc?.() ?? '';
    if (!content.trim()) {
      setError('Editor is empty');
      return;
    }
    setBusy(true);
    setError('');
    try {
      await writeScript({
        id: `s_${Date.now().toString(36)}`,
        name: n,
        description: desc().trim() || undefined,
        content,
      });
      setName('');
      setDesc('');
      setStatus('ready', `Saved "${n}"`);
      await refresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onLoad = async (id: string) => {
    setBusy(true);
    setError('');
    try {
      const doc = await readScript(id);
      props.setDoc?.(doc.content, doc.name);
      props.onLoaded?.(doc, doc.content);
      setStatus('ready', `Loaded "${doc.name}"`);
      appendLog('ok', `Loaded library script ${doc.name}`, 'library');
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onDelete = async (id: string, scriptName: string) => {
    if (!confirm(`Delete "${scriptName}"?`)) return;
    setBusy(true);
    try {
      await removeScript(id);
      await refresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onExport = async () => {
    try {
      const docs = await exportLibraryJson();
      const blob = new Blob([JSON.stringify(docs, null, 2)], { type: 'application/json' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'pynescript-library.json';
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const onImportFile = async (e: Event) => {
    const input = e.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    setBusy(true);
    try {
      const data = JSON.parse(await file.text());
      if (!Array.isArray(data)) throw new Error('Expected a JSON array of scripts');
      const n = await importLibraryJson(data, { forceNewIds: true });
      setStatus('ready', `Imported ${n} script(s)`);
      await refresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
      input.value = '';
    }
  };

  return (
    <div class="flex flex-col gap-3 text-[11px]">
      <div class="flex flex-col gap-1">
        <label class="text-[10px] text-text-dim uppercase tracking-wider">Storage backend</label>
        <select
          class="sc-input"
          value={store.activePlugins?.storage || 'local'}
          onChange={(e) => {
            setActivePlugin('storage', e.currentTarget.value);
          }}
          title="Where user Pine scripts are stored"
        >
          <For each={storages()}>
            {(s) => (
              <option value={s.id}>
                {s.name}
                {s.builtIn ? '' : ' (plugin)'}
              </option>
            )}
          </For>
        </select>
        <p class="text-text-faint font-mono text-[10px]">{statusLine()}</p>
      </div>

      <Show when={isCloud()}>
        <div class="border-2 border-border p-2 flex flex-col gap-1.5 bg-bg-elev">
          <div class="text-[10px] text-text-dim uppercase tracking-wider">Cloud credentials</div>
          <input
            class="sc-input font-mono text-[11px]"
            placeholder="Worker URL (http://127.0.0.1:8787)"
            value={cloudEndpoint()}
            onInput={(e) => setCloudEndpoint(e.currentTarget.value)}
            spellcheck={false}
          />
          <input
            class="sc-input font-mono text-[11px]"
            placeholder="API key (pn_…)"
            type="password"
            value={cloudKey()}
            onInput={(e) => setCloudKey(e.currentTarget.value)}
            spellcheck={false}
            autocomplete="off"
          />
          <button
            class="sc-btn sc-btn-ghost text-[10px]"
            onClick={() => {
              saveCloudCfg(cloudEndpoint(), cloudKey());
              void refresh();
            }}
          >
            Save cloud settings
          </button>
          <p class="text-[9px] text-text-faint">
            Create keys via Worker <code class="font-mono">/api/keys</code> (admin token). Local
            wrangler sets <code class="font-mono">ALLOW_OPEN_KEYS=1</code> for any Bearer key.
          </p>
        </div>
      </Show>

      <div class="border-2 border-border p-2 flex flex-col gap-1.5 bg-bg-elev">
        <div class="text-[10px] text-text-dim uppercase tracking-wider">Save current editor</div>
        <input
          class="sc-input"
          placeholder="Script name"
          value={name()}
          onInput={(e) => setName(e.currentTarget.value)}
        />
        <input
          class="sc-input"
          placeholder="Description (optional)"
          value={desc()}
          onInput={(e) => setDesc(e.currentTarget.value)}
        />
        <button
          class="sc-btn sc-btn-primary inline-flex items-center gap-1 justify-center"
          disabled={busy()}
          onClick={() => void onSave()}
        >
          <Icons.download size={13} />
          Save to library
        </button>
      </div>

      <div class="flex gap-1.5 flex-wrap">
        <button class="sc-btn sc-btn-ghost text-[10px] inline-flex items-center gap-1" onClick={() => void refresh()} disabled={busy()}>
          {busy() ? <Icons.loader size={12} class="animate-spin" /> : null}
          Refresh
        </button>
        <button class="sc-btn sc-btn-ghost text-[10px]" onClick={() => void onExport()}>
          Export JSON
        </button>
        <button class="sc-btn sc-btn-ghost text-[10px]" onClick={() => fileInput?.click()}>
          Import…
        </button>
        <input
          ref={fileInput}
          type="file"
          accept="application/json,.json"
          class="hidden"
          onChange={(e) => void onImportFile(e)}
        />
      </div>

      <Show when={error()}>
        <p class="text-red font-mono text-[10px]">{error()}</p>
      </Show>

      <div>
        <div class="text-[10px] text-text-dim uppercase tracking-wider mb-1">
          Library ({items().length})
        </div>
        <Show
          when={items().length > 0}
          fallback={<div class="text-text-faint p-2">No saved scripts yet.</div>}
        >
          <ul class="flex flex-col gap-1 max-h-[240px] overflow-auto">
            <For each={items()}>
              {(item) => (
                <li class="flex items-center gap-2 border-2 border-border bg-bg-elev px-2 py-1.5">
                  <div class="flex-1 min-w-0">
                    <div class="text-text font-medium truncate">{item.name}</div>
                    <div class="text-text-faint font-mono text-[9px] truncate">
                      {item.description || item.id}
                      {' · '}
                      {item.updatedAt ? new Date(item.updatedAt).toLocaleString() : ''}
                    </div>
                  </div>
                  <button
                    class="sc-btn sc-btn-ghost px-1.5 text-[10px]"
                    title="Load into editor"
                    onClick={() => void onLoad(item.id)}
                  >
                    Load
                  </button>
                  <button
                    class="sc-btn sc-btn-ghost px-1.5"
                    title="Delete"
                    onClick={() => void onDelete(item.id, item.name)}
                  >
                    <Icons.x size={13} />
                  </button>
                </li>
              )}
            </For>
          </ul>
        </Show>
      </div>
    </div>
  );
};
