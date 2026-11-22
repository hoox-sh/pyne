# Re-measure: numeric-mode inventory (2026-11-17)

Card: HQ `pyne-re-measure-numeric-mode-inv-423e9330` (mirror of local `re-measure-numeric-mode-inventor-ea84d331`).
Repo: /mnt/data/home/jango/Git/hoox-open-trading-stack/pynescript @ HEAD 9ce574722876e3729b2a0e04c913f3b6f739c506 (bgcolor fix 0968048c + plotshape numeric 915b65ba are IN this HEAD).
Seat: oo-spec-2 (Deploy). Scope: measurement + artifacts only. No source changes, no board edits, nothing committed/pushed.

## TL;DR

| Item | Before (card claim) | Now (measured 2026-11-17/18) |
|---|---|---|
| bgcolor, set05+06, never scanned | unmeasured (card: "2315 scripts") | **2315 scanned: 18 numeric / 1238 object / 1059 error** (set05 11/256/1023 of 1290; set06 7/982/36 of 1025) |
| bgcolor, set01–04 | 0→10 numeric, 289→279 object, 65 err (2026-11-17 artifact) | **recheck: 11/278/65** (+1 flip: set04/...0873_ind_day_and_direction_change.pine — HEAD now includes plotshape numeric synthesis) |
| plotshape "359" | unsourced card estimate | **re-sourced: set01–04 files containing `plotshape` = 359 exactly**; set05+06 = 2875; all six = 3234. Never a corpus-wide or "blocked" count |
| input.* type tokens "115" | unsourced single-source | **re-sourced: set01–04 = 115 exactly** (regex `type\s*=\s*input\.`); set05+06 = 1878; all six = 1993 |
| runtime.error "563" | unsourced single-source | **NOT REPRODUCIBLE.** Reproducible: 553 (set01–04) / 199 (set05+06) / 752 (all six), regex `runtime\.error`. 563 appears nowhere else; corpus unchanged since the source doc was written |
| assigned hline "48" | unsourced single-source | **re-sourced: set01–04 = 48 exactly** (regex `=\s*hline\s*\(`, multiline); set05+06 = 479; all six = 527 |

Error populations are dominated by scraped-doc parse failures (e.g. 617/1059 bgcolor errors in set05 are `mismatched input '>' expecting <EOF>` from markdown blockquotes). Errors are reported as their own class, never folded into object/numeric.

## 1. bgcolor measurement (same method as 2026-11-17)

Method (identical to `.oo/proof/bgcolor-2026-11-17/scan_*.json`): for every
`tests/data/setXX/**/*.pine` containing `bgcolor`, call
`pynescript.compiler.engine._transpile_once(src)` (transpile-only, no JIT, no bar
loop) and record `object_mode` / kinds / exception. Reconstructed scanner:
`scan_numeric_mode.py` (run with `/usr/bin/python`, 3.14.10 — same interpreter
family as the `pyne` entry point, which resolves `pynescript` to this repo's
`src/`). Validation: re-running on set01–04 reproduces the artifact's totals
(354 files, 65 errors) with exactly one object→numeric flip explained by HEAD.

| Set | total | numeric | object | error |
|---|---|---|---|---|
| set01 | 27 | 0 | 27 | 0 |
| set02 | 61 | 0 | 58 | 3 |
| set03 | 175 | 2 | 135 | 38 |
| set04 | 91 | 9 | 58 | 24 |
| set01–04 (recheck) | 354 | 11 | 278 | 65 |
| set05 | 1290 | 11 | 256 | 1023 |
| set06 | 1025 | 7 | 982 | 36 |
| set05–06 | 2315 | 18 | 1238 | 1059 |
| all six | 2669 | 29 | 1516 | 1124 |

The 2026-11-17 artifact (`summary.json` there) is untouched, as required.

## 2. `pyne corpus run` — all four modes (operator-mandated invocation)

