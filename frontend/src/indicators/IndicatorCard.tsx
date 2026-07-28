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

import { Component, For, createSignal, Show } from 'solid-js';
import type { Indicator } from '../store/types';
import { toggleIndicator, removeIndicator, setIndicatorColor } from '../store';
import { getManager } from '../chart/manager-access';
import { PLOT_PALETTE } from '../chart/series-factory';

interface Props {
  indicator: Indicator;
}

export const IndicatorCard: Component<Props> = (props) => {
  const [editingColor, setEditingColor] = createSignal<string | null>(null);

  const toggle = () => toggleIndicator(props.indicator.id);

  const remove = () => {
    const manager = getManager();
    if (manager) {
      manager.removeOverlays(props.indicator.paneId);
      if (props.indicator.paneId !== 'price' && props.indicator.paneId !== 'volume') {
        manager.destroyPane(props.indicator.paneId);
      }
    }
    removeIndicator(props.indicator.id);
  };

  const changeColor = (plotName: string, color: string) => {
    setIndicatorColor(props.indicator.id, plotName, color);
    setEditingColor(null);
    const manager = getManager();
    if (manager) {
      manager.removeOverlays(props.indicator.paneId);
    }
  };

  return (
    <div class="bg-bg-elev border-2 border-border-soft p-2.5 mb-2">
      <div class="flex items-center justify-between mb-1.5">
        <div class="flex items-center gap-2 min-w-0">
          <button
            class={`w-5 h-5 text-xs flex items-center justify-center border-2 ${
              props.indicator.visible
                ? 'border-accent bg-accent/15 text-accent'
                : 'border-border bg-bg-hover text-text-dim'
            }`}
            onClick={toggle}
            title={props.indicator.visible ? 'Hide indicator' : 'Show indicator'}
          >
            {props.indicator.visible ? '●' : '○'}
          </button>
          <span class="text-xs font-semibold text-text truncate max-w-[120px]">{props.indicator.name}</span>
        </div>
        <button
          class="text-text-faint hover:text-red text-xs px-1 border-2 border-transparent hover:border-border"
          onClick={remove}
          title="Remove indicator"
        >
          ×
        </button>
      </div>
      <div class="flex flex-col gap-0.5">
        <For each={Object.entries(props.indicator.plots)}>
          {([name, { color }]) => (
            <div class="flex items-center gap-2 text-[11px] text-text-dim">
              <button
                class="inline-block w-2.5 h-2.5 flex-shrink-0 cursor-pointer border border-border"
                style={{ background: color }}
                title={`Change color for "${name}"`}
                onClick={() => setEditingColor(editingColor() === name ? null : name)}
              />
              <span class="truncate">{name}</span>
              <Show when={editingColor() === name}>
                <div class="flex gap-1 ml-auto flex-wrap">
                  <For each={PLOT_PALETTE}>
                    {(c) => (
                      <button
                        class="w-3 h-3 cursor-pointer border-2 border-border hover:border-accent"
                        style={{ background: c }}
                        onClick={() => changeColor(name, c)}
                      />
                    )}
                  </For>
                </div>
              </Show>
            </div>
          )}
        </For>
      </div>
    </div>
  );
};
