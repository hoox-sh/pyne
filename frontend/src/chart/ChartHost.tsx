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

import { Component, Show, createEffect, createMemo, onMount, onCleanup, untrack } from 'solid-js';
import { PaneManager } from './pane-manager';
import { DrawingToolbar } from './DrawingToolbar';
import { PineTableHud } from './PineTableHud';
import { store } from '../store';
import { HooxLoader } from '../ui/HooxLoader';
import {
  getManager,
  setManager,
  getDrawingLayer,
  setDrawingLayer,
  setDataToChart,
  getActiveDrawingLayer,
} from './manager-access';

export {
  getManager,
  getDrawingLayer,
  setDataToChart,
  getActiveDrawingLayer,
} from './manager-access';

/** Imperative chart mount only — never put Solid children inside this node. */
let panesEl: HTMLDivElement | undefined;

export const ChartHost: Component = () => {
  const emptyHint = createMemo(() => {
    if (store.bars.length > 0) return null;
    if (store.status === 'loading') return { title: 'Loading market data…', sub: store.statusMessage || '' };
    if (store.status === 'error') return { title: 'Could not load chart', sub: store.statusMessage || 'Try again' };
    if (store.status === 'running') return { title: 'Running script…', sub: store.statusMessage || '' };
    return {
      title: 'Load data to begin',
      sub: `${store.symbol} · ${store.interval} — press Load or pick a watchlist symbol`,
    };
  });

  onMount(() => {
    if (!panesEl) return;
    const manager = new PaneManager(panesEl);
    setManager(manager);

    for (const pane of store.panes) {
      manager.createPane(pane.id, pane.type, pane.label || pane.type, pane.height || undefined);
    }
    manager.syncTimeScales();
    manager.syncCrosshair(() => {});

    if (store.bars.length) {
      setDataToChart(store.bars, { fit: true });
    }
  });

  // Full history reloads only (loadBars bumps chartDataGen). Live ticks use
  // manager.appendBar via multiplex — never full setData + fitContent here.
  // untrack(bars) is required: reading store.bars would re-subscribe to every tick.
  createEffect(() => {
    const gen = store.chartDataGen;
    void gen;
    if (!getManager()) return;
    untrack(() => {
      if (store.bars.length) setDataToChart(store.bars, { fit: true });
    });
  });

  // Keep tool in sync when store changes from toolbar
  createEffect(() => {
    const tool = store.drawingTool;
    getDrawingLayer()?.setTool(tool);
  });

  onCleanup(() => {
    const drawingLayer = getDrawingLayer();
    if (drawingLayer) {
      drawingLayer.destroy();
      setDrawingLayer(undefined);
    }
    const manager = getManager();
    if (manager) {
      manager.dispose();
      setManager(undefined);
    }
  });

  return (
    // Outer shell owns Solid children (empty overlay). PaneManager only
    // mutates the inner ref node — Solid must never reconcile that subtree
    // or it wipes LWC canvases when the empty-state <Show> flips off.
    <div class="flex-1 flex flex-col min-h-0 relative bg-bg-base">
      <div
        ref={(el) => {
          panesEl = el;
        }}
        class="flex-1 flex flex-col min-h-0"
        data-axis-panes
      />
      <Show when={store.bars.length > 0}>
        <DrawingToolbar />
        <PineTableHud />
      </Show>
      <Show when={emptyHint()}>
        {(hint) => (
          <div class="absolute inset-0 flex flex-col items-center justify-center gap-2 z-[5] pointer-events-none px-6">
            <div
              class={`text-[11px] tracking-[0.18em] uppercase font-medium ${
                store.status === 'error' ? 'text-red' : 'text-text-faint'
              }`}
            >
              {hint().title}
            </div>
            <Show when={hint().sub}>
              <div class="text-[11px] text-text-faint/80 font-mono text-center max-w-md">{hint().sub}</div>
            </Show>
            <Show when={store.status === 'loading' || store.status === 'running'}>
              <div class="mt-3">
                <HooxLoader
                  size="l"
                  layout="stack"
                  label={store.status === 'running' ? 'Running' : 'Loading'}
                />
              </div>
            </Show>
          </div>
        )}
      </Show>
    </div>
  );
};
