# Slice 7 — event shape: gate fixes + interpret/compile divergence (2026-11-18)

Scope: interpret-only fix (`src/pynescript/ast/evaluator/builtins/strategy.py`).
Fixtures (`tests/fixtures/parity/json/strategy_03..06_*.json`) pin **interpret** output.
No compiler files were touched. No commits were made.

## ⚠️ Session incident — slice-7 changes are parked in `stash@{0}`

During this session an **external process** (not this task) ran
`git stash push -u -m "temp: park unrelated dirt for hook-clean cherry-pick"`
(2026-11-18 20:44:14 +0100) and cherry-picked `8f5b0b91` "fix: fail verify when the
OKF bundle is stale" onto `main` (touches `scripts/verify.sh` +
`tests/okf/verify_okf_step.test.ts` only). Consequences:

- All slice-7 working-tree changes (strategy.py, 4 fixtures,
  `tests/test_reverse_order_semantics.py`, `tests/test_cli_util_coverage.py`,
  `.prettierignore`, `.vscode/settings.json`) are parked in `stash@{0}`.
  Verified: `git stash show --include-untracked --name-only stash@{0}` lists them all,
  including this note's scope files.
- Working tree at note-writing time contains only the `.prettierignore` modification.
- My edit to `tests/test_reverse_order_semantics.py` (Q000 fix) is preserved inside
  `stash@{0}` (verified: the stashed diff contains the double-quoted line).
- All verification below was run **before** the stash, against the live slice-7 tree.
- I did NOT pop/apply the stash — the cherry-pick flow that parked it may still be
  in flight. Restoring is a one-liner once the owner confirms:
  `git stash pop stash@{0}` (or `git checkout stash@{0} -- <paths>` for a partial restore).

## 1. Lint fix (gate item 1)

- `tests/test_reverse_order_semantics.py:170` — single quotes → double quotes, plus
  `ruff format` (line re-wrapped).
- `ruff check` and `ruff format --check` on both changed files
  (`strategy.py`, `tests/test_reverse_order_semantics.py`): **exit 0** (ruff 0.15.20).
- `pytest tests/test_reverse_order_semantics.py -q` → **9 passed**
- `pytest tests/test_parity.py -q` → **16 passed**

## 2. Fixture/compile divergence (gate item 2)

Interpret vs compile event counts (OHLCV corpus, `Runtime.run(..., mode=...)`):

| Fixture | interpret | compile | HEAD interpret | delta (compile − interpret) now | at HEAD |
|---|---|---|---|---|---|
| strategy_03_close_long | 173 | 173 | 149 | 0 | 24 |
| strategy_04_close_short | 173 | 173 | 149 | 0 | 24 |
| strategy_05_close_all | 173 | 198 | 149 | **25** | 49 |
| strategy_06_exit_stop_limit | 166 | 166 | 143 | 0 | 23 |

(HEAD interpret counts measured from `git show HEAD:<fixture>`; compile is byte-identical
to HEAD because `git diff -- src/pynescript/compiler/` is empty and the compile broker
(`compiler/strategy_broker.py`) imports only `strategy_risk_core` + `timeframe`, not the
interpret builtins module. The slice's `_emit_cover_close_event` is called only from the
interpret `_fill_order` branches.)

Fixture ↔ interpret equivalence verified pre-stash: each stashed fixture
(`git show stash@{0}:tests/fixtures/parity/json/<name>.json`) is deep-equal to a fresh
interpret run for all 4 fixtures.

### strategy_05_close_all — the 25 extra compile events

`strategy.close_all()` cycle: compile emits **one extra `close` per close_all placement**
(at the signal bar, e.g. bar_index=1, id=null, qty=10.0) **in addition to** the realized
`close` at the fill bar (e.g. bar_index=2, id="close"). Interpret emits only the
fill-time `close` (id="close_all"). 25 close_all placements → 25 extra compile `close`
events (compile: 49 `close` vs interpret 24; `close_all` = 50 in both).

Concrete divergence (index 4 of the stream):

- interpret[4]: `{"kind":"close_all","id":null,"direction":null,"qty":null,"bar_index":1}`
- compile[4]:   `{"kind":"close","id":null,"direction":"long","qty":10.0,"bar_index":1}`

### One concrete interpret↔compile diff line per fixture

- 03 (index 1): interpret `{"kind":"close","id":"L","qty":10.0,"bar_index":0}` vs
  compile `{"kind":"close","id":"L","qty":0.0,"bar_index":0}` (compile emits a 0-qty close)
- 04 (index 1): interpret `{"kind":"close","id":"S","qty":5.0,"bar_index":0}` vs
  compile `{"kind":"close","id":"S","qty":0.0,"bar_index":0}`
- 05 (index 4): see above (placement-bar `close` missing on interpret side)
- 06 (index 1): interpret `{"kind":"exit","id":"X","comment":null,"qty":0.0,"bar_index":0}` vs
  compile `{"kind":"exit","id":null,"comment":"X","qty":0.0,"bar_index":0}`
  (id/comment placement differs; pre-existing, count-neutral)

## 3. Pre-existing or caused by this slice?

**Pre-existing.** The divergence is unchanged in kind and strictly *reduced* in size by
this slice (compile−interpret: 24/24/49/23 → 0/0/25/0). The slice only added
interpret-side `close` emissions on raw-cover fills; it cannot alter compile output
(compiler untouched; no shared code path). HEAD interpret fixtures pinned 149/149/149/143
events, i.e. compile>interpret held before the slice too.

**Not attributable to this slice.** No compile files were changed and no fixtures were
fudged to force equality. If the intent is full interpret≡compile parity, the remaining
25 events are a compile-side placement-close emission question for the compiler owner —
do NOT paper over it by regenerating fixtures to compile output.

## 4. Not done / out of scope

- No commits, no board edits, no pushes.
- `.prettierignore`, `tests/test_cli_util_coverage.py`, `.vscode/` untouched by me.
- Working tree currently does **not** contain the slice-7 changes (parked in `stash@{0}`,
  see warning above). Tests/lint results above were produced on the pre-stash tree.
