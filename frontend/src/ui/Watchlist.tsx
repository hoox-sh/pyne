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

import { Component, For, createSignal, createEffect, onCleanup, Show } from 'solid-js';
import {
  store,
  setStore,
  persist,
  addWatchlistSymbol,
  removeWatchlistSymbol,
  setWatchlistWidth,
  setWatchlistOpen,
  setWatchlistRefreshSec,
} from '../store';
import { loadSymbolData } from '../data/load-symbol';
import {
  fetchWatchlistTickers,
  WATCHLIST_INTERVALS,
  WATCHLIST_REFRESH_OPTIONS,
  type WatchTicker,
} from '../data/watchlist-tickers';
import { ResizeHandle } from './ResizeHandle';

export const Watchlist: Component = () => {
  const [prices, setPrices] = createSignal<Record<string, WatchTicker>>({});
  const [addValue, setAddValue] = createSignal('');
  const [refreshing, setRefreshing] = createSignal(false);
  let timer: ReturnType<typeof setInterval> | undefined;

  const fetchPrices = async () => {
    const symbols = store.watchlist.symbols;
    if (!symbols.length) return;
    setRefreshing(true);
    try {
      const next = await fetchWatchlistTickers(symbols, store.source);
      setPrices(next);
    } finally {
      setRefreshing(false);
    }
  };

  // Re-poll when symbols, source, or refresh interval change
  createEffect(() => {
    const _syms = store.watchlist.symbols.join(',');
    const _src = store.source;
    const sec = store.watchlist.refreshSec || 15;
    void _syms;
    void _src;

    if (timer) clearInterval(timer);
    void fetchPrices();
    timer = setInterval(() => void fetchPrices(), Math.max(5, sec) * 1000);

    onCleanup(() => {
      if (timer) clearInterval(timer);
    });
  });

  const select = async (sym: string) => {
    setStore('symbol', sym.toUpperCase());
    persist();
    await loadSymbolData(sym, store.interval, store.source);
  };

  const onInterval = async (iv: string) => {
    if (iv === store.interval) return;
    setStore('interval', iv);
    persist();
    // Reload chart for active symbol on the new interval
    if (store.symbol) {
      await loadSymbolData(store.symbol, iv, store.source);
    }
  };

  const onAdd = () => {
    let v = addValue().trim().toUpperCase();
    if (!v) return;
    if (!/USDT$|USD$|USDC$/i.test(v) && /^[A-Z0-9]{2,12}$/.test(v)) {
      v = `${v}USDT`;
    }
    addWatchlistSymbol(v);
    setAddValue('');
    void fetchPrices();
  };

  const fmtPrice = (n?: number) =>
    n == null
      ? '—'
      : n.toLocaleString(undefined, {
          minimumFractionDigits: n < 1 ? 4 : 2,
          maximumFractionDigits: n < 1 ? 6 : 2,
        });

  const sourceShort = () => {
    const s = store.source || '';
    if (s.includes('binance')) return 'BN';
    if (s.includes('okx')) return 'OKX';
    if (s.includes('bybit')) return 'BB';
    if (s.includes('coinbase')) return 'CB';
    if (s.includes('mock')) return 'MOCK';
    if (s.includes('csv')) return 'CSV';
    return s.slice(0, 6) || '—';
  };

  return (
    <Show when={store.watchlist.open}>
      <aside
        class="flex flex-col flex-shrink-0 bg-bg-panel border-r-2 border-border min-h-0 overflow-hidden relative"
        style={{ width: `${store.watchlist.width}px` }}
        data-testid="axis-watchlist"
        aria-label="Watchlist"
      >
        <div class="flex items-center justify-between gap-1 px-2 py-1.5 border-b-2 border-border flex-shrink-0">
          <span class="text-[10px] text-text-dim uppercase tracking-wider font-semibold">
            Watchlist
          </span>
          <div class="flex items-center gap-0.5">
            <span
              class="text-[9px] font-mono text-text-faint px-1"
              title={`Quotes from ${store.source}`}
            >
              {sourceShort()}
            </span>
            <button
              type="button"
              class="sc-btn sc-btn-ghost px-1 text-[10px] leading-none"
              title="Refresh quotes"
              disabled={refreshing()}
              onClick={() => void fetchPrices()}
            >
              {refreshing() ? '…' : '↻'}
            </button>
            <button
              class="sc-btn sc-btn-ghost px-1.5 text-[11px] leading-none"
              title="Collapse watchlist"
              onClick={() => setWatchlistOpen(false)}
            >
              ‹
            </button>
          </div>
        </div>

        {/* Interval + quote refresh — compact controls */}
        <div class="flex items-center gap-1 px-2 py-1 border-b border-border-soft flex-shrink-0">
          <span class="text-[9px] text-text-faint uppercase tracking-wider shrink-0">TF</span>
          <select
            class="sc-input flex-1 text-[11px] py-0.5 min-w-0"
            value={store.interval}
            title="Chart interval · applies on symbol select"
            onChange={(e) => void onInterval(e.currentTarget.value)}
          >
            <For each={[...WATCHLIST_INTERVALS]}>
              {(i) => <option value={i}>{i}</option>}
            </For>
          </select>
          <span class="text-[9px] text-text-faint uppercase tracking-wider shrink-0" title="Quote poll">
            ↻
          </span>
          <select
            class="sc-input w-[52px] text-[11px] py-0.5 shrink-0"
            value={String(store.watchlist.refreshSec || 15)}
            title="Watchlist quote refresh interval"
            onChange={(e) => setWatchlistRefreshSec(Number(e.currentTarget.value))}
          >
            <For each={[...WATCHLIST_REFRESH_OPTIONS]}>
              {(o) => <option value={o.value}>{o.label}</option>}
            </For>
          </select>
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
                  onClick={() => void select(sym)}
                >
                  <span class={`font-semibold truncate ${active() ? 'text-accent' : 'text-text'}`}>
                    {sym.replace(/USDT$/i, '').replace(/USD$/i, '')}
                    <span class="text-text-faint font-normal text-[10px]">
                      {/USDT$/i.test(sym) ? 'USDT' : /USD$/i.test(sym) ? 'USD' : ''}
                    </span>
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

        <div class="border-t-2 border-border p-1.5 flex-shrink-0 flex flex-col gap-1">
          <input
            class="sc-input w-full text-[11px]"
            placeholder="Add symbol… (BTC or BTCUSDT)"
            value={addValue()}
            onInput={(e) => setAddValue(e.currentTarget.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') onAdd();
            }}
          />
          <div class="text-[9px] text-text-faint font-mono truncate" title={store.source}>
            {store.interval} · {store.source}
            {store.watchlist.refreshSec ? ` · ${store.watchlist.refreshSec}s` : ''}
          </div>
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
