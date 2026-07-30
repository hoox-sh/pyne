# AGENT 11 — LSP + diagnostics correctness/perf

**AGENT_ID:** 11  
**ROLE:** LSP + diagnostics correctness/perf (editor path)  
**BASE_SHA:** ca5215ac33c34f9b60584f8c230bc281dc768782  
**Date:** 2026-07-30

## 1. Scope & files touched

| Path | Change |
| --- | --- |
| `src/pynescript/langserver/features/symbols.py` | Fix double-flush; optional workspace AST |
| `src/pynescript/langserver/features/references.py` | Always walk function/type bodies; optional AST |
| `src/pynescript/langserver/features/definitions.py` | Optional workspace AST (`...` vs `None`) |
| `src/pynescript/langserver/features/semantic_tokens.py` | Optional workspace AST |
| `src/pynescript/langserver/features/inlay_hints.py` | Optional workspace AST |
| `src/pynescript/langserver/features/hover.py` | Clearer dotted-name resolution |
| `src/pynescript/langserver/features/diagnostics.py` | Fix end-column overshoot; skip lineless warnings |
| `src/pynescript/langserver/workspace.py` | EOF incremental edit; skip re-parse on no-op; diag range |
| `src/pynescript/langserver/server.py` | Pass `doc.ast` into AST-backed handlers |
| `tests/test_lsp_features.py` | Symbols/refs/semantic/capabilities regressions |
| `tests/test_langserver.py` | Stale diags, EOF edit, incomplete input, ranges |

**Not touched:** `builtin_metadata.json` / `.enc`, CRYPTO_KEY, runtime/evaluator/compiler.

## 2. Bugs found

| Severity | Bug | Repro |
| --- | --- | --- |
| **P0** | Document symbols double-counted every function (`f1,f1,f2,f2`) and dropped top-level assigns after a function (`x = 3` missing) — `_flush_function` never cleared `_current_function` | Outline on script with 2 funcs + later var |
| **P1** | Find-references skipped function/type body when name matched → recursive calls missing | `myFunc` refs → 2 instead of 3 |
| **P1** | `_apply_text_edit` returned **unchanged** source when range was past last line (no trailing NL) → **stale buffer + stale diagnostics** after incremental `didChange` | Edit at `(1,0)` on source `"a"` |
| **P2** | Diagnostic end column = `column + len(line)` overshot line length | Warning at col 5 on 16-char line → end 21 |
| **P2** | Features re-parsed on every hover/def/refs/symbols/semantic/inlay after workspace already parsed | 500-assign script: symbols ~880ms reparse vs ~48ms cached |
| **P3** | Lineless lint codes (e.g. C004) inconsistently handled between workspace vs `features/diagnostics` | Align: skip when `line is None` |

Capabilities check: `signatureHelp` / `codeAction` correctly **not** advertised. No metadata load failures on plaintext path.

## 3. Changes (what/why)

1. **Symbols flush:** set `_current_function = None` after flush → single outline entry; post-function top-level vars appear at root.
2. **References:** always visit `FunctionDef`/`TypeDef` body after optional declaration hit.
3. **Incremental edit:** pad line list for EOF ranges; clamp columns; never silent no-op on valid appends.
4. **No-op `didChange`:** if text unchanged after applying edits, skip `_parse_and_lint` (keep AST identity).
5. **Workspace AST reuse:** server passes `tree=doc.ast` into definition/references/symbols/inlay/semantic. Handlers use `tree=...` default = “parse myself”; explicit `None` = workspace already failed (no second parse).
6. **Diagnostic ranges:** end char = end of line (or `column+1`), never past line length.

## 4. Benchmarks (before/after)

Script: 500× `v{i} = ta.sma(close, …)` + plot; Python 3.x via `/home/jango/Git/pynescript/.venv`; `PYTHONPATH=src:.`.

| Path | Before (re-parse) | After (cached AST) | Δ |
| --- | --- | --- | --- |
| `documentSymbol` | ~882 ms | ~48 ms | **~18×** |
| `semanticTokens/full` | ~1103 ms | ~17 ms | **~64×** |

Workspace `put_document` still pays full parse+lint once (~0.3–3.5 s cold/hot variance on this machine for 500 lines); feature requests after `didChange` no longer double that cost.

Correctness: symbols/token data identical reparse vs cache.

## 5. Tests run

```bash
PYTHONPATH=src:. .venv/bin/python -m pytest \
  tests/test_lsp_features.py tests/test_langserver.py -q --tb=line
# 44 passed in ~0.9s
```

New coverage: double-flush, recursive refs, EOF partial edit, stale diag recovery, incomplete input, end-column clamp, capabilities, AST reuse.

## 6. Residual risks / follow-ups

- **UTF-16 vs Python code points** for `character` positions (emoji) still unhandled — common LSP footgun; not fixed here.
- **Formatting** still re-parses (intentionally; not wired to cache).
- **Debounced parse** on rapid typing not implemented (full re-parse per `didChange` when text changes remains).
- **Pull workspace diagnostics** handler exists but capability sets `workspace_diagnostics=False` (intentional).
- Position ranges for refs/defs still line-only (character 0) — pre-existing; improve with `col_offset` later.

## 7. Out of scope / did not touch

- Runtime bar loop, compiler Numba, strategy broker  
- CRYPTO_KEY / encrypt / hand-edit of `builtin_metadata.json`  
- Grammar / builder / AXIS frontend  
- New LSP methods (signatureHelp, codeAction)
