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

# Project Rating (Value)

This rating is based on the published claims and evidence in [docs/compatibility_guarantee.md](compatibility_guarantee.md).

## Overall Value: 4/5 (Strong for Tooling)

PyneScript offers a solid open-source Pine Script v5/v6 parser + AST + evaluator implementation with good test coverage. It excels at parsing, round-tripping, linting, and running many indicators/strategies in Python. Some advanced execution fidelity and platform features are still maturing or out of scope.

## Why This Is High Value

1. Compatibility & Fidelity (8/10)
   - Syntax: Strong v5/v6 syntax compatibility (verified on 100+ real scripts).
   - AST round-trip: High structural fidelity on real corpora.
   - Type system: Good alignment with Pine types (series, arrays, matrix, map, UDTs, strategy).

2. Robustness & Validation (8/10)
   - Regression suite: 1142 automated tests with full pass rate on core.
   - Real-world scripts: 138+ scripts tested with high parse/roundtrip success.
   - Full pytest: 1142 passed, 4 skipped.

3. Feature Completeness (7/10)
   - Builtins: 200+ built-in functions.
   - Technical analysis + strategy: Broad coverage with tests.
   - Deductions: Plotting is stubbed/no-op in evaluator; some broker/live features out of scope; full semantic parity for complex strategies continues to improve.

4. Transparency & Practicality (9/10)
   - Known limitations documented.
   - Strong parser foundation for tooling.

## Best-Fit Use Cases

- Parsing, linting, transforming, and round-tripping Pine Script.
- Backtesting-style analysis in Python where “correctness-first” matters more than real-time execution speed.
- Migration tooling and compatibility testing against Pine v5/v6.

## Caveats (Value Still High)

- Some limitations are by design (no chart rendering, no live feeds); value depends on whether you need those features.
- If you require TradingView-identical execution for all edge cases, the guarantee document’s “95%+ semantic compatibility” should be validated against your own script corpus.
