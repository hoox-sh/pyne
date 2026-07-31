# AGENT 11 — Parser / sanitize / corpus residual

**Date:** 2026-07-31  
**BASE_SHA:** 32697c97f7e56de817325356e4dbd692809ecbe8  
**Role:** Correctness — residual FAIL / scrape chrome (set05 themes) without weakening real syntax

---

## 1. Scope & files

| Path | Change |
| --- | --- |
| `src/pynescript/util/corpus_sanitize.py` | Residual scrape repairs + safer ternary / island pick |
| `tests/test_corpus_sanitize.py` | +11 regression tests (incl. FP locks) |
| `docs/perf_round6/AGENT_11_parser_sanitize.md` | This report |

**Not touched:** `resource/*.g4`, `generated/`, `builder.py`, `helper.py`, lexer bulk, evaluator/TA/Runtime.

---

## 2. Bugs found

### Prior context (Round 5 AGENT_08)

set01–04 already at **2476/2477** (only intentional invalid line-wrap demo). Residual product noise is **set05** dump chrome (~149 FAIL in `.cache/corpus_flow_set05_parse.csv`, 98.33% OK historical).

### B1 — HIGH (false positive risk, prevented): ternary heal vs `"Highlight ?"`

Incomplete-ternary repair must be **quote-aware**. Naive `?` / trailing `:` matching would rewrite valid inputs:

```pine
highlight = input(title="Highlight ?", type=input.bool, defval=true)  // must stay
```

into `…) : na` and break set01. Locked by `test_question_mark_inside_string_is_not_ternary`.

### B2 — set05 multi-copy scrapes (truncated preview + full //@version)

hasnocool pattern: mid-call `minval=1,...` → `PineScript code:` / `Copy code` / digit gutters → second full `//@version` copy. Line-filter alone stopped at chrome and kept the **truncated** half.

### B3 — other set05 residual themes (addressed where safe)

| Theme | Repair |
| --- | --- |
| `import … as x loading...` (after hair-space normalize) | strip `loading...` |
| Curly `It’s important…` prose after script | `_PROSE_CONTINUE_RE` + U+2019/U+2018 apostrophe class |
| `c = … ? color.red :` / true-branch-only at EOF | quote-aware ternary suffix |
| `type pivotPoint` + same-indent fields | promote fields (docs lost INDENT) |
| Same-indent `f() =>` under `if` | no longer treated as body continuation → `=> na` |
| Mid-call `,...` without `)` | strip ellipsis; close parens without bogus `na` when args present |
| Intentional `indicator()\n    plot(1)` / `study($)` | **leave FAIL** |

---

## 3. Changes

1. **UI chrome** — `_UI_CHROME_LINE_RE`, digit-only gutters; stop line-filter after pine on these.
2. **Multi-`//@version` islands** — split **before** line-filter; score + pick best complete copy.
3. **Polish** — mid-call ellipsis; `loading...` on imports.
4. **Quote-aware incomplete ternary** — `_incomplete_ternary_suffix`.
5. **Partial-arg call close** — close unclosed `(`/`[` when next line is a new statement; placeholder `na` only for bare `foo(` / trailing `,`.
6. **Type same-indent fields** — promote field lines under `type Name`.
7. **`=>` continuation** — require `nxt_indent > base` **or** `0 < nxt < base` (multi-line signature); same-indent → empty-arrow `na`.
8. **Prose** — curly apostrophes; `Take note of` / `When using`.

---

## 4. Benchmarks

Not perf-primary. Corpus parse measurement only:

| Metric | Before (this agent) | After |
| --- | ---: | ---: |
| set05 prior FAIL rows (149) re-parse OK | ~baseline cache 0 OK on re-run list | **91 OK / 58 still FAIL (61.1% recovery)** |
| Random 200 set01–04 | — | **199 OK / 1 FAIL** (intentional invalid wrap) |
| set04 invalid line-wrap demo | FAIL | FAIL (kept) |

Remaining set05 FAIL (~58): intentional error demos (`$`, bad INDENT), `var switch` (v4 id / hard keyword), recursion-depth monsters, deep string truncations, docs list chrome (`indicator(), library(),…`), unclosed multi-line `if` conditions — not safe to “heal” without FP risk.

**Do not claim 100% corpus.** Full set05 wall-clock re-sweep not re-run (9k files); measurement is reparse of prior FAIL CSV + set01–04 sample.

---

## 5. Tests run

```bash
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_corpus_sanitize.py \
  tests/test_lexer_corpus_fixes.py -q --tb=line
# 67 passed
```

New tests include: multi-copy island pick, import `loading...`, truncated ternary, complete ternary preserve, curly prose stop, type field promote, same-indent arrow `=> na`, intentional indent still fails, mid-call ellipsis, **question-mark-in-string FP lock**.

---

## 6. Residual risks

| Item | Note |
| --- | --- |
| Island scoring | Heuristic; prefers balanced parens + no `,...` |
| Partial-arg close | Only when next line is new statement / EOF |
| `var switch` | Needs soft-keyword grammar (out of scope) |
| Builder TypeError on list-of-calls docs | Parser accepts junk; builder flattens None — optional follow-up |
| Intentional invalid demos | Must stay FAIL |

---

## 7. Out of scope

- ANTLR regeneration / hand-edit `generated/`
- set05 full 9k re-sweep commit
- Evaluator / Runtime / compile
- Soft-keyword `switch` as identifier
- Push / merge

---

## Handoff summary (≤20 lines)

Sanitize residual for set05 scrape chrome: multi-`//@version` island pick, UI `Copy code`/gutter stop, import `loading...`, quote-aware ternary heal, type same-indent fields, safer `=>`/call close. **Critical FP lock:** `?` inside strings must not become ternary. Measured **91/149** prior set05 FAILs recovered; set01–04 sample green except intentional invalid wrap. Tests: **67 passed**. No grammar regen.
