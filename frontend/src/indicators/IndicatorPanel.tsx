import { Component, For, Show } from 'solid-js';
import { store } from '../store';
import { IndicatorCard } from './IndicatorCard';

export const IndicatorPanel: Component = () => {
  return (
    <Show when={store.indicatorPanel.open}>
      <div class="w-56 bg-bg-panel border-l border-border flex flex-col flex-shrink-0 overflow-hidden">
        <div class="px-2.5 py-1.5 border-b border-border text-[11px] text-text-dim uppercase tracking-wider font-semibold">
          Indicators
        </div>
        <div class="flex-1 overflow-y-auto p-2">
          <Show
            when={store.scripts.length > 0}
            fallback={<div class="text-text-faint text-[11px] italic p-2">No indicators running.</div>}
          >
            <For each={store.scripts}>
              {(ind) => <IndicatorCard indicator={ind} />}
            </For>
          </Show>
        </div>
      </div>
    </Show>
  );
};
