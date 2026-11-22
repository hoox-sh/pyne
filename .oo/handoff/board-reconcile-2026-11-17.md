# Handoff: reconcile local pyne board with HQ board

from: oo-ops
to: oo-chief
objective: Fix four false/stale board records without touching any Done status, and document which board is authoritative for pyne delivery.
artifacts: `pynescript/.oo/board.md` (L6-9 scope note, L14 proof pointer + owner, L13/L14 verdict notes, L16 Ready for Review); `hoox-open-trading-stack/.oo/board.md` L129 stale prune clause + L142 stale push note + 34 swept `.openorchestrate/` refs; `pynescript/.oo/playbook.md` (authority rule, `updated` rule, roster gap); `.oo/plans/openorchestrate-path-sweep-2026-11-17.md`; this handoff.
decisions: HQ board is authoritative for `PYNE:` cards and this board is the agency mirror; owner `pyne / HQ` mapped to `oo-misc` with the original label preserved; zero Done-status changes; the plotshape plan already exists so nothing was fabricated; no cross-workspace card sync exists here.
open questions: `updated` semantics decided (substantive change only); HQ plotshape card status is owned by oo-spec-2 (do not edit); `oo-misc` stays as the cross-agency owner and the roster gap is recorded in the playbook; the `.openorchestrate/` sweep is complete (59 rewritten, 18 left with reasons — see `.oo/plans/openorchestrate-path-sweep-2026-11-17.md`).
next gate: oo-checker verdict on the two local Done cards and HQ card `verify-proof-integrity-of-hq-pyn-f2181d0c`; only the Checker moves a card to Done.

## Artifacts

- `pynescript/.oo/board.md`
  - L6-9: added scope note under the header quote — pyne `PYNE:` cards live on HQ `../.oo/board.md`; this file is the agency mirror.
  - L14: proof pointer `.openorchestrate/handoff/pyne-live-full-count.md` → `.oo/handoff/pyne-live-full-count.md`. Root cause: the agency state dir was migrated from `.openorchestrate/` to `.oo/` (`git status` shows the `.openorchestrate/*` deletions) and the record was not updated in the same change. The file resolves at `.oo/handoff/pyne-live-full-count.md`.
  - L14: owner `pyne / HQ` → `oo-misc`; original label preserved in the proof cell as received, with the mapping rationale.
  - L13 + L14: appended "Awaiting oo-checker proof-integrity verdict (card f2181d0c); status unchanged." to both local Done cards. Status left `Done` on both.
  - L16: reconcile card moved Todo → Ready for Review with this handoff as proof.
- `hoox-open-trading-stack/.oo/board.md` L129: replaced the stale clause `Checker raw failing-before 26b8cb47 retained; not pruned.` with the pruned record (2026-11-16, `oo proof prune`, dryRun=false, also 2310dcd5 + 1479076e, show.ok=true after, before/after JSON, prune card Id). Line length kept at 2874 bytes, so the table column width is unchanged. Only L129 differs (verified by diff).
- `pynescript/.oo/playbook.md` L50: new paragraph under `## The board` recording the authority relationship and the absence of cross-workspace sync.

## Decisions

1. **HQ is authoritative for pyne delivery.** HQ carries 44 `PYNE:` cards (25 Done, 1 Ready for Review, 18 Todo) dated 2026-11-14..2026-11-17; this board carried 4 when the pass started and 5 when it ended (another seat added `make-the-verify-format-gate-real-01ddf2fc` concurrently — preserved, not mine). A reader of the local file alone would wrongly conclude pyne shipped nothing since 2026-11-09. The local board is the agency mirror for cards needing a local seat owner (cross-agency handoffs, audits). No mass duplication.
2. **Owner mapping is `oo-misc`, not an invented seat.** `pyne / HQ` is not in `.oo/config.json` `seats[]`; it is the HQ-side receiving label from axis (`from: axis / oo-spec-2`, `to: pyne / HQ`). The work is pyne backend/runtime (`backend/api/live_ws.py`, `src/pynescript/runtime/host.py`), which no pyne specialist seat owns; General Desk (`oo-misc`) is the documented catch-all. Original label retained in the proof cell so provenance is not lost.
3. **No status changes.** Both local Done cards now carry the oo-checker verdict (54 passed in 10.59s exact match; 23 passed on the grown suite) and stay `Done`. The HQ realtime/varip and exported-library cards stay `Done`; only their record text changed.
4. **No cross-workspace sync exists.** `oo board sync` normalises this file's columns only (dry-run: 4 rows, 9 columns, no columns added/removed). `oo board index` indexes local rows into local `.oo/state.db`. Neither imports HQ cards. Hand-copying 44 cards was rejected.
5. **Item 4 needed no repair — the premise was stale.** `.oo/plans/pyne-plotshape-numeric-2026-11-17.md` exists (7127 bytes, 141 lines) with objective, scope, change, acceptance criteria, failing-before hash, results, residual. It was rewritten at 10:43:44 during this pass (same size/content), i.e. the card owner is actively working it — the task's "no `.md` plan" observation was true only before that write. It is backed by `.proof.py` (`PLOTSHAPE_NUMERIC_OK positives=7 boundaries=5`) and `.oo/proof/verify-plotshape-2026-11-17.txt` (5 passed). Nothing was fabricated and the plotshape card was not edited.

## Open questions

- Local Done cards keep `updated: 2026-11-09` although their records were edited today. Should a record-only edit bump `updated`, or does `updated` track status movement only? Left unchanged to avoid masking staleness for `oo board lint`.
- HQ plotshape card `pyne-plotshape-constant-conditio-9d93e431` is `Ready for Review` (verified 2026-11-17), matching its plan's `Ready for Review — numeric synthesis, no commit/push`. The real open item is that the work is uncommitted in worktree `/mnt/data/home/jango/Git/pyne-plotshape-wt` at `0968048c`; owner/checker should decide whether review reads the worktree or waits for a commit.
- Is `oo-misc` the permanent home for cross-agency pyne cards, or does this workspace need a dedicated engineering seat? Mapping is honest but generic.
- HQ board still says "Nothing is done until this file says Done" — correct there, but it now differs in scope from the local header note.
- **Systemic pointer debt — swept 2026-11-17.** After the `.openorchestrate/` → `.oo/` migration, 59 resolvable references were rewritten (25 in pynescript records, 34 on the HQ board) and 18 were left with recorded reasons (transcripts, captured patch, generated okf map, card titles, one ambiguous base, one functional output path). HQ's `.openorchestrate/` now holds only `state/daemon-tick.log`. Log: `.oo/plans/openorchestrate-path-sweep-2026-11-17.md`. Remaining decision: whether `okf/architecture.md:40` should be regenerated by its owner.

## Next gate

oo-checker / Chief review of this handoff and the sweep log `.oo/plans/openorchestrate-path-sweep-2026-11-17.md`. The two local Done cards carry verdicts but were not moved; only the Checker may change their status. This card and the sweep card are Ready for Review, not Done.
