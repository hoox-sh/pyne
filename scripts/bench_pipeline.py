#!/usr/bin/env python3
# Copyright (C) 2024-2026 jango_blockchained
#
# This file is part of pynescript.
#
# pynescript is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pynescript is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""End-to-end pipeline benchmark: parse → unparse → interpret → compile+execute.

Usage (from repo root, with .venv):
  PYTHONPATH=src:. .venv/bin/python scripts/bench_pipeline.py
  PYTHONPATH=src:. .venv/bin/python scripts/bench_pipeline.py --profile
  PYTHONPATH=src:. .venv/bin/python scripts/bench_pipeline.py --json out.json

Measures:
  - parse ms (small / med / large scripts)
  - unparse ms (same)
  - interpret Runtime ms/bar and bars/sec for: minimal, ta_sma, ta_combo, strategy-ish
  - compile cold/warm + execute for same (where supported)
  - optional cProfile top-20 cumulative on ta_combo interpret
"""

from __future__ import annotations

import argparse
import cProfile
import io
import json
import pstats
import statistics
import sys
import time
from pathlib import Path
from typing import Any

# Prefer repo layout
_REPO = Path(__file__).resolve().parents[1]
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

# Builtin scripts may live only on main checkout
_BUILTIN_CANDIDATES = [
    _REPO / "tests" / "fixtures" / "parity" / "pine",
    _REPO / "tests" / "data" / "examples",
]


SCRIPTS: dict[str, str] = {
    "minimal": """//@version=5
indicator("Minimal")
plot(close)
""",
    "ta_sma": """//@version=5
indicator("SMA")
plot(ta.sma(close, 14))
""",
    "ta_combo": """//@version=5
indicator("TA multi")
s = ta.sma(close, 14)
e = ta.ema(close, 21)
r = ta.rsi(close, 14)
a = ta.atr(14)
d = ta.stdev(close, 20)
[bb_m, bb_u, bb_l] = ta.bb(close, 20, 2.0)
h = ta.highest(high, 20)
l = ta.lowest(low, 20)
plot(s)
plot(e)
plot(r)
plot(a)
plot(d)
plot(bb_m)
plot(h)
plot(l)
""",
    "strategy_ish": """//@version=5
strategy("Bench strat", overlay=true, initial_capital=100000)
fast = ta.sma(close, 10)
slow = ta.sma(close, 30)
longCond = ta.crossover(fast, slow)
shortCond = ta.crossunder(fast, slow)
if longCond
    strategy.entry("L", strategy.long)
if shortCond
    strategy.close("L")
