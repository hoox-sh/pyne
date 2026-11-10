# Pyne engineering review

Reviewed `hoox-pyne` 0.6.34 (parser, interpreter, Numba compiler, CLI, `pyne-lsp`) on Python 3.12. Install was `pip install -e ".[lsp,compile,dev-lsp]"`. Core CI tests (`test_linter`, `test_evaluator`, `test_cli`) passed, 339 tests. A wider slice (evaluator, parity, compiler/Numba, LSP) passed after the fixes below. `examples/rsi_strategy.pine` runs on both hosts and the RSI column matches.

This PR fixes the bugs that were small, reproduced, and covered by regression tests. Larger redesigns are proposals only.

A separate effort already owns three LSP gaps. They are listed at the end and are not changed here: series/simple semantic tokens, comment-preserving formatting, and Pyne Edge series/`na` type propagation.

## What was exercised

| Surface | Result |
| --- | --- |
| `pyne check examples/rsi_strategy.pine` | Parses. |
| `pyne execute … --mode interpret` and `--mode compile` | Both succeed. RSI last value matches (`82.262…`). Compile of this strategy is object mode. |
| `pyne info` | 0.6.34, Numba present, Rich and the MCP extra not installed in this environment. |
| `pyne execute --timeframe` | The flag was printed and ignored. Fixed in this PR. |
| `pyne check <directory>` | Walked only `*.pine`. Fixed so `*.pyne` is included. |
| LSP semantic diagnostics | S001/S002 work on ASCII. Columns were code points, so an emoji earlier on the line shifted the squiggle. Fixed. |
| `make test` / corpus files | `tests/test_set06_pine_int_na.py` raises `FileNotFoundError` when `tests/data/set06/` is absent. Those files are local-only. CI does not run them. |

Cold parse of the RSI script is about **6.2 ms**. A cache hit is about **0.07 ms**. A 2,000-bar script plotting `ta.sma`, `ta.ema`, `ta.rsi`, and `ta.atr` ran at about **63k bars/s** interpreted and about **2.3M bars/s** compiled (Numba, after warm-up). `cProfile` puts almost all cold-parse time inside the generated ANTLR parser, and almost all interpret time inside `visit_Call`.

## Fixes in this PR

### 1. Compile treated `na` as true — high

`na` lowers to `np.nan`. Python `bool(np.nan)` is `True`, and `if np.nan` takes the body. Interpret uses `None`, which is false, and `not na` is `na`.

Repro (before): `na and true`, `na or false`, `na ? 1 : 0`, and `if na` plotted `1` on compile and `0` on interpret. `switch float(na) / na => 1` plotted `3` on compile (IEEE `nan == nan` is false) and `1` on interpret.

Location: `compiler.py` `visit_BoolOp`, `visit_UnaryOp`, `visit_Conditional`, `visit_While`, `_as_bool_cond`, `_switch_arm_cond`.

Fix: conditions go through `pine_bool` (NaN/`None` → false, nopython overload already existed). `not` goes through new `pine_not` (`na` stays `na`). Numeric `switch` arms use `numba_pine_eq` (`na == na`). String arms stay on `==`. `pine_bool` / `pine_not` are on the numeric-expr allow list so `plot(close > open ? 1 : 0)` stays nopython.

Pinned by `tests/test_compile_na_parity.py`.

### 2. Dynamic `for … to` froze the end on compile — high

Pine v6 re-evaluates `to` every iteration. Interpret does. Compile stored `__end_i` once, so this plotted `3` on compile and `1` on interpret:

```pine
limit = 2
s = 0.0
for i = 0 to limit
    s := s + 1
    limit := 0
```

Fix: re-read `to` at the end of each iteration **before** the counter increments (so `for i = 0 to i` cannot chase itself), including on `continue`. Constant `to` is unchanged. Disk IR schema bumped to 53.

### 3. Integer `%` on the Numba path was garbage — high

`np.fmod` on Numba integers returns `0` for `fmod(-7, 3)` and `7` for `fmod(7, -3)`. Float `fmod` is fine (`-1` and `1`). Interpret used Python `%`, whose sign follows the divisor (`-7 % 3` is `2`).

The compiler helper is documented as dividend-signed remainder (C `fmod` / Pine). Interpret now matches that, exactly for ints. The jit casts to float64 before `fmod`. The emitter also adds `0.0` so a stale Numba cache of an integer call site cannot keep the old lowering.

### 4. Semantic diagnostic columns were not UTF-16 — medium

Lint diagnostics convert code-point columns in `features/diagnostics.py`. S001/S002 in `semantic_diagnostics.py` published the raw code-point index. A line `"🚀" + p.bad` underlined one UTF-16 unit early.

