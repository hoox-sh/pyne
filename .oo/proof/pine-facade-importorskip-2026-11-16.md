# Proof — pine_facade importorskip cleanup in test_cli_util_coverage

Date: 2026-11-16
Seat: oo-spec-2
Card: pynescript: 8 pre-existing importorskip(pine_facade) calls in test_cli_util_coverage skip on clean checkout

## Root cause

pine_facade was removed from the shipped package in e90563c7 and is local-only via .git/info/exclude:13. The 8 coverage tests used pytest.importorskip(\"pynescript.util.pine_facade\"), so a clean checkout always skipped them. Modern equivalent: CLI/MCP fail-closed (\"removed\" / kind=unsupported); download-builtins surface already covered by test_download_builtins_available + test_download_builtins_fails_closed_without_facade.

## Fix

Removed the 8 importorskip-gated facade helper tests and unused _CATALOG from tests/test_cli_util_coverage.py. Did not invent a fake pine_facade module; did not re-ship the excluded helper; did not touch compiler.py or VERSION.

## Commands

### With local pine_facade present
```
PYTHONPATH=src .venv/bin/python -m pytest tests/test_cli_util_coverage.py -q --tb=line
102 passed in 13.28s
EXIT=0
```

### Clean-checkout simulation (mv pine_facade aside)
```
mv src/pynescript/util/pine_facade.py /tmp/pine_facade.py.bak
PYTHONPATH=src .venv/bin/python -m pytest tests/test_cli_util_coverage.py -q --tb=line
102 passed in 4.10s
EXIT=0
PYTHONPATH=src .venv/bin/python -m pytest tests/test_cli_util_coverage.py -k "download_builtins or facade" -q --tb=line
2 passed, 100 deselected in 0.11s
EXIT=0
mv /tmp/pine_facade.py.bak src/pynescript/util/pine_facade.py
```

## Before/after

- Before without module: 2 passed, 8 skipped (importorskip)
- After without module: 102 passed, 0 skipped
- importorskip(pine_facade) sites remaining in this file: 0
