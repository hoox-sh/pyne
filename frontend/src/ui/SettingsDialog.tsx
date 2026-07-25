import { Component, createSignal, Show } from 'solid-js';
import { store, setStore, persist } from '../store';

interface Props {
  open: boolean;
  onClose: () => void;
}

export const SettingsDialog: Component<Props> = (props) => {
  const [endpoint, setEndpoint] = createSignal(store.endpoint);
  const [engine, setEngine] = createSignal(store.engine);

  const save = () => {
    setStore('endpoint', endpoint());
    setStore('engine', engine());
    persist();
    props.onClose();
  };

  return (
    <Show when={props.open}>
      <div class="fixed inset-0 bg-black/55 flex items-center justify-center z-[1000] backdrop-blur-[2px]">
        <div class="bg-bg-panel border border-border rounded-md w-[min(540px,calc(100vw-32px))] max-h-[calc(100vh-64px)] flex flex-col shadow-[0_10px_30px_rgba(0,0,0,0.4)]">
          <div class="flex items-center justify-between px-3.5 py-2.5 border-b border-border">
            <span class="text-sm font-semibold text-text">Settings</span>
            <button class="text-text-dim hover:text-text text-xs bg-transparent border-none cursor-pointer" onClick={props.onClose}>×</button>
          </div>
          <div class="p-3.5 flex flex-col gap-2.5 overflow-auto">
            <div class="flex flex-col gap-1">
              <label class="text-xs text-text-dim uppercase tracking-wider">Backend Endpoint</label>
              <input
                class="bg-bg-elev text-text border border-border rounded px-2 py-1.5 text-sm font-mono outline-none focus:border-accent"
                value={endpoint()}
                onInput={(e) => setEndpoint(e.currentTarget.value)}
              />
            </div>
            <div class="flex flex-col gap-1">
              <label class="text-xs text-text-dim uppercase tracking-wider">Engine</label>
              <select
                class="bg-bg-elev text-text border border-border rounded px-2 py-1.5 text-sm outline-none focus:border-accent"
                value={engine()}
                onChange={(e) => setEngine(e.currentTarget.value)}
              >
                <option value="server">Server-Side</option>
                <option value="pyodide">Client-Side (Pyodide)</option>
              </select>
            </div>
          </div>
          <div class="flex items-center gap-2 px-3.5 py-2.5 border-t border-border bg-bg-base rounded-b-md">
            <div class="flex-1" />
            <button class="bg-bg-elev text-text border border-border rounded px-3 py-1 text-xs cursor-pointer hover:bg-bg-hover" onClick={props.onClose}>
              Cancel
            </button>
            <button class="bg-accent border border-accent text-white rounded px-3 py-1 text-xs cursor-pointer font-medium hover:bg-accent-hover" onClick={save}>
              Save
            </button>
          </div>
        </div>
      </div>
    </Show>
  );
};
