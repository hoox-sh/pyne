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

// Example plugin: a custom calculation engine that runs a tiny built-in
// Pine-like DSL in the browser.  Useful for offline demos that don't need
// the full pynescript runtime.
//
// Supports:
//   • close, open, high, low, volume
//   • sma(series, n), ema(series, n), rsi(series, n)
//   • plot(value) → emits a line series
//   • strategy.entry(id, dir) / strategy.close(id) → emits events

function sma(arr, n) {
    const out = new Array(arr.length).fill(NaN);
    let s = 0, q = [];
    for (let i = 0; i < arr.length; i++) {
        q.push(arr[i]);
        s += arr[i];
        if (q.length > n) s -= q.shift();
        if (q.length === n) out[i] = s / n;
    }
    return out;
}

function ema(arr, n) {
    const out = new Array(arr.length).fill(NaN);
    const k = 2 / (n + 1);
    let prev = null;
    for (let i = 0; i < arr.length; i++) {
        prev = prev == null ? arr[i] : (arr[i] - prev) * k + prev;
        if (i + 1 >= n) out[i] = prev;
    }
    return out;
}

function rsi(arr, n) {
    const out = new Array(arr.length).fill(NaN);
    let g = 0, l = 0;
    for (let i = 1; i < arr.length; i++) {
        const d = arr[i] - arr[i - 1];
        const gain = Math.max(d, 0), loss = Math.max(-d, 0);
        if (i <= n) {
            g += gain; l += loss;
            if (i === n) {
                g /= n; l /= n;
                const rs = l === 0 ? Infinity : g / l;
                out[i] = 100 - 100 / (1 + rs);
            }
        } else {
            g = (g * (n - 1) + gain) / n;
            l = (l * (n - 1) + loss) / n;
            const rs = l === 0 ? Infinity : g / l;
            out[i] = 100 - 100 / (1 + rs);
        }
    }
    return out;
}

