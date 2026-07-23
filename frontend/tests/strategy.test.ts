// Tests for the strategy tester — derives closed trades from the event
// stream and computes stats. Re-implements the algorithm here so we can
// test the math independently of the DOM.

import { describe, expect, it } from 'bun:test';

function buildStrategyReport(events: any[]) {
    const sorted = (events || []).slice().sort((a, b) => (a.time || 0) - (b.time || 0));
    const open = new Map<string, { entry: number; time: number; dir: string }>();
    const trades: any[] = [];
    for (const ev of sorted) {
        const t = ev.time, p = ev.price;
        if (t === undefined || p === undefined) continue;
        const kind = (ev.type || ev.event || '').toLowerCase();
        const id = ev.id || '_default';
        if (kind.includes('entry')) {
            const dir = (ev.dir || kind).toString().toLowerCase();
            open.set(id, { entry: p, time: t, dir });
        } else if (kind.includes('close') || kind.includes('exit')) {
            const o = open.get(id);
            if (o) {
                const pnl = (p - o.entry) * (o.dir.includes('short') ? -1 : 1);
                trades.push({ id, dir: o.dir, entryTime: o.time, entry: o.entry, exitTime: t, exit: p, pnl, pnlPct: pnl / o.entry });
                open.delete(id);
            }
        }
    }
    const wins = trades.filter((t) => t.pnl > 0);
    const losses = trades.filter((t) => t.pnl <= 0);
    const totalPnl = trades.reduce((s, t) => s + t.pnl, 0);
    const winRate = trades.length ? (wins.length / trades.length) * 100 : 0;
    const profitFactor = losses.length > 0 && losses.reduce((s, t) => s + Math.abs(t.pnl), 0) > 0
        ? wins.reduce((s, t) => s + t.pnl, 0) / losses.reduce((s, t) => s + Math.abs(t.pnl), 0)
        : (wins.length > 0 ? Infinity : 0);
    const avgTrade = trades.length ? totalPnl / trades.length : 0;
    return { trades, stats: { totalPnl, winRate, profitFactor, avgTrade, wins: wins.length, losses: losses.length, trades: trades.length } };
}

describe('Strategy tester', () => {
    it('returns no trades for an empty event list', () => {
        const r = buildStrategyReport([]);
        expect(r.trades).toHaveLength(0);
        expect(r.stats.winRate).toBe(0);
        expect(r.stats.profitFactor).toBe(0);
    });

    it('pairs entries with subsequent closes', () => {
        const events = [
            { time: 1, type: 'entry', id: 'L', dir: 'long', price: 100 },
            { time: 2, type: 'close', id: 'L', price: 110 },
        ];
        const r = buildStrategyReport(events);
        expect(r.trades).toHaveLength(1);
        expect(r.trades[0].pnl).toBe(10);
        expect(r.trades[0].pnlPct).toBeCloseTo(0.1);
    });

    it('inverts PnL for short positions', () => {
        const events = [
            { time: 1, type: 'entry', id: 'S', dir: 'short', price: 100 },
            { time: 2, type: 'close', id: 'S', price: 90 },
        ];
        const r = buildStrategyReport(events);
        expect(r.trades[0].pnl).toBe(10);  // short profits when price goes DOWN
    });

    it('handles multiple trades and computes winRate + avg', () => {
        const events = [
            { time: 1, type: 'entry', id: 'A', dir: 'long', price: 100 },
            { time: 2, type: 'close', id: 'A', price: 110 },  // +10
            { time: 3, type: 'entry', id: 'B', dir: 'long', price: 50 },
            { time: 4, type: 'close', id: 'B', price: 45 },   // -5
            { time: 5, type: 'entry', id: 'C', dir: 'long', price: 200 },
            { time: 6, type: 'close', id: 'C', price: 220 },  // +20
        ];
        const r = buildStrategyReport(events);
        expect(r.trades).toHaveLength(3);
        expect(r.stats.wins).toBe(2);
        expect(r.stats.losses).toBe(1);
        expect(r.stats.totalPnl).toBe(25);
        expect(r.stats.winRate).toBeCloseTo(66.666, 1);
        expect(r.stats.avgTrade).toBeCloseTo(25 / 3);
    });

    it('ignores closes without a matching entry', () => {
        const events = [
            { time: 1, type: 'close', id: 'X', price: 100 },
        ];
        const r = buildStrategyReport(events);
        expect(r.trades).toHaveLength(0);
    });

    it('supports closing only the matching id', () => {
        const events = [
            { time: 1, type: 'entry', id: 'A', dir: 'long', price: 100 },
            { time: 2, type: 'entry', id: 'B', dir: 'long', price: 200 },
            { time: 3, type: 'close', id: 'A', price: 110 },
        ];
        const r = buildStrategyReport(events);
        expect(r.trades).toHaveLength(1);
        expect(r.trades[0].id).toBe('A');
        expect(r.trades[0].pnl).toBe(10);
    });

    it('computes profitFactor as Infinity when there are no losses', () => {
        const events = [
            { time: 1, type: 'entry', id: 'A', dir: 'long', price: 100 },
            { time: 2, type: 'close', id: 'A', price: 110 },
        ];
        const r = buildStrategyReport(events);
        expect(r.stats.profitFactor).toBe(Infinity);
    });
});