`pyne corpus run set05 set06 --workers 4 --rich --mode {auto,compile,interpret,parse}`
(CLI `--help` confirms `--mode` accepts `interpret|compile|auto|run|parse`; `run` is an
alias for `interpret`; flag names match the operator's invocation; logs untruncated).

| mode | exit | processed | OK | FAIL breakdown | T/O | rate | elapsed |
|---|---|---|---|---|---|---|---|
| parse | 1 | 23651 | 23510 | 135 FAIL | 6 | 99.40% | 3566 s |
| interpret | 1 | 23651 | 23334 | 139 PARSE_FAIL + 157 RUN_FAIL | 21 | 98.66% | 3288 s |
| compile | 1 | 23651 | 23393 | 136 PARSE_FAIL + 108 RUN_FAIL | 14 | 98.91% | 6565 s |
| auto | 1 | 23651 | 23448 | 134 PARSE_FAIL + 53 RUN_FAIL | 16 | 99.14% | 4787 s |

set05: parse 9055 OK / interpret 9013 / compile 9028 / auto 9041 (of 9114)
set06: parse 14455 OK / interpret 14321 / compile 14365 / auto 14407 (of 14537)

Exit code 1 for every mode is the `--strict` default firing on residual
FAIL/PARSE/RUN/TIMEOUT > 0 — expected on this corpus, not a runner failure.
Per-file results: `corpus-<mode>.csv` (row counts re-verified with a CSV parser:
exactly 23651 rows per mode; status tallies match the `corpus-<mode>_summary.txt`
files exactly). Full untruncated logs: `corpus-<mode>.log` (4–8.5 MB each,
ANSI progress output preserved; final summaries quoted above verbatim from
`corpus-<mode>_summary.txt`).

Note: FAIL = PARSE_FAIL + RUN_FAIL + TIMEOUT (verified arithmetic on all four modes).

## 3. The four unsourced figures — re-source vs measure

No measurement harness exists in the repo or the CLI for any of the four; the
2026-11-14 proof (`pyne-numeric-coverage-2026-11-14.proof.py`) only carries two
of the regexes used. Exact wording of the source (the only source) and the
re-measured counts are in `re-source.md`; raw numbers in `file_counts.json`.

| figure | source says | re-measured (set01–04 / set05+06 / all six) | verdict |
|---|---|---|---|
| plotshape 359 | "plotshape 359" (2026-11-14 plan lines 25, 236); plotshape slice itself says "card estimate, not a re-measured count" | 359 / 2875 / 3234 (substring `plotshape`) | matches as set01–04 file count |
| input.* 115 | "`type=input.integer/float/bool/source` — 115 scripts" (line 229) | 115 / 1878 / 1993 (regex `type\s*=\s*input\.`) | matches exactly |
| runtime.error 563 | "runtime.error — 563 scripts" (line 235) | 553 / 199 / 752 (regex `runtime\.error`) | **NOT reproducible** — treat 563 as unsourced; corpus unchanged since 2026-11-14 |
| assigned hline 48 | "assigned hline (`h = hline(...)`) — 48 scripts" (line 233); also "corpus-wide" (line 22, misleading) | 48 / 479 / 527 (regex `=\s*hline\s*\(` multiline) | matches exactly (set01–04) |

Method caveat: these are *files containing the construct* — the same sense as the
354/359/115/48 figures. They are not counts of numeric-mode blockers. No
numeric/object/error split exists for these populations and none is claimed.

## 4. Not done / not claimed

- No numeric/object/error transpile scan was run for the plotshape/input/hline/runtime.error populations (would be ~8× the bgcolor scan cost); available on request.
- The `~359` remains a set01–04-scoped figure; extending it to all six sets changes it to 3234 files containing `plotshape`.
- No board edits, no commits, no pushes; `.oo/proof/bgcolor-2026-11-17/` untouched; no source files modified. Pre-existing repo dirt (`.prettierignore`, `docker-compose.yml`, `tests/test_cli_util_coverage.py`, `.vscode/`) left as found.

## 5. Artifacts (this directory)

`summary.json` (machine-readable), `REPORT.md` (this file), `re-source.md`,
`file_counts.json`, `scan_set01_04_recheck.json`, `scan_set05_06_bgcolor.json`,
`scan_numeric_mode.py` (scanner used for both bgcolor scans),
`scan logs: backscan.log, bgcolor_scan_status.txt`, `environment.txt` (pyne/python/git state + `pyne corpus run --help` verbatim),
`corpus-{parse,interpret,compile,auto}.{log,csv}` + `corpus-<mode>_summary.txt`,
`status.txt` (per-mode wall-clock start/end + exit codes), `corpus_runs.sh`, `bgcolor_set05_06_scan.sh`.
