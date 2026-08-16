# Agent 03 — P1p interpret ↔ compile **value** MISMATCH tail

| Field | Value |
| --- | --- |
| **Role / ID** | 03 — residual P1p numeric series |
| **Verdict** | **partial win** |
| **Date** | 2026-08-16 |
| **Oracle** | Interpret. Compile fixed to match. Never silent na→0. |

## What ran

```
PYTHONPATH=src:. .venv/bin/python -m pytest tests/test_interp_compile_parity.py -q
# 18 passed, 18 skipped (optional builtin_scripts/ absent)

PYTHONPATH=src:. .venv/bin/python scripts/compare_interp_compile.py \
  --dir tests/fixtures/first_party --limit 0 --bars 200 --workers 1 --no-sanitize
# 8/8 OK, 0 MISMATCH

PYTHONPATH=src:. .venv/bin/python scripts/compare_interp_compile.py \
  --bars 200 --ignore-hline-keys --ignore-fill-keys --files \
  tests/data/set01/indicators/245_ind_hma_kahlman_trend_clipping_and_trendlines.pine \
  tests/data/set02/indicators/178_ind_bulls_bears_index_bbi_2.pine \
  tests/data/set02/strategies/071_str_multi_vwap_crossover.pine
# 178 OK; 071 values OK + structural keys; 245 type/na (v4 wma interpret-all-na)

Verify (required + new goldens):
  tests/test_interp_compile_parity.py
  tests/test_first_party_ta_goldens.py
  tests/test_p1p_mismatch_goldens.py
# 32 passed, 18 skipped
```

First-party fixtures (`plot_close`, `sma`, `ema`, `rsi`, `strategy_entry`, `atr`, `keltner`, `supertrend`) are clean on values.

## Found (classified)

| Item | Class | Owner |
| --- | --- | --- |
| MACD signal/hist first-value seed vs interpret SMA seed | **value bug (compile)** | **fixed here** |
| `ta.obv` compile included bar-1 change; interpret `_obv` skips it (locked by `test_evaluator_ta_obv` = -50) | **value bug (compile)** | **fixed here** |
| `ta.ao` / `ta.aroon` unmapped → compile all-na | **value bug (compile missing kernel)** | **fixed here** |
| `245` HMA-Kahlman `plot_0`/`plot_1` interp=na compile=finite | interpret v4 `wma()` always-na (v5 `ta.wma` dual-host OK) | interpret dispatch, not compile |
| `245` `plot_5`/`plot_6` vs `plot_3`/`plot_4` | structural keys | Agent 04 |
| `071` Midnight/Session VWAP | **values now OK** | — |
| `071` `Outside Backtest Range` / `Session Shading` | structural keys | Agent 04 |
| `178` BBI | **already OK** this tree | — |
| MACD/CCI warmup interp=`0.0` compile=`na` | interpret na→0; compile kept na | do not copy 0 |
| Stoch warmup interp=partial-window compile=`na` | post-warmup values already match | leave compile na |
| `ta.pvt` interp=non-cumulative + bar0 na; compile=cumulative + bar0 0 | interpret `_vpt` ignores its own “previous VPT +” comment | leave compile (TV-like). Not silent-fill of a finite series |
| v4 bare `wma(close, 22)` interpret all-na | interpret builtin map | not compile |
| `ta.nvi` / `ta.pvi` compile `NameError` | foreign / T2 leftover | Agent 01 |
| Supertrend formula | owned elsewhere | Agent 02 |
| `ta.cog` / `ta.mode` / `ta.range` / `ta.percentile_linear_interpolation` compile all-na | missing kernels | residual |
| `request.*` foreign | leave | — |

## Fixed

Interpret is the oracle. Compile kernels/emit only.

1. **MACD signal SMA seed** (`numba_macd` / `numba_macd_inc`)
   - Was: first-value seed at first valid MACD bar (`slow-1`) → post-warmup drift vs interpret `_ema` on the MACD line.
   - Now: SMA seed over first `signal` finite MACD samples; first finite signal at `slow + signal - 2` (33 for 12/26/9). Warm-up stays **na**, not 0.
   - State vector `[ema_f, ema_s, sig, last_i, seed_n, seed_sum]` (size 4 → 6). `compiler.py` alloc + `engine.py` prewarm updated.

2. **OBV skip-first-change** (`numba_obv` / `numba_obv_inc`)
   - Matches interpret `_obv`: `0` until 3 samples; accumulate from index 2 (skip `close[0]` vs `close[1]`).
   - Dual-host OBV now allclose on synthetic bars.

3. **`ta.ao`** — `numba_ao(high, low, fast, slow, i)` = `SMA(hl2, fast) - SMA(hl2, slow)` (default 5/34). Wired as `ta.ao` / `ta.ao()` / bare `ta.ao`.

4. **`ta.aroon`** — `numba_aroon` returns `(down, up)` with `length+1` window, oldest-extreme ties. Wired + added to multi-return unpack prefixes.

## Goldens

`tests/test_p1p_mismatch_goldens.py`

- `test_macd_signal_sma_seed_interp_compile` — compile signal first finite at 33; overlapping finite cells match; compile not 0-filled.
- `test_obv_skip_first_change_interp_compile` — bar 0/1 are 0; series match; bar 2 = ±`volume[2]` only.
- `test_ao_aroon_interp_compile` — AO first finite at 33; Aroon at 14; dual-host match.

## Remaining

- **245 / v4 `wma`**: compile is numerically right; interpret never produces WMA. Not fixed (interpret-owned).
- **Structural keys** (hline/fill/bgcolor/plotshape, 071 session shade, 245 plot index): Agent 04.
- **Interpret warmup 0 vs compile na** (MACD/CCI): left as-is (never silent na→0 on compile).
- **Unwired compile TA**: cog / mode / range / percentile_linear_interpolation / dc / ac (both-na or compile-na).
- **PVT accumulation** vs interpret last-bar-only: interpret bug; compile stays cumulative.
- **nvi/pvi, supertrend formula, trail broker, Flask**: other agents.

## Files touched

- `src/pynescript/compiler/numba_builtins.py` — MACD seed, OBV window, `numba_ao`, `numba_aroon`
- `src/pynescript/compiler/compiler.py` — emit + unpack + `ta.ao` bare attr
- `src/pynescript/compiler/engine.py` — MACD prewarm state size 6
- `tests/test_p1p_mismatch_goldens.py` — new
- `docs/gaps_close_2026-08-16/AGENT_03_p1p.md` — this report

No commit.
