/**
 * Capability badges + labels for plugin catalog UI.
 */

import { Component, For, Show } from 'solid-js';
import type { PluginBase, PluginCapabilities } from '../plugins/types';

export type CapKey = keyof PluginCapabilities;

const CAP_META: Record<
  CapKey,
  { label: string; class: string; title: string }
> = {
  offline: {
    label: 'offline',
    class: 'border-accent-2/40 text-accent-2',
    title: 'Works without network',
  },
  needsNetwork: {
    label: 'network',
    class: 'border-accent-3/40 text-accent-3',
    title: 'Requires network access',
  },
  needsAuth: {
    label: 'auth',
    class: 'border-orange/40 text-orange',
    title: 'Requires credentials / API key',
  },
  needsProxy: {
    label: 'proxy',
    class: 'border-text-faint/40 text-text-faint',
    title: 'May need CORS proxy',
  },
};

export function capabilityKeys(caps?: PluginCapabilities | null): CapKey[] {
  if (!caps) return [];
  return (Object.keys(CAP_META) as CapKey[]).filter((k) => caps[k]);
}

export function engineOptionLabel(p: PluginBase): string {
  const caps = capabilityKeys(p.capabilities);
  const tags = caps.length ? ` [${caps.join(', ')}]` : '';
  const extra = p.builtIn === false ? ' · plugin' : '';
  return `${p.name}${tags}${extra}`;
}

export const CapabilityBadges: Component<{
  capabilities?: PluginCapabilities | null;
  builtIn?: boolean;
  kind?: string;
  active?: boolean;
  compact?: boolean;
}> = (props) => {
  const keys = () => capabilityKeys(props.capabilities);
  return (
    <span class={`inline-flex flex-wrap items-center gap-0.5 ${props.compact ? '' : 'mt-0.5'}`}>
      <Show when={props.kind}>
        <span class="px-1 py-px border border-border text-[9px] font-mono uppercase text-text-faint">
          {props.kind}
        </span>
      </Show>
      <Show when={props.builtIn}>
        <span class="px-1 py-px border border-border text-[9px] font-mono text-text-faint">built-in</span>
      </Show>
      <Show when={props.builtIn === false}>
        <span class="px-1 py-px border border-accent/40 text-[9px] font-mono text-accent">plugin</span>
      </Show>
      <Show when={props.active}>
        <span class="px-1 py-px border border-accent-2/50 text-[9px] font-mono text-accent-2">active</span>
      </Show>
      <For each={keys()}>
        {(k) => (
          <span
            class={`px-1 py-px border text-[9px] font-mono ${CAP_META[k].class}`}
            title={CAP_META[k].title}
          >
            {CAP_META[k].label}
          </span>
        )}
      </For>
    </span>
  );
};
