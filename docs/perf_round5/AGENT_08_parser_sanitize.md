# AGENT 08 — Parser / builder residual + corpus sanitize

**Date:** 2026-07-30  
**BASE_SHA:** ca5215ac33c34f9b60584f8c230bc281dc768782  
**Role:** Correctness + light sanitize residual (no mass grammar regen)

---

## 1. Scope & files touched

| Path | Change |
| --- | --- |
| `src/pynescript/util/corpus_sanitize.py` | Three false-positive repairs (continuation detection + multiline-string state) |
| `tests/test_corpus_sanitize.py` | +6 regression tests for FPs + empty-arrow EOF lock |
| `tests/test_lexer_corpus_fixes.py` | Soft-keyword / reassignment / multiline string roundtrip locks |
| `docs/perf_round5/AGENT_08_parser_sanitize.md` | This report |

**Not touched:** `resource/*.g4`, `generated/`, `builder.py`, `helper.py` (no safe residual micro-opt beyond Round 4), evaluator/TA.

---

## 2. Bugs found (severity, repro)

### B1 — HIGH (false positive): multi-line UDF `) =>` body destroyed

**Severity:** High for corpus — turned **valid** Pine into parse failures.  
**Repro:** set02 `119_ind_parabolic_sar_extended_sarext.pine`, libraries `019_lib_functionnnetwork.pine`, `031_lib_mathstatisticskerneldensityestimation.pine`.

Raw parses OK. Sanitize injected `=> na` when the closing `) =>` line was **more indented** than the function body (multi-line parameter wrap):

```pine
sarext(..., af_max_short = 0.20) =>   // indent ~7
    if af_init_long <= 0              // indent 4  ← real body
```

`_line_has_arg_continuation` only treated `nxt_indent > base_indent` as body → false empty-arrow repair → `) => na` + orphan INDENT → **PARSE_FAIL**.

Same for `export network ( … ) => //{` with region comments.

### B2 — HIGH (false positive): zero-indent call args → `plot(na)`

**Severity:** High — broke valid TV release-notes demos.  
**Repro:** set04 `0635_ind_line_wrapping_between_parentheses_demo.pine` (raw OK).

```pine
plot(
median,            // indent 0
  "Median",
   chart.fg_color,
    3
)
```

Truncate-call repair saw bare `plot(` with next line at same indent and rewrote to `plot(na)`, leaving a dangling arg list.

### B3 — HIGH (false positive): prose-stop mid-multiline string

**Severity:** High — unclosed `"""` → lexer error.  
**Repro:** set04 `0842_ind_multiline_string_demo.pine` (raw OK).

Triple-quoted content includes English “We do not have to…” which matched `_PROSE_CONTINUE_RE` (`We\s+do\b`). Line filter stopped the script mid-string.

### B4 — intentional residual (leave FAIL)

`set04/indicators/0768_ind_invalid_line_wrap_demo.pine` — docs demo of **invalid** line wrap. Must stay FAIL.

---

## 3. Changes (what / why)

### `_line_has_arg_continuation`

1. **Bare open `(`/`[`** after comment strip → any following non-empty non-comment line is a continuation (Pine free-indent inside parens). Truncated EOF calls still have no next line → still get `…(na)`.
2. **Trailing `=>`** (after comment strip, including `=> //{`) → following line with `indent > 0` is a function body even when body indent **&lt;** signature-continuation indent.
3. Helper `_code_without_line_comment` for quote-aware `//` strip on the current line.

### `_line_filter` + `_string_state_after_line`

Track open `"""` / `'''` / `"` / `'` across lines. While inside a string, keep lines verbatim and **skip** prose / chrome / foreign stops so English string content cannot truncate the script.

### Empty-arrow path

Uses `_code_without_line_comment` instead of naive `re.sub(//…)` for consistency with region comments.

---

## 4. Benchmarks

Not a perf-primary agent. No `bench_pipeline` claim.

| Metric | Round 4 residual | After this agent |
| --- | ---: | ---: |
| set01–04 OK | 2468 / 2477 (**99.64%**) | **2476 / 2477 (99.960%)** |
| FAIL | 9 | **1** (intentional invalid wrap) |
| TIMEOUT | 0 | 0 |

Recovered from sanitize FPs (not grammar): 3× set02 (sarext + 2 libraries) + 2× set04 (paren wrap + multiline string). Prior Round 4 “9 residual” list was mostly already OK on current tree; **new** regressions were sanitize FPs on real Pine.

---

## 5. Tests run

```bash
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_corpus_sanitize.py \
  tests/test_lexer_corpus_fixes.py \
  tests/test_v6_features.py \
  tests/test_for_loop_syntax.py -q --tb=line
# 102 passed in ~2.3s
```

Full set01–04 sanitize+parse+unparse scan: **2476 OK / 1 FAIL**.

Soft-keyword / typed UDF / `=` / `:=` / compound assign / triple-quote probes: green (hard keywords `export`/`import`/`var`/… correctly rejected as identifiers).

---

## 6. Residual risks / follow-ups

| Item | Note |
| --- | --- |
| Intentional invalid wrap demo | Keep FAIL; do not “heal” |
| Bare `(`/`[` continuation | If a mid-file truncated call is followed by an unrelated stmt, we no longer inject `na` (prefer preserving valid free-indent wraps) |
| String-state tracker | Best-effort; exotic escapes unlikely in corpus |
| set05 chrome bulk | Still low product value; not re-swept this round |
| Soft keyword `export` as id | Hard keyword in grammar — correct |

---

## 7. Out of scope / did not touch

- Mass ANTLR regeneration / `generated/` / ASDL generated
- `builder.py` / `helper.py` further micro-opts (Round 4 already landed SLL + singletons + location fast path)
- Evaluator / TA / Runtime / compile
- Committing or pushing

---

## Handoff summary

Sanitize false positives were the real residual PARSE_FAIL driver on set01–04, not open grammar holes. After continuation + multiline-string fixes: **99.960%** parse, only intentional invalid-line-wrap demo fails. Tests: **102 passed**.
