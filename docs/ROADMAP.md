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

# Pynescript Future Roadmap

**Last Updated:** 2026-08-15 (H1 Runtime unify largely done; tick-offset exits)
**Status:** Core v6 language/builtins essentially closed. Remaining work is
**interpret↔compile plot residuals**, **corpus execution tail**, and optional **TV-oracle
re-baselines** — not missing syntax. Product warm-compile (H2), series caps (T1), and
package Runtime SoT (H1) landed.

---

## Project Status Summary

| Component | Status |
|-----------|--------|
| Parser (ANTLR4) | ✅ v5/v6 + multiline / export const |
| Evaluator | ✅ incl. full var/varip, ReAssign |
| Built-in Functions / TA / collections | ✅ broad (0 missing vs public TV ref list) |
| Strategy Events + broker (OCA, commission, risk) | ✅ |
| Numba + object-mode compile | ✅ MVP+ (disk IR cache, auto mode, `time_arr`, cache recovery) |
| Pro API (Flask) + auth + Docker | ✅ (`mode` default `auto`) |
| pyne-worker (Python CF Worker) | ✅ sibling `hoox-sh/pyne-worker`; thin wrap over package Runtime |
| pine-worker (TS port) | not colocated — sibling `hoox-sh/pine-worker` |
| Drawing / input / request | ✅ (request data mock/feed by design; foreign-na policy landed) |
| Linter / Jupyter / data providers | ✅ |
| LSP (core) | ✅ advanced set; polish only |
| Drawing max_*_count GC | ✅ (package + Pro API + AXIS pyodide) |
| Interpret↔compile plot parity | ⚙️ harness + goldens landed; residual MISMATCH tail open |
| Dual-host Runtime parity | ✅ largely done (package SoT + backend shims + pyne-worker thin wrap) |
| Tests | 1000+ green core suites |

---

## Completed Features

### Quick Wins (All Done ✅)
1. **Better error messages** - Improved with type hints and module suggestions
2. **Code cleanup** - Removed backup files (evaluator_backup.py, technical_new.py)
3. **Type hint improvements** - Enhanced mypy configuration

### Short-term (All Done ✅)
4. **Jupyter support** - Added `pynescript/ext/jupyter.py`:
   - `%%pinescript` cell magic for running Pine Script
   - `create_sample_data()` - Generate OHLCV test data
   - `evaluate_indicator()` - Run indicators with data
   - `display_indicator_table()` - Display as pandas DataFrame

5. **Script validation/linting** - Added `pynescript/ast/linter.py`:
   - 7+ lint rules (version, deprecated patterns, naming, style)
   - CLI: `pynescript lint <file>`

### Medium-term (All Done ✅)
7. **Real data integration** - Added `pynescript/util/data.py`:
   - `MockDataProvider` - For testing
   - `YahooFinanceProvider` - Via yfinance
   - `AlphaVantageProvider` - Free API
   - `CCXTProvider` - 100+ crypto exchanges (historical)
   - Realtime datafeed: `pynescript/util/datafeed.py` using CCXT Pro (watch_ohlcv, trades, etc.) — integrated into evaluator (request.* via context), DataFeedBroker for exec/pos, Mock/Composite, backend/runtime support, tests (2026-07)

---

