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

# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the

# GNU Affero General Public License for more details.

#

# SPDX-License-Identifier: AGPL-3.0-or-later

# PyneScript Compatibility Guarantee

Product map (working / partial / residual / out of scope):
[docs/pyne/reference/compatibility.mdx](pyne/reference/compatibility.mdx).
Repo-root distillation of the same map.

---

## Executive Summary

**PYNE** (PyPI **`hoox-pyne`**, import `pynescript`) provides strong syntax compatibility (full parser coverage for v5/v6 grammar on real scripts) and good semantic compatibility with TradingView® Pine Script™ v5/v6. The parser, AST, and builtins (including technical indicators and strategy support) are implemented and covered by tests.

**Compatibility is not full TradingView® platform parity.** PYNE is an independent language engine, not a hosted chart host, not a proprietary multi-symbol data feed, and not an editor UI. Numerical results match reference Pine within floating-point bounds on the supported surface — they are not bit-identical on every script or bar.

**Interpret ↔ compile plot parity** is a first-class testing pillar: same script + OHLCV under `Runtime.run(..., mode="interpret")` vs `mode="compile"`, compared with nan-aware allclose (`scripts/compare_interp_compile.py`, `tests/test_interp_compile_parity.py`). Residual value `MISMATCH` buckets and structural hline/fill key differences are tracked deliberately.

**Foreign `request.*` / NA policy:** compile does not invent multi-asset series. Same-symbol simple OHLCV may lower; foreign tickers and complex `request.security` expressions resolve to `na` on both backends when data is absent (prefer honest NA over chart-close-as-foreign).

---

## Compatibility Metrics

The product-facing numbers below come from the live dispatch surface and the open-source corpus (set01–04, measured locally, **not shipped** in git):

| Category                           | Result                       | Notes                                                          |
| ---------------------------------- | ---------------------------- | -------------------------------------------------------------- |
| Dispatch builtins (callable)       | **941**                      | Live `NodeLiteralEvaluator` map                                |
| Dispatch namespaces                | **255**                      | `ta`, `strategy`, `array`, `matrix`, …                         |
| Official TV v6 function reference  | **434 symbols — 0 missing**  | A registered name is not the same as hosted-platform semantics |
| Partial-heuristic dispatch entries | **10**                       | Stub/mock docstrings; real partials may be higher              |
| Parse + unparse (set01–04)         | **99.96%** (2,476/2,477)     | Residual: 1 intentional invalid line-wrap demo                 |
| Runtime interpret (50 bars)        | **100%** excl. EXPECTED_FAIL | 2466 OK + 11 intentional demos                                 |
| set01 Runtime                      | **249/249** (100%)           |                                                                |

EXPECTED_FAIL scripts are path-listed intentional demos — not silent suppression.

---

## Grouped Map (distilled)

| Class            | Scope                                                       | Examples                                                                                                                                           |
| ---------------- | ----------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Working**      | Implemented, usable, covered by first-party tests           | Language core, series, TA hot path, collections, strategy broker, drawings, alerts, libraries, interpret Runtime                                   |
| **Partial**      | Callable but mock, host-bound, or incomplete vs hosted Pine | `request.*` feeds (honest `na`), compile eligibility, nopython compile alerts (`[]`; object-mode compile exports firings), PyneTS vs Python oracle |
| **Residual**     | Known open hole on an otherwise landed surface              | Plot MISMATCH corpus tail (P1p official builtins closed), `PYNE_SERIES_RING` default off                                                           |
| **Out of scope** | Intentionally not a TV platform clone                       | Pixel chart, editor UX, foreign live fundamentals, bit-identical TV bars                                                                           |

---

## Key Guarantees (honestly scoped)

1. **Syntax:** All valid Pine Script v5/v6 grammar in the resource grammar parses. Round-trip `parse → unparse → parse` preserves semantics (whitespace may differ).
2. **Language surface:** 0 missing dispatch entries vs the public TV v6 function reference list. Registered callables exist; semantic parity is best-effort, not guaranteed identical on every edge.
3. **Numerical:** Errors within IEEE 754 floating-point limits on validated kernels (see `docs/numerical_validation_report.md`, v1.0 Nov 2025). Not eternal SLAs — re-validate after smoother changes.
4. **Foreign data:** Honest `na` — no inventing chart close as foreign fundamentals.
5. **Alerts:** `alert()` / `alertcondition()` firings exported on `/run`; L2 webhooks optional.

---

## Known Limitations

### By design (not compatibility issues)

| Area                    | Limitation                                 | Reason                                              |
| ----------------------- | ------------------------------------------ | --------------------------------------------------- |
| Real-time data          | No live market feeds                       | Library design; use external data provider          |
| Plot rendering          | No chart visualization                     | AST focus; pixels are AXIS / clients                |
| Request functions       | Mock / same-symbol; foreign → `na`         | Requires external API integration; honest NA policy |
| Strategy backtesting    | OHLC-path broker simulation, not tick-path | In-process model only                               |
| Pixel chart / editor UI | Not this runtime                           | AXIS / editor clients are separate products         |

---

## Verification Resources

### Run tests yourself

```bash
# Clone repository
git clone https://github.com/hoox-sh/pyne.git
cd pynescript

# Install dependencies
pip install -e ".[lsp,pro,compile]"

# Core unit slice
python -m pytest tests/test_linter.py tests/test_evaluator.py tests/test_cli.py -q

# Interpret ↔ compile parity
pytest tests/test_interp_compile_parity.py -q

# Incremental TA parity
pytest tests/test_ta_incremental.py -q
```

Numerical validation: see `docs/numerical_validation_report.md`.

Real-world scripts: first-party fixtures under `tests/fixtures/`. Third-party corpora are not shipped.

---

## License

- **License:** AGPL-3.0-or-later
- **Copyright:** 2024-2026 jango_blockchained
- **Warranty:** See LICENSE file

## Contact

- **Documentation:** https://hoox.sh/pyne/docs
- **GitHub:** https://github.com/hoox-sh/pyne
- **Issues:** https://github.com/hoox-sh/pyne/issues
