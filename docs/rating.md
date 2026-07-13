# Copyright 2024-2025 Yunseong Hwang, jango_blockchained
#
# Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.gnu.org/licenses/lgpl-3.0.en.html
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: LGPL-3.0-or-later

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
