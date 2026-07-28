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

/**
 * Strategy tester — pair entry/exit events into closed trades + summary stats.
 * Ported from legacy ui/results.js for AXIS Solid panel.
 *
 * Accepts both Pro API parity events (`kind`/`bar_time`/`direction`/`ohlc`)
 * and legacy UI fields (`type`/`time`/`dir`/`price`). Pass bars for price fill
 * when ohlc is empty.
 */

import type { Bar } from '../store/types';
import { normalizeStrategyEvents } from './events';

export interface StrategyEvent {
  time?: number;
  price?: number;
  type?: string;
  event?: string;
  kind?: string;
  id?: string;
  dir?: string;
  direction?: string;
  bar_time?: number;
  bar_index?: number;
  ohlc?: number[];
  symbol?: string;
  [key: string]: unknown;
}

export interface ClosedTrade {
  id: string;
  dir: string;
  entryTime: number;
  entry: number;
  exitTime: number;
  exit: number;
  pnl: number;
  pnlPct: number;
}

export interface StrategyStats {
  totalPnl: number;
  winRate: number;
  profitFactor: number;
  avgTrade: number;
  avgWin: number;
  avgLoss: number;
  maxDD: number;
  wins: number;
  losses: number;
  trades: number;
}

export function buildStrategyReport(
  events: StrategyEvent[] | Record<string, unknown>[],
  bars?: Bar[],
): {
  trades: ClosedTrade[];
  stats: StrategyStats;
} {
  const normalized = normalizeStrategyEvents(events, { bars, includeOrders: true });
  const sorted = normalized.slice().sort((a, b) => (a.time || 0) - (b.time || 0));
  const open = new Map<string, { entry: number; time: number; dir: string }>();
  const trades: ClosedTrade[] = [];

  for (const ev of sorted) {
    const t = ev.time;
    let p = ev.price;
    // Allow pairing even if price missing (use 0) — better to show a trade than drop it
    if (t === undefined || t === null || !Number.isFinite(Number(t))) continue;
    if (p === undefined || p === null || !Number.isFinite(Number(p))) {
      // last resort: skip only if we truly have no price at all
      continue;
    }
    const kind = String(ev.type || ev.event || ev.kind || '').toLowerCase();
    const id = String(ev.id || '_default');
    if (kind.includes('entry') || kind === 'long' || kind === 'short') {
      const dir = String(ev.dir || ev.direction || (kind === 'short' ? 'short' : 'long')).toLowerCase();
      open.set(id, { entry: Number(p), time: Number(t), dir });
    } else if (
      kind.includes('close') ||
      kind.includes('exit') ||
      kind === 'closelong' ||
      kind === 'closeshort'
    ) {
      // Prefer matching id; fall back to sole open trade if only one
      let o = open.get(id);
      if (!o && open.size === 1) {
        const only = open.keys().next().value as string;
        o = open.get(only);
        if (o) open.delete(only);
      } else if (o) {
        open.delete(id);
      }
      if (o) {
        const pnl = (Number(p) - o.entry) * (o.dir.includes('short') ? -1 : 1);
        const pnlPct = o.entry !== 0 ? pnl / o.entry : 0;
        trades.push({
          id: id || '_default',
          dir: o.dir,
          entryTime: o.time,
          entry: o.entry,
          exitTime: Number(t),
          exit: Number(p),
          pnl,
          pnlPct,
        });
      }
    }
  }

  const wins = trades.filter((t) => t.pnl > 0);
  const losses = trades.filter((t) => t.pnl <= 0);
  const totalPnl = trades.reduce((s, t) => s + t.pnl, 0);
  const grossProfit = wins.reduce((s, t) => s + t.pnl, 0);
  const grossLoss = Math.abs(losses.reduce((s, t) => s + t.pnl, 0));
  const winRate = trades.length ? (wins.length / trades.length) * 100 : 0;
  const profitFactor =
    grossLoss > 0 ? grossProfit / grossLoss : grossProfit > 0 ? Number.POSITIVE_INFINITY : 0;
  const avgTrade = trades.length ? totalPnl / trades.length : 0;
  const avgWin = wins.length ? grossProfit / wins.length : 0;
  const avgLoss = losses.length ? -grossLoss / losses.length : 0;

  let equity = 0;
  let peak = 0;
  let maxDD = 0;
  for (const t of trades) {
    equity += t.pnl;
    if (equity > peak) peak = equity;
    const dd = (peak - equity) / Math.max(1, Math.abs(peak) + 1);
    if (dd > maxDD) maxDD = dd;
  }

  return {
    trades,
    stats: {
      totalPnl,
      winRate,
      profitFactor,
      avgTrade,
      avgWin,
      avgLoss,
      maxDD,
      wins: wins.length,
      losses: losses.length,
      trades: trades.length,
    },
  };
}

export function formatPct(n: number): string {
  if (!Number.isFinite(n)) return '—';
  return `${(n * 100).toFixed(2)}%`;
}

export function formatMoney(n: number): string {
  if (!Number.isFinite(n)) return '—';
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}`;
}

export function formatNum(n: unknown): string {
  if (n === null || n === undefined) return '—';
  if (typeof n !== 'number' || Number.isNaN(n)) return '—';
  if (Math.abs(n) >= 1e6) return n.toExponential(2);
  return n.toFixed(Math.abs(n) >= 100 ? 2 : 4);
}

export function tradesToCsv(trades: ClosedTrade[]): string {
  const header = 'id,dir,entry_time,entry,exit_time,exit,pnl,pnl_pct';
  const rows = trades.map((t) =>
    [
      t.id,
      t.dir,
      t.entryTime,
      t.entry,
      t.exitTime,
      t.exit,
      t.pnl,
      t.pnlPct,
    ].join(','),
  );
  return [header, ...rows].join('\n');
}
