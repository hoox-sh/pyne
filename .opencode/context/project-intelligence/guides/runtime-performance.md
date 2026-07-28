# Runtime performance guide

> Companion to `.opencode/plans/2026-07-28-runtime-performance.md` and
> `.grok/skills/pynescript-perf/`.

## Mental model

```
parse once → for each bar: update series → visit(AST) → collect plots/events
```

Pine requires **sequential bars**. Speed comes from cheaper series/TA kernels,
not from skipping the bar loop.

## Highest-ROI safe ideas

1. Do not rebuild OHLCV history with `list(reversed(...))` every bar — append once.
2. Lock function/type/import registration after bar 0 (`_pine_defs_locked`).
3. Incremental `ta.sma`/`ema`/`rsi` with call-site state (behind flag + golden tests).
4. Single Runtime SoT in pynescript; worker thin host.

## Danger zone

- Vectorizing scripts with `if`/`var`/strategy
- Truncating history below recursive MA warm-up without documenting
- Sharing one EMA state across different call sites
- Fixing ATR/VWMA “while optimizing” without parity fixtures (semantics may be wrong today)

## Measure first

```bash
cd /home/jango/Git/pyne-worker
PYTHONPATH=src .venv/bin/python scripts/benchmark.py
```

Track `minimal` (floor) vs `ta_sma` / `ta_combo` / `big_strategy`.
EOF