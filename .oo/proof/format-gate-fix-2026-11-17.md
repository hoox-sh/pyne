# Format gate fix — scripts/verify.sh — 2026-11-17

**Seat:** oo-spec-2 (deploy)
**Repo:** `/mnt/data/home/jango/Git/hoox-open-trading-stack/pynescript`
**HEAD at time of work:** `0968048c`
**Verdict:** the gate is now a real check, and the real check is **RED**. This is a
**decision for the Chief**, not a done card. No source file was reformatted, no
exclude was added, no gate was weakened or skipped.

## Done checks

```text
[1] PASS artifact exists at .oo/proof/format-gate-fix-2026-11-17.md;
         FORMAT_CMD changed in scripts/verify.sh (oo:commands block only)
[2] PASS verified by command: before/after ./scripts/verify.sh pre-commit,
         exit codes, and direct ruff format --check → 10 files, exit 1
[3] PASS nothing outside deploy touched: no .py edited, no commit/push/
         deploy/delete; only verify.sh + .oo/board.md + .oo/proof/*
[4] FAIL (deliberate) the Format gate is red on 10 files, so this card is
         Blocked, not Done. Reformat-vs-scope is the Chief's decision.
```

---

## (a) What `bun fmt --check` actually does

```text
$ command -v bun; bun --version
/usr/bin/bun
1.4.4

$ bun fmt --help
Usage: bun fmt [flags] [...files, directories or patterns]
  Format JavaScript, TypeScript, CSS, HTML, JSON, YAML, Markdown and more.
Flags:
  -c, --check   Do not write. Exit with 1 if a file needs formatting

$ bun fmt --check
All 396 files are formatted.
exit=0

$ bun fmt --check --verbose
error: Invalid option '--verbose' - perhaps you meant '--version'?
```

It is **not** a no-op: bun 1.4.4 ships a built-in Prettier-like formatter, and it
genuinely examined 396 JS/TS/CSS/HTML/JSON/YAML/Markdown files and found them
formatted. But it cannot examine Python. This repo has **481 tracked `.py` files**
and **14 tracked `.ts/.tsx/.js/.mjs/.jsx` files**. The 0.0s green `✔` in
`.oo/proof/verify-plotshape-2026-11-17.txt` is consistent with this script: it
was a real exit-0 run of a formatter aimed at the wrong language. The Format
gate therefore proved nothing about the product code.

There is no `bunfig.toml` and no `fmt` script in `package.json` (scripts are
`docs:exports*`, `check`, `okf:*`, `prepare`). `bun fmt` here is bun's own
subcommand, not a package script.

## (b) The real formatter, and the new FORMAT_CMD

Per `AGENTS.md`, `Makefile`, and `pyproject.toml`:

```text
$ grep -n -A2 '^fmt:' Makefile
95:fmt:
96-	ruff format src/ tests/ backend/

pyproject.toml:
[tool.ruff]
target-version = "py310"
line-length = 120
extend-exclude = ["generated"]

$ ruff --version
ruff 0.15.20
```

New command (scope matches `LINT_CMD`):

```bash
# Keep FORMAT_CMD aligned with `make fmt` (ruff format src/ tests/ backend/).
FORMAT_CMD='ruff format --check src/ tests/ backend/'
```

Diff of my change (only the `oo:commands` block, only `FORMAT_CMD` + its comment):

```diff
 # oo:commands — detected by `oo init`; edit freely.
-FORMAT_CMD='bun fmt --check'
+# Keep FORMAT_CMD aligned with `make fmt` (ruff format src/ tests/ backend/).
+FORMAT_CMD='ruff format --check src/ tests/ backend/'
 # Keep LINT_CMD aligned with `make lint` (ruff check src/ tests/ backend/).
```

**Caveat on the diff:** `scripts/verify.sh` already had uncommitted working-tree
changes when this task started (HEAD still contains a `scope_to_changed` block
and the old `run_step`; the working tree did not). Those changes are not mine.
The file I read before editing contained `FORMAT_CMD='bun fmt --check'` and
already contained the newer `run_step`; my edit replaced exactly those two
lines. `git diff` vs HEAD shows the other hunks because they predate this task.

Isolated diff (reconstructed pre-edit file vs current, so it excludes the
pre-existing working-tree hunks):

```diff
 # oo:commands — detected by `oo init`; edit freely.
-FORMAT_CMD='bun fmt --check'
+# Keep FORMAT_CMD aligned with `make fmt` (ruff format src/ tests/ backend/).
+FORMAT_CMD='ruff format --check src/ tests/ backend/'
 # Keep LINT_CMD aligned with `make lint` (ruff check src/ tests/ backend/).
```

## (c) Honest result: RED

```text
$ ruff format --check src/ tests/ backend/
Would reformat: backend/api/live_ensure.py
Would reformat: backend/api/live_ws.py
Would reformat: src/pynescript/ast/evaluator/builtins/map.py
Would reformat: src/pynescript/compiler/compiler.py
Would reformat: src/pynescript/langserver/features/hover.py
Would reformat: tests/test_axb1.py
Would reformat: tests/test_cli_util_coverage.py
Would reformat: tests/test_compiler_library_inline.py
Would reformat: tests/test_mae_realtime_ticks.py
Would reformat: tests/test_realtime_datafeed_ticks.py
10 files would be reformatted, 421 files already formatted
exit=1
```