Fix: `collect()` converts both ends with `codepoint_column_to_utf16`. Pinned in `tests/test_lsp_semantics.py`.

### 5. `pyne execute --timeframe` did not reach the runtime — medium

`Runtime(timeframe=)` drives `timeframe.*`. `execute_source` accepted `--timeframe` (default `1m`), echoed it in JSON, and constructed `Runtime(symbol=ticker)` only. The script still saw a daily chart. Passing the raw string `"1m"` would be worse: `_period_flags` upper-cases it to monthly `"1M"`.

Fix: `to_pine_period` (the same map `POST /run` already used) now lives in `timeframe.py`. Execute passes `to_pine_period(timeframe)`. Backend `_to_pine_period` calls it. `1m` → `"1"`.

### 6. `pyne check <dir>` skipped `.pyne` — low

The product accepts `.pine` and `.pyne`. Directory walks used `--ext .pine` only. Default is now `.pine,.pyne` (comma-separated). A single file path is still checked regardless of suffix.

### 7. `SyntaxError` without a location crashed in `__str__` — low

`SyntaxError("boom")` then `str(err)` raised `AttributeError` because `details` is only set when a location is passed. `__str__` now returns the message.

## Findings not fixed

### F1. `iff(na, a, b)` still disagrees — medium

Interpret returns `na` when the condition is `na` (`numeric.py` `_builtin_iff`; pinned by `tests/test_builtins_coverage.py`). Compile emits `a if np.nan else b`, which selects `a` because NaN is truthy.

Not changed here: a function-call helper would evaluate both branches, and Pine `iff` is lazy. The fix is a single-assignment ternary that returns `na` for a NaN condition without forcing object mode. `visit_Conditional` (`? :`) is already `na`-false and lazy.

### F2. v6 `and` / `or` are never short-circuit — medium, intentional today

Both hosts evaluate every operand so v5 series state stays continuous (`expressions.py` `visit_BoolOp`, `compiler.py` `visit_BoolOp`). v6 Pine is lazy. Scripts that rely on the right-hand side not running will disagree with TradingView. A version-gated lazy path is the fix; it will change `ta.*` state inside dead arms, so it needs goldens, not a drive-by edit.

### F3. `math.round` is banker's rounding — low

`numeric.py` `_builtin_math_round` uses Python `round`. `math.round(2.5)` is `2`. TradingView half-away-from-zero is often `3`. Both hosts share it, so it is not a dual-host bug. Confirm against a TV golden before switching.

### F4. Compile inputs are empty for strategies — low

`pyne execute` on `examples/rsi_strategy.pine`: interpret `inputs_count` is 3, compile is 0 and `meta.inputs` is `[]`. Overrides are already documented as interpret-only (`Runtime.run`). The compile result should still report the declared inputs, or the CLI should say they were dropped.

### F5. S002 only sees calls whose callee is a bare name — low

`semantic_diagnostics.py` `_call_arity` skips `h(1)` when `h` is a variable holding a user function, and skips method calls. Under-reporting is the stated policy for builtins. Aliased user functions are a real false negative. Resolve the callee through the symbol index before giving up.

### F6. Symbol-index failures are swallowed — medium

`analysis.py` `ensure_symbol_index` returns `None` on any exception from `parse` or `build_symbol_index`. Navigation, rename, and semantic checks then vanish with no log. Log the exception at debug and surface a single diagnostic when the index build fails on a tree that parsed.

### F7. Two lint→diagnostic converters — low

`features/diagnostics.py` `lint_warnings_to_diagnostics` is what the server publishes (code descriptions, tags, UTF-16, C001 filter). `workspace.py` still has a parallel converter used by tests. Delete or forward the workspace copy so they cannot drift.

### F8. README / image versions lag the package — low

`__version__` is `0.6.34`. `README.md` still says **0.6.32** and the docker examples pull `0.6.31`. `pyne info` is the accurate source.

### F9. `for i = 0 to i` first-iteration difference — low

The dynamic-end fix re-reads `to` while the counter still holds this iteration's value. The first evaluation still happens after `i = start`, so a pre-existing `i` is not visible to the first `to` on compile the way it is on interpret. Rare. Eval `to` once before binding the counter only when `to` does not mention the counter.

## Optimization proposals

Measured on this machine, 2,000 bars, four `ta.*` plots, unless noted.

