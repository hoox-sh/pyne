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
