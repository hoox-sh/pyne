/**
 * Capability badges + labels for plugin catalog UI.
 */

import { Component, For, Show } from 'solid-js';
import type { PluginCapabilities } from '../plugins/types';
import { CAP_META, capabilityKeys, type CapKey } from './plugin-badges-utils';

export type { CapKey };
export { capabilityKeys, engineOptionLabel } from './plugin-badges-utils';

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
        {(k: CapKey) => (
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
