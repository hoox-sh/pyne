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

**Last Updated:** 2026-08-01 (roadmap honesty pass + residual P1–P6 open list)  
**Status:** Core v6 language/builtins essentially closed. Remaining work is **host parity**,
**corpus execution tail**, **product compile path**, and optional **TV-oracle re-baselines** —
not missing syntax.

---

## Project Status Summary

| Component | Status |
|-----------|--------|
| Parser (ANTLR4) | ✅ v5/v6 + multiline / export const |
| Evaluator | ✅ incl. full var/varip, ReAssign |
| Built-in Functions / TA / collections | ✅ broad (0 missing vs public TV ref list) |
| Strategy Events + broker (OCA, commission, risk) | ✅ |
| Numba + object-mode compile | ✅ MVP+ (disk IR cache, auto mode) |
| Pro API (Flask) + auth + Docker | ✅ (`mode` default `auto`) |
| pine-worker (Python CF Worker) | ✅ edge host; dual-host drift open |
| pine-worker (TS port + converter) | ✅ colocated extra tool (port ongoing) |
| Drawing / input / request | ✅ (request data mock/feed by design) |
| Linter / Jupyter / data providers | ✅ |
| LSP (core) | ✅ advanced set; polish only |
| Drawing max_*_count GC | ✅ (package + Pro API + AXIS pyodide) |
| Dual-host Runtime parity | ⬜ open (largest P1) |
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
- `pine-worker/` — TypeScript evaluator port + `scripts/convert-python-to-ts.py` converter, treated as extra tool of the main repo.
- See `.opencode/plans/2026-07-09-main-consolidation-remaining-work.md` for the full consolidation plan.

## Roadmap: Remaining Work (actionable)

Historical Phase A–D “build API / LSP / Jupyter” items are **done**. Do not re-plan them.

### Open backlog (IDs stable for agents)

| ID | Item | Pri | Owner |
| --- | --- | --- | --- |
| **H1** | Port R5–R6 host surface to pyne-worker (fail-cache, `error_kind`, inputs→interpret, compile cache) | P1 ✅ host surface + **alerts export** dual-host (Aug 2026); package-level Runtime unify still open | pyne-worker + backend |
| **H2** | Product warm-compile path (document SLOs; optional prewarm workers; IR cache on in deploy) | P1 | pyne + ops |
| **C1** | Corpus TIMEOUT / RUN_FAIL residual (set01–04 ~90% → **~94.3%** OK projected after 8-agent pass) | P1 ⚙️ ongoing (~21 RUN_FAIL + PARSE stubs ~118) | pyne + pyne-worker |
| **T1** | Cap `current_series` to `max_bars_back` / `_SERIES_MAX` | P2 | pyne |
| **T2** | Incremental TA for remaining heavy kernels (`ta.bb`, nested full paths) | P2 | pyne |
| **F1** | ATR Wilder / TV supertrend re-baseline **only** with dedicated goldens | P2 | pyne |
| **F2** | Pending-fill averaging when pyramiding ≤ 0 | P2 | pyne |
| **L1** | v5↔v6 converter maturity (`scripts/convert_pine_version.py`) | P3 | pyne |
| **L2** | Webhook alerts productization | P3 ✅ pyne-worker edge + Pro API `/run` export **and** outbound `ALERT_WEBHOOK_URL` / `webhook_url` | pyne-worker + backend |
| **L3** | pine-worker (TS) full builtin parity | P3 | pine-worker tool |
| **B1** | Real (non-mock) `request.*` market data | ⚙️ by design | adapters |

### Phase map

```text
P0 docs honesty → P1 dual-host (H1) → P2 corpus (C1) + P3 warm compile (H2)
                              ↘ P4 series caps / residual TA (T1/T2)
                                  → P5 optional TV re-baselines (F1/F2)
                                  → P6 long-horizon (L1–L3)
```

### By design / out of scope for “missing features”
- Editor-only TV release notes (word wrap, UI)
- Pixel chart host (AXIS / clients)
- Bit-identical every recursive smoother vs live TV (numerical bounds track)

### Longer-horizon ideas (not next)
- ML / advanced stats wrappers
- Automatic refactor suggestions
- Parallel / distributed evaluation experiments

---

## Priority Recommendation

### Short-term (Next)
1. **H1 Dual-host Runtime** — pyne-worker host parity with SoT `backend/runtime.py`
2. **C1 Corpus tail** — fix high-frequency RUN_FAIL with unit goldens
3. **H2 Warm compile product path** — SLOs + deploy defaults

### Medium-term
4. **T1/T2** Series memory caps + residual incremental TA
5. **F1/F2** Optional fidelity goldens (opt-in oracle changes)

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