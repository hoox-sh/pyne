# Re-source of the four unsourced figures — 2026-11-17

Method: exact-match file counts over `tests/data/setXX/**/*.pine` (regex searched
with Python `re.search` on full file text; cross-checked with `grep -rlE` and
`rg -l --no-messages`). No measurement harness for these four figures exists in
the repo or the `pyne` CLI (see "harness status" per figure). Counts below are
a re-measure of the *same kind* the 2026-11-14 inventory used (files-containing-
pattern), not a re-derivation of the original author's exact procedure, which was
never committed or documented beyond the plan doc lines quoted.

Reproduction commands (all from repo root):
    /usr/bin/python (3.14.10) with regex matched against
    Path("tests/data/<set>").rglob("*.pine"), read_text(errors="ignore")
    cross-check: grep -rlE / rg -l --no-messages (both agree; see file_counts.json)

## Figure 1 — plotshape = 359
- Source (only one): `.oo/plans/pyne-numeric-coverage-2026-11-14.md` lines 25
  ("(`bgcolor` 354, `plotshape` 359)") and 236-237
  ("5. Visual events (`bgcolor` 354, `plotshape` 359) — larger feature...").
- The plotshape card's own plan disclaims it:
  `.oo/plans/pyne-plotshape-numeric-2026-11-17.md`:
  "- No corpus scan was run in this slice; the ~359 number is the card estimate,
     not a re-measured count."
  and "Of the ~359 corpus scripts blocked by `plotshape`..."
- Re-measured (files containing substring `plotshape`): set01=58, set02=61,
  set03=172, set04=68 → set01–04 = **359 (exact match)**; set05=2122,
  set06=753 → set05+06 = **2875**; all six sets = **3234**.
- No dedicated measurement harness exists in repo/CLI (the plotshape proof
  `.oo/plans/pyne-plotshape-numeric-2026-11-17.proof.py` is a unit-level proof of
  numeric synthesis, not a corpus scan). The 359 == set01–04 file count exactly,
  so the estimate is now sourced as "files containing `plotshape` in
  set01–04, counted 2026-11-17".

## Figure 2 — input.* type tokens = 115
- Source (only one): `.oo/plans/pyne-numeric-coverage-2026-11-14.md` lines 23
  ("`input.*` type tokens (115)") and 229-230
  ("1. `input.*` type tokens (`type=input.integer/float/bool/source`) — 115 scripts;").
- Pattern used in the 2026-11-14 proof harness
  (`.oo/plans/pyne-numeric-coverage-2026-11-14.proof.py`, `PATS["input_type"]`):
  `type\s*=\s*input\s*\.`
- Re-measured with that exact regex: set01=80, set02=8, set03=17, set04=10 →
  set01–04 = **115 (exact match)**; set05=1541, set06=337 → set05+06 = **1878**;
  all six = **1993**.
- No corpus-scanning harness for this figure exists beyond that proof's regex;
  the proof never printed the 115 (it used the regex only for candidate filtering).

## Figure 3 — runtime.error = 563
- Source (only one): `.oo/plans/pyne-numeric-coverage-2026-11-14.md` lines 24
  ("`runtime.error` (563)") and 235
  ("4. `runtime.error` — 563 scripts; needs an njit-safe raise path.").
- NO harness and NO reproducible recipe found. Tried:
  `runtime\.error`, `runtime\s*\.\s*error`, case-insensitive — all give
  set01=10, set02=83, set03=291, set04=169 → set01–04 = **553**, NOT 563
  (Δ=10, shortfall in every variant). set05=71, set06=128 → set05+06 = 199;
  all six = **752**.
- `grep -rn "563" .oo` finds no other occurrence; the corpus has not changed
  since 2026-11-14 (no commits touching tests/data since then), so 563 is not
  explainable by corpus drift. It is best treated as a miscount or a count of a
  slightly different population that was never recorded.
- Recommendation: treat "563" as unsourced/unverifiable; the defensible figure
  as of 2026-11-17 is **553** (set01–04, regex `runtime\.error`, files containing
  the token) or **752** (all six sets). Do not quote 563 without re-derivation.

## Figure 4 — assigned hline = 48
- Source (only one): `.oo/plans/pyne-numeric-coverage-2026-11-14.md` lines 22-24
  ("assigned `hline` (48 scripts corpus-wide)") and 233-234
  ("3. Assigned `hline` (`h = hline(...)`) — 48 scripts; ...").
- ("corpus-wide" in the doc is misleading: 48 is exactly the set01–04 count of
  files matching the 2026-11-14 proof regex `=\s*hline\s*\(` — see
  `pyne-numeric-coverage-2026-11-14.proof.py` PATS["hline"].)
- Re-measured with that exact regex (multiline-aware): set01=16, set02=5,
  set03=17, set04=10 → set01–04 = **48 (exact match)**; set05=339, set06=140 →
  set05+06 = **479**; all six = **527**.
  Note: line-oriented `grep -l` gives 336/139 (475) for set05/06 because
  `=\n hline(` across a newline only matches with multiline semantics; the
  2026-11-14 pattern is multiline, so 339/140 is the comparable figure.
- No dedicated harness beyond that proof regex.

## Bonus cross-check (not asked, same method)
- `bgcolor` files: set01=27, set02=61, set03=175, set04=91 (=354 ✓ matches the
  2026-11-17 after-scan), set05=1290, set06=1025 → set05+06 = **2315** (matches
  the card note "set05/set06 = 2315 scripts"), all six = 2669.

Corpus unchanged since 2026-11-14: `git log --oneline --since=2026-11-10 -- tests/data`
→ only pre-Nov-10 commits; no commits touch tests/data after the inventory was written.

Scope note: all figures above are *files containing the construct*, the same sense
as the 354/359/115/48 card figures. They are NOT counts of scripts blocked in the
numeric-mode sense (a script can contain `runtime.error` and still compile
numeric); no numeric/object/error split for these populations was previously
published and none is claimed here except via the bgcolor scan (see summary.json).
