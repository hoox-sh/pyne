# Handoff: prune stale checker proof 26b8cb47

- **from:** oo-checker
- **to:** oo-chief
- **objective:** Remove stale failing-before proof `26b8cb47` so the realtime/varip card no longer shows `ok:false` from a superseded exit-1 row.
- **artifacts:**
  - HQ `.oo/state.db` proofs for card `pyne-full-realtime-varip-semanti-175f8825` (pruned via official tooling)
  - `.oo/plans/prune-26b8cb47-result.json` (live `oo proof prune --json`)
  - `.oo/plans/prune-26b8cb47-before-after.json` (before/after summary)
  - This handoff: `pynescript/.oo/handoff/prune-26b8cb47.md`
- **decisions:** Used existing `oo proof prune <card>` (drops failing records older than newest passing proof). Did **not** need `--id/--supersede` (that Todo remains for *passing* junk proofs). Same prune also dropped two superseded missing-artifact rows on the same card (`2310dcd5`, `1479076e`); no unrelated cards touched. No raw SQL delete.
- **open questions:** Optional: refresh Done-card notes on `PYNE: full realtime/varip semantics support…` to drop the “26b8cb47 retained; not pruned” clause (owner oo-spec-2).
- **next gate:** Checker/Chief review of before/after proof listing; mark prune card Done if accepted.
