import { Component, createEffect, createSignal, Show } from 'solid-js';
import { store, setStore, persist, setStatus } from '../store';
import { Icons } from './icons';
import { probeEndpoint } from '../indicators/runner';

interface Props {
  open: boolean;
  onClose: () => void;
}

export const SettingsDialog: Component<Props> = (props) => {
  const [endpoint, setEndpoint] = createSignal(store.endpoint);
  const [engine, setEngine] = createSignal(store.engine);
  const [probing, setProbing] = createSignal(false);
  const [probeMsg, setProbeMsg] = createSignal('');

  createEffect(() => {
    if (props.open) {
      setEndpoint(store.endpoint);
      setEngine(store.engine);
      setProbeMsg('');
    }
  });

  const save = () => {
    setStore('endpoint', endpoint().trim());
    setStore('engine', engine());
    persist();
    setStatus('ready', `Settings saved · engine=${engine()}`);
    props.onClose();
  };

  const onBackdrop = (e: MouseEvent) => {
    if (e.target === e.currentTarget) props.onClose();
  };

  const onKey = (e: KeyboardEvent) => {
    if (e.key === 'Escape') props.onClose();
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) save();
  };

  const testEndpoint = async () => {
    setProbing(true);
    setProbeMsg('Probing…');
    const r = await probeEndpoint(endpoint().trim());
    setProbing(false);
    setProbeMsg(r.ok ? `✓ ${r.message}` : `✗ ${r.message}`);
    if (r.ok) setStatus('ready', `Endpoint OK · ${endpoint().trim()}`);
    else setStatus('error', `Endpoint failed · ${r.message}`);
  };

  return (
    <Show when={props.open}>
      <div
        class="fixed inset-0 bg-black/75 flex items-center justify-center z-[1000] p-4"
        onClick={onBackdrop}
        onKeyDown={onKey}
        role="presentation"
      >
        <div
          class="bg-bg-panel border-2 border-border w-[min(520px,calc(100vw-32px))] max-h-[calc(100vh-64px)] flex flex-col shadow-[0_16px_48px_rgba(0,0,0,0.6)] outline-none"
          role="dialog"
          aria-modal="true"
          aria-labelledby="axis-settings-title"
          tabIndex={-1}
          ref={(el) => queueMicrotask(() => el?.focus())}
        >
          <div class="h-0.5 w-full bg-accent flex-shrink-0" />

          <div class="flex items-center justify-between px-3.5 py-2.5 border-b-2 border-border">
            <span id="axis-settings-title" class="text-sm font-semibold text-text tracking-tight">
              Settings
            </span>
            <button class="sc-btn sc-btn-ghost px-2" onClick={props.onClose} aria-label="Close">
              <Icons.x size={14} />
            </button>
          </div>

          <div class="p-3.5 flex flex-col gap-3.5 overflow-auto">
            <div class="flex flex-col gap-1">
              <label class="text-[10px] text-text-dim uppercase tracking-wider" for="axis-endpoint">
                Backend Endpoint
              </label>
              <div class="flex gap-1.5">
                <input
                  id="axis-endpoint"
                  class="sc-input font-mono text-[12px] flex-1 min-w-0"
                  value={endpoint()}
                  onInput={(e) => setEndpoint(e.currentTarget.value)}
                  placeholder="http://host:5002"
                  spellcheck={false}
                />
                <button
                  type="button"
                  class="sc-btn inline-flex items-center gap-1 flex-shrink-0"
                  disabled={probing()}
                  onClick={testEndpoint}
                  title="GET / health probe"
                >
                  {probing() ? (
                    <Icons.loader size={13} class="animate-spin" />
                  ) : (
                    <Icons.activity size={13} />
                  )}
                  Test
                </button>
              </div>
              <Show when={probeMsg()}>
                <p
                  class={`text-[10px] font-mono mt-0.5 ${
                    probeMsg().startsWith('✓') ? 'text-accent-2' : 'text-red'
                  }`}
                >
                  {probeMsg()}
                </p>
              </Show>
              <p class="text-[10px] text-text-faint mt-0.5">
                Pro API for server engine (e.g. VPS :5002). CORS must allow this origin.
              </p>
            </div>

            <div class="flex flex-col gap-1">
              <label class="text-[10px] text-text-dim uppercase tracking-wider" for="axis-engine">
                Engine
              </label>
              <select
                id="axis-engine"
                class="sc-input w-full"
                value={engine()}
                onChange={(e) => setEngine(e.currentTarget.value)}
              >
                <option value="server">Server — PYNE / Pro API</option>
                <option value="pyodide">Client — Pyodide (offline)</option>
              </select>
              <p class="text-[10px] text-text-faint mt-0.5">
                {engine() === 'pyodide' ? (
                  <span class="text-accent-2">Offline-ready</span>
                ) : (
                  <span class="text-accent-3">Requires reachable endpoint</span>
                )}
              </p>
            </div>
          </div>

          <div class="flex items-center gap-2 px-3.5 py-2.5 border-t-2 border-border bg-bg-base">
            <div class="flex-1 text-[10px] text-text-faint font-mono truncate">AXIS · void</div>
            <button type="button" class="sc-btn" onClick={props.onClose}>
              Cancel
            </button>
            <button type="button" class="sc-btn sc-btn-primary inline-flex items-center gap-1" onClick={save}>
              <Icons.check size={13} />
              Save
            </button>
          </div>
        </div>
      </div>
    </Show>
  );
};
