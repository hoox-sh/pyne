# pynescript verify debt after 0.7.1 — format + four stale tests

- **Date:** 2026-11-16
- **Seat:** `oo-spec-2` (Engineering)
- **Card:** `pynescript: verify red after 0.7.1 — 4 tests expect 0.7.0 CLI surfaces + REVIEW.md format drift`
- **Status:** implementation slice; no push until operator approval.

## Why

`./scripts/verify.sh` is red 2/5 after the 0.7.1 release:

- **Format:** `REVIEW.md` fails `bun fmt --check`. It is a hand-written review
  note (not generated; last changed upstream `4ddab46e`), so formatting it is
  safe.
- **Tests:** four tests still encode the 0.7.0 surfaces:
  - `test_pygls_initialize_advertises_semantic_token_legend` and
    `test_pyne_lsp_version_flag` hardcode `"0.7.0"` instead of the package
    version.
  - `test_download_builtins_removed` and `test_list_facade_templates_removed`
    assert the `pine_facade` helper is gone, but 0.7.1 restored it. They also
    hit the network / depend on the environment.

## Acceptance criteria

1. `REVIEW.md` is formatted by the repo formatter and `bun fmt --check` passes.
2. The two version tests compare against `pynescript.__about__.__version__`
   (no hardcoded release) and still assert a non-empty version.
3. The CLI test proves the current `download-builtins` path runs without
   `ImportError` or network (monkeypatched downloader, `--list` → `dry_run`),
   **and** the removed-helper path still fails closed with "removed".
4. The MCP test proves `list_facade_templates` returns the catalog from a
   monkeypatched `list_builtin_scripts` (no network), **and** the removed-helper
   path still fails closed with `kind="unsupported"`.
5. `./scripts/verify.sh` is **5/5 green**.
6. No source behavior change beyond the tests/format; no dependencies.

## Implementation sketch

- `bunx prettier --write REVIEW.md` (only that file; check the diff is table
  alignment, no content change).
- Version tests: `assert __version__` + `== __version__`.
- CLI/MCP tests: monkeypatch the facade functions for the available path; a
  fake `builtins.__import__` for the removed path. No network, no installed-CLI
  dependency.

## Proof plan

- Failing-before: `./scripts/verify.sh` 2 failed / 3 passed; four tests fail.
- After: `./scripts/verify.sh` 5/5; proof script prints `VERIFY_DEBT_OK ...`.
- Named `--expect` assertion on the verify transcript and the proof script.

## Results

### Failing-before (HEAD `e2d160ee`)

`./scripts/verify.sh` — **2 failed / 3 passed**:
- Format: `REVIEW.md` needs formatting.
- Tests: `test_download_builtins_removed`,
  `test_pygls_initialize_advertises_semantic_token_legend`,
  `test_pyne_lsp_version_flag`, `test_list_facade_templates_removed`.
Transcript: `pynescript-verify-debt-2026-11-16.failing-before.txt`.

### After

- `./scripts/verify.sh` — **5/5 green** (pytest 451.1s).
- `REVIEW.md` formatted (table alignment only; hand-written, not generated).
- Version tests derive from `pynescript.__about__.__version__`.
- CLI/MCP tests exercise the current 0.7.1 surfaces with monkeypatched
  facade functions (no network, no installed-CLI dependence) **and** keep the
  removed-helper fail-closed assertions.
- Proof token:
  `VERIFY_DEBT_OK version=0.7.1 format=1 cli=1 mcp=1 failclosed=1`.

### Portability (checker condition)

`pynescript.util.pine_facade` is ignored via `.git/info/exclude:13` and
untracked at HEAD, so a clean checkout lacks it. The two "available" tests now
inject a fake `sys.modules["pynescript.util.pine_facade"]` module (with
`DEFAULT_DEST` / `download_builtin_scripts` / `_meta_name` /
`list_builtin_scripts`) instead of importing the worktree file. The fail-closed
tests keep faking import absence.

Proof: `pynescript-verify-debt-2026-11-16.clean-checkout.sh` builds a clean
`git archive HEAD` of `src` + the test files (no facade), overlays the updated
tests, and runs the six tests there: **6 passed**,
`CLEAN_CHECKOUT_TESTS_OK tests=6`.

### Files

- `REVIEW.md` — formatter only.
- `tests/test_cli_util_coverage.py`,
  `tests/test_langserver_server_coverage.py`,
  `tests/test_mcp_ops_low_coverage.py`.
- `.openorchestrate/plans/pynescript-verify-debt-2026-11-16.md` (this file),
  `.proof.py`, `.failing-before.txt`, `.verify.txt`, `.clean-checkout.sh`.
