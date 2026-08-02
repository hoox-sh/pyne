# Agent 05 — Parse/AST cache by `sha256(source)` (Phase 1.6)

| Field | Value |
| --- | --- |
| **Role / ID** | 05 — Parse/AST multi-run warm path |
| **Date** | 2026-08-02 |
| **Roadmap** | Phase 1.6 / residual perf plan |
| **Verdict** | **win** |

## What you did (files touched)

| File | Change |
| --- | --- |
| `src/pynescript/ast/helper.py` | Process-local **LRU** parse cache on public `parse()`; helpers `clear_parse_cache` / `parse_cache_info`; env toggles |
| `backend/runtime.py` | Thin `_parse_script` → `parse()` only (removed duplicate host dict cache) |
| `tests/test_parse_cache.py` | **New** — identity, unparse, LRU, env off, concurrency |
| `docs/perf_round7/AGENT_05_parse_cache.md` | This report |

**Did not:** regenerate grammar / touch `generated/`.

## API

```python
from pynescript.ast.helper import parse, clear_parse_cache, parse_cache_info, unparse

tree = parse(source)                 # default cache ON
tree2 = parse(source)                # same object (read-only share)
clear_parse_cache()                  # tests / hot-reload / after mutation
info = parse_cache_info()            # {enabled, size, maxsize, hits, misses}
```

Public `parse(source, filename="<unknown>", mode="exec")` signature **unchanged**.

### Cache key

`(sha256_hex(source.encode("utf-8")), mode)`

- `filename` is **not** in the key (diagnostics only).
- Failed parses are **not** cached.

### Defaults

| Setting | Default | Notes |
| --- | --- | --- |
| `PYNE_PARSE_CACHE` | **ON** (`1`) | Disable: `0` / `false` / `off` / `no` |
| `PYNE_PARSE_CACHE_MAX` | **128** | Bounded LRU (`OrderedDict`); pop oldest on insert |
| Thread safety | `threading.RLock` | Safe for Flask multi-worker **threads** (per-process) |

### Invalidation

1. `clear_parse_cache()` — full clear + hit/miss counters.
2. Natural LRU eviction when `size >= maxsize`.
3. `PYNE_PARSE_CACHE=0` — bypass put/get entirely.

### Mutability risks (documented)

Cached AST **identity is shared**. Evaluators/Runtime treat trees as read-only.
Callers that mutate returned nodes (`NodeTransformer`, `increment_lineno`, field
rewrites) poison the entry for all later hits. Mitigations:

- Treat `parse()` results as immutable, or
- `clear_parse_cache()` after intentional mutation, or
- `PYNE_PARSE_CACHE=0` for isolation (LSP heavy rewrite paths, etc.).

Unparse of a warm hit is **identical** to the cold-parse unparse of the same tree.

## Before / after bench

Same process, N=40 parses of the **same source** after one warm-up parse.
Python 3.14, `PYTHONPATH=src:.`.

| Script | Cache OFF median | Cache ON median | Speedup |
| --- | ---: | ---: | ---: |
| micro (`ta.sma/ema/rsi`) | **3.412 ms** | **0.003 ms** | ~1000× |
| med builtin (~583 B) | **7.906 ms** | **0.004 ms** | ~2000× |
| large sample (~344 B) | **4.437 ms** | **0.003 ms** | ~1500× |

Warm path is hash + dict lookup only. This is the multi-run API / batch re-eval
win (parse once per distinct source per process).

Runtime multi-run still routes through `_parse_script` → `parse()`; host-local
duplicate cache removed so one SoT exists. (Full Runtime e2e import was broken
in-tree by concurrent series API churn at measurement time — cache layer itself
is package-level and covered by unit tests.)

## Tests run

```bash
PYTHONPATH=src:. .venv/bin/python -m pytest tests/test_parse_cache.py -v --tb=short
# 9 passed

PYTHONPATH=src:. .venv/bin/python -m pytest tests/test_parse_cache.py tests/test_for_loop_syntax.py -q
# 14 passed
```

Coverage: identity share, unparse equality, mode in key, clear, env disable,
LRU max=3 eviction, filename independence, 8-thread concurrent first-fill.

## Residual / follow-ups

- Optional: do **not** cache for LSP if rewrite tools mutate trees (or clear on
  document change — today each edit is a new source hash anyway).
- Cross-process disk parse cache not needed (ANTLR cold is process-level).
- When Runtime import surface stabilizes, re-measure `parse_ms` across 5
  identical `evaluate()` calls (expect first miss, rest ~0).

## Verdict

**win** — bounded, thread-safe, env-toggleable sha256 parse cache on the public
API; multi-parse warm path drops from multi-ms to microseconds; unparse
identity/semantics preserved; host Runtime thinned to shared SoT.
