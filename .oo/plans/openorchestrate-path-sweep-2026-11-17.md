# `.openorchestrate/` path sweep — 2026-11-17

**Card:** `sweep-stale-openorchestrate-path-b3828ffd`

**Rule:** rewrite only when the target moved to `.oo/` and the old path does not resolve. Record old → new plus the check that proved the old path was dead. No pattern-matching rewrites.

**Result:** 59 references rewritten (25 in pynescript `.oo/` records across 22 files; 34 on the HQ board across 22 rows). 21 references left in place at 18 locations, with reasons below.

## Method

For each reference, resolve the old path from the record's root — `pynescript/` for agency records, `hoox-open-trading-stack/` for the HQ board. Rewrite only if `old` is absent **and** `new` exists. Brace expansions (`{md,proof.py,...}`) were checked member by member. Transcripts, captured patches, generated files, card titles, and prose that documents the migration were excluded regardless of resolution.

## Rewritten — pynescript records (25)

| file:line | old | new |
|---|---|---|
| `.oo/proof/deploy-p0-live-splice.md:45` | `.openorchestrate/proof/p0-live-frames-2026-11-11.jsonl` | `.oo/proof/p0-live-frames-2026-11-11.jsonl` |
| `.oo/plans/pyne-historical-extremes-2026-11-16.md:84` | `.openorchestrate/plans/pyne-historical-extremes-2026-11-16.{md,proof.py,failing-before.txt,failing-before-samebar.txt}` | `.oo/plans/pyne-historical-extremes-2026-11-16.{md,proof.py,failing-before.txt,failing-before-samebar.txt}` |
| `.oo/plans/pynescript-verify-debt-2026-11-16.md:94` | `.openorchestrate/plans/pynescript-verify-debt-2026-11-16.md` | `.oo/plans/pynescript-verify-debt-2026-11-16.md` |
| `.oo/plans/pyne-realtime-varip-2026-11-14.proof.py:8` | `.openorchestrate/plans/pyne-realtime-varip-2026-11-14.proof.py` | `.oo/plans/pyne-realtime-varip-2026-11-14.proof.py` |
| `.oo/plans/pyne-library-internal-calls-2026-11-15.md:165` | `.openorchestrate/plans/pyne-library-internal-calls-2026-11-15.md` | `.oo/plans/pyne-library-internal-calls-2026-11-15.md` |
| `.oo/plans/pyne-nested-realtime-rollback-2026-11-15.md:131` | `.openorchestrate/plans/pyne-nested-realtime-rollback-2026-11-15.md` | `.oo/plans/pyne-nested-realtime-rollback-2026-11-15.md` |
| `.oo/plans/pyne-cross-library-calls-2026-11-15.md:176` | `.openorchestrate/plans/pyne-cross-library-calls-2026-11-15.md` | `.oo/plans/pyne-cross-library-calls-2026-11-15.md` |
| `.oo/plans/pyne-reverse-order-position-2026-11-16.md:93` | `.openorchestrate/proof/verify-reverse-order-risk-2026-11-16.txt` | `.oo/proof/verify-reverse-order-risk-2026-11-16.txt` |
| `.oo/plans/pyne-reverse-order-position-2026-11-16.md:105` | `.openorchestrate/plans/pyne-reverse-order-position-2026-11-16.{md,proof.py,failing-before.txt,failing-before-risk.txt}` | `.oo/plans/pyne-reverse-order-position-2026-11-16.{md,proof.py,failing-before.txt,failing-before-risk.txt}` |
| `.oo/plans/pyne-library-methods-udt-inline-2026-11-15.md:89` | `.openorchestrate/plans/pyne-library-inline-2026-11-15.proof.py` | `.oo/plans/pyne-library-inline-2026-11-15.proof.py` |
| `.oo/plans/pyne-tick-mae-mfe-2026-11-16.md:98` | `.openorchestrate/plans/pyne-tick-mae-mfe-2026-11-16.{md,proof.py,failing-before.txt,failing-before-exit.txt}` | `.oo/plans/pyne-tick-mae-mfe-2026-11-16.{md,proof.py,failing-before.txt,failing-before-exit.txt}` |
| `.oo/plans/pyne-numeric-coverage-2026-11-14.proof.py:8` | `.openorchestrate/plans/pyne-numeric-coverage-2026-11-14.proof.py` | `.oo/plans/pyne-numeric-coverage-2026-11-14.proof.py` |
| `.oo/plans/pyne-exported-library-default-args-2026-11-16.md:54` | `.openorchestrate/plans/pyne-exported-library-default-args-2026-11-16.failing-before.txt` | `.oo/plans/pyne-exported-library-default-args-2026-11-16.failing-before.txt` |
| `.oo/plans/pyne-exported-library-default-args-2026-11-16.md:84` | `.openorchestrate/proof/verify-exported-library-defaults-2026-11-16.txt` | `.oo/proof/verify-exported-library-defaults-2026-11-16.txt` |
| `.oo/plans/pyne-exported-library-default-args-2026-11-16.md:92` | `.openorchestrate/plans/pyne-exported-library-default-args-2026-11-16.{md,failing-before.txt}` | `.oo/plans/pyne-exported-library-default-args-2026-11-16.{md,failing-before.txt}` |
| `.oo/plans/pyne-realtime-varip-2026-11-14.md:109` | `.openorchestrate/plans/pyne-realtime-varip-2026-11-14.proof.py` | `.oo/plans/pyne-realtime-varip-2026-11-14.proof.py` |
| `.oo/plans/pyne-intrabar-pending-fills-2026-11-16.md:121` | `.openorchestrate/plans/pyne-intrabar-pending-fills-2026-11-16.md` | `.oo/plans/pyne-intrabar-pending-fills-2026-11-16.md` |
| `.oo/plans/pyne-codemode-2026-11-13.proof.py:7` | `.openorchestrate/plans/pyne-codemode-2026-11-13.proof.py` | `.oo/plans/pyne-codemode-2026-11-13.proof.py` |
| `.oo/plans/pyne-library-methods-2026-11-15.md:99` | `.openorchestrate/plans/pyne-library-methods-2026-11-15.proof.py` | `.oo/plans/pyne-library-methods-2026-11-15.proof.py` |
| `.oo/plans/pyne-library-inline-2026-11-15.md:107` | `.openorchestrate/plans/pyne-library-inline-2026-11-15.proof.py` | `.oo/plans/pyne-library-inline-2026-11-15.proof.py` |
| `.oo/plans/pyne-axb1-known-bad-2026-11-13.sh:11` | `.openorchestrate/plans/pyne-axb1-known-bad-2026-11-13.sh` | `.oo/plans/pyne-axb1-known-bad-2026-11-13.sh` |
| `.oo/plans/pyne-library-udt-inline-2026-11-15.md:188` | `.openorchestrate/plans/pyne-library-udt-inline-2026-11-15.md` | `.oo/plans/pyne-library-udt-inline-2026-11-15.md` |
| `.oo/plans/pyne-drawing-realtime-rollback-2026-11-15.md:102` | `.openorchestrate/plans/pyne-drawing-realtime-rollback-2026-11-15.proof.py` | `.oo/plans/pyne-drawing-realtime-rollback-2026-11-15.proof.py` |
| `.oo/plans/pyne-nz-numeric-unlock-2026-11-15.md:123` | `.openorchestrate/plans/pyne-nz-numeric-unlock-2026-11-15.md` | `.oo/plans/pyne-nz-numeric-unlock-2026-11-15.md` |
| `.oo/plans/pyne-drawings-udt-methods-2026-11-15.md:108` | `.openorchestrate/plans/pyne-drawings-udt-methods-2026-11-15.proof.py` | `.oo/plans/pyne-drawings-udt-methods-2026-11-15.proof.py` |

