/**
 * AXIS results / export drawer — Trades, Strategy, Plots, Metrics, Raw + export.
 */

import { Component, For, Show, createMemo, createSignal } from 'solid-js';
import { store, setStore, persist } from '../store';
import type { RunResult } from '../indicators/runner';
import {
  buildStrategyReport,
  formatMoney,
  formatNum,
  formatPct,
  tradesToCsv,
  type ClosedTrade,
  type StrategyEvent,
} from '../results/strategy';
import { normalizeStrategyEvents } from '../results/events';
import { getManager } from '../chart/ChartHost';
import { Icons } from './icons';

type TabId = 'events' | 'strategy' | 'plots' | 'metrics' | 'raw';

const TABS: { id: TabId; label: string }[] = [
  { id: 'events', label: 'Events' },
  { id: 'strategy', label: 'Strategy' },
  { id: 'plots', label: 'Plots' },
  { id: 'metrics', label: 'Metrics' },
  { id: 'raw', label: 'Raw' },
];

function downloadText(filename: string, text: string, mime = 'text/plain') {
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

export const ResultsPanel: Component = () => {
  const [tab, setTab] = createSignal<TabId>('events');
  const [copied, setCopied] = createSignal(false);

  const result = () => store.lastRun as RunResult | null;

  const report = createMemo(() => {
    const r = result();
    if (!r) return null;
    return buildStrategyReport((r.events || []) as StrategyEvent[], store.bars);
  });

  const normalizedEvents = createMemo(() => {
    const r = result();
    if (!r) return [] as StrategyEvent[];
    return normalizeStrategyEvents((r.events || []) as StrategyEvent[], {
      bars: store.bars,
      includeOrders: true,
    });
  });

  function jumpToTrade(trade: ClosedTrade, which: 'entry' | 'exit' = 'entry') {
    const t = which === 'exit' ? trade.exitTime : trade.entryTime;
    getManager()?.scrollToTime(t);
  }

  const plotSummary = createMemo(() => {
    const r = result();
    if (!r) return [] as { name: string; pts: number; last: string }[];
    const out: { name: string; pts: number; last: string }[] = [];
    const series = r.series || {};
    const keys = Object.keys(series).filter((k) => !k.startsWith('__'));
    if (keys.length) {
      for (const k of keys) {
        const arr = series[k] as (number | null)[];
        const nonNull = arr?.filter((v) => v != null) ?? [];
        const last = [...(arr || [])].reverse().find((v) => v != null);
        out.push({ name: k, pts: nonNull.length, last: formatNum(last) });
      }
    } else if (r.plots?.length) {
      const nonNull = r.plots.filter((v) => v != null).length;
      const last = [...r.plots].reverse().find((v) => v != null);
      out.push({ name: 'plot_0', pts: nonNull, last: formatNum(last) });
    }
    return out;
  });

  const metrics = createMemo(() => {
    const r = result();
    if (!r) return [] as { label: string; value: string }[];
    const m: { label: string; value: string }[] = [];
    if (r.meta?.ms != null) m.push({ label: 'Runtime', value: `${r.meta.ms.toFixed(0)} ms` });
    if (r.meta?.script_name) m.push({ label: 'Script', value: String(r.meta.script_name) });
    m.push({ label: 'Status', value: r.status });
    m.push({ label: 'Events', value: String(r.events?.length ?? 0) });
    m.push({ label: 'Plot series', value: String(plotSummary().length) });
    m.push({ label: 'Bars', value: String(store.bars.length) });
    m.push({ label: 'Engine', value: store.engine });
    m.push({ label: 'Source', value: store.source });
    const rep = report();
    if (rep && rep.stats.trades > 0) {
      m.push({ label: 'Closed trades', value: String(rep.stats.trades) });
      m.push({ label: 'Net P&L', value: formatMoney(rep.stats.totalPnl) });
      m.push({ label: 'Win rate', value: `${rep.stats.winRate.toFixed(1)}%` });
    }
    if (r.error) m.push({ label: 'Error', value: r.error });
    return m;
  });

  const rawJson = createMemo(() => {
    const r = result();
    if (!r) return '';
    try {
      return JSON.stringify(r, null, 2);
    } catch {
      return String(r);
    }
  });

  const flashCopied = async (text: string) => {
    if (await copyText(text)) {
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    }
  };

  const exportJson = () => {
    const r = result();
    if (!r) return;
    const name = `axis-run-${Date.now()}.json`;
    downloadText(name, rawJson(), 'application/json');
  };

  const exportTradesCsv = () => {
    const rep = report();
    if (!rep?.trades.length) return;
    downloadText(`axis-trades-${Date.now()}.csv`, tradesToCsv(rep.trades), 'text/csv');
  };

  const setHeight = (h: number) => {
    setStore('resultsPanel', 'height', h);
    persist();
  };

  return (
    <Show when={store.resultsPanel.open}>
      <div
        class="flex flex-col border-t-2 border-border bg-bg-panel flex-shrink-0"
        style={{ height: `${store.resultsPanel.height}px` }}
      >
        {/* Header */}
        <div class="flex items-center gap-2 px-2.5 py-1 border-b-2 border-border min-h-[28px]">
          <span class="text-[11px] font-semibold text-text tracking-tight uppercase">Results</span>
          <div class="flex items-center gap-0.5 ml-1">
            <For each={TABS}>
              {(t) => (
                <button
                  class={`sc-btn sc-btn-ghost px-2 py-0.5 text-[10px] ${
                    tab() === t.id ? 'text-accent border-b-2 border-accent' : ''
                  }`}
                  onClick={() => setTab(t.id)}
                >
                  {t.label}
                </button>
              )}
            </For>
          </div>
          <div class="flex-1" />
          <Show when={copied()}>
            <span class="text-[10px] text-accent-2">Copied</span>
          </Show>
          <button
            class="sc-btn sc-btn-ghost px-2 text-[10px] inline-flex items-center gap-1"
            title="Copy current tab"
            onClick={() => {
              const r = result();
              if (!r) return;
              if (tab() === 'raw') flashCopied(rawJson());
              else if (tab() === 'strategy') {
                const rep = report();
                flashCopied(rep ? tradesToCsv(rep.trades) : '');
              } else flashCopied(rawJson());
            }}
          >
            <Icons.copy size={12} />
            Copy
          </button>
          <button
            class="sc-btn sc-btn-ghost px-2 text-[10px] inline-flex items-center gap-1"
            title="Export full run JSON"
            onClick={exportJson}
            disabled={!result()}
          >
            <Icons.fileJson size={12} />
            JSON
          </button>
          <button
            class="sc-btn sc-btn-ghost px-2 text-[10px] inline-flex items-center gap-1"
            title="Export closed trades CSV"
            onClick={exportTradesCsv}
            disabled={!report()?.trades.length}
          >
            <Icons.fileCsv size={12} />
            CSV
          </button>
          <select
            class="sc-input text-[10px] py-0.5 min-w-0"
            value={store.resultsPanel.height}
            onChange={(e) => setHeight(Number(e.currentTarget.value))}
            title="Panel height"
          >
            <option value={160}>S</option>
            <option value={220}>M</option>
            <option value={320}>L</option>
          </select>
          <button
            class="sc-btn sc-btn-ghost px-2"
            onClick={() => {
              setStore('resultsPanel', 'open', false);
              persist();
            }}
            aria-label="Close results"
          >
            <Icons.x size={14} />
          </button>
        </div>

        {/* Body */}
        <div class="flex-1 min-h-0 overflow-auto p-2 text-[11px]">
          <Show when={!result()}>
            <div class="text-text-faint uppercase tracking-wider text-[10px] p-3">
              Run a script to populate results
            </div>
          </Show>

          <Show when={result()?.status === 'error'}>
            <div class="text-red p-2 border-2 border-red/40 bg-red/5 font-mono">
              {result()?.error || 'Run error'}
            </div>
          </Show>

          <Show when={result() && tab() === 'events'}>
            <Show
              when={normalizedEvents().length > 0}
              fallback={
                <div class="text-text-faint p-2">No strategy events in this run.</div>
              }
            >
              <ul class="flex flex-col gap-0.5 font-mono">
                <For each={normalizedEvents()}>
                  {(ev) => {
                    const kind = String(ev.type || ev.event || ev.kind || '?');
                    const t = ev.time
                      ? new Date(ev.time * 1000).toISOString().slice(0, 16).replace('T', ' ')
                      : '—';
                    const dir = ev.dir || ev.direction || '';
                    return (
                      <li class="flex gap-2 py-0.5 border-b border-border-soft/60 items-baseline">
                        <span class="text-text-faint w-[118px] flex-shrink-0">{t}</span>
                        <span class="text-accent w-16 flex-shrink-0 truncate">{kind}</span>
                        <span class="text-text-dim w-12 truncate">{String(dir)}</span>
                        <span class="text-text-dim w-16 truncate">{String(ev.id || '')}</span>
                        <span class="text-text flex-1 truncate">
                          {ev.price !== undefined && ev.price !== null
                            ? Number(ev.price).toFixed(2)
                            : '—'}
                        </span>
                      </li>
                    );
                  }}
                </For>
              </ul>
            </Show>
          </Show>

          <Show when={result() && tab() === 'strategy'}>
            <Show
              when={(report()?.stats.trades ?? 0) > 0}
              fallback={
                <div class="text-text-faint p-2">
                  {(result()?.events?.length ?? 0) > 0
                    ? 'Events present but no closed trades yet.'
                    : 'No events. Strategy tester pairs entry/close events.'}
                </div>
              }
            >
              <div class="grid grid-cols-3 sm:grid-cols-6 gap-2 mb-3">
                <Metric
                  label="Net P&L"
                  value={formatMoney(report()!.stats.totalPnl)}
                  tone={report()!.stats.totalPnl >= 0 ? 'pos' : 'neg'}
                />
                <Metric label="Win rate" value={`${report()!.stats.winRate.toFixed(1)}%`} />
                <Metric label="# Trades" value={String(report()!.stats.trades)} />
                <Metric
                  label="Profit factor"
                  value={
                    Number.isFinite(report()!.stats.profitFactor)
                      ? report()!.stats.profitFactor.toFixed(2)
                      : '∞'
                  }
                />
                <Metric
                  label="Avg trade"
                  value={formatMoney(report()!.stats.avgTrade)}
                  tone={report()!.stats.avgTrade >= 0 ? 'pos' : 'neg'}
                />
                <Metric
                  label="Max DD"
                  value={`${(report()!.stats.maxDD * 100).toFixed(2)}%`}
                  tone="neg"
                />
              </div>
              <div class="overflow-auto border-2 border-border">
                <table class="w-full text-left font-mono text-[10px]">
                  <thead class="bg-bg-elev text-text-dim sticky top-0">
                    <tr>
                      <th class="px-2 py-1">ID</th>
                      <th class="px-2 py-1">Dir</th>
                      <th class="px-2 py-1">Entry</th>
                      <th class="px-2 py-1">Exit</th>
                      <th class="px-2 py-1">P&L</th>
                      <th class="px-2 py-1">%</th>
                    </tr>
                  </thead>
                  <tbody>
                    <For each={report()!.trades}>
                      {(t) => (
                        <tr
                          class="border-t border-border-soft cursor-pointer hover:bg-bg-hover/80 transition-colors"
                          title="Jump to entry on chart"
                          onClick={() => jumpToTrade(t, 'entry')}
                        >
                          <td class="px-2 py-0.5">{t.id}</td>
                          <td class="px-2 py-0.5">{t.dir}</td>
                          <td
                            class="px-2 py-0.5 text-accent hover:underline"
                            title="Jump to entry"
                            onClick={(e) => {
                              e.stopPropagation();
                              jumpToTrade(t, 'entry');
                            }}
                          >
                            {new Date(t.entryTime * 1000).toISOString().slice(0, 10)} @{' '}
                            {t.entry.toFixed(2)}
                          </td>
                          <td
                            class="px-2 py-0.5 hover:underline"
                            title="Jump to exit"
                            onClick={(e) => {
                              e.stopPropagation();
                              jumpToTrade(t, 'exit');
                            }}
                          >
                            {new Date(t.exitTime * 1000).toISOString().slice(0, 10)} @{' '}
                            {t.exit.toFixed(2)}
                          </td>
                          <td
                            class={`px-2 py-0.5 ${t.pnl >= 0 ? 'text-accent-2' : 'text-red'}`}
                          >
                            {formatMoney(t.pnl)}
                          </td>
                          <td
                            class={`px-2 py-0.5 ${t.pnlPct >= 0 ? 'text-accent-2' : 'text-red'}`}
                          >
                            {formatPct(t.pnlPct)}
                          </td>
                        </tr>
                      )}
                    </For>
                  </tbody>
                </table>
              </div>
            </Show>
          </Show>

          <Show when={result() && tab() === 'plots'}>
            <Show
              when={plotSummary().length > 0}
              fallback={<div class="text-text-faint p-2">No plots in this run.</div>}
            >
              <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
                <For each={plotSummary()}>
                  {(p) => (
                    <div class="border-2 border-border bg-bg-elev px-2 py-1.5">
                      <div class="text-text-dim text-[10px] uppercase tracking-wider">● {p.name}</div>
                      <div class="font-mono text-text mt-0.5">
                        {p.pts} pts · last {p.last}
                      </div>
                    </div>
                  )}
                </For>
              </div>
            </Show>
          </Show>

          <Show when={result() && tab() === 'metrics'}>
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <For each={metrics()}>
                {(m) => (
                  <div class="border-2 border-border bg-bg-elev px-2 py-1.5">
                    <div class="text-text-dim text-[10px] uppercase tracking-wider">{m.label}</div>
                    <div class="font-mono text-text mt-0.5 break-all">{m.value}</div>
                  </div>
                )}
              </For>
            </div>
          </Show>

          <Show when={result() && tab() === 'raw'}>
            <pre class="font-mono text-[10px] text-text-dim whitespace-pre-wrap break-all p-2 bg-bg-base border-2 border-border min-h-full">
              {rawJson()}
            </pre>
          </Show>
        </div>
      </div>
    </Show>
  );
};

const Metric: Component<{ label: string; value: string; tone?: 'pos' | 'neg' }> = (props) => (
  <div class="border-2 border-border bg-bg-elev px-2 py-1.5">
    <div class="text-text-dim text-[10px] uppercase tracking-wider">{props.label}</div>
    <div
      class={`font-mono font-semibold mt-0.5 ${
        props.tone === 'pos' ? 'text-accent-2' : props.tone === 'neg' ? 'text-red' : 'text-text'
      }`}
    >
      {props.value}
    </div>
  </div>
);
