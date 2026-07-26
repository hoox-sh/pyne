import { Component, For, Show } from 'solid-js';
import { store, setStore, persist, setIndicatorWidth } from '../store';
import { IndicatorCard } from './IndicatorCard';
import { ResizeHandle } from '../ui/ResizeHandle';

export const IndicatorPanel: Component = () => {
  return (
    <Show when={store.indicatorPanel.open}>
      <div
        class="bg-bg-panel border-l-2 border-border flex flex-col flex-shrink-0 overflow-hidden relative"
        style={{ width: `${store.indicatorPanel.width}px` }}
      >
        <ResizeHandle
          direction="grow-left"
          getWidth={() => store.indicatorPanel.width}
          setWidth={setIndicatorWidth}
          min={160}
          max={400}
          class="absolute top-0 left-0 bottom-0 z-10"
        />
        <div class="flex items-center justify-between px-2.5 py-1.5 border-b-2 border-border text-[10px] text-text-dim uppercase tracking-wider font-semibold">
          <span>Indicators</span>
          <button
            class="sc-btn sc-btn-ghost px-1.5 text-[11px] leading-none normal-case tracking-normal"
            onClick={() => {
              setStore('indicatorPanel', 'open', false);
              persist();
            }}
          >
            ›
          </button>
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
