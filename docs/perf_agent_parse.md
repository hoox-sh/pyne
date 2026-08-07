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

# Parse Performance Agent Report

**Date:** 2026-07-28  
**Scope:** Pine Script source → AST (`parse` / `_parse` / AST builder)  
**Goal:** Speed up parsing without correctness loss.

## Benchmark Setup

- **Python:** `/mnt/data/home/jango/Git/pynescript/.venv/bin/python` (3.14)
- **API:** `from pynescript.ast.helper import parse`
- **Corpus sample:** 12 scripts from `tests/data/builtin_scripts/*.pine`, size-stratified
  (201–2653 bytes): `average_day_range`, `least_squares_moving_average`,
  `moving_average_weighted`, `klinger_oscillator`, `channelbreakoutstrategy`,
  `chande_momentum_oscillator`, `detrended_price_oscillator`,
  `cumulative_volume_index`, `keltner_channels`, `zig_zag`,
  `moving_average_convergence_divergence`, `williams_fractals`
- **Iters:** 20–40 full passes after warmup (also fair A/B LL vs SLL in-process)
- **Complex single:** `auto_fib_extension.pine` (~16 KB)

Note: worktree `tests/data/builtin_scripts/` is empty (gitignore only); benches and
corpus tests used `/mnt/data/home/jango/Git/pynescript/tests/data/builtin_scripts`.

## Baseline (before changes)

| Metric | Value |
| --- | --- |
| Mean pass (12 scripts) | ~1348–1678 ms |
| Mean per script | **~112–140 ms** |
| Ops/sec | **~7–9** |
| Complex (`auto_fib_extension`) | **~1917 ms** |

cProfile (williams_fractals × 25): ANTLR `ParserATNSimulator` dominates (~85%+);
our builder/helper is ~10–15% of wall time. Hot ANTLR: `closure_`, `adaptivePredict`,
`execATNWithFullContext` (full-context fallbacks are expensive).

## Changes Made

### 1. SLL-first parse with LL fallback — `src/pynescript/ast/helper.py`

**What:** Two-stage ANTLR parse (standard ANTLR pattern):

1. `PredictionMode.SLL` + `BailErrorStrategy`
2. On `ParseCancellationException`: `token_stream.seek(0)`, `parser.reset()`,
   `PredictionMode.LL` + `DefaultErrorStrategy`, re-parse

**Why:** SLL avoids full-context prediction (`execATNWithFullContext`) on
unambiguous input. Profile showed frequent full-context work under pure LL.
SLL was **~5.4×** faster in a same-process A/B with **identical** ASTs
(`dump(..., include_attributes=True)` match on 30 stratified scripts; 0
fallbacks on the mid-size sample).

Public API of `parse(source, filename, mode)` unchanged. Syntax errors still
surface as `SyntaxError` via the LL stage / error listener.

### 2. Skip annotation pass when no `@` — `helper.py`

**What:** If `stream.strdata` has no `@`, skip `StatementCollector` + comment
token scan + `_add_annotations`.

**Why:** Annotation comments are always `//@…`. Cheap early exit for scripts
without annotations (and for many micro-snippets).

### 3. Cheaper recursion-limit handling — `helper.py`

**What:** Only call `sys.setrecursionlimit` when current limit &lt; 5000; restore
only when raised. Named constant `_PARSE_RECURSION_LIMIT`.

**Why:** Avoids redundant syscalls on every parse under default elevated limits.

### 4. Faster mode dispatch — `helper.py`

**What:** `_parse_rule(parser, mode)` instead of allocating a dict of bound
methods per parse.

### 5. `_setLocations` / `_getLocations` micro-opt — `src/pynescript/ast/builder.py`

**What:** Cache `stop.text`; use `"\n" in stop_text` before `count`/`rfind`;
single-line fast path (no `count`).

**Why:** Called once per AST node with locations; most tokens are single-line.

## After Numbers

| Metric | Before | After | Change |
| --- | --- | --- | --- |
| Mean per script (12-file mix) | ~112–140 ms | **~14.5 ms** | **~5.4× vs fair LL A/B (~80 ms → ~15 ms, 81.6%)** |
| Ops/sec | ~7–9 | **~69** | **~8–10× vs first cold baseline** |
| Mean pass (12 scripts) | ~1.3–1.7 s | **~175 ms** | |
| Complex 16 KB script | ~1917 ms | **~254 ms** | **~7.5×** |

Fair same-process A/B (12 iters × 12 scripts, alternating):

```
SLL-first (current): pass≈175.7 ms  per≈14.6 ms  ops≈68
LL-only (baseline):  pass≈953.7 ms  per≈79.5 ms  ops≈12.6
speedup: 5.43×   improvement: 81.6%
```

(First cold baseline was slower than the A/B LL arm due to machine noise /
cache; A/B is the better comparison. Either way, well above the ≥3% bar.)

## Correctness

- **AST identity:** SLL path vs forced pure-LL parse: `dump(include_attributes=True)`
  equal on 30 size-stratified builtin scripts (0 mismatches).
- **Annotations:** scripts with `//@` still get `script.annotations` populated.
- **Syntax errors:** still raise `SyntaxError` on incomplete inputs.
- **eval mode:** `parse("1+2", mode="eval")` works.

## Tests Run

| Command | Result |
| --- | --- |
| `pytest tests/test_parse_and_unparse.py -q --tb=line --example-scripts-dir=/mnt/data/home/jango/Git/pynescript/tests/data/builtin_scripts` | **138 passed** |
| `pytest tests/test_for_loop_syntax.py tests/test_lexer_corpus_fixes.py -q` | **13 passed** |
| `ruff check src/pynescript/ast/helper.py src/pynescript/ast/builder.py` | **All checks passed** |

(Default worktree corpus dir is empty → without `--example-scripts-dir` the
parametrized test is collected as a single SKIP.)

## Residual Opportunities (not taken)

| Opportunity | Risk / notes |
| --- | --- |
| Cache DFA / share lexer+parser instances across parses | High risk of state bleed; ANTLR interpreter caches grow with unique inputs; threading concerns |
| Pure SLL without LL fallback | Incorrect trees if SLL decides differently on ambiguity (we proved SLL OK on sample, but fallback is the safe ANTLR pattern) |
| Grammar simplifications to cut `adaptivePredict` | Touches `resource/*.g4` + generated code — out of scope; high correctness risk |
| Cython/Nuitka for builder visit methods | Build complexity; our builder is already &lt;15% of time after SLL |
| Skip `token_stream.fill()` when comments not needed | Minor; already skip comment collect when no `@` |
| Optimize `StatementCollector` / visitor further | Tiny vs ANTLR; low ROI after SLL |
| Parallel parse of independent files | API-level / call-site concern, not in-process parse micro-opt |
| Measure SLL fallback rate on full library corpus | Low risk investigation; if high on some styles, document when LL path dominates |

## Files Changed

- `src/pynescript/ast/helper.py` — SLL-first + LL fallback, annotation early exit, recursion limit, `_parse_rule`
- `src/pynescript/ast/builder.py` — `_setLocations` / `_getLocations` single-line fast path
- `docs/perf_agent_parse.md` — this report

**Not changed (constraints):** `generated/*`, `resource/*.g4`, public `parse(...)` signature.
