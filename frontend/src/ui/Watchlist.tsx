import { Component, For, createSignal, onMount, onCleanup, Show } from 'solid-js';
import {
  store,
  setStore,
  persist,
  addWatchlistSymbol,
  removeWatchlistSymbol,
  setWatchlistWidth,
  setWatchlistOpen,
} from '../store';
import { loadSymbolData } from '../data/load-symbol';
import { ResizeHandle } from './ResizeHandle';

interface Ticker {
  price: number;
  change: number;
}

export const Watchlist: Component = () => {
  const [prices, setPrices] = createSignal<Record<string, Ticker>>({});
  const [addValue, setAddValue] = createSignal('');
  let timer: ReturnType<typeof setInterval> | undefined;

  const fetchPrices = async () => {
    const symbols = store.watchlist.symbols;
    if (!symbols.length) return;
    try {
      const res = await fetch(
        `https://api.binance.com/api/v3/ticker/24hr?symbols=${JSON.stringify(symbols)}`,
      );
      if (!res.ok) return;
      const data = await res.json();
      const next: Record<string, Ticker> = {};
      for (const t of data) {
        next[t.symbol] = {
          price: parseFloat(t.lastPrice),
          change: parseFloat(t.priceChangePercent),
        };
      }
      setPrices(next);
    } catch {
      /* offline / rate limit */
    }
  };

  onMount(() => {
    fetchPrices();
    timer = setInterval(fetchPrices, 30_000);
  });

  onCleanup(() => {
    if (timer) clearInterval(timer);
  });

  const select = async (sym: string) => {
    setStore('symbol', sym);
    persist();
    await loadSymbolData(sym, store.interval);
  };

  const onAdd = () => {
    const v = addValue().trim();
    if (!v) return;
    addWatchlistSymbol(v);
    setAddValue('');
    fetchPrices();
  };

  const fmtPrice = (n?: number) =>
    n == null
      ? '—'
      : n.toLocaleString(undefined, {
          minimumFractionDigits: n < 1 ? 4 : 2,
          maximumFractionDigits: n < 1 ? 6 : 2,
        });

  return (
    <Show when={store.watchlist.open}>
      <aside
        class="flex flex-col flex-shrink-0 bg-bg-panel border-r-2 border-border min-h-0 overflow-hidden relative"
        style={{ width: `${store.watchlist.width}px` }}
      >
        <div class="flex items-center justify-between px-2 py-1.5 border-b-2 border-border flex-shrink-0">
          <span class="text-[10px] text-text-dim uppercase tracking-wider font-semibold">Watchlist</span>
          <button
            class="sc-btn sc-btn-ghost px-1.5 text-[11px] leading-none"
            title="Collapse watchlist"
            onClick={() => setWatchlistOpen(false)}
          >
            ‹
          </button>
        </div>

        <div class="flex-1 overflow-y-auto min-h-0">
          <For each={store.watchlist.symbols}>
            {(sym) => {
              const tick = () => prices()[sym];
              const active = () => store.symbol === sym;
              const change = () => tick()?.change;
              return (
                <div
                  class={`flex items-center justify-between gap-1 px-2 py-1.5 cursor-pointer border-b border-border-soft text-[12px] ${
                    active()
                      ? 'bg-accent/10 border-l-2 border-l-accent pl-[6px]'
                      : 'border-l-2 border-l-transparent hover:bg-bg-hover'
                  }`}
                  onClick={() => select(sym)}
                >
                  <span class={`font-semibold truncate ${active() ? 'text-accent' : 'text-text'}`}>
                    {sym.replace(/USDT$/, '')}
                    <span class="text-text-faint font-normal text-[10px]">USDT</span>
                  </span>
                  <div class="flex items-center gap-1.5 flex-shrink-0">
                    <span class="font-mono text-[11px] text-text-dim">{fmtPrice(tick()?.price)}</span>
                    <Show when={change() != null}>
                      <span
                        class={`font-mono text-[10px] px-1 ${
                          (change() ?? 0) >= 0 ? 'text-accent-2' : 'text-red'
                        }`}
                      >
                        {(change()! >= 0 ? '+' : '') + change()!.toFixed(2)}%
                      </span>
                    </Show>
                    <button
                      class="text-text-faint hover:text-red text-sm leading-none px-0.5"
                      title={`Remove ${sym}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        removeWatchlistSymbol(sym);
                      }}
                    >
                      ×
                    </button>
                  </div>
                </div>
              );
            }}
          </For>
        </div>

        <div class="border-t-2 border-border p-1.5 flex-shrink-0">
          <input
            class="sc-input w-full text-[11px]"
            placeholder="Add symbol…"
            value={addValue()}
            onInput={(e) => setAddValue(e.currentTarget.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') onAdd();
            }}
          />
        </div>

        <ResizeHandle
          direction="grow-right"
          getWidth={() => store.watchlist.width}
          setWidth={setWatchlistWidth}
          min={140}
          max={360}
          class="absolute top-0 right-0 bottom-0"
        />
      </aside>
    </Show>
  );
};
