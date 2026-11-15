# Pyne engineering review (0.7.0)

Reviewed `hoox-pyne` **0.7.0** on Python 3.12 (`main` at `b2f2012f`). Install was `pip install -e ".[lsp,compile,dev-lsp]"`. Numba 0.68.1.

[PR #73](https://github.com/hoox-sh/pyne/pull/73) and [PR #72](https://github.com/hoox-sh/pyne/pull/72) are both **merged**. This note does not repeat those fixes (`na` as a false condition, dynamic `for … to`, dividend-signed `%`, UTF-16 S001/S002 columns, `pyne execute --timeframe`, `.pyne` directory checks, `SyntaxError.__str__`, series/simple tokens, comment-preserving format, the LSP qualifier lattice).

## What was exercised

| Surface | Result |
| --- | --- |
| `pyne check examples/rsi_strategy.pine` | Parses. |
| `pyne execute` interpret and compile, 80 synthetic bars | RSI last value matches (`80.057…`). Compile of this strategy is object mode. |
| `pyne info` / `pyne-lsp --version` | 0.7.0, Numba present. |
| `pyne execute` input metadata | Interpret and compile both report `inputs_count` 3 and the same three literal declarations (RSI Length, Oversold, Overbought). |
| Differential scripts | A small interpret-vs-compile harness over arithmetic, `iff`, `math.round` / `math.log` / `math.pow`, comparisons, and `for`. Mismatches below were reproduced, then the low-risk ones were fixed and pinned in `tests/test_compile_expr_parity.py`. |
| Tests | Evaluator, CLI, linter, LSP, Numba compiler, first-party goldens, and the new parity file: **844 passed**, 9 skipped in the main slice, then strategy/realtime/expr parity **197 passed**. Backend tests need `hoox-pyne[pro]` (Flask); they were not installed here, so that slice was not run. `tests/test_set06_pine_int_na.py` now skips when the local corpus is absent. |

Uncached parse of `examples/rsi_strategy.pine`, after the parser module is imported, is about **7.1 ms** (mean of ten unique sources). A cache hit is about **0.12 ms**. A 2,000-bar script plotting `ta.sma`, `ta.ema`, `ta.rsi`, and `ta.atr` ran at about **61k bars/s** interpreted and about **2.2M bars/s** compiled (Numba, after warm-up). `cProfile` still puts cold parse time inside the generated ANTLR parser and interpret time inside `visit_Call`.

## Fixes in this change

### 1. `iff(na)` took the then-branch on compile — medium

Interpret returns `na` (`numeric.py` `_builtin_iff`). Compile emitted `a if np.nan else b`, and `bool(nan)` is true, so `iff(na, 1, 0)` plotted `1`.

A walrus ternary that returns `na` for a NaN condition does not type-check under Numba when the condition is a bool (`close > open`). `iff` is a call on the interpreter, so both arguments already run before the builtin. Compile now calls `pine_iff`, which is njit-overloaded, returns `na` for a NaN or `None` condition, and stays nopython for `plot(iff(close > open, 1, 0))`.

Location: `compiler.py` `iff` arm, `numba_builtins.py` `pine_iff`.

### 2. `math.round` ignored precision on compile — high

`math.round(1.234, 2)` was `1.23` interpreted and `1` compiled. `math.round(123.45, -1)` was `120` vs `123`. `numba_round` passes the precision through `np.round`. A NaN precision rounds to 0 decimals. One-argument half-values stay banker's (`math.round(2.5)` is `2` on both hosts).

### 3. `math.log` ignored the base, and base 1 aborted interpret — high

`math.log(100, 10)` was `2` interpreted and `ln(100)` compiled. `math.log(10, 1)` raised `ZeroDivisionError` on interpret and plotted a finite log on compile. Both hosts now return `na` for a non-positive argument or a base of `1`. Compile uses `numba_log` (change of base, one evaluation of each argument).

### 4. `math.pow(na, 0)` was `1` on compile — medium

IEEE `nan ** 0` is `1`. Interpret returns `na`. `numba_pow` propagates `na`.

### 5. Operator `na == na` was true on compile — medium

`na == na ? 1 : 0` plotted `0` interpreted and `1` compiled, because every numeric `==` used `numba_pine_eq` (`na == na` is true). That helper is the right rule for **switch** arms (`switch na` / `na =>`). The operator now uses IEEE `==` after `na` is `np.nan`, so `na == na` is false. `!=` stays on `numba_pine_ne` (`na != 1` is false; IEEE `!=` would be true). Switch is unchanged and still selects the `na` arm.

### 6. `for i = 0 to i` after `i = 5` ran six times on compile — medium

Interpret evaluates `to` against the pre-loop binding, then the counter shadows that name, so the loop body runs once (`s` is `1`). Compile stored `i` as `i_arr` and re-read `i_arr` every iteration, so the end stayed `5` (`s` is `6`). The same shape with `i = -3` ran four times on compile and once on interpret.

The first `to` is now emitted before the counter is assigned. When `to` reads the counter and contains no call, the per-iteration re-read is visited again after the counter is bound, so it sees the scalar. A call inside `to` is not visited twice (that would allocate a second TA state buffer). `limit = 2` / `limit := 0` still stops after one iteration.

`for i = 0 to i` with no previous `i` still does not run (both hosts, `s` is `0`).

### 7. Compile dropped `input.*` declarations — medium

`Runtime.run(mode="compile")` set `inputs` to `[]`. Interpret recorded the declarations. Literal global `input` / `input.*` calls are now folded with the same keyword order as the handlers (`minval` → `min`, and so on) and copied onto the compile result and `meta.inputs`. Non-literal arguments skip that call rather than inventing a default. Overrides remain interpret-only. `examples/rsi_strategy.pine` matches on both hosts, including through `pyne execute` (`inputs_count` 3).

### 8. Symbol-index failures were silent — medium

`build_symbol_index` exceptions in `ensure_symbol_index` and in `Workspace._parse_and_lint` are logged at debug. When the buffer parsed but the index raised, publish adds one **E002** diagnostic and leaves navigation/semantic checks empty. Pinned by `test_symbol_index_failure_is_a_diagnostic`.

### 9. README version and CI — low

`README.md` still said **0.6.32**. The package line is **0.7.0**. Docker examples still pull `0.6.31`; those tags were not changed here. CI's runtime job now runs `tests/test_compile_na_parity.py` and `tests/test_compile_expr_parity.py`. `tests/test_set06_pine_int_na.py` skips the corpus cases when `tests/data/set06/` is absent instead of raising `FileNotFoundError`.

Disk IR schema is **55** so cached modules from the previous emitter are not reused.

## Still open

### F2. v6 `and` / `or` are eager — medium, intentional

Both hosts still evaluate every operand (`expressions.py` `visit_BoolOp`, `compiler.py` `visit_BoolOp`) so v5 series state stays continuous. v6 Pine is lazy. Not changed: it moves `ta.*` state inside dead arms and needs goldens.

### F3. `math.round` ties — low, not switched

One-argument `math.round(2.5)` is `2` and `math.round(-2.5)` is `-2` on both hosts (Python / NumPy half-to-even). Secondary write-ups disagree on Pine: several say ties go toward +∞ (`2.5` → `3`, `-2.5` → `-2`), which would change only the positive tie relative to today; others say away from zero (`-2.5` → `-3`). There is no vendored TradingView column for the tie. Left as banker's until a golden exists.

### F5. S002 still misses non-name callees — low

`semantic_diagnostics.py` `_call_arity` only walks `Call` nodes whose callee is a bare `Name` that resolves to a user function. Reproduced with semantic diagnostics on: `h = f` then `h(1, 2)`, and `ta.sma(close, close)`, produce no diagnostic. Builtin parameter qualifiers are still absent from the catalog (PR #72).

### F-LSP. Pyne Edge gaps from #72 — still open

Re-checked against current `analysis.py` / `semantic_diagnostics.py`. Still true:

- Builtin parameter qualifiers are not checked (`ta.sma(close, close)`).
- No diagnostic suggests `nz()` / `fixnan()` for values that can be `na`. Only untyped `na` is S004.
- `var` / `varip` persistence is not analyzed.
- History `[]` promotes to `series` and does not warn when Pine would reject `[]` on a non-series value.
- Unqualified UDT fields are not treated as `series`.
- Non-`math` builtin returns follow the catalog. `math.abs(1)` is `const float`, not `const int`.
- `Type.is_compatible_with` (`type_system.py`) is still equality for `BuiltinType`. The compiler does not use the LSP lattice.
- Comment formatting does not restore blank lines the unparser drops.

### F-struct. Two type stories — large, not started

LSP `analysis.py` infers qualifier strings. The compiler infers overload tags in `compiler.py`. The runtime `Type` / `TypeRegistry` is unused by the language server. Hover, arity, and compile overload choice can drift. Unifying them is a redesign.

### Other leftovers

- `for` end expressions that both mention the counter **and** call a function still re-read the pre-loop series. A second visit would double-allocate TA state.
- Compile input metadata skips a call when any argument is not a literal.
- `docs/optimization_notes.md` still describes an 859-test suite and a one-time ~2% speedup. The code has SLL-then-LL parse, a parse LRU, and the series ring.
- Other `tests/test_set06_*.py` files still open `tests/data/set06/` and raise `FileNotFoundError` on a fresh clone. Only `test_set06_pine_int_na.py` skips.
- `pyne download-builtins` and `list_facade_templates` imported `pynescript.util.pine_facade`, which was deleted in `e90563c7`. They now fail closed with "removed" instead of `ImportError`. The downloader was not restored.
- `mypy src/ --ignore-missing-imports` is still `|| true` in CI.
- README docker examples still say `0.6.31`.

## Optimization proposals

Measured on this machine unless noted. 2,000 bars, four `ta.*` plots.

| Rank | Change | Evidence | Impact | Effort |
| --- | --- | --- | --- | --- |
| 1 | Keep numeric scripts on compile / `auto` | Interpret ~61k bars/s, compile ~2.2M bars/s (~36×) after JIT. Profile: `visit_Call` dominates interpret. | High for numeric studies | M — widen eligibility, don't change semantics |
| 2 | Do not pay ANTLR on an unchanged buffer | Uncached RSI parse ~7.1 ms; cache hit ~0.12 ms. Profile is `PinescriptParser.*`. LSP still reparses the whole buffer on each debounced edit. | High for the editor | L for an incremental parser. S to avoid hashing the full source before the cache lookup in `helper.py` `parse` |
| 3 | One series representation | `runtime/series.py` keeps a newest-first deque and a chronological list unless `PYNE_SERIES_RING` is on. TA windows then copy a reversed list. | High on long interpret histories | L — flip the default only with the TA goldens |
| 4 | Index occurrences by line | `analysis.py` `occurrence_at` / `scope_at` scan every occurrence and every scope. | Medium on large files | S |
| 5 | Stop scanning from byte 0 for comments | `protocol/utils.py` `in_comment_or_string` walks the prefix of the file per request. | Medium at EOF of large files | S — per-line flags |
| 6 | Realtime snapshots | `compiler.py` copies list/dict state on unconfirmed ticks. Idle when `realtime_ticks` is 1. | High only for multi-tick realtime | M |
| 7 | Rewrite `docs/optimization_notes.md` | The 2% suite figure and the 859-test count are stale. | Docs only | S |

No hot-path rewrite landed with these fixes. The new helpers (`pine_iff`, `numba_round`, `numba_log`, `numba_pow`) are njit-overloaded so numeric scripts stay on the fast path.

## Structure proposals

| Rank | Proposal | Why | Effort |
| --- | --- | --- | --- |
| 1 | One type story | LSP strings, compiler overload tags, and `type_system.Type` are three models. `is_compatible_with` does not implement the qualifier lattice the LSP already has. | L |
| 2 | Split `compiler.py` | Emit, strategy, request, plot wire format, and the numeric-safety heuristic live in one visitor. A mistake in `_is_safe_numeric_expr` silently forces object mode. | L |
| 3 | Split `numba_builtins.py` | Kernels and coercion helpers are star-imported. Names must stay public. Group TA kernels vs coercion so the import surface is explicit. | M |
| 4 | Skip every local-only corpus test | `test_set06_pine_int_na.py` skips. Sibling `test_set06_*.py` files still crash when `tests/data/set06/` is absent. | S |
| 5 | Delete or gate the removed facade | `download-builtins` fails closed. Unit tests that imported `pine_facade` skip. The CLI help still advertises the command. Removing the command is a public-API change; left for a deliberate cleanup. | S |
| 6 | Dead branch in `visit_BinOp` | After `return f"pine_add(...)"` for Name+Name adds inside a function, the following string-arithmetic branch is unreachable. String `+` / `-` on the scripts tried here already match. | S |

`compiler.py` and `host.py` are still where a small semantic fix is most likely to knock a script off nopython or out of the disk IR cache. Bump `_DISK_META_VERSION` when generated code changes. It is 55.

## Tests

- `tests/test_compile_expr_parity.py` — interpret vs compile for `iff`, round precision, log base, `pow(na, 0)`, `na == na`, switch-on-`na`, shadowed `for`, literal inputs, nopython retention, and E002.
- `tests/test_compile_na_parity.py` — previous `na` / modulo / `for` pins; still green, now on the CI runtime job.
- `tests/test_set06_pine_int_na.py` — corpus cases skip when the tree is absent.
- `tests/test_mcp_ops_low_coverage.py`, `tests/test_cli_util_coverage.py` — removed facade fails closed.