Repo-wide, for comparison with the HQ board card ("`ruff format --check .` finds
7 files"):

```text
$ ruff format --check .
Would reformat: backend/api/live_ensure.py
Would reformat: backend/api/live_ws.py
Would reformat: scripts/build/ci_build.py
Would reformat: scripts/build/compile.py
Would reformat: src/pynescript/ast/evaluator/builtins/map.py
Would reformat: src/pynescript/compiler/compiler.py
Would reformat: src/pynescript/langserver/features/hover.py
Would reformat: tests/test_axb1.py
Would reformat: tests/test_cli_util_coverage.py
Would reformat: tests/test_compiler_library_inline.py
Would reformat: tests/test_mae_realtime_ticks.py
Would reformat: tests/test_realtime_datafeed_ticks.py
12 files would be reformatted, 437 files already formatted
exit=1
```

The card's count has grown from 7 to 12 (10 in the scoped dirs; the extra two are
`scripts/build/ci_build.py` and `scripts/build/compile.py`, outside `make fmt`'s
scope). Nothing was excluded or ignored to change this number.

## (d) Before / after `./scripts/verify.sh`

Raw captures: `.oo/proof/format-gate-before-2026-11-17.txt` and
`.oo/proof/format-gate-after-2026-11-17.txt`.

Mode used for both captures: **`pre-commit`** (runs Format, Lint, Typecheck, OKF;
**does not run Tests**). The ~290s Tests step was not run in either capture. The
Format step is not mode-scoped in the current working tree, so the comparison is
valid for `all` and `pre-push` too.

### BEFORE — `./scripts/verify.sh pre-commit` (exit 1)

```text
OpenOrchestrate · pre-commit · pyne
────────────────────────────────────────────────────────────

▸ Format     bun fmt --check
  ✔ 0.0s
▸ Lint       ruff check src/ tests/ backend/
  ✖ 0.0s
    I001 [*] Import block is un-sorted or un-formatted
      --> tests/test_compiler_plotshape_numeric.py:28:1
    Found 1 error.
    [*] 1 fixable with the `--fix` option.
▸ Typecheck  bun run check
  ✔ 0.1s
▸ OKF        okn --no-telemetry validate --spec 0.2 okf
  ✔ 0.1s

────────────────────────────────────────────────────────────
✖ pre-commit failed (1 failed, 3 passed, 0 skipped)
```

Format green while `ruff format --check` is red on 10 files — that is the lie.

### AFTER — `./scripts/verify.sh pre-commit` (exit 1)

```text
OpenOrchestrate · pre-commit · pyne
────────────────────────────────────────────────────────────

▸ Format     ruff format --check src/ tests/ backend/
  ✖ 0.1s
    Would reformat: backend/api/live_ensure.py
    Would reformat: backend/api/live_ws.py
    Would reformat: src/pynescript/ast/evaluator/builtins/map.py
    Would reformat: src/pynescript/compiler/compiler.py
    Would reformat: src/pynescript/langserver/features/hover.py
    Would reformat: tests/test_axb1.py
    Would reformat: tests/test_cli_util_coverage.py
    Would reformat: tests/test_compiler_library_inline.py
    Would reformat: tests/test_mae_realtime_ticks.py
    Would reformat: tests/test_realtime_datafeed_ticks.py
    10 files would be reformatted, 421 files already formatted
▸ Lint       ruff check src/ tests/ backend/
  ✖ 0.0s
    I001 [*] Import block is un-sorted or un-formatted
      --> tests/test_compiler_plotshape_numeric.py:28:1
    Found 1 error.
    [*] 1 fixable with the `--fix` option.
▸ Typecheck  bun run check
  ✔ 0.1s
▸ OKF        okn --no-telemetry validate --spec 0.2 okf
  ✔ 0.1s

────────────────────────────────────────────────────────────
✖ pre-commit failed (2 failed, 2 passed, 0 skipped)
```

Summary lines:

| run | Format step | summary |
| --- | --- | --- |
| before | `✔ 0.0s` (`bun fmt --check`) | `pre-commit failed (1 failed, 3 passed, 0 skipped)` |
| after | `✖ 0.1s` (`ruff format --check …`, 10 files) | `pre-commit failed (2 failed, 2 passed, 0 skipped)` |

## What I did not touch

- No `.py` file was reformatted, edited, or deleted.
- No exclude/ignore was added; `extend-exclude` is unchanged.
- No `skip` command, no `OO_SKIP` default.
- No commit, push, deploy, or delete.
- The Lint failure (`tests/test_compiler_plotshape_numeric.py` I001) was already
  present in the before run and is outside this task; left alone.

## Decision needed from the Chief

The gate now tells the truth and the truth is red. Pick one:

1. **Reformat the 10 scoped files** (`make fmt`), then re-run — this changes
   source code and is your call, not mine.
2. **Keep the gate red** and fix the files in a separate card/owner.
3. **Narrow scope** (e.g. only `src/`) — but that hides `backend/` and `tests/`
   debt, so it needs an explicit reason on the record.

Until then the card is **Blocked on decision**, not Done.
