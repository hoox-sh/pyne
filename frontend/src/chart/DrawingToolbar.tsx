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

  return (
    <div
      class="absolute left-2 top-10 z-20 flex flex-col gap-0.5 p-0.5 bg-bg-panel/95 border-2 border-border shadow-lg"
      role="toolbar"
      aria-label="Drawing tools"
    >
      <For each={TOOLS}>
        {(t) => {
          const I = t.icon;
          return (
            <button
              type="button"
              class={`sc-btn sc-btn-ghost w-8 h-8 p-0 flex items-center justify-center ${
                active() === t.id ? 'bg-accent/15 text-accent border-accent' : 'text-text-dim'
              }`}
              title={toolLabel(t.id)}
              aria-label={toolLabel(t.id)}
              aria-pressed={active() === t.id}
              onClick={() => select(t.id)}
            >
              <I size={15} />
            </button>
          );
        }}
      </For>

      <div class="h-px bg-border my-0.5" />

      <button
        type="button"
        class="sc-btn sc-btn-ghost w-8 h-8 p-0 flex items-center justify-center text-text-dim"
        title="Delete selected (Del)"
        aria-label="Delete selected drawing"
        onClick={() => {
          getActiveDrawingLayer()?.deleteSelected();
        }}
      >
        <Icons.trash size={14} />
      </button>
      <button
        type="button"
        class="sc-btn sc-btn-ghost w-8 h-8 p-0 flex items-center justify-center text-text-dim"
        title="Clear all drawings"
        aria-label="Clear all drawings"
        onClick={() => {
          if (store.drawings.length && !confirm('Clear all drawings?')) return;
          getActiveDrawingLayer()?.clearAll();
          clearDrawings();
        }}
      >
        <Icons.eraser size={14} />
      </button>

      <Show when={store.drawings.length > 0}>
        <span
          class="text-[9px] font-mono text-text-faint text-center py-0.5 tabular-nums"
          title="Drawing count"
        >
          {store.drawings.length}
        </span>
      </Show>
    </div>
  );
};
