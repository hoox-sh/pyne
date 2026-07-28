# Unparse performance optimization

Date: 2026-07-28  
Scope: `src/pynescript/ast/unparser.py` (+ minimal `helper.unparse` reuse wiring)

## Baseline / after numbers

Workload: parse 99 scripts from `tests/data/set01/{indicators,strategies}` once, then unparse each in a loop (`N=30` full passes, median of 5 rounds). Python: worktree package via `PYTHONPATH=src` and `/mnt/data/home/jango/Git/pynescript/.venv/bin/python`.

| Mode | Throughput | Median wall (30×99) | ms / unparse |
| --- | ---: | ---: | ---: |
| **Baseline** (`NodeUnparser().visit` on HEAD unparser) | **1266 /s** | 2.345 s | **0.790 ms** |
| **After** (`helper.unparse` / thread-local reuse) | **2469 /s** | 1.203 s | **0.405 ms** |

**Speedup: ~1.95× (~48.7% faster)** on the corpus loop.

Large-script check (~21k chars unparsed, 400 iterations, median of 5):

| Mode | ms / call | Speedup |
| --- | ---: | ---: |
| Baseline fresh | 4.585 ms | — |
| After (tls) | 2.161 ms | **~2.12×** |

Byte-identical unparse output vs HEAD unparser on all 99 ASTs.

Earlier cProfile (pre-opt, same corpus shape) highlighted:

- `traverse` / `NodeVisitor.visit` dispatch
- `write` → `list.extend` (high call volume)
- `contextlib` for `delimit` / `require_parens` / `nullcontext`
- `fill` redoing `"    " * indent`
- operator maps keyed by `__class__.__name__` strings
- `Precedence.next()` via try/except construction

## Changes + rationale

### 1. Thread-local unparser reuse (`unparse_node` + `helper.unparse`)

- `NodeUnparser.visit` fully resets `_source`, `_precedences`, and `_indent` so one instance is safe across calls.
- `unparse_node()` keeps a per-thread `NodeUnparser` so the type→visitor method cache stays warm.
- `helper.unparse` calls `unparse_node` (public API signature unchanged).

Rationale: building a new visitor + cold method cache on every `unparse()` dominated cost for small/medium scripts.

### 2. Hot-path I/O primitives

- `write`: single-arg fast path uses `list.append` instead of always `extend`.
- `fill` / newlines: direct appends; indent prefixes from a precomputed `_INDENT_CACHE`.
- Lightweight `_DelimitCM` / `_BlockCM` / `_NullCM` instead of `@contextmanager` + `contextlib.nullcontext` (removes per-use generator + contextlib object churn).

### 3. Faster dispatch and operator tables

- `traverse` uses exact `node.__class__ is list` for containers and a **type-object** visitor cache (no class-name strings, no `super().visit`).
- BinOp / BoolOp / Compare / UnaryOp maps keyed by **op type** (`ast.Add`, …) with precomputed spaced tokens (`" + "`, `" == "`, …).
- `Precedence.next()` uses a precomputed successor table (no try/except enum construction).

### 4. Minor local micro-opts

- Hot visitors append to `self._source` directly for fixed tokens.
- `items_view` uses a bound `_write_comma_space` instead of a fresh `lambda: self.write(", ")` per call.

## Tests

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_parse_and_unparse.py -q --tb=line \
  --example-scripts-dir=tests/data/set01/indicators
# → 141 passed, 4 failed

PYTHONPATH=src .venv/bin/python -m pytest tests/test_parse_and_unparse.py -q --tb=line \
  --example-scripts-dir=tests/data/set01/strategies
# → 74 passed, 5 failed
```

- Failures are **pre-existing** round-trip/parse issues (e.g. `simple int` qualify dropping on reparse; some strategy files fail to parse as source). Confirmed: HEAD unparser emits **identical** text and the same round-trip `repr` mismatches.
- Corpus identity: optimized unparse == HEAD unparse for 99 successfully parsed set01 ASTs.
- `ruff check src/pynescript/ast/unparser.py src/pynescript/ast/helper.py` — clean.

(`tests/data/builtin_scripts/` is empty in this worktree; set01 was used as the representative corpus.)

## Leftover opportunities

1. **Faster string constants** — `json.dumps` still used for most string literals; a carefully validated escape path for plain ASCII strings could win on scripts heavy with titles/tooltips (an earlier naive scan was *slower* than `json.dumps` for short strings).
2. **Reduce piece count** — still many tiny string fragments joined at the end; a chunked buffer or writing multi-token pieces as single strings in the hottest visitors (`visit_Call`, `visit_Arg`) may help slightly.
3. **LSP formatting** — `langserver/features/formatting.py` still constructs a fresh `NodeUnparser()`; could call `unparse_node` / `helper.unparse` for free reuse (out of this task’s strict file scope).
4. **Visitor base** — `NodeVisitor` still uses name-string caches; other visitors could adopt type-keyed dispatch similarly.
5. **Cython/mypyc** for `traverse`/`visit_*` if unparse becomes a measured production bottleneck in the worker path.

## Files changed

| File | Change |
| --- | --- |
| `src/pynescript/ast/unparser.py` | Primary optimizations + `unparse_node()` |
| `src/pynescript/ast/helper.py` | `unparse()` → `unparse_node()` (API stable) |
| `docs/perf_agent_unparse.md` | This report |