## Recent Additions (July 2026 consolidation)
- Full `strategy.*` event capture with `StrategyEvent` dataclass, parity test corpus, `var`/`varip` support.
- pine-worker is **not colocated** in this repo (sibling [`hoox-sh/pyne-worker`](https://github.com/hoox-sh/pyne-worker) Python CF host; TS port lives in [`hoox-sh/pine-worker`](https://github.com/hoox-sh/pine-worker)).
- See `.opencode/plans/2026-07-09-main-consolidation-remaining-work.md` for the full consolidation plan.

## Roadmap: Remaining Work (actionable)

Historical Phase A–D “build API / LSP / Jupyter” items are **done**. Do not re-plan them.

### Open backlog (IDs stable for agents)

| ID | Item | Pri | Owner |
| --- | --- | --- | --- |
| **H1** | Port R5–R6 host surface to pyne-worker (fail-cache, `error_kind`, inputs→interpret, compile cache) | P1 ✅ **largely done** — package Runtime SoT + backend shims + pyne-worker thin wrap; residual = worker-only extras (logs/profile, CF first-plot), not a forked bar loop | sibling `hoox-sh/pyne-worker` |
| **H2** | Product warm-compile path (document SLOs; optional prewarm workers; IR cache on in deploy) | P1 ✅ SLOs + prewarm API/CLI + deploy defaults (2026-08); Numba `.nb*` corrupt-cache recovery landed | pyne + ops |
| **C1** | Corpus Runtime residual (set01–04) | P1 ✅ **closed (2026-08-09)** — parse **99.96%** (2476/2477); Runtime interpret **100%** excl. EXPECTED_FAIL (2466 OK + 11 intentional demos); set01 **249/249**. Residual class = intentional `runtime.error` / lower-TF / pathological loop demos only | pyne |
| **P1p** | Compile/interpret **plot parity** residual | P1 ⚙️ harness landed (`scripts/compare_interp_compile.py`, `tests/test_interp_compile_parity.py`); smoke OK on stable TA scripts; residual buckets: value `MISMATCH`, structural hline/fill keys, one-sided runtime errors | pyne |
| **T1** | Cap `current_series` to `max_bars_back` / `_SERIES_MAX` | P2 ✅ `PYNE_SERIES_CAP` default ON + goldens (R7 Agent 03) | pyne |
| **T2** | Incremental TA for remaining heavy kernels (`ta.bb`, nested full paths) | P2 ✅ R7: bb/kama/cmo/stochrsi inc; **wma/hma/linreg inc landed**; further nested full-list helpers residual | pyne |
| **F1** | ATR Wilder / TV supertrend re-baseline **only** with dedicated goldens | P2 ⚙️ **RSI Wilder** compile↔interpret aligned (2026-08 residual); ATR EMA→Wilder and TV supertrend ratchet still require explicit goldens | pyne |
| **F2** | Pending-fill averaging when pyramiding ≤ 0 | P2 ✅ R7 Agent 10 (interpret + compile broker goldens) | pyne |
| **L1** | v5↔v6 converter maturity (`scripts/convert_pine_version.py`) | P3 | pyne |
| **L2** | Webhook alerts productization | P3 ✅ pyne-worker edge + Pro API `/run` export **and** outbound `ALERT_WEBHOOK_URL` / `webhook_url` | pyne-worker + backend |
| **L3** | pine-worker (TS) full builtin parity | P3 | sibling `hoox-sh/pine-worker` |
| **B1** | Real (non-mock) `request.*` market data | ⚙️ by design; **foreign-na policy** landed (same-symbol OHLCV only; foreign/complex `request.security` → `na`, no chart-close-as-dividend) | adapters |

### Phase map

```text
P0 docs honesty → P1 dual-host H1 ✅ (package SoT + shims + worker thin wrap)
                → P1 plot parity residual (P1p) + C1 corpus tail
                → H2 warm compile ✅ · T1 series caps ✅ · F2 pending-fill ✅
                              ↘ T2 residual nested TA · F1 ATR/supertrend goldens
                                  → P6 long-horizon (L1–L3)
```

### By design / out of scope for “missing features”
- Editor-only TV release notes (word wrap, UI)
- Pixel chart host (AXIS / clients)
- Bit-identical every recursive smoother vs live TV (numerical bounds track)
- **Real multi-symbol `request.*` feeds** without a host data provider (mock/chart OHLCV only; foreign tickers correctly return `na` rather than invent series)

### Landed residual notes (2026-08; keep for agents)

- **Compile/interpret plot parity:** Always-on smoke set in `tests/test_interp_compile_parity.py` (e.g. ALMA/ATR/AO-class scripts). Full corpus compare is opt-in via `python scripts/compare_interp_compile.py` (report under `.cache/interp_compile_parity.json`). Flags `--ignore-hline-keys` / `--ignore-fill-keys` drop structural residuals when titled `fill()` / constant `hline` key sets differ by design. Grow goldens from harness `MISMATCH` buckets, not ad-hoc benches.
- **Corpus (C1, 2026-08-09):** set01–04 parse **99.96%** (2476/2477); Runtime interpret **100%** excl. EXPECTED_FAIL (2466 OK + 11 intentional demos: library `runtime.error`, lower-TF security guards, invalid-wrap docs, pathological loops). set01 Runtime **249/249**. Not core syntax gaps.
- **`auto_fib` pivot data limits:** Auto Fib Extension/Retracement raise the same “not enough data / Depth” insufficient-pivot errors on interpret and compile when pivot arrays are empty (normalized as `both_error_same` in the parity harness). Not a silent success path; hosts must supply enough bars or lower Depth.
- **`request.*` foreign-na policy:** `request.security` / bare `security` on foreign symbols or complex expressions resolve to `na` on both backends; `ChartOHLCVProvider` refuses non-chart symbols. Same-symbol simple OHLCV still passthrough. Real fundamentals remain **B1** (adapters).
- **Tick-offset exits (2026-08-15):** `strategy.exit` `profit`/`loss` are ticks × mintick from entry avg (interpret + compile). `limit`/`stop` stay absolute; absolute wins if both set.
- **Incremental WMA / HMA / linreg:** interpret inc kernels landed (`_wma_inc_update` / `_hma_inc_update` / `_linreg_inc_update`); further nested full-list helpers still residual (T2).
- **Plot pack:** interpret host packs dirty plot columns (`_plot_pack_dirty`); compile `_pack_plot_sequence` uniquifies titles.
- **Ring tail-view:** `PYNE_SERIES_RING` chronological tail (default **off**).

### Longer-horizon ideas (not next)
- ML / advanced stats wrappers
- Automatic refactor suggestions
- Parallel / distributed evaluation experiments

---

## Priority Recommendation

### Short-term (Next)
1. **P1p Plot parity residual** — drive down harness `MISMATCH` / one-sided errors with unit goldens
2. **C1 Corpus tail** — residual RUN_FAIL with unit goldens (not one-off scrapes)
3. **H1 residual polish** — worker-only extras (logs/profile, CF first-plot); bar loop is already package SoT

### Medium-term
4. **T2 residual** further nested incremental TA where profiled
5. **F1** Optional ATR Wilder / supertrend fidelity goldens (RSI Wilder already aligned)

### Long-term
6. **L1 / L3** Converter maturity, TS pine-worker parity (**L2 webhooks ✅**)

---

## Usage Examples

### Jupyter
```python
from pynescript.ext.jupyter import load_ipython_extension, create_sample_data
load_ipython_extension(ipython)

# Then in a cell:
%%pinescript
//@version=5
indicator("SMA")
plot(ta.sma(close, 14))
```

### CLI Lint
```bash
pynescript lint script.pine
pynescript lint --fail-on warnings
```

### CLI Data
```bash
pynescript data AAPL --provider mock
pynescript data BTC/USDT --provider ccxt --exchange binance
pynescript data AAPL --provider yahoo --period 6mo
```

### Python API
```python
from pynescript.util.data import get_provider
provider = get_provider("ccxt", exchange="binance")
data = provider.fetch("BTC/USDT", "1y")
```

---

## Contributing

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for guidelines.

---

*This roadmap is a living document and will be updated as the project evolves.*