| Rank | Change | Evidence | Impact | Effort |
| --- | --- | --- | --- | --- |
| 1 | Keep numeric scripts on compile/`auto` | Interpret ~63k bars/s, compile ~2.3M bars/s (~37×) after JIT. Profile: `visit_Call` dominates interpret. | High for numeric studies | M — widen eligibility, don't change semantics |
| 2 | Do not pay ANTLR on an unchanged buffer | Cold parse ~6.2 ms; cache hit ~0.07 ms. Profile is `PinescriptParser.*`. LSP still reparses the whole buffer on each debounced edit (`workspace.py` `_parse_and_lint`). | High for the editor | L for an incremental parser. S to avoid hashing the full source before the cache lookup in `helper.py` `parse` |
| 3 | One series representation | `runtime/series.py` `apply_bar_sample` appends a newest-first deque **and** a chronological list unless `PYNE_SERIES_RING` is on. TA windows then `list(reversed(hist))` (`technical_submodules/core.py`). | High on long interpret histories | L — flip the default only with the TA goldens |
| 4 | Index occurrences by line | `analysis.py` `occurrence_at` / `scope_at` scan every occurrence and every scope. Cheap on the RSI script (27 occurrences, 3.5 ms index+lint). Linear in identifiers per hover. | Medium on large files | S |
| 5 | Stop scanning from byte 0 for comments | `protocol/utils.py` `in_comment_or_string` walks the prefix of the file per request. | Medium at EOF of large files | S — per-line flags |
| 6 | Realtime snapshots | `compiler.py` `_emit_rt_tick_snapshot` copies list/dict state every unconfirmed tick. Idle when `realtime_ticks` is 1. | High only for multi-tick realtime | M |
| 7 | `docs/optimization_notes.md` is stale | It still describes a string-keyed visitor cache and a one-time 2% suite speedup. The code now has SLL-then-LL parse, a parse LRU, a hot script body, and the ring buffer. | Docs only | S |

`docs/optimization_notes.md` items that are still true: direct location attributes in the builder, module-level operator callables, and precomputed math constants. They are not the bottleneck next to ANTLR and the AST walk.

## Structure proposals

| Rank | Proposal | Why | Effort |
| --- | --- | --- | --- |
| 1 | One type story | LSP `analysis.py` infers string labels (`ta.*` → `"series float"`). The compiler infers overload tags in `compiler.py` (`_infer_udf_arg_type`). The runtime has a real `Type` / `TypeRegistry` in `type_system.py` (372 lines) that the language server does not use. Hover, arity, and compile overload choice can drift. Related series/`na` propagation is already owned elsewhere; the split is the larger problem. | L |
| 2 | Split `compiler.py` | 10,546 lines: emit, strategy, request, plot wire format, and the numeric-safety heuristic in one visitor. A bug in `_is_safe_numeric_expr` silently forces object mode (this review hit that with `pine_bool`). Split by namespace (plot / strategy / request / expr) behind the same visitor. | L |
| 3 | Split `numba_builtins.py` | 7,637 lines of kernels plus coercion helpers, star-imported by generated modules. Names must stay public. Group TA kernels vs coercion (`pine_bool`, `na_num`, `safe_float`) so the import surface is explicit. | M |
| 4 | CI should run the parity tests this PR added | `.github/workflows/ci.yml` runs a short list (`test_linter`, `test_evaluator`, `test_cli`, a handful of runtime files, two LSP files). `tests/test_lsp_semantics.py`, `tests/test_compile_na_parity.py`, and most compiler tests are local-only. `mypy` is `|| true`. | S |
| 5 | Corpus tests should skip, not crash | `test_set06_pine_int_na.py` opens `tests/data/set06/**` with no `pytest.skip` when the tree is absent. `make test` fails on a fresh clone. README already says community corpora stay local. | S |
| 6 | Delete the second diagnostic converter | See F7. | S |

`compiler.py` and `host.py` (4,716 lines) are the modules where a small semantic fix is most likely to knock a script off nopython or out of the disk IR cache. The disk schema version (`engine.py` `_DISK_META_VERSION`, now 53) is the right hammer when generated code changes; source hashes alone reuse old IR.

## Out of scope (already assigned)

- Series / `simple` semantic tokens.
- Comment-preserving formatting (the unparser drops comments; the server falls back to a whitespace pass).
- Pyne Edge series / `na` type propagation. The LSP string-label inference in F-structure-1 will keep drifting until that work and the compiler share a representation.

## Tests

- `tests/test_compile_na_parity.py` — interpret vs compile for `na` boolean ops, `not na`, `if na`, `switch` on `na` and on strings, dynamic and constant `for`, dividend-signed `%`, and nopython retention.
- `tests/test_lsp_semantics.py` — S001 column is UTF-16 after an emoji.
- `tests/test_mcp_ops.py` — `timeframe="1m"` is intraday, not monthly; `1d` is not intraday.
- `tests/test_cli.py` — a directory of `.pyne` is checked.
- `tests/test_numba_builtins_direct.py` — negative `numba_safe_mod`, including ints.
