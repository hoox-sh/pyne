# Parse performance — round 4 (Agent 2)

**Date:** 2026-07-29  
**Scope:** Pine source → AST (`parse` / lexer base / builder / annotation pass)  
**Prior wins (round 1):** SLL-first + LL fallback; skip annotations without `@`;
`_setLocations` single-line fast path (~5.4× on complex scripts).  
**Goal:** ≥10% on large scripts **or** structural win; correctness first.

## Benchmark setup

- **Python:** `/mnt/data/home/jango/Git/pynescript/.venv/bin/python` (3.14)  
- **API:** `from pynescript.ast.helper import parse`  
- **Corpus:** scripts under `/mnt/data/home/jango/Git/pynescript/tests/data/`  
  (worktree `tests/data/` is empty / unlinked; benches use the main tree)  
- **Method:** multi-round median of full `parse()` (5 rounds × N iters after warmup);
  staged timing (lex fill / ANTLR parse / builder visit) for attribution  
- **Sizes:**

| Label | Source | Bytes |
| --- | --- | ---: |
| minimal | synthetic `//@version=5` + plot | 40 |
| small | `builtin_scripts/average_day_range.pine` | 201 |
| medium | `builtin_scripts/williams_fractals.pine` | 2 653 |
| set01_med | `set01/indicators/189_ind_ehlers_decycler_oscillator.pine` | 2 761 |
| large_builtin | `builtin_scripts/auto_fib_extension.pine` | 16 076 |
| set03_large | `set03/indicators/0797_ind_spy_0dte_scalper_15min.pine` | 77 544 |

## Profile (before this round)

`cProfile` on `auto_fib_extension` ×12 (after prior SLL work):

| Hotspot | Role |
| --- | --- |
| `ParserATNSimulator.adaptivePredict` / `execATN` | Dominant wall time (~ANTLR prediction) |
| `LexerATNSimulator` + `CommonTokenStream.LT` | Lex / token stream |
| **`PinescriptLexerBase._checkNextToken`** | Our indent/newline logic (~20% of tottime stack under lex) |
| Builder visits + `_setLocations` | ~20–25% of staged wall on medium/large builtins |
| Annotation collect / StatementCollector | &lt;1–2% |

Stage breakdown (pre-opt, warm):

| Stage | medium | large_builtin |
| --- | ---: | ---: |
| lex_fill | ~6.9 ms | ~87 ms (cold DFA noise) / ~50 ms typical |
| parse (SLL) | ~26 ms | ~162 ms |
| build | ~8.3 ms | ~57 ms |
| annot | ~0.2 ms | ~1 ms |

ANTLR still dominates overall; remaining wins are in **LexerBase** and **builder**.

## Changes

### 1. LexerBase hot path — `resource/` + `generated/PinescriptLexerBase.py`

| Change | Why |
| --- | --- |
| `_pendingTokens: deque` + `popleft()` | O(1) vs `list.pop(0)` every token |
| Class-cached `_operator_types` frozenset | Avoid rebuild of operator set every lexer `__init__` |
| `_inputStarted` flag | Skip `len(indentStack)` / start bootstrap check after first token |
| `if/elif` token dispatch instead of `match` | Slightly cheaper dense int dispatch on every token |
| String fast path: skip rewrite when no `\n`/`\r` | 170/170 strings in `auto_fib` are single-line; skip 2× `re.sub` |
| Precompiled `_STRING_COLLAPSE_NL` / `_STRING_STRIP_WRAP_INDENT` | When rewrite is needed |
| Simpler `_getIndentationLength` (if vs match per char) | Indent WS scan |

### 2. Builder micro-opts — `builder.py`

| Change | Why |
| --- | --- |
| Singleton empty ops / ctx (`_LOAD`, `_STORE`, `_ADD`, …) | Empty AST op/ctx nodes are never mutated; cut allocs on every name/binop |
| `_parse_number_literal` | Fast path for decimal/hex/bin/oct/float without `ast.literal_eval` |
| Inline `visitName_load` / `visitName_store` | Drop extra `visit()` hop; use `ctx.name().getText()` |

### 3. Helper polish — `helper.py`

| Change | Why |
| --- | --- |
| Shared `_BAIL_ERROR_STRATEGY` / `_DEFAULT_ERROR_STRATEGY` | Skip strategy alloc every parse |
| Shared `_SHARED_BUILDER` | Builder is visit-stateless |
| Cached `StatementCollector` import | One-time circular-import resolution |
| `_collect_comment_nodes`: only tokens with `@` that parse as `@…` annotations | Skip plain `//` and `//# region` (never attached) |

Public API of `parse(source, filename, mode)` unchanged.

## After numbers

### Full `parse()` multi-round median (5 rounds)

