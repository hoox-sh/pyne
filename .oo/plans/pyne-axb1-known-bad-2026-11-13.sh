#!/usr/bin/env bash
# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Known-bad reproduction for the two pre-existing tests/test_axb1.py subscribe
# failures at a4f094b5. It proves the failures exist in a CLEAN worktree (no
# Code Mode changes), so this card neither caused nor fixes them.
#
# Run from the pynescript repo root:
#
#     bash .oo/plans/pyne-axb1-known-bad-2026-11-13.sh
#
# The final KNOWN_BAD_DETECTED line is what `oo proof attach --expect` matches.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="$REPO/.venv/bin/python"
WT="${PYNE_AXB1_WORKTREE:-/tmp/opencode/pyne-a4f094b5}"
REV="${PYNE_AXB1_REV:-a4f094b5}"

if [ ! -e "$WT/.git" ]; then
  git -C "$REPO" worktree add --detach "$WT" "$REV" >/dev/null 2>&1
fi

# A dirty worktree would not isolate the failure from this card's changes.
if [ -n "$(git -C "$WT" status --porcelain)" ]; then
  echo "FAIL: worktree is dirty: $WT" >&2
  exit 2
fi

if [ "$(git -C "$WT" rev-parse --short HEAD)" != "$REV" ]; then
  echo "FAIL: worktree HEAD is not $REV" >&2
  exit 2
fi

OUT="$(cd "$WT" && PYTHONPATH="$WT/src" "$PY" -m pytest tests/test_axb1.py -q 2>&1 || true)"
printf '%s\n' "$OUT"

# Assert the exact pre-existing signature, not merely a non-zero exit.
printf '%s\n' "$OUT" | grep -q "2 failed, 50 passed"
printf '%s\n' "$OUT" | grep -q "test_subscribe_with_axb1_sends_bytes - KeyError: 5"
printf '%s\n' "$OUT" | grep -q "test_subscribe_axb1_full_sends_binary_for_status_and_snapshot"
printf '%s\n' "$OUT" | grep -q "KeyError: 5"

echo "KNOWN_BAD_DETECTED pyne_axb1_subscribe_2_failed_clean_${REV}"
