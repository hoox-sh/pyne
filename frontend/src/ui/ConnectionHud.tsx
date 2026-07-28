// Copyright (C) 2024-2026 jango_blockchained
//
// This file is part of pynescript.
//
// pynescript is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// pynescript is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
//
// SPDX-License-Identifier: AGPL-3.0-or-later

/**
 * AXIS Connection HUD — glanceable transport / engine / tick telemetry.
 * Composed into StatusBar; reads ephemeral store.telemetry.
 */

import { Component, For, Show, createMemo, createSignal, onCleanup, onMount } from 'solid-js';
import { store } from '../store';
import type { ConnState, PlaneTelemetry, TransportClass } from '../store/types';
import {
  connDotClass,
  formatLatency,
  formatTickAge,
  transportLabel,
} from './telemetry';
import { Icons } from './icons';
import { getEngine } from '../engines/catalog';
import { defaultStreamForSource } from '../streams/catalog';

function PlaneChip(props: {
  label: string;
  plane: PlaneTelemetry;
  title?: string;
}) {
  const t = () => props.plane;
  return (
    <span
      class="inline-flex items-center gap-1 px-1.5 py-0.5 border border-border-soft bg-bg-elev/60 max-w-[148px]"
      title={
        props.title ||
        `${props.label}: ${t().name} · ${transportLabel(t().transport)} · ${t().state}${
          t().detail ? ` · ${t().detail}` : ''
        }${t().error ? ` · ${t().error}` : ''}`
      }
      data-plane={props.label.toLowerCase()}
    >
      <span
        class={`inline-block w-1.5 h-1.5 rounded-full flex-shrink-0 ${connDotClass(t().state)}`}
        aria-hidden="true"
      />
      <span class="text-[9px] font-mono uppercase text-text-faint tracking-wide">{props.label}</span>
      <span class="text-[10px] font-mono text-text-dim truncate max-w-[52px]">{t().id}</span>
      <TransportBadge transport={t().transport} />
      <Show when={t().latencyMs != null}>
        <span class="text-[10px] font-mono tabular-nums text-text-faint">{formatLatency(t().latencyMs)}</span>
      </Show>
    </span>
  );
}

function TransportBadge(props: { transport: TransportClass }) {
  const color = () => {
    switch (props.transport) {
      case 'ws':
        return 'border-accent-2/40 text-accent-2';
      case 'rest':
        return 'border-accent-3/40 text-accent-3';
      case 'broker':
        return 'border-accent/40 text-accent';
      case 'local':
        return 'border-border text-text-faint';
      default:
        return 'border-border text-text-faint';
    }
  };
  return (
    <span class={`px-1 py-px border text-[8px] font-mono leading-none ${color()}`}>
      {transportLabel(props.transport)}
    </span>
  );
}

function TickPulse() {
  const tick = () => store.telemetry?.lastTick;
  const [now, setNow] = createSignal(Date.now());
  onMount(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    onCleanup(() => clearInterval(id));
  });

  const fresh = () => {
    const t = tick();
    if (!t) return false;
    return now() - t.at < 2000;
  };

  const dirColor = () => {
    const d = tick()?.dir;
    if (d === 'up') return 'text-accent-2';
    if (d === 'down') return 'text-red';
    return 'text-text-faint';
  };

  /** Fixed-width price so digit changes don't resize the chip. */
  const priceText = () => {
    const t = tick();
    if (!t) return '—';
    return t.price.toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  };

  return (
    <span
      class="inline-flex items-center gap-1 px-1.5 py-0.5 border border-border-soft font-mono text-[10px] h-[22px] box-border flex-shrink-0"
      title={
        tick()
          ? `Last tick ${tick()!.price} @ ${tick()!.time} (${formatTickAge(tick()!.at, now())})`
          : 'No live ticks yet'
      }
      data-testid="axis-tick-indicator"
    >
      {/* Fixed 8×8 box; ping is absolute and clipped so it cannot grow layout */}
      <span
        class="relative w-2 h-2 flex-shrink-0 overflow-visible"
        style={{ width: '8px', height: '8px' }}
        aria-hidden="true"
      >
        <span
          class={`absolute inset-0 rounded-full ${
            store.live.active && store.stream.status === 'connected'
              ? 'bg-accent-2'
              : 'bg-border'
          }`}
        />
        <Show when={fresh()}>
          <span
            class="absolute left-0 top-0 w-2 h-2 rounded-full bg-accent-2 animate-ping opacity-50 pointer-events-none"
            style={{ width: '8px', height: '8px' }}
          />
        </Show>
      </span>
      <span class="text-[9px] uppercase text-text-faint w-[2.5ch] flex-shrink-0">tick</span>
      <span
        class={`tabular-nums text-right w-[7.5ch] flex-shrink-0 overflow-hidden text-ellipsis ${dirColor()}`}
      >
        {priceText()}
      </span>
      <span class="text-text-faint tabular-nums w-[3ch] flex-shrink-0 text-right">
        {tick() ? formatTickAge(tick()!.at, now()) : '—'}
      </span>
    </span>
  );
}

