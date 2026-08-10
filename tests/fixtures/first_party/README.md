# First-party always-on fixtures

Small, license-clean Pine scripts shipped with the repo for CI and local
interpret↔compile parity smoke. These replace reliance on third-party
`tests/data/builtin_scripts/` corpora that are not shipped in clean clones.

Lives under `tests/fixtures/` (not `tests/data/`) so the root gitignore
`data/` rule does not exclude them.

| Script | Notes |
|--------|--------|
| `plot_close.pine`, `sma.pine`, `ema.pine`, `rsi.pine`, `strategy_entry.pine` | Always-on smoke in `test_interp_compile_parity.py` |
| `atr.pine` | Wave B Wilder RMA ATR; dual-host goldens in `test_first_party_ta_goldens.py` |
| `supertrend.pine` | ATR consumer; dual-host goldens |
| `keltner.pine` | `ta.kc` (EMA ± mult×ATR); dual-host goldens |

Do not put scraped third-party community scripts here.
