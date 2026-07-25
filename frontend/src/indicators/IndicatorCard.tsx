import { Component, For, createSignal, Show } from 'solid-js';
import type { Indicator } from '../store/types';
import { toggleIndicator, removeIndicator, setIndicatorColor } from '../store';
import { getManager } from '../chart/ChartHost';

interface Props {
  indicator: Indicator;
}

const QUICK_COLORS = ['#2962ff', '#ff6d00', '#2e7d32', '#9c27b0', '#00bcd4', '#fdd835', '#e91e63', '#ef5350'];

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
    // Re-apply overlays with new color
    const manager = getManager();
    if (manager) {
      manager.removeOverlays(props.indicator.paneId);
      // The next run will re-apply with updated colors
    }
  };

  return (
    <div class="bg-bg-elev rounded border border-border-soft p-2.5 mb-2">
      <div class="flex items-center justify-between mb-1.5">
        <div class="flex items-center gap-2">
          <button
            class={`w-5 h-5 rounded text-xs flex items-center justify-center ${
              props.indicator.visible ? 'bg-accent/20 text-accent' : 'bg-bg-hover text-text-dim'
            }`}
            onClick={toggle}
            title={props.indicator.visible ? 'Hide indicator' : 'Show indicator'}
          >
            {props.indicator.visible ? '👁' : '👁‍🗨'}
          </button>
          <span class="text-xs font-semibold text-text truncate max-w-[120px]">{props.indicator.name}</span>
        </div>
        <button class="text-text-faint hover:text-red text-xs px-1 rounded hover:bg-bg-hover" onClick={remove} title="Remove indicator">
          ×
        </button>
      </div>
      <div class="flex flex-col gap-0.5">
        <For each={Object.entries(props.indicator.plots)}>
          {([name, { color }]) => (
            <div class="flex items-center gap-2 text-[11px] text-text-dim">
              <button
                class="inline-block w-2 h-2 rounded-full flex-shrink-0 cursor-pointer hover:ring-1 hover:ring-white/30 relative"
                style={{ background: color }}
                title={`Click to change color for "${name}"`}
                onClick={() => setEditingColor(editingColor() === name ? null : name)}
              />
              <span class="truncate">{name}</span>
              <Show when={editingColor() === name}>
                <div class="flex gap-1 ml-auto">
                  <For each={QUICK_COLORS}>
                    {(c) => (
                      <button
                        class="w-3 h-3 rounded-full cursor-pointer border border-white/20 hover:scale-125 transition-transform"
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