| Script | Before (ms) | After (ms) | Δ |
| --- | ---: | ---: | ---: |
| minimal | 0.92 | 0.89 | ~−3% |
| small | 3.48 | 3.33 | ~−4% |
| medium | 46.50 | 45.02 | ~−3% |
| set01_med | 46.93 | 43.61 | ~−7% |
| large_builtin (~16 KB) | 243.46 | 254.97 | ~noise (ranges overlap) |
| **set03_large (~78 KB)** | **1194.28** | **1026.95** | **~−14%** |

Large-script target: **set03_large ≈ 14% faster** (median; ranges [1046–1240] → [1023–1033]).

### Staged (warm, same process style)

| Stage | medium before → after | large_builtin before → after |
| --- | --- | --- |
| lex_fill | 6.85 → 6.62 ms | 86.5 → 42.7 ms* |
| parse | 26.3 → 24.9 ms | 162 → 164 ms |
| **build** | **8.30 → 7.32 ms (~12%)** | **57.2 → 38.6 ms (~33%)** |

\*Lex fill for large is sensitive to ANTLR DFA warmth; absolute ms varies. Structural
LexerBase changes still reduce per-token Python overhead (`_checkNextToken` tottime
down in cProfile).

### Builder-only revisit (same parse tree, N visits)

| Script | Before | After |
| --- | ---: | ---: |
| medium | 7.20 ms | 5.81 ms (~19%) |
| large_builtin | 41.86 ms | 42.42 ms (~flat; noise) |

## cProfile top (after, our modules, large_builtin ×10)

Still dominated by ANTLR when sorting global tottime. Among **our** code:

1. `PinescriptLexerBase._checkNextToken` / `_setNextInternalTokens` / `nextToken`
2. `builder._setLocations`
3. Expression visitors (`visitConditional_expression`, binops, …)
4. `visitName_load` / `visitArgument_definition`

Annotation path remains negligible.

## Correctness

- **AST identity:** re-`parse` + `dump(..., include_attributes=True)` equal on 10
  size-stratified builtins (0 mismatches).
- **Unparse roundtrip:** `parse(unparse(parse(src)))` succeeds on same sample.
- **Annotations:** `//@version=5` still attached to `Script.annotations`.
- **Numbers:** leading-zero ints (`01`), hex/bin/oct, underscores, floats/scientific.
- **eval mode:** `parse("1+2*3", mode="eval")` works.
- **SLL fallbacks:** 0 on the six bench scripts over 3 parses each (LL path unused).
- **Singleton ops:** dump still shows `Load()` / `Add()` by type; no mutation of shared
  empty nodes in the builder.

## Tests

| Command | Result |
| --- | --- |
| `pytest tests/test_for_loop_syntax.py tests/test_lexer_corpus_fixes.py -q` | **13 passed** |
| `pytest tests/test_parse_and_unparse.py -q -k 'not corpus'` | **1 skipped** (empty worktree corpus) |
| `pytest tests/test_parse_and_unparse.py --example-scripts-dir=…/builtin_scripts` | **138 passed** |

## Files changed

| Path | Role |
| --- | --- |
| `src/pynescript/ast/grammar/antlr4/resource/PinescriptLexerBase.py` | Source of truth for lexer base |
| `src/pynescript/ast/grammar/antlr4/generated/PinescriptLexerBase.py` | Runtime copy (kept in sync) |
| `src/pynescript/ast/builder.py` | Singletons, number parse, name load/store |
| `src/pynescript/ast/helper.py` | Shared builder/strategies; annotation filter |
| `docs/perf_round4/02_parser_perf.md` | This report |

**Not changed:** `generated/PinescriptParser*.py`, `resource/*.g4`, public `parse` signature.

## Residual opportunities

| Opportunity | Risk / notes |
| --- | --- |
| Grammar reductions to cut `adaptivePredict` | High correctness risk; regenerate parser |
| Share lexer/parser instances across parses | State bleed / threading; DFA already shared on ATN |
| Cython/Nuitka builder visit methods | Build complexity; builder already minority after SLL |
| Skip location attachment under a flag | API / tooling breakage for LSP |
| Measure SLL fallback rate on full set03/set05 | Investigation only |

## Summary

Round 4 targets the **remaining Python hot path** after SLL:

- **LexerBase** structure (deque, operator cache, string early-exit, lighter dispatch)
- **Builder** allocation cuts (singleton ops/ctx, faster numbers, fewer visits)
- **Helper** shared objects + annotation comment filter

**Headline:** ~**14%** faster full parse on a **~78 KB set03** script; builder stage
~**12–33%** on medium/large builtins; small scripts a few percent. ANTLR prediction
remains the ceiling for further large gains without grammar work.