## Rewritten — HQ board (34)

| line | old | new |
|---|---|---|
| L10 | `.openorchestrate/plans/hq-commit-plan-2026-11-08.md` | `.oo/plans/hq-commit-plan-2026-11-08.md` |
| L10 | `.openorchestrate/plans/` | `.oo/plans/` |
| L15 | `.openorchestrate/workspace.json` | `.oo/workspace.json` |
| L18 | `.openorchestrate/plans/hoox-smart-trading-git-2026-11-09.md` | `.oo/plans/hoox-smart-trading-git-2026-11-09.md` |
| L18 | `.openorchestrate/plans/hoox-smart-trading-git-2026-11-09.md` | `.oo/plans/hoox-smart-trading-git-2026-11-09.md` |
| L23 | `.openorchestrate/plans/portfolio-verify-2026-11-13.json` | `.oo/plans/portfolio-verify-2026-11-13.json` |
| L25 | `.openorchestrate/plans/usage-ledger-proof-2026-11-13.sh` | `.oo/plans/usage-ledger-proof-2026-11-13.sh` |
| L46 | `.openorchestrate/plans/hq-commit-plan-2026-11-08.md` | `.oo/plans/hq-commit-plan-2026-11-08.md` |
| L47 | `.openorchestrate/board.md` | `.oo/board.md` |
| L59 | `.openorchestrate/plans/agency-oo-status-2026-11-09.md` | `.oo/plans/agency-oo-status-2026-11-09.md` |
| L60 | `.openorchestrate/plans/agency-l7-2026-11-09.md` | `.oo/plans/agency-l7-2026-11-09.md` |
| L62 | `.openorchestrate/plans/cf-healthchecks-2026-11-09.md` | `.oo/plans/cf-healthchecks-2026-11-09.md` |
| L62 | `.openorchestrate/plans/cf-healthchecks-2026-11-09.md` | `.oo/plans/cf-healthchecks-2026-11-09.md` |
| L63 | `.openorchestrate/plans/oo-loops-graphs-2026-11-09.md` | `.oo/plans/oo-loops-graphs-2026-11-09.md` |
| L63 | `.openorchestrate/plans/oo-loops-graphs-2026-11-09.md` | `.oo/plans/oo-loops-graphs-2026-11-09.md` |
| L63 | `.openorchestrate/state/state.db` | `.oo/state/state.db` |
| L63 | `.openorchestrate/state/state.db` | `.oo/state/state.db` |
| L64 | `.openorchestrate/plans/oo-optional-skill-catalog-2026-11-09.md` | `.oo/plans/oo-optional-skill-catalog-2026-11-09.md` |
| L64 | `.openorchestrate/plans/oo-optional-skill-catalog-2026-11-09.md` | `.oo/plans/oo-optional-skill-catalog-2026-11-09.md` |
| L66 | `.openorchestrate/plans/agency-status-quo-2026-11-09.md` | `.oo/plans/agency-status-quo-2026-11-09.md` |
| L67 | `.openorchestrate/plans/dispatch-2026-11-09.md` | `.oo/plans/dispatch-2026-11-09.md` |
| L67 | `.openorchestrate/plans/dispatch-2026-11-09.proof.py` | `.oo/plans/dispatch-2026-11-09.proof.py` |
| L68 | `.openorchestrate/plans/p0-proof-rollout-gitlinks.proof.py` | `.oo/plans/p0-proof-rollout-gitlinks.proof.py` |
| L69 | `.openorchestrate/plans/agency-oo-hygiene-2026-11-09.proof.py` | `.oo/plans/agency-oo-hygiene-2026-11-09.proof.py` |
| L69 | `.openorchestrate/plans/agency-oo-status-2026-11-09.md` | `.oo/plans/agency-oo-status-2026-11-09.md` |
| L70 | `.openorchestrate/board.md` | `.oo/board.md` |
| L70 | `.openorchestrate/plans/proof-expect-exit-2026-11-09/` | `.oo/plans/proof-expect-exit-2026-11-09/` |
| L84 | `.openorchestrate/plans/board-identity-review-2026-11-09.md` | `.oo/plans/board-identity-review-2026-11-09.md` |
| L84 | `.openorchestrate/plans/board-identity-live-check.sh` | `.oo/plans/board-identity-live-check.sh` |
| L92 | `.openorchestrate/plans/axis-codemode-2026-11-13/summary.sh` | `.oo/plans/axis-codemode-2026-11-13/summary.sh` |
| L93 | `.openorchestrate/config.json` | `.oo/config.json` |
| L107 | `.openorchestrate/board.md` | `.oo/board.md` |
| L107 | `.openorchestrate/board.md` | `.oo/board.md` |
| L123 | `.openorchestrate/board.md` | `.oo/board.md` |

