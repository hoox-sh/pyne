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
 * Floating left toolbar for interactive chart drawings.
 */

import { Component, For, Show } from 'solid-js';
import { store, setDrawingTool, clearDrawings } from '../store';
import type { DrawingToolId } from './drawing-types';
import { toolLabel } from './drawing-types';
import { Icons } from '../ui/icons';
import { getActiveDrawingLayer } from './drawing-layer';

const TOOLS: { id: DrawingToolId; title: string; icon: typeof Icons.cursor }[] = [
  { id: 'cursor', title: 'Cursor (select)', icon: Icons.cursor },
  { id: 'hline', title: 'Horizontal line', icon: Icons.minus },
  { id: 'trend', title: 'Trend line', icon: Icons.trend },
  { id: 'ray', title: 'Ray', icon: Icons.ray },
  { id: 'rect', title: 'Rectangle', icon: Icons.square },
  { id: 'fib', title: 'Fibonacci', icon: Icons.fib },
  { id: 'measure', title: 'Measure', icon: Icons.ruler },
  { id: 'text', title: 'Text note', icon: Icons.type },
];

export const DrawingToolbar: Component = () => {
  const active = () => store.drawingTool;

  const select = (id: DrawingToolId) => {
    setDrawingTool(id);
    getActiveDrawingLayer()?.setTool(id);
  };

  const iconPx = 20;
  const btnClass =
    'sc-btn sc-btn-ghost w-10 h-10 min-w-10 min-h-10 p-0 flex items-center justify-center';

  return (
    <div
      class="absolute left-2 top-10 z-20 flex flex-col gap-1 p-1 bg-bg-panel/95 border-2 border-border shadow-lg"
      role="toolbar"
      aria-label="Drawing tools"
      data-testid="axis-drawing-toolbar"
    >
      <For each={TOOLS}>
        {(t) => {
          const I = t.icon;
          return (
            <button
              type="button"
              class={`${btnClass} ${
                active() === t.id ? 'bg-accent/15 text-accent border-accent' : 'text-text-dim'
              }`}
              title={toolLabel(t.id)}
              aria-label={toolLabel(t.id)}
              aria-pressed={active() === t.id}
              onClick={() => select(t.id)}
            >
              <I size={iconPx} strokeWidth={2.25} />
            </button>
          );
        }}
      </For>

      <div class="h-px bg-border my-0.5" />

      <button
        type="button"
        class={`${btnClass} text-text-dim`}
        title="Delete selected (Del)"
        aria-label="Delete selected drawing"
        onClick={() => {
          getActiveDrawingLayer()?.deleteSelected();
        }}
      >
        <Icons.trash size={iconPx} strokeWidth={2.25} />
      </button>
      <button
        type="button"
        class={`${btnClass} text-text-dim`}
        title="Clear all drawings"
        aria-label="Clear all drawings"
        onClick={() => {
          if (store.drawings.length && !confirm('Clear all drawings?')) return;
          getActiveDrawingLayer()?.clearAll();
          clearDrawings();
        }}
      >
        <Icons.eraser size={iconPx} strokeWidth={2.25} />
      </button>

      <Show when={store.drawings.length > 0}>
        <span
          class="text-[10px] font-mono text-text-faint text-center py-0.5 tabular-nums"
          title="Drawing count"
        >
          {store.drawings.length}
        </span>
      </Show>
    </div>
  );
};
