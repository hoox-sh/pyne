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

## Overall Value: 5/5 (Exceptional / Enterprise-Grade)

PyneScript’s value proposition is unusually strong for an open-source language implementation: it aims for “drop-in” Pine Script v5/v6 parsing plus high-fidelity AST round-trip and broad builtin/indicator coverage, and backs that with a large automated test suite and explicit validation methodology.

## Why This Is High Value

1. Compatibility & Fidelity (10/10)
   - Syntax: 100% v5/v6 syntax compatibility claimed.
   - AST round-trip: 100% structural identity claimed across both fixtures and real-world corpora.
   - Type system: claims full alignment with Pine types (series, arrays, matrix, map, UDTs).

2. Robustness & Validation (10/10)
   - Regression suite: 997 automated tests claimed with 100% pass rate.
   - Real-world scripts: 150+ scripts tested with 98%+ success claimed.
   - Numerical validation: 99.999% precision target with floating-point caveats stated.

3. Feature Completeness (9/10)
   - Builtins: 181+ built-in functions claimed.
   - Technical analysis: 85+ indicators claimed with cross-validation against TradingView® outputs.
   - Minor deduction: several “platform” concerns are explicitly out-of-scope (plot rendering, live feeds, broker simulation).

4. Transparency & Practicality (10/10)
   - Known limitations and performance tradeoffs are documented rather than hidden.
   - Benchmarks are provided for parse/unparse and evaluation operations.

## Best-Fit Use Cases

- Parsing, linting, transforming, and round-tripping Pine Script.
- Backtesting-style analysis in Python where “correctness-first” matters more than real-time execution speed.
- Migration tooling and compatibility testing against Pine v5/v6.

## Caveats (Value Still High)

- Some limitations are by design (no chart rendering, no live feeds); value depends on whether you need those features.
- If you require TradingView-identical execution for all edge cases, the guarantee document’s “95%+ semantic compatibility” should be validated against your own script corpus.
