# Handoff — pine_facade importorskip cleanup

- **from:** oo-spec-2
- **to:** oo-checker
- **objective:** Eliminate the 8 `importorskip(pine_facade)` skips in `tests/test_cli_util_coverage.py` on a clean checkout without inventing a fake facade module.
- **artifacts:**
  - `tests/test_cli_util_coverage.py` (removed 8 importorskip-gated facade helper tests + unused `_CATALOG`; docstring notes fail-closed CLI coverage)
  - `.oo/proof/pine-facade-importorskip-2026-11-16.md`
  - `.oo/proof/pine-facade-importorskip-2026-11-16.with.txt`
  - `.oo/proof/pine-facade-importorskip-2026-11-16.without.txt`
  - `.oo/proof/pine-facade-importorskip-2026-11-16.download-builtins.txt`
- **decisions:** Do not re-ship `src/pynescript/util/pine_facade.py` (intentionally removed in e90563c7; local-only via `.git/info/exclude`). Keep CLI/MCP fail-closed paths. Dedicated tracked `tests/test_pine_facade*.py` left alone (out of card scope; still skip locally when the exclude file is absent).
- **open questions:** Whether to delete or gate the tracked `tests/test_pine_facade.py` / `tests/test_pine_facade_helpers_coverage.py` files the same way (still importorskip on clean checkout).
- **next gate:** Checker verifies proof commands and moves HQ card to Done (no commit/push from this seat).
