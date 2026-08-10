# Test data

This tree does **not** ship third-party Pine Script™ sources (TradingView®
builtins, community library scrapes, or large open-source corpora).

| Path | Role |
| --- | --- |
| *(optional local)* `examples/` | Local-only `*.pine` for `--example-scripts-dir` sweeps (gitignored) |
| `../fixtures/parity/` | First-party strategy parity fixtures owned by this project |
| `../fixtures/first_party/` | Always-on interpret↔compile smoke scripts (CI) |

Regression coverage uses **inline snippets** in `tests/test_*.py` and the
parity fixtures under `tests/fixtures/`. Do not re-add scraped corpora or
download helpers that pull from TradingView® network endpoints.