function tokenize(src) {
    const tokens = [];
    const re = /\s*(?:(\/\/[^\n]*)|(\d+(?:\.\d+)?)|("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')|([A-Za-z_][\w]*)|([+\-*/%<>=!(),.])|(<=|>=|==|!=))/y;
    re.lastIndex = 0;
    let m;
    while ((m = re.exec(src))) {
        if (m[1] !== undefined) continue;
        if (m[2] !== undefined) tokens.push({ type: 'num', value: parseFloat(m[2]) });
        else if (m[3] !== undefined) tokens.push({ type: 'str', value: m[3].slice(1, -1) });
        else if (m[4] !== undefined) tokens.push({ type: 'id', value: m[4] });
        else tokens.push({ type: 'op', value: m[5] || m[6] });
    }
    return tokens;
}

function parseExpr(tokens) {
    // Tiny recursive-descent for: id, number, string, call, member access,
    // arithmetic, comparisons.  Good enough for demo scripts.
    let pos = 0;
    function peek() { return tokens[pos]; }
    function eat(type, value) {
        const t = tokens[pos];
        if (!t) throw new Error('unexpected end of input');
        if (t.type !== type || (value !== undefined && t.value !== value)) {
            throw new Error(`expected ${type}${value ? '(' + value + ')' : ''}, got ${t.type}(${t.value})`);
        }
        pos++; return t;
    }
    function parsePrimary() {
        const t = peek();
        if (!t) throw new Error('unexpected end of input');
        if (t.type === 'num') { pos++; return { kind: 'num', value: t.value }; }
        if (t.type === 'str') { pos++; return { kind: 'str', value: t.value }; }
        if (t.type === 'id') {
            pos++;
            if (peek()?.value === '.') {
                eat('op', '.');
                const attr = eat('id').value;
                return { kind: 'attr', target: { kind: 'id', name: t.value }, attr };
            }
            if (peek()?.value === '(') {
                eat('op', '(');
                const args = [];
                while (peek() && peek().value !== ')') {
                    args.push(parseExpr());
                    if (peek()?.value === ',') eat('op', ',');
                }
                eat('op', ')');
                return { kind: 'call', name: t.value, args };
            }
            return { kind: 'id', name: t.value };
        }
        if (t.type === 'op' && (t.value === '(' )) {
            eat('op', '(');
            const e = parseExpr();
            eat('op', ')');
            return e;
        }
        throw new Error(`unexpected token ${t.type}(${t.value})`);
    }
    function parseMul() {
        let left = parsePrimary();
        while (peek() && (peek().value === '*' || peek().value === '/' || peek().value === '%')) {
            const op = tokens[pos++].value;
            const right = parsePrimary();
            left = { kind: 'binop', op, left, right };
        }
        return left;
    }
    function parseAdd() {
        let left = parseMul();
        while (peek() && (peek().value === '+' || peek().value === '-')) {
            const op = tokens[pos++].value;
            const right = parseMul();
            left = { kind: 'binop', op, left, right };
        }
        return left;
    }
    function parseCmp() {
        let left = parseAdd();
        while (peek() && ['<', '>', '<=', '>=', '==', '!='].includes(peek().value)) {
            const op = tokens[pos++].value;
            const right = parseAdd();
            left = { kind: 'cmp', op, left, right };
        }
        return left;
    }
    return parseCmp();
}

function parseStatements(src) {
    // Split on ';' and newlines, parse each as `name = expr` or `expr`.
    const out = [];
    const re = /([^;]+)(;|$)/g;
    let m;
    while ((m = re.exec(src))) {
        const stmt = m[1].trim();
        if (!stmt) continue;
        const assign = /^([A-Za-z_]\w*)\s*=\s*([\s\S]+)$/.exec(stmt);
        if (assign) {
            out.push({ kind: 'assign', name: assign[1], expr: parseExpr(tokenize(assign[2])) });
        } else {
            out.push({ kind: 'expr', expr: parseExpr(tokenize(stmt)) });
        }
    }
    return out;
}

const tinyEngine = {
    id: 'tiny-pine',
    name: 'Tiny Pine (JS DSL)',
    kind: 'engine',
    description: 'In-browser engine for the bundled Tiny-Pine DSL. Limited subset (sma/ema/rsi/plot/strategy.*). Always available, never makes a network call.',
    configSchema: {},
    async isReady() { return true; },
    async run({ script, bars, config }) {
        const t0 = performance.now();
        try {
            const close = bars.map((b) => b.close);
            const open = bars.map((b) => b.open);
            const high = bars.map((b) => b.high);
            const low = bars.map((b) => b.low);
            const volume = bars.map((b) => b.volume || 0);
            const env = { close, open, high, low, volume, sma, ema, rsi, NaN };
            const stmts = parseStatements(script);
            const events = [];
            const plots = {};
            function evalNode(n) {
                if (n.kind === 'num') return n.value;
                if (n.kind === 'str') return n.value;
                if (n.kind === 'id') return env[n.name];
                if (n.kind === 'attr') return evalNode(n.target)?.[n.attr];
                if (n.kind === 'call') {
                    const fn = env[n.name];
                    if (typeof fn !== 'function') throw new Error(`${n.name} is not a function`);
                    return fn(...n.args.map(evalNode));
                }
                if (n.kind === 'binop') {
                    const a = evalNode(n.left), b = evalNode(n.right);
                    return { '+': a + b, '-': a - b, '*': a * b, '/': a / b, '%': a % b }[n.op];
                }
                if (n.kind === 'cmp') {
                    const a = evalNode(n.left), b = evalNode(n.right);
                    return { '<': a < b, '>': a > b, '<=': a <= b, '>=': a >= b, '==': a === b, '!=': a !== b }[n.op];
                }
                throw new Error(`unknown node ${n.kind}`);
            }
            function runPlot(name, values) {
                plots[name] = values.map((v) => (Number.isFinite(v) ? v : null));
            }
            // Run per-bar: each statement is evaluated once; references to
            // bar fields return the per-bar value.
            const N = bars.length;
            for (let i = 0; i < N; i++) {
                env.i = i;
                env.t = bars[i].time;
                // Per-bar shortcuts: assign series with the i-th value.
                function barSeries(name) { return (fn) => { const out = fn(close, open, high, low, volume, i); env[name] = out; }; }
                for (const stmt of stmts) {
                    if (stmt.kind === 'assign') {
                        // Special-cased builtins
                        if (stmt.expr.kind === 'call' && stmt.expr.name === 'plot') {
                            const [val, ...rest] = stmt.expr.args;
                            const series = evalNode(val);
                            // plot(name, series)
                            const labelNode = rest[0];
                            const label = labelNode ? (labelNode.kind === 'str' ? labelNode.value : `plot${i}`) : stmt.name;
                            runPlot(label || stmt.name, Array.isArray(series) ? series : new Array(N).fill(series));
                            continue;
                        }
                        if (stmt.expr.kind === 'call' && stmt.expr.name === 'strategy.entry') {
                            const id = stmt.expr.args[0]?.value || 'trade';
                            events.push({ time: bars[i].time, type: 'entry', id, dir: 'long', price: close[i] });
                            continue;
                        }
                        if (stmt.expr.kind === 'call' && stmt.expr.name === 'strategy.close') {
                            const id = stmt.expr.args[0]?.value || 'trade';
                            events.push({ time: bars[i].time, type: 'close', id, price: close[i] });
                            continue;
                        }
                        env[stmt.name] = evalNode(stmt.expr);
                    } else {
                        // top-level expression
                        const v = evalNode(stmt.expr);
                        if (stmt.expr.kind === 'call' && stmt.expr.name === 'plot') {
                            const [val, ...rest] = stmt.expr.args;
                            const series = evalNode(val);
                            const label = rest[0]?.value || 'plot';
                            runPlot(label, Array.isArray(series) ? series : new Array(N).fill(series));
                        } else if (stmt.expr.kind === 'call' && stmt.expr.name === 'strategy.entry') {
                            const id = stmt.expr.args[0]?.value || 'trade';
                            events.push({ time: bars[i].time, type: 'entry', id, dir: 'long', price: close[i] });
                        } else if (stmt.expr.kind === 'call' && stmt.expr.name === 'strategy.close') {
                            const id = stmt.expr.args[0]?.value || 'trade';
                            events.push({ time: bars[i].time, type: 'close', id, price: close[i] });
                        }
                    }
                }
            }
            // Pick the first numeric plot as `plots` for legacy fields
            const firstPlotKey = Object.keys(plots)[0];
            const plotsArr = firstPlotKey ? plots[firstPlotKey] : [];
            return {
                status: 'success',
                plots: plotsArr,
                series: plots,
                events,
                meta: { mode: 'tiny-pine', count: N, ms: performance.now() - t0, script_name: 'Tiny Pine' },
            };
        } catch (err) {
            return { status: 'error', plots: [], events: [], error: err.message, meta: { ms: performance.now() - t0 } };
        }
    },
};

export default tinyEngine;
