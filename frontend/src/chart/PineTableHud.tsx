/**
 * HUD overlay for Pine ``table.*`` drawings (screen-space, not price scale).
 */

import { Component, For, Show, createMemo } from 'solid-js';
import { store } from '../store';
import type { RunResult } from '../indicators/runner';

interface TableCell {
  row: number;
  col: number;
  text: string;
  text_color?: string;
  bgcolor?: string;
}

interface PineTable {
  type: string;
  position?: string;
  rows?: number;
  columns?: number;
  cells?: TableCell[];
  frame_color?: string;
  bgcolor?: string;
}

function positionClass(pos: string): string {
  const p = (pos || 'top_right').toLowerCase().replace('position.', '');
  if (p.includes('top') && p.includes('left')) return 'top-2 left-12';
  if (p.includes('top') && p.includes('center')) return 'top-2 left-1/2 -translate-x-1/2';
  if (p.includes('top') && p.includes('right')) return 'top-2 right-14';
  if (p.includes('middle') && p.includes('left')) return 'top-1/2 left-12 -translate-y-1/2';
  if (p.includes('middle') && p.includes('right')) return 'top-1/2 right-14 -translate-y-1/2';
  if (p.includes('bottom') && p.includes('left')) return 'bottom-10 left-12';
  if (p.includes('bottom') && p.includes('center')) return 'bottom-10 left-1/2 -translate-x-1/2';
  if (p.includes('bottom') && p.includes('right')) return 'bottom-10 right-14';
  return 'top-2 right-14';
}

export const PineTableHud: Component = () => {
  const tables = createMemo(() => {
    const r = store.lastRun as RunResult | null;
    const drawings = (r as { drawings?: unknown[] } | null)?.drawings;
    if (!drawings?.length) return [] as PineTable[];
    return drawings.filter(
      (d): d is PineTable =>
        !!d && typeof d === 'object' && (d as PineTable).type === 'table',
    ) as PineTable[];
  });

  return (
    <Show when={tables().length > 0}>
      <For each={tables()}>
        {(tb) => {
          const rows = Math.max(1, tb.rows || 1);
          const cols = Math.max(1, tb.columns || 1);
          const grid: (TableCell | null)[][] = Array.from({ length: rows }, () =>
            Array.from({ length: cols }, () => null),
          );
          for (const c of tb.cells || []) {
            if (c.row >= 0 && c.row < rows && c.col >= 0 && c.col < cols) {
              grid[c.row]![c.col] = c;
            }
          }
          // Only show tables that have at least one non-empty cell
          const hasText = (tb.cells || []).some((c) => (c.text || '').trim());
          return (
            <Show when={hasText}>
              <div
                class={`absolute z-[6] pointer-events-none ${positionClass(tb.position || '')}`}
                role="table"
                aria-label="Pine table"
              >
                <table
                  class="border-collapse text-[10px] font-mono shadow-lg"
                  style={{
                    'border-color': tb.frame_color || '#3a3d4a',
                    'background-color': tb.bgcolor || 'rgba(17,18,24,0.92)',
                  }}
                >
                  <tbody>
                    <For each={grid}>
                      {(row) => (
                        <tr>
                          <For each={row}>
                            {(cell) => (
                              <td
                                class="border border-border px-1.5 py-0.5 min-w-[1.5rem] text-center"
                                style={{
                                  color: cell?.text_color || '#eceef4',
                                  'background-color':
                                    cell?.bgcolor && !String(cell.bgcolor).includes('255,255,255')
                                      ? cell.bgcolor
                                      : undefined,
                                }}
                              >
                                {cell?.text ?? ''}
                              </td>
                            )}
                          </For>
                        </tr>
                      )}
                    </For>
                  </tbody>
                </table>
              </div>
            </Show>
          );
        }}
      </For>
    </Show>
  );
};