function LiveBadge() {
  const st = () => store.stream.status;
  const label = () => {
    if (!store.live.active) return 'OFF';
    if (st() === 'connected') return 'LIVE';
    if (st() === 'connecting') return '…';
    if (st() === 'error') return 'ERR';
    return 'OFF';
  };
  const cls = () => {
    if (!store.live.active) return 'text-text-faint border-border';
    if (st() === 'connected') return 'text-accent-2 border-accent-2/50';
    if (st() === 'connecting') return 'text-orange border-orange/40';
    if (st() === 'error') return 'text-red border-red/40';
    return 'text-text-faint border-border';
  };
  return (
    <span class={`px-1.5 py-0.5 border text-[9px] font-mono tracking-wider ${cls()}`} title="Live stream mode">
      {label()}
    </span>
  );
}

function EngineModeChip() {
  const meta = createMemo(() => {
    const eng = getEngine(store.engine);
    const mode =
      (store.pluginsConfig?.[`engine:${store.engine}`]?.mode as string) ||
      (store.pluginsConfig?.[store.engine]?.mode as string) ||
      'interpret';
    return {
      id: store.engine,
      name: eng?.name || store.engine,
      offline: !!eng?.capabilities?.offline,
      mode: String(mode),
      latency: store.telemetry?.engine?.latencyMs ?? store.lastRunMs,
      state: (store.telemetry?.engine?.state || 'idle') as ConnState,
    };
  });

  return (
    <span
      class="inline-flex items-center gap-1 px-1.5 py-0.5 border border-border-soft font-mono text-[10px]"
      title={`${meta().name} · ${meta().mode} · ${formatLatency(meta().latency)}`}
      data-testid="axis-engine-chip"
    >
      <span class={`w-1.5 h-1.5 rounded-full ${connDotClass(meta().state)}`} />
      {meta().offline ? <Icons.activity size={11} class="text-accent-2" /> : <Icons.wifi size={11} class="text-accent-3" />}
      <span class="truncate max-w-[72px]">{meta().id}</span>
      <span class="text-[9px] text-text-faint uppercase">{meta().mode}</span>
      <span class="tabular-nums text-text-dim">{formatLatency(meta().latency)}</span>
    </span>
  );
}

function PairingWarn() {
  const warn = createMemo(() => {
    const src = store.source;
    const expected = defaultStreamForSource(src);
    const actual = store.live.streamId || store.activePlugins?.stream;
    if (!actual || actual === expected) return null;
    // mock/csv with mock-poll is fine; only warn venue mismatch
    if (src === 'mock-walk' || src === 'csv-upload') return null;
    return `Stream ${actual} ≠ default ${expected} for ${src}`;
  });
  return (
    <Show when={warn()}>
      <span class="text-[9px] font-mono text-orange truncate max-w-[140px]" title={warn()!}>
        ⚠ pair
      </span>
    </Show>
  );
}

export const ConnectionHud: Component = () => {
  const tel = () => store.telemetry;
  const compact = () => tel()?.hud?.compact;

  return (
    <div
      class="flex items-center gap-1.5 flex-nowrap min-w-0 flex-shrink-0"
      data-testid="axis-connection-hud"
      role="status"
      aria-label="Connection status"
    >
      <LiveBadge />
      <TickPulse />
      <EngineModeChip />
      <Show when={!compact()}>
        <For
          each={[
            { label: 'SRC', plane: () => tel()?.source },
            { label: 'STR', plane: () => tel()?.stream },
            { label: 'ENG', plane: () => tel()?.engine },
            { label: 'STO', plane: () => tel()?.storage },
          ]}
        >
          {(item) => (
            <Show when={item.plane()}>
              {(p) => <PlaneChip label={item.label} plane={p()} />}
            </Show>
          )}
        </For>
        <PairingWarn />
      </Show>
    </div>
  );
};
