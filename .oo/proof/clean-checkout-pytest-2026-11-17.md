# Proof — clean-checkout pytest no longer hard-fails on the absent corpus

Card: `clean-checkout-pytest-hard-fails-d08a42fc`
Seat: `oo-spec-2`
Commit: `01a11897` — `test: skip corpus-dependent tests when tests/data is absent instead of failing`
Base: `31510706` (= `origin/main` before this commit)
Push: `31510706..01a11897  main -> main`
`git rev-list --count origin/main..HEAD` = 0 after push.

## Defect

`tests/data` is gitignored (`.gitignore:144` `data/`) and tracks only 3 files
(`README.md`, `axb1-vectors.json`, `builtin_scripts/.gitignore`). 24 tests read a
specific corpus `.pine` file with `Path.read_text()` and raised
`FileNotFoundError` on a bare checkout instead of skipping.

## Fix shape

24 per-test `pytest.mark.skipif` guards, one per failing test — **no module-level
`pytestmark`**, so inline tests in the same 12 files keep running. Every reason
string names `tests/data`:

- `tests/data/set06 corpus is gitignored and not part of a fresh clone` (23 cases)
- `tests/data/builtin_scripts corpus is gitignored and not part of a fresh clone` (1 case)

Matches the existing repo convention (`tests/test_set06_pine_int_na.py`
`_needs_set06`, `tests/test_corpus_runtime_residuals.py` per-test skipif).

## Converted vs skipped

**0 converted / 24 skipped.** Every one of the 24 takes a specific third-party
`.pine` file as its *subject* (e.g. `test_corpus_3712_matrix_kron` asserts on the
transpiled output of `3712_ind_matrix_kron.pine`). Converting them to inline
snippets would require vendoring the corpus, which AGENTS.md forbids
("No third-party corpus is shipped"). Each of the 12 files already retains
inline-snippet tests for the underlying language feature — with the corpus
present all 118 tests in those files pass and 0 skip, so no feature coverage is
lost.

No test was added or deleted (`git diff --cached | grep '^-def test_'` → empty;
volume_shadow test count HEAD 7 → 7).

## Both directions (clean `git archive` extracts, PYTHONPATH=<extract>/src)

### WITHOUT corpus

```
5313 passed, 86 skipped, 1 xfailed, 9 warnings in 223.35s
exit=0
0 FAILED lines
```

86 skipped = 62 pre-existing + **24 new**. Sum of my guard entries = **24**.
Baseline before the fix was `24 failed, 5313 passed, 62 skipped, 1 xfailed`,
exit 1.

### WITH corpus

```
5385 passed, 14 skipped, 1 xfailed, 9 warnings in 296.08s
exit=0
0 FAILED lines
```

Identical to the pre-fix with-corpus baseline (`5385 passed, 14 skipped,
1 xfailed`). Skips attributable to my guards = **0**. No test that used to run
now skips — no regression.

## Reproduce

```bash
# without corpus
rm -rf /tmp/opencode/taskb-clean && mkdir -p /tmp/opencode/taskb-clean
git archive HEAD | tar -x -C /tmp/opencode/taskb-clean
cd /tmp/opencode/taskb-clean
PYTHONPATH=/tmp/opencode/taskb-clean/src python -m pytest -q -rs --tb=no -p no:cacheprovider
# expect: 5313 passed, 86 skipped, 1 xfailed; exit 0

# with corpus
cp -a <repo>/tests/data/. /tmp/opencode/taskb-corpus/tests/data/
PYTHONPATH=/tmp/opencode/taskb-corpus/src python -m pytest -q -rs --tb=no -p no:cacheprovider
# expect: 5385 passed, 14 skipped, 1 xfailed; exit 0
```

## Scope

Touched only `tests/` — 12 files, +96/−13. `.gitignore`, the
`.openorchestrate/` migration, and all tracked-file deletions were left
untouched. Staged by explicit path (no `git add -A`), no `--no-verify`, no
force, no rebase.

## Still red / notes

- `tests/test_set06_color_overload.py::test_corpus_2693_same_class` still does
  `if not _2693.is_file(): return` — a vacuous *pass* when the corpus is absent,
  not a failure. Not one of the 24, so left alone; candidate for a follow-up.
- Done status left to the oo-checker verdict; card is Working with this proof
  attached.