## Left in place (21 references, 18 locations)

| location | reference | reason |
|---|---|---|
| `okf/architecture.md:40` | `.openorchestrate/board.md` | Generated okf map, outside `.oo/`; the agent definitions already say `.oo/board.md`. Needs regeneration by its owner, not a hand edit. |
| `.oo/proof/pyne-numeric-2026-11-14/git_state.txt:4,7,8` | `.openorchestrate/board.md`, `plans/`, `proof/` | Captured `git status` transcript; rewriting would falsify the snapshot. |
| `.oo/proof/pyne-numeric-2026-11-14/parity_14.log:18` | `.openorchestrate/proof/.../parity_14.json` | Captured run log. |
| `.oo/proof/checker-library-defaults-2026-11-16.txt:20` | `.openorchestrate` (bare) | Migration note; it is the record of the rename. |
| `.oo/proof/audit-2026-11-17.md:46` | `.openorchestrate/` | Describes the `.prettierignore` diff at audit time. |
| `.oo/proof/audit-2026-11-17.md:70` | `.openorchestrate/plans/pyne-codemode-2026-11-13.proof.py` | The audit finding is that this old path no longer exists; rewriting destroys the finding. |
| `.oo/handoff/board-reconcile-2026-11-17.md:8,15,36` | old/new mapping | Documents the migration and the debt; must keep both sides. |
| `.oo/board.md:18` | `.openorchestrate/` | Card title; exact task text preserved. |
| `.oo/plans/pyne-plotshape-numeric-2026-11-17.md:70` | `.openorchestrate/` | Owner-active plan; the sentence describes `.prettierignore` entries, not a moved target. |
| `.oo/plans/pyne-numeric-coverage-2026-11-14.md:53,54` | `board.md`, `plans/`, `proof/` | Historical 'pre-existing dirty/untracked' note. |
| `.oo/plans/pyne-numeric-coverage-2026-11-14.parity.sh:9` | `.openorchestrate/proof/.../parity_14.json` | Functional output path, not a pointer; rewriting would let a re-run overwrite the archived proof. |
| `.oo/plans/pyne-plotshape-numeric-2026-11-17.patch:7` | `.openorchestrate/` | Captured patch artifact; editing it would invalidate the diff. |
| HQ board L22 | `.openorchestrate/keep.md` | Both old and new paths absent; no `.oo/keep.md`. |
| HQ board L88 | `.openorchestrate/proof/p0-live-lag-checker.md` | Both old and new absent at HQ root and under `pynescript/.oo/`. |
| HQ board L110 | `.openorchestrate/plans/pyne-codemode-2026-11-13.proof.py` | Card title; the target exists only at `pynescript/.oo/plans/...`, so the reference base is ambiguous. Not rewritten. |

## Verification

- At apply time every rewritten reference asserted `old` absent and `new` present; brace members checked individually.
- Post-sweep re-scan of pynescript: **0** resolvable dead pointers remain.
- HQ board: 3 references remain, all both-dead or ambiguous; 0 resolvable dead pointers remain.
- HQ board rows kept their original byte length, so table column alignment is unchanged.
- No source code, no commits, no pushes, no deletes. `pytest` was not run (oo-spec-2 held the suite).