plot(fast)
plot(slow)
""",
}


def _find_builtin_dir() -> Path | None:
    for p in _BUILTIN_CANDIDATES:
        if p.is_dir() and any(p.glob("*.pine")):
            return p
    return None


def _load_size_scripts() -> dict[str, tuple[str, str, int]]:
    """Return small/med/large: (name, source, nbytes)."""
    d = _find_builtin_dir()
    out: dict[str, tuple[str, str, int]] = {}
    if d is None:
        # fallback synthetic sizes
        out["small"] = ("synthetic_small", SCRIPTS["minimal"], len(SCRIPTS["minimal"]))
        med = SCRIPTS["ta_combo"]
        out["med"] = ("synthetic_med", med, len(med))
        large = (SCRIPTS["ta_combo"] + "\n") * 20
        out["large"] = ("synthetic_large", large, len(large))
        return out

    files = sorted(d.glob("*.pine"), key=lambda f: f.stat().st_size)
    picks = {
        "small": files[0],
        "med": files[len(files) // 2],
        "large": files[-1],
    }
    for k, f in picks.items():
        src = f.read_text(encoding="utf-8", errors="replace")
        out[k] = (f.name, src, len(src.encode("utf-8")))
    return out


def _make_ohlcv(n: int, seed: int = 42) -> list[dict[str, Any]]:
    import random

    rng = random.Random(seed)
    bars: list[dict[str, Any]] = []
    price = 100.0
    t0 = 1_600_000_000_000
    for i in range(n):
        price = max(1.0, price * (1.0 + rng.uniform(-0.01, 0.01)))
        o = price
        h = price * (1.0 + rng.uniform(0, 0.005))
        l = price * (1.0 - rng.uniform(0, 0.005))
        c = rng.uniform(l, h)
        v = rng.uniform(100, 1000)
        bars.append(
            {
                "time": t0 + i * 60_000,
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "volume": v,
            }
        )
        price = c
    return bars


def _median_ms(samples: list[float]) -> float:
    if not samples:
        return float("nan")
    return float(statistics.median(samples))


def _bench(fn, warmup: int = 2, iters: int = 7) -> dict[str, float]:
    for _ in range(warmup):
        fn()
    times: list[float] = []
    for _ in range(iters):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1000.0)
    return {
        "median_ms": _median_ms(times),
        "mean_ms": float(statistics.mean(times)),
        "min_ms": min(times),
        "max_ms": max(times),
        "n": float(iters),
    }


def bench_parse_unparse(size_scripts: dict[str, tuple[str, str, int]]) -> dict[str, Any]:
    from pynescript.ast.helper import parse, unparse

    results: dict[str, Any] = {}
    for label, (name, src, nbytes) in size_scripts.items():
        # cold-ish: first call separately
        t0 = time.perf_counter()
        tree = parse(src)
        cold_parse = (time.perf_counter() - t0) * 1000.0
        t0 = time.perf_counter()
        _ = unparse(tree)
        cold_unparse = (time.perf_counter() - t0) * 1000.0

        parse_stats = _bench(lambda s=src: parse(s), warmup=3, iters=15)
        trees = [parse(src) for _ in range(3)]
        unparse_stats = _bench(lambda t=trees[0]: unparse(t), warmup=3, iters=15)
        results[label] = {
            "name": name,
            "bytes": nbytes,
            "cold_parse_ms": cold_parse,
            "warm_parse": parse_stats,
            "cold_unparse_ms": cold_unparse,
            "warm_unparse": unparse_stats,
        }
    return results


def bench_interpret(
    scripts: dict[str, str],
    n_bars: int = 2000,
    warmup: int = 2,
    iters: int = 5,
) -> dict[str, Any]:
    from backend.runtime import Runtime

    ohlcv = _make_ohlcv(n_bars)
    results: dict[str, Any] = {}
    for name, src in scripts.items():
        rt = Runtime(symbol="BENCH")

        def run_once(source=src, runtime=rt):
            out = runtime.run(source, ohlcv, mode="interpret")
            if isinstance(out, dict) and out.get("error"):
                raise RuntimeError(f"{name}: {out['error']}")
            return out

        # one probe for errors
        try:
            run_once()
        except Exception as e:
            results[name] = {"error": str(e), "n_bars": n_bars}
            continue

        stats = _bench(run_once, warmup=warmup, iters=iters)
        med = stats["median_ms"]
        results[name] = {
            **stats,
            "n_bars": n_bars,
            "ms_per_bar": med / n_bars,
            "bars_per_sec": (n_bars / (med / 1000.0)) if med > 0 else float("inf"),
        }
    return results


def bench_compile_execute(
    scripts: dict[str, str],
    n_bars: int = 5000,
    warmup_run: int = 3,
    iters: int = 11,
) -> dict[str, Any]:
    import numpy as np

    from pynescript.compiler.engine import clear_compile_cache, compile_script, has_numba

    results: dict[str, Any] = {"has_numba": has_numba()}
    ohlcv = _make_ohlcv(n_bars)
    open_ = np.asarray([b["open"] for b in ohlcv], dtype=np.float64)
    high = np.asarray([b["high"] for b in ohlcv], dtype=np.float64)
    low = np.asarray([b["low"] for b in ohlcv], dtype=np.float64)
    close = np.asarray([b["close"] for b in ohlcv], dtype=np.float64)
    volume = np.asarray([b["volume"] for b in ohlcv], dtype=np.float64)

    for name, src in scripts.items():
        entry: dict[str, Any] = {"n_bars": n_bars}
        # cold compile (clear cache first)
        clear_compile_cache()
        t0 = time.perf_counter()
        try:
            cs = compile_script(src, use_cache=True)
        except Exception as e:
            entry["error"] = f"compile: {e}"
            results[name] = entry
            continue
        entry["cold_compile_ms"] = (time.perf_counter() - t0) * 1000.0

        # warm compile (cache hit)
        t0 = time.perf_counter()
        _ = compile_script(src, use_cache=True)
        entry["warm_compile_ms"] = (time.perf_counter() - t0) * 1000.0
        entry["object_mode"] = bool(getattr(cs, "object_mode", False))

        def run_once(script=cs):
            return script.run(open_, high, low, close, volume)

        try:
            for _ in range(warmup_run):
                run_once()
            run_stats = _bench(run_once, warmup=0, iters=iters)
            med = run_stats["median_ms"]
            entry["run"] = run_stats
            entry["ms_per_bar"] = med / n_bars
            entry["bars_per_sec"] = (n_bars / (med / 1000.0)) if med > 0 else float("inf")
        except Exception as e:
            entry["run_error"] = str(e)

        # also Runtime compile mode for host overhead comparison
        try:
            from backend.runtime import Runtime

            rt = Runtime(symbol="BENCH")
            # warm host compile path
            for _ in range(2):
                out = rt.run(src, ohlcv, mode="compile")
                if isinstance(out, dict) and out.get("error"):
                    raise RuntimeError(out["error"])
            host_stats = _bench(
                lambda: rt.run(src, ohlcv, mode="compile"),
                warmup=1,
                iters=5,
            )
            entry["runtime_compile_mode"] = host_stats
        except Exception as e:
            entry["runtime_compile_mode_error"] = str(e)

        results[name] = entry
    return results


def profile_interpret(source: str, n_bars: int = 1500, sort: str = "cumtime") -> str:
    from backend.runtime import Runtime

    ohlcv = _make_ohlcv(n_bars)
    rt = Runtime(symbol="PROFILE")
    # warmup
    rt.run(source, ohlcv, mode="interpret")

    pr = cProfile.Profile()
    pr.enable()
    rt.run(source, ohlcv, mode="interpret")
    pr.disable()
    buf = io.StringIO()
    ps = pstats.Stats(pr, stream=buf).sort_stats(sort)
    ps.print_stats(20)
    return buf.getvalue()


def pipeline_cost_breakdown(
    parse_ms: float,
    unparse_ms: float,
    interpret_ms: float,
    cold_compile_ms: float,
    warm_run_ms: float,
) -> dict[str, Any]:
    """Relative costs for a representative ta_combo path.

    Two scenarios:
      A) One-shot interpret (parse once + run bars) — unparse not on hot path
      B) Compile once cold + many warm executes
    """
    interpret_total = parse_ms + interpret_ms
    compile_path = cold_compile_ms + warm_run_ms  # one cold + one run
    return {
        "interpret_oneshot": {
            "parse_ms": parse_ms,
            "run_ms": interpret_ms,
            "total_ms": interpret_total,
            "parse_pct": 100.0 * parse_ms / interpret_total if interpret_total else 0,
            "run_pct": 100.0 * interpret_ms / interpret_total if interpret_total else 0,
        },
        "compile_cold_plus_one_run": {
            "cold_compile_ms": cold_compile_ms,
            "run_ms": warm_run_ms,
            "total_ms": compile_path,
            "compile_pct": 100.0 * cold_compile_ms / compile_path if compile_path else 0,
            "run_pct": 100.0 * warm_run_ms / compile_path if compile_path else 0,
        },
        "unparse_side": {"unparse_ms": unparse_ms},  # LSP/format, not Runtime hot path
    }


def fmt_table(headers: list[str], rows: list[list[Any]]) -> str:
    cols = list(zip(*([headers] + [[str(c) for c in r] for r in rows]), strict=False))
    widths = [max(len(x) for x in col) for col in cols]
    def line(cells: list[str]) -> str:
        return "| " + " | ".join(c.ljust(w) for c, w in zip(cells, widths, strict=False)) + " |"
    out = [line(headers), "| " + " | ".join("-" * w for w in widths) + " |"]
    for r in rows:
        out.append(line([str(c) for c in r]))
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bars-interpret", type=int, default=2000)
    ap.add_argument("--bars-compile", type=int, default=5000)
    ap.add_argument("--profile", action="store_true", help="cProfile ta_combo interpret")
    ap.add_argument("--json", type=Path, default=None, help="Write raw JSON results")
    ap.add_argument("--skip-compile", action="store_true")
    args = ap.parse_args()

    print("=== pynescript pipeline bench ===")
    print(f"repo={_REPO}")
    print(f"python={sys.executable}")

    size_scripts = _load_size_scripts()
    print("\n## Parse / Unparse")
    pu = bench_parse_unparse(size_scripts)
    rows = []
    for label in ("small", "med", "large"):
        r = pu[label]
        rows.append(
            [
                label,
                r["name"],
                r["bytes"],
                f"{r['warm_parse']['median_ms']:.3f}",
                f"{r['warm_unparse']['median_ms']:.3f}",
                f"{r['cold_parse_ms']:.3f}",
            ]
        )
    print(fmt_table(["size", "script", "bytes", "parse_med_ms", "unparse_med_ms", "cold_parse_ms"], rows))

    print(f"\n## Interpret Runtime (n={args.bars_interpret})")
    interp = bench_interpret(SCRIPTS, n_bars=args.bars_interpret)
    rows = []
    for name in SCRIPTS:
        r = interp[name]
        if "error" in r:
            rows.append([name, "ERR", r["error"][:60], "", ""])
        else:
            rows.append(
                [
                    name,
                    f"{r['median_ms']:.2f}",
                    f"{r['ms_per_bar']*1000:.2f} µs",
                    f"{r['bars_per_sec']:.0f}",
                    f"{r['min_ms']:.2f}-{r['max_ms']:.2f}",
                ]
            )
    print(fmt_table(["script", "med_ms", "µs/bar", "bars/s", "min-max_ms"], rows))

    compile_res: dict[str, Any] = {}
    if not args.skip_compile:
        print(f"\n## Compile + Execute (n={args.bars_compile})")
        compile_res = bench_compile_execute(SCRIPTS, n_bars=args.bars_compile)
        rows = []
        for name in SCRIPTS:
            r = compile_res.get(name, {})
            if r.get("error"):
                rows.append([name, "ERR", r["error"][:50], "", "", ""])
            else:
                run = r.get("run") or {}
                rows.append(
                    [
                        name,
                        f"{r.get('cold_compile_ms', float('nan')):.1f}",
                        f"{r.get('warm_compile_ms', float('nan')):.3f}",
                        f"{run.get('median_ms', float('nan')):.3f}",
                        f"{r.get('bars_per_sec', float('nan')):.0f}",
                        "obj" if r.get("object_mode") else "numba",
                    ]
                )
        print(
            fmt_table(
                ["script", "cold_ms", "warm_ms", "run_med_ms", "bars/s", "mode"],
                rows,
            )
        )

    profile_text = ""
    if args.profile:
        print("\n## cProfile ta_combo interpret (top 20 cumtime)")
        profile_text = profile_interpret(SCRIPTS["ta_combo"], n_bars=1500)
        print(profile_text)

    # cost breakdown using med sizes / ta_combo
    med_parse = pu["med"]["warm_parse"]["median_ms"]
    med_unparse = pu["med"]["warm_unparse"]["median_ms"]
    ta_interp = interp.get("ta_combo", {})
    ta_compile = compile_res.get("ta_combo", {}) if compile_res else {}
    breakdown = pipeline_cost_breakdown(
        parse_ms=med_parse,
        unparse_ms=med_unparse,
        interpret_ms=float(ta_interp.get("median_ms", float("nan"))),
        cold_compile_ms=float(ta_compile.get("cold_compile_ms", float("nan"))),
        warm_run_ms=float((ta_compile.get("run") or {}).get("median_ms", float("nan"))),
    )
    print("\n## Pipeline cost (ta_combo-ish)")
    print(json.dumps(breakdown, indent=2))

    payload = {
        "parse_unparse": pu,
        "interpret": interp,
        "compile": compile_res,
        "breakdown": breakdown,
        "profile": profile_text,
        "meta": {
            "bars_interpret": args.bars_interpret,
            "bars_compile": args.bars_compile,
            "python": sys.executable,
            "repo": str(_REPO),
        },
    }
    if args.json:
        args.json.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        print(f"\nWrote {args.json}")

    # always dump to .cache if present
    cache = _REPO / ".cache"
    if not cache.is_dir():
        main_cache = Path("/mnt/data/home/jango/Git/pynescript/.cache")
        if main_cache.is_dir():
            cache = main_cache
    if cache.is_dir():
        outp = cache / "bench_pipeline_latest.json"
        outp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        print(f"Wrote {outp}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
