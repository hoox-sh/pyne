import { Component, For, createEffect, createSignal, Show, createMemo } from 'solid-js';
import { store, setStore, persist, setStatus, setActivePlugin } from '../store';
import { Icons } from './icons';
import { HooxLoader } from './HooxLoader';
import { probeEndpoint } from '../indicators/runner';
import { listEngines } from '../engines/catalog';
import { listStorages } from '../storage/catalog';
import { CapabilityBadges, engineOptionLabel } from './plugin-badges';
import { getEngine } from '../engines/catalog';
import {
  WATCHLIST_INTERVALS,
  WATCHLIST_REFRESH_OPTIONS,
} from '../data/watchlist-tickers';
import { loadSymbolData } from '../data/load-symbol';

interface Props {
  open: boolean;
  onClose: () => void;
}

export const SettingsDialog: Component<Props> = (props) => {
  const [endpoint, setEndpoint] = createSignal(store.endpoint);
  const [engine, setEngine] = createSignal(store.engine);
  const [storage, setStorage] = createSignal(store.activePlugins?.storage || 'local');
  const [chartInterval, setChartInterval] = createSignal(store.interval);
  const [refreshSec, setRefreshSec] = createSignal(store.watchlist.refreshSec || 15);
  const [preferAfterLoad, setPreferAfterLoad] = createSignal(!!store.live.preferAfterLoad);
  const [rerunOn, setRerunOn] = createSignal<'every-tick' | 'bar-close'>(
    store.live.rerunOn === 'bar-close' ? 'bar-close' : 'every-tick',
  );
  const [hudCompact, setHudCompact] = createSignal(!!store.telemetry?.hud?.compact);
  const [probing, setProbing] = createSignal(false);
  const [probeMsg, setProbeMsg] = createSignal('');

  const engines = createMemo(() => listEngines());
  const storages = createMemo(() => listStorages());

  const selectedEngine = createMemo(() => getEngine(engine()) || engines()[0]);
  /** Show endpoint field only for engines that take a backend URL (not pyodide). */
  const needsEndpoint = createMemo(() => {
    const e = selectedEngine();
    return e?.id === 'server' || !!e?.configSchema?.endpoint;
  });

  createEffect(() => {
    if (props.open) {
      setEndpoint(store.endpoint);
      setEngine(store.engine);
      setStorage(store.activePlugins?.storage || 'local');
      setChartInterval(store.interval);
      setRefreshSec(store.watchlist.refreshSec || 15);
      setPreferAfterLoad(!!store.live.preferAfterLoad);
      setRerunOn(store.live.rerunOn === 'bar-close' ? 'bar-close' : 'every-tick');
      setHudCompact(!!store.telemetry?.hud?.compact);
      setProbeMsg('');
    }
  });

  const save = async () => {
    const prevInterval = store.interval;
    const nextInterval = chartInterval().trim() || prevInterval;
    const nextRefresh = Math.min(120, Math.max(5, Math.round(Number(refreshSec()) || 15)));

    setStore('endpoint', endpoint().trim());
    setStore('interval', nextInterval);
    setStore('watchlist', 'refreshSec', nextRefresh);
    setStore('live', 'preferAfterLoad', preferAfterLoad());
    setStore('live', 'rerunOn', rerunOn());
    setStore('telemetry', 'hud', 'compact', hudCompact());
    setActivePlugin('engine', engine());
    setActivePlugin('storage', storage());
    persist();
    setStatus(
      'ready',
      `Settings saved · ${nextInterval} · refresh ${nextRefresh}s · engine=${engine()} · live re-run=${rerunOn()}`,
    );
    // Reload chart bars if default interval changed
    if (nextInterval !== prevInterval && store.symbol) {
      void loadSymbolData(store.symbol, nextInterval, store.source);
    }
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
          data-testid="axis-settings"
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
              <label class="text-[10px] text-text-dim uppercase tracking-wider" for="axis-engine">
                Calculation engine
              </label>
              <select
                id="axis-engine"
                class="sc-input w-full"
                value={engine()}
                onChange={(e) => setEngine(e.currentTarget.value)}
              >
                <For each={engines()}>
                  {(en) => <option value={en.id}>{engineOptionLabel(en)}</option>}
                </For>
              </select>
              <Show when={selectedEngine()}>
                {(en) => (
                  <div class="mt-0.5">
                    <CapabilityBadges
                      capabilities={en().capabilities}
                      builtIn={en().builtIn}
                    />
                    <p class="text-[10px] text-text-faint mt-0.5">{en().description}</p>
                  </div>
                )}
              </Show>
            </div>

            <Show when={needsEndpoint()}>
              <div class="flex flex-col gap-1">
                <label
                  class="text-[10px] text-text-dim uppercase tracking-wider"
                  for="axis-endpoint"
                >
                  Backend Endpoint
                </label>
                <div class="flex gap-1.5">
                  <input
                    id="axis-endpoint"
                    class="sc-input font-mono text-[12px] flex-1 min-w-0"
                    value={endpoint()}
                    onInput={(e) => setEndpoint(e.currentTarget.value)}
                    placeholder="http://host:5002 or Worker URL"
                    spellcheck={false}
                  />
                  <button
                    type="button"
                    class="sc-btn inline-flex items-center gap-1 flex-shrink-0"
                    disabled={probing()}
                    onClick={testEndpoint}
                    title="GET / health probe"
                  >
                    {probing() ? <HooxLoader size="xs" /> : <Icons.activity size={13} />}
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
                  Used by the server engine and cloud script storage. CORS must allow this origin.
                </p>
              </div>
            </Show>

            <div class="flex flex-col gap-1">
              <label class="text-[10px] text-text-dim uppercase tracking-wider" for="axis-storage">
                Script storage
              </label>
              <select
                id="axis-storage"
                class="sc-input w-full"
                value={storage()}
                onChange={(e) => setStorage(e.currentTarget.value)}
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
              <p class="text-[10px] text-text-faint mt-0.5">
                Where saved Pine scripts live (local browser, cloud Worker, or git). Configure
                credentials under Manager → Script Library.
              </p>
            </div>

            <div class="border-t border-border-soft pt-3 flex flex-col gap-3">
              <div class="text-[10px] text-text-dim uppercase tracking-wider font-semibold">
                Chart &amp; watchlist
              </div>

              <div class="flex flex-col gap-1">
                <label
                  class="text-[10px] text-text-dim uppercase tracking-wider"
                  for="axis-default-interval"
                >
                  Default interval
                </label>
                <select
                  id="axis-default-interval"
                  class="sc-input w-full"
                  value={chartInterval()}
                  onChange={(e) => setChartInterval(e.currentTarget.value)}
                >
                  <For each={[...WATCHLIST_INTERVALS]}>
                    {(i) => <option value={i}>{i}</option>}
                  </For>
                </select>
                <p class="text-[10px] text-text-faint mt-0.5">
                  Used when loading symbols from the watchlist and top bar. Changing this reloads
                  the active chart.
                </p>
              </div>

              <div class="border-t border-border-soft pt-3 flex flex-col gap-3">
                <div class="text-[10px] text-text-dim uppercase tracking-wider font-semibold">
                  Live stream
                </div>

                <label class="flex items-start gap-2 cursor-pointer" for="axis-prefer-live">
                  <input
                    id="axis-prefer-live"
                    type="checkbox"
                    class="mt-0.5"
                    checked={preferAfterLoad()}
                    onChange={(e) => setPreferAfterLoad(e.currentTarget.checked)}
                  />
                  <span>
                    <span class="text-[12px] text-text">Auto-start live after Load</span>
                    <span class="block text-[10px] text-text-faint mt-0.5">
                      Prefer WebSocket feed immediately after historical REST load. Off by default
                      to avoid surprise sockets.
                    </span>
                  </span>
                </label>

                <div class="flex flex-col gap-1">
                  <label
                    class="text-[10px] text-text-dim uppercase tracking-wider"
                    for="axis-rerun-on"
                  >
                    Indicator re-run on live bars
                  </label>
                  <select
                    id="axis-rerun-on"
                    class="sc-input w-full"
                    value={rerunOn()}
                    onChange={(e) =>
                      setRerunOn(
                        e.currentTarget.value === 'bar-close' ? 'bar-close' : 'every-tick',
                      )
                    }
                  >
                    <option value="every-tick">Every tick (responsive)</option>
                    <option value="bar-close">Bar close only (lighter)</option>
                  </select>
                  <p class="text-[10px] text-text-faint mt-0.5">
                    Bar-close uses venue closed flags (Binance/OKX/Bybit) or bar time advance.
                  </p>
                </div>

                <label class="flex items-start gap-2 cursor-pointer" for="axis-hud-compact">
                  <input
                    id="axis-hud-compact"
                    type="checkbox"
                    class="mt-0.5"
                    checked={hudCompact()}
                    onChange={(e) => setHudCompact(e.currentTarget.checked)}
                  />
                  <span>
                    <span class="text-[12px] text-text">Compact connection HUD</span>
                    <span class="block text-[10px] text-text-faint mt-0.5">
                      Hide SRC/STR/ENG/STO plane chips; keep Live · Tick · Engine latency.
                    </span>
                  </span>
                </label>
              </div>

              <div class="flex flex-col gap-1">
                <label
                  class="text-[10px] text-text-dim uppercase tracking-wider"
                  for="axis-watchlist-refresh"
                >
                  Watchlist quote refresh
                </label>
                <select
                  id="axis-watchlist-refresh"
                  class="sc-input w-full"
                  value={String(refreshSec())}
                  onChange={(e) => setRefreshSec(Number(e.currentTarget.value))}
                >
                  <For each={[...WATCHLIST_REFRESH_OPTIONS]}>
                    {(o) => <option value={o.value}>{o.label}</option>}
                  </For>
                </select>
                <p class="text-[10px] text-text-faint mt-0.5">
                  How often the watchlist polls live prices (source-aware: Binance / OKX / Bybit /
                  Coinbase). Also adjustable from the watchlist panel.
                </p>
              </div>
            </div>
          </div>

          <div class="flex items-center gap-2 px-3.5 py-2.5 border-t-2 border-border bg-bg-base">
            <div class="flex-1 text-[10px] text-text-faint font-mono truncate">AXIS · plugins</div>
            <button type="button" class="sc-btn" onClick={props.onClose}>
              Cancel
            </button>
            <button
              type="button"
              class="sc-btn sc-btn-primary inline-flex items-center gap-1"
              onClick={save}
            >
              <Icons.check size={13} />
              Save
            </button>
          </div>
        </div>
      </div>
    </Show>
  );
};
