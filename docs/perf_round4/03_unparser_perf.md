# Unparser performance — round 4 polish

Date: 2026-07-29  
Scope: `src/pynescript/ast/unparser.py` (helper entry unchanged; still uses thread-local `unparse_node`)  
Prior: `docs/perf_agent_unparse.md` (~1.95× via TLS reuse + type-keyed dispatch + light CMs)

## Workload

- Corpus: `tests/data/set01/{indicators,strategies}` (parse once, unparse many).
- Bench: `N=30` full passes over 50 or 99 successfully parsed ASTs; median of 5 rounds.
- Large-script: ~21k chars unparsed (`113_ind_unit_testing_framework.pine`), 400 iters, median of 5.
- Python: `/mnt/data/home/jango/Git/pynescript/.venv/bin/python` with `PYTHONPATH=src` (this worktree).

## Numbers

### This round (round-3 / HEAD unparser already includes TLS + type dispatch)

| Mode | Corpus | Throughput | Median wall (30×N) | ms / unparse |
| --- | ---: | ---: | ---: | ---: |
| **Before (this session)** | 50 | **2076 /s** | 0.722 s | **0.482 ms** |
| **After** | 50 | **2654 /s** | 0.565 s | **0.377 ms** |
| **After** | 99 | **2957 /s** | 1.004 s | **0.338 ms** |

**Round-4 speedup on 50-script loop: ~1.28× (~22% less wall time).**

| Large script (~21k chars) | ms / call | vs session before |
| --- | ---: | ---: |
| Before | 3.161 | — |
| After | **1.937** | **~1.63×** |

### Cumulative vs original baseline (`docs/perf_agent_unparse.md`)

| Stage | 99-script thr | ms / unparse | vs original |
| --- | ---: | ---: | ---: |
| Original baseline | 1266 /s | 0.790 | 1.00× |
| After TLS / dispatch (prior) | 2469 /s | 0.405 | ~1.95× |
| After round-4 polish | **2957 /s** | **0.338** | **~2.34×** |

## cProfile (30×50, tottime)

| Hotspot | Before | After | Notes |
| --- | ---: | ---: | --- |
| `list.append` | 1.33M calls / 0.241 s | 1.18M / 0.229 s | fewer fragments |
| `visit_Constant` | 0.163 s (+ `json.dumps` 0.079 s) | 0.139 s (no dumps in top) | plain-string fast path |
| `_DelimitCM` init/exit | ~77k each | largely gone on Call/BinOp/… | manual delimit |
| `traverse` | still #1 | still #1 | dispatch remains structural |

## Changes + rationale

### 1. Buffer reuse on `visit()`

- `self._source.clear()` / `self._precedences.clear()` instead of allocating fresh list/dict every unparse.
- Reuses capacity for repeated calls (TLS already keeps the instance warm).

### 2. Plain-string constant fast path

- Strings without `\` `"` newline/tab/etc. emit as `"…"` via `_quote_plain_string` (byte-identical to `json.dumps(..., ensure_ascii=False)` for that set).
- Multiline still prefers `"""…"""` / `'''…'''`; special chars still use `repr` / `json.dumps`.
- Cuts most of the `json.dumps` tax on title/tooltip-heavy scripts.

### 3. Manual delimit / parens (no CM on hot ops)

- `visit_Call`, `visit_Subscript`, `visit_Tuple`, `visit_Specialize`, `visit_FunctionDef`: append `(`/`)` etc. directly.
- `visit_BinOp` / `BoolOp` / `UnaryOp` / `Compare` / `Conditional`: `_needs_parens` + direct `(`/`)` instead of `_DelimitCM` / `_NullCM` enter/exit.
- Removes thousands of small context-manager objects per unparse of a typical script.

### 4. Type-keyed precedence maps

- `_BINOP_PREC`, `_BOOLOP_PREC`, `_UNOP_PREC` keyed by op type (skip string intermediate).
- Unary `not` emitted as single token `"not "` (same text as before).

### 5. Fewer pieces / less interleave overhead

- `items_view` fast-path for arity 2 (common Call).
- `visit_Arg`: `name + "="` as one fragment.
- `visit_Attribute`: `"." + attr` as one fragment.
- BoolOp interleave uses bound `_write_boolop_spaced` + save/restore of `_boolop_spaced` (nested `and`/`or` correct; no per-call lambda).

## Round-trip / v6 fidelity

Spot-checks (parse → unparse → parse → unparse stable):

| Feature | Result |
| --- | --- |
| Multiline `"""…"""` / `'''…'''` | OK, stable |
| `export const int/float` | OK, stable |
| Bitwise `\| & ^ << >> ~` | OK, stable |
| Typed UDF params (`series float x`) | OK, stable |
| `method` methods | OK, stable |
| `enum` / `export enum` + member values | OK, stable |
| Nested bool ops `(a or b) and c` | OK (save/restore token) |

**Known non-cheap gap (not fixed):** AST `FunctionDef` has no return-type field, so prefix return types like `float f(x) => …` are dropped on parse (builder/ASDL), not an unparser-only fix.

## Tests

```bash
PYTHONPATH=src pytest tests/test_v6_features.py tests/test_for_loop_syntax.py \
  tests/test_bgcolor_plotshape_export.py -q
# → 49 passed

PYTHONPATH=src pytest tests/test_parse_and_unparse.py -q --tb=line \
  --example-scripts-dir=tests/data/set01/indicators
# → 141 passed, 4 failed

PYTHONPATH=src pytest tests/test_parse_and_unparse.py -q --tb=line \
  --example-scripts-dir=tests/data/set01/strategies
# → 74 passed, 5 failed
```

- Failures are **pre-existing** round-trip/`simple int`/parse issues (same as prior unparse report).
- Confirmed: optimized unparse is **byte-identical** to `HEAD` unparser on 99 set01 ASTs (and on the four failing indicator files).
- `ruff check src/pynescript/ast/unparser.py` — clean.

## Leftover opportunities

1. **`traverse` still dominates** — further gains likely need mypyc/Cython or a flatter codegen path, not more Python micro-opts.
2. **LSP formatting** — still may construct a fresh `NodeUnparser()`; wire to `unparse_node` if measured.
3. **Prefix function return types** — needs ASDL + builder (out of unparser-only scope).
4. **Chunked string builder** — join of ~O(nodes) fragments is already cheap vs visit dispatch.

## Files changed

| File | Change |
| --- | --- |
| `src/pynescript/ast/unparser.py` | Round-4 hot-path polish (buffers, strings, delimit, maps, items_view) |
| `docs/perf_round4/03_unparser_perf.md` | This report |
