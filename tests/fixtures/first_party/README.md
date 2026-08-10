# First-party always-on fixtures

Small, license-clean Pine scripts shipped with the repo for CI and local
interpret↔compile parity smoke. These replace reliance on third-party
`tests/data/builtin_scripts/` corpora that are not shipped in clean clones.

Lives under `tests/fixtures/` (not `tests/data/`) so the root gitignore
`data/` rule does not exclude them.

Do not put scraped TradingView community scripts here.
