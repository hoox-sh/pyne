import { Component, For, Show } from 'solid-js';
import { store, setIndicatorPanelOpen, setIndicatorWidth } from '../store';
import { IndicatorCard } from './IndicatorCard';
import { ResizeHandle } from '../ui/ResizeHandle';

export const IndicatorPanel: Component = () => {
  return (
    <Show when={store.indicatorPanel.open}>
      <aside
        class="flex flex-col flex-shrink-0 bg-bg-panel border-l-2 border-border min-h-0 overflow-hidden relative z-10"
        style={{ width: `${store.indicatorPanel.width}px` }}
        data-axis-indicator-panel
        data-testid="axis-indicators"
        aria-label="Indicators"
      >
        <ResizeHandle
          direction="grow-left"
          getWidth={() => store.indicatorPanel.width}
          setWidth={setIndicatorWidth}
          min={160}
          max={400}
          class="absolute top-0 left-0 bottom-0 z-10"
        />
        <div class="flex items-center justify-between px-2.5 py-1.5 border-b-2 border-border text-[10px] text-text-dim uppercase tracking-wider font-semibold flex-shrink-0">
          <span>Indicators</span>
          <button
            type="button"
            class="sc-btn sc-btn-ghost px-1.5 text-[11px] leading-none normal-case tracking-normal"
            title="Hide indicators"
            onClick={() => setIndicatorPanelOpen(false)}
          >
            ›
          </button>
        </div>
        <div class="flex-1 overflow-y-auto p-2 min-h-0">
          <Show
            when={store.scripts.length > 0}
            fallback={
              <div class="text-text-faint text-[11px] italic p-2">
                No indicators running.
                <div class="mt-2 not-italic text-text-dim normal-case tracking-normal">
                  Run a Pine script to list plots here. Toggle visibility and colors per series.
                </div>
              </div>
            }
          >
            <For each={store.scripts}>{(ind) => <IndicatorCard indicator={ind} />}</For>
          </Show>
        </div>
      </aside>
    </Show>
  );
};
