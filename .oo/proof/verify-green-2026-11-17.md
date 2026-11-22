# Verify Format gate — real ruff check is GREEN — 2026-11-17

**Seat:** oo-spec-2 (deploy)
**Repo:** `/mnt/data/home/jango/Git/hoox-open-trading-stack/pynescript`
**HEAD:** `0968048c` (branch `main`)
**Ruff:** 0.15.20
**Verdict:** the Format gate is real (`ruff format --check src/ tests/ backend/`)
and the tree now satisfies it. Full `./scripts/verify.sh all` is **5 passed,
0 skipped, exit 0**.

This proof covers the **format + lint gate only**. It does **not** cover the
plotshape feature — see `.oo/proof/plotshape-root-clean-2026-11-17.md` and the
explicit scope note at the bottom.

## Done checks

```text
[1] PASS artifact exists at .oo/proof/verify-green-2026-11-17.md
[2] PASS verified by command: 4 checks, exit 0 each, transcripts in
         .oo/proof/verify-green-2026-11-17/
[3] PASS nothing outside deploy touched: no logic hand-edited, no exclude
         added, no gate narrowed, no commit/push/deploy/delete of source;
         the only removal is the authorized stale plotshape test copy
         (backed up first, separate card/proof)
```

---

## (a) Before — the gate told the truth and the truth was red

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

$ ruff check src/ tests/ backend/
I001 [*] Import block is un-sorted or un-formatted
  --> tests/test_compiler_plotshape_numeric.py:28:1
Found 1 error.
[*] 1 fixable with the `--fix` option.
exit=1
```

`verify.sh pre-commit` before this work: Format was `bun fmt --check` (green,
proving nothing about Python) and Lint was red → `1 failed, 3 passed`.
After the FORMAT_CMD fix but before reformatting: `2 failed, 2 passed`
(Format ✖ 10 files, Lint ✖ I001). See
`.oo/proof/format-gate-fix-2026-11-17.md`.

## (b) What changed

Chief's decision: **option 1 — reformat the files.** Gate stays at full scope.
No excludes, no narrowed paths, no skips.

Commands run:

```text
make fmt
  → ruff format src/ tests/ backend/
  → 10 files reformatted, 421 files left unchanged

ruff format scripts/build/ci_build.py scripts/build/compile.py
  → 2 files reformatted

ruff check --fix tests/test_compiler_plotshape_numeric.py
  → Found 1 error (1 fixed, 0 remaining)   [I001 import block sorted]
```

### Files reformatted — 12

In scope (`make fmt`):

```text
1.  backend/api/live_ensure.py
2.  backend/api/live_ws.py
3.  src/pynescript/ast/evaluator/builtins/map.py
4.  src/pynescript/compiler/compiler.py
5.  src/pynescript/langserver/features/hover.py
6.  tests/test_axb1.py
7.  tests/test_cli_util_coverage.py
8.  tests/test_compiler_library_inline.py
9.  tests/test_mae_realtime_ticks.py
10. tests/test_realtime_datafeed_ticks.py
```

Out of scope, formatted so `ruff format --check .` is clean repo-wide:

```text
11. scripts/build/ci_build.py
12. scripts/build/compile.py
```

Plus: `tests/test_compiler_plotshape_numeric.py` had its import block sorted
(I001), then the file was removed as part of the **separate** root-cleanup
card. It was backed up first — see the cleanup proof.

### Formatting changed layout only — proof

Every one of the 12 files was snapshotted before and after `make fmt`: the
`ast.dump(...)` of the whole module was compared.

```text
files compared: 12
AST identical: 12/12
AST DIFFERENT: none
byte-level changed: 12
```

A byte-identical AST means no expression, statement, operator, literal value,
or control flow changed. Only whitespace/quote layout moved. After the later
plotshape revert, `compiler.py` was reformatted again and re-checked:

```text
compiler.py AST == HEAD AST: True
```

So the committed `compiler.py` is HEAD's logic with ruff layout only.

### Uncommitted work from other seats

The tree already held other seats' uncommitted work before this task. Ruff only
rewrites layout, so reformatting them is safe, but it does mean the working-tree
diff of two files is **mixed** (their logic + my formatting):

```text
FORMATTING-ONLY            backend/api/live_ensure.py
FORMATTING-ONLY            backend/api/live_ws.py
FORMATTING-ONLY            scripts/build/ci_build.py
FORMATTING-ONLY            scripts/build/compile.py
FORMATTING-ONLY            src/pynescript/ast/evaluator/builtins/map.py
FORMATTING-ONLY            src/pynescript/compiler/compiler.py
MIXED (has logic edits)    src/pynescript/langserver/features/hover.py
FORMATTING-ONLY            tests/test_axb1.py
MIXED (has logic edits)    tests/test_cli_util_coverage.py
FORMATTING-ONLY            tests/test_compiler_library_inline.py
FORMATTING-ONLY            tests/test_mae_realtime_ticks.py
FORMATTING-ONLY            tests/test_realtime_datafeed_ticks.py
```

Classification method: take `HEAD:<file>`, run `ruff format` on it, compare to
the working-tree file. Equal → the whole diff is HEAD + formatting.

`hover.py` is covered by HQ Todo card
`pyne-lsp-hover-docs-card-formatt-4bd58cb6` ("dirty worktree work").
Those two files' logic is **not** mine and is not part of this card.

## (c) After — four checks, all green

Raw transcripts: `.oo/proof/verify-green-2026-11-17/`.

```text
$ ruff format --check .
448 files already formatted
exit=0

$ ruff check src/ tests/ backend/
All checks passed!
exit=0

$ ./scripts/verify.sh pre-commit
▸ Format     ruff format --check src/ tests/ backend/   ✔ 0.1s
▸ Lint       ruff check src/ tests/ backend/            ✔ 0.0s
▸ Typecheck  bun run check                              ✔ 0.1s
▸ OKF        okn --no-telemetry validate --spec 0.2 okf ✔ 0.1s
✔ pre-commit passed (4 passed, 0 skipped)
exit=0

$ ./scripts/verify.sh all
▸ Format     ruff format --check src/ tests/ backend/   ✔ 0.1s
▸ Lint       ruff check src/ tests/ backend/            ✔ 0.0s
▸ Typecheck  bun run check                              ✔ 0.1s
▸ OKF        okn --no-telemetry validate --spec 0.2 okf ✔ 0.1s
▸ Tests      pytest                                     ✔ 291.0s
✔ all passed (5 passed, 0 skipped)
exit=0
```

Before/after summary:

| check | before | after |
| --- | --- | --- |
| `ruff format --check .` | 12 files, exit 1 | 448 formatted, exit 0 |
| `ruff check src/ tests/ backend/` | 1 error (I001), exit 1 | All checks passed, exit 0 |
| `verify.sh pre-commit` | 1 failed / 3 passed (then 2/2) | 4 passed / 0 skipped, exit 0 |
| `verify.sh all` | Tests red (7 plotshape failures) | 5 passed / 0 skipped, exit 0 |

`448` vs the earlier `449` is the removed stale plotshape test file (12 files
needing format + 437 already formatted = 449 before; minus that one file).

## (d) Tree state — no deletions by me

`git status --porcelain` after cleanup:
`.oo/proof/verify-green-2026-11-17/git-status-after-cleanup.txt`

- 71 `D` entries, **all** under `.openorchestrate/` — the pre-existing
  `.oo/` migration, present before this task started. None are mine.
- `grep '^ D' | grep -v '.openorchestrate/'` → **none**.
- No untracked source files remain at root.

## Scope note — this green does NOT cover plotshape

The plotshape feature is **not** in the repo root. Its full implementation lives
in worktree `/mnt/data/home/jango/Git/pyne-plotshape-wt` at `0968048c`
(12/12 tests there). The root's partial patch was removed under the separate
cleanup card, with backups. `tests/test_compiler_plotshape_numeric.py` does not
exist at root, so this `verify.sh all` pass says **nothing** about plotshape.

## (e) Landed — commit series and push

Authorized by the operator after this proof's gate went green. Three commits,
scoped by path, no `git add -A`, no `--no-verify`:

```text
d912b88c chore(verify): gate Python formatting with ruff instead of bun
         1 file: scripts/verify.sh  (+21 / -72)
879622dd style: apply ruff format to src/, tests/, backend/ and build scripts
         12 files  (+52 / -51)
494fe98d chore(release): align VERSION and live docs pins to 0.7.1
         5 files: VERSION, README.md, docs/ROADMAP.md,
                  docs/missing_features.md,
                  docs/pinescript_implementation_status.md  (+5 / -5)
```

`git push origin main` → `0968048c..494fe98d  main -> main`, exit 0.
Pre-push hook ran the full gate: `✔ pre-push passed (5 passed, 0 skipped)`
(Tests `✔ 307.1s`). Final `git rev-list --count origin/main..HEAD` → **0**.

### Commit 2 did not sweep other seats' logic

`hover.py` and `test_cli_util_coverage.py` were staged as **formatting-only
blobs** (`ruff format(HEAD content)`), not as their working-tree versions. So
the commit contains layout only; their uncommitted logic remains in the working
tree, unstaged:

```text
 M src/pynescript/langserver/features/hover.py
 M tests/test_cli_util_coverage.py
```

Proof: every staged blob was checked byte-for-byte against
`ruff format(HEAD:<file>)` → `ALL STAGED BLOBS == ruff_format(HEAD): True`.
`hover.py`'s staged diff is 4 lines (+1/−3), not its 399-line logic diff;
`test_cli_util_coverage.py`'s is 4 lines, not 133.

Note on commit 1: the `scripts/verify.sh` working-tree diff predates this task
and also removes the old `scope_to_changed` block (+21/−72). That removal is
what makes the gate full-tree in hooks; it was committed as part of the
authorized gate path. My own edit is the 2-line `FORMAT_CMD` change.

## Not done here

- No deploy, no source delete, no force-push, no rebase.
- `scripts/verify.sh` was not edited again; FORMAT_CMD was already
  `ruff format --check src/ tests/ backend/`.
- No `extend-exclude` change, no skip, no `OO_SKIP`.

