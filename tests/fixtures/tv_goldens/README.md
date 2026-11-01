# TradingView goldens

This directory is the repo's **numerical parity evidence against TradingView
itself**. Every other TA test checks PYNE against a spec, against another PYNE
path (interpret ↔ compile), or against a value derived by hand. None of those
catches an `rma` seeded one bar early, an `atr` using the wrong true-range
branch, or a `stdev` with the wrong denominator. Only TradingView's own output
does.

The fixtures are vendored from
[OpenPineScript](https://github.com/be-thomas/OpenPineScript)
(`conformance/v5/golden`, commit
`cbf7ce9183cf46221a76a7453cfa78542d220108`, GPL-3.0). They are nine Pine
harnesses and the nine Pine Logs exports TradingView produced when those
harnesses ran on `BINANCE:BTCUSDT` `1D` (2,474–2,475 daily bars,
2020-01-03 → 2026-10-12).

## What other projects do

| Project | How it proves TradingView parity | Reused here |
| --- | --- | --- |
| **OpenPineScript** (GPL-3.0) | A `.pine` harness plus the actual TV export (CSV or Pine Logs). The harness is the test program; the export carries OHLCV and plot columns. Comparator matches columns, warm-up, first non-`na`, and vacuity guards. | **Yes** — harnesses, exports, comparison contract |
| **PineTS** (AGPL-3.0) | Compatibility tests are self-generated baselines (regression protection, not external proof). Its strategy broker tests are hand-pinned to values measured on TV runs, but raw exports are not shipped. | Methodology only |
| **talipp** (MIT) | Hard-coded expected values in unit tests; no TradingView exports or capture recipe in-tree. | No |
| **pineforge-backtest-mcp** (MIT) | Consumes a user's TradingView strategy export (List of Trades) and grades a local engine; no bundled fixture. | Methodology only |
| **Healy218/HealysBacktester** (unlicensed) | A runbook for capturing a user CSV and comparing scoped columns; no bundled fixture. | Methodology only |

OpenPineScript is the only surveyed project that ships the **scripts and the
post-run TradingView data together**, which is what makes a reproducible
comparison possible. Its full recipe is in
[`conformance/common/golden.md`](https://github.com/be-thomas/OpenPineScript/blob/main/conformance/common/golden.md)
and its comparator is
[`conformance/common/tradingview_golden.test.ts`](https://github.com/be-thomas/OpenPineScript/blob/main/conformance/common/tradingview_golden.test.ts).

## Why the export is manual

TradingView publishes no API for indicator values, and scripting the UI would
breach their terms. A human has to run the harness once per fixture. Two routes
work:

* **Pine Logs (free)** — `log.info()` runs on historical bars. The generated
  `v5` harnesses emit one tagged row per bar (`OPSHEAD|` for the header,
  `OPS|` for each row). Copy the whole pane and save it as
  `<harness>.<SYMBOL>.<TF>.log`.
* **Export chart data (PRO+/Premium)** — the `v3`/`v4` source harnesses
  `plot()` the same values. Export the chart data as CSV next to the harness.
  Those source harnesses are vendored too; only the v5 log exports are
  compared today.

`alert()` cannot be used: alerts fire only on realtime bars, never on
historical ones, so a 2,475-bar daily export would take years to collect.

## How the comparison works

`scripts/compare_tv_goldens.py` mirrors OpenPineScript's comparator:

1. **The harness is the test program.** Run the same `.pine` through
   `pynescript.runtime.Runtime` on the OHLCV bars carried by the export.
2. **Compare the intersection.** Only columns present in both the export and
   PYNE's output are compared; `MIN_COLUMNS = 5` stops a degraded harness from
   passing with one accidental match.
3. **Warm-up.** Skip 300 bars for convergent indicators so a seeded EMA/RMA can
   forget history the export did not include. Path-dependent harnesses
   (`state`, `control`, `strategy`, `exits`) compare from bar 0 because their
   values never converge.
4. **Tolerance.** `abs(PYNE - TV) <= 1e-9` or `rel <= 1e-6`.
5. **`na` parity.** A bar where TradingView has `na` is not a value comparison,
   but PYNE inventing a value there is a failure. This catches indicators that
   emit `0` during warm-up.
6. **First non-`na` bar.** If TradingView's first value is after bar 0, PYNE
   must start on the same bar. An indicator that is right but starts one bar
   early/late is still a parity bug.
7. **Vacuity guards.** All-`na` columns, columns with fewer than 50 compared
   points, and constant columns fail unless they are explicitly
   constant-by-construction (`harness_loops::nested_loops`).
8. **Known divergences.** `baseline.json` records each remaining red column
   with a reason. New failures fail the suite; documented ones do not.

## Run it

```bash
# Human-readable report (exit 0 when there are no NEW failures)
python scripts/compare_tv_goldens.py

# Machine-readable report
python scripts/compare_tv_goldens.py --json

# Ignore the baseline: every divergence is red
python scripts/compare_tv_goldens.py --strict

# One or two harnesses while iterating
python scripts/compare_tv_goldens.py --only harness_core,harness_state

# Re-record the known-divergence baseline after an intentional change
python scripts/compare_tv_goldens.py --update-baseline
```

The pytest wrapper is `tests/test_tv_goldens.py`; it asserts that every export
has a sibling harness, that no column is a new failure, and that every baseline
entry has a real reason.

## Current baseline

After the second parity pass: **111 / 112 columns pass, 1 is a documented
divergence, 0 are unclassified.** Everything is green except one deliberately
ambiguous loop-series probe. Fixed in this pass:

- `ta.stdev` / `ta.variance` population `ddof=0`; `ta.bb` returns
  `(middle, upper, lower)`; `ta.tsi` returns the raw `[-1, 1]` ratio.
- Warm-up `na` semantics for `ta.macd` / `ta.wpr` / `ta.mfi` / `ta.atr` /
  `ta.highestbars` / `ta.lowestbars` / `ta.percentrank` / `ta.barssince`
  (and `ta.tr(true)` seeding bar 0 with `high - low`).
- Pine v5 eager `and` / `or` (both operands evaluate so series state inside
  the right side stays continuous); incremental TA state is keyed by the
  **AST call site**, so conditional branches no longer shift later calls.
- `na()` unwraps series; `fixnan` carries the last non-`na` sample forward
  (leading `na` stays `na`); `math.max` / `math.min` propagate `na`.
- `ta.sar` matches TradingView exactly (seed at bar 1, EP/AF updated before
  the reversal check, reversal against the unclamped SAR, two-bar clamp).
- `ta.vwap` anchors to the daily session by default.
- Strategy broker: market orders fill at the **next bar's open**, an order
  never fills on its placement bar, `strategy.entry` uses target-position
  (reversal) semantics, and all fills/brackets are quoted on the
  `syminfo.mintick` grid (market nearest; exit brackets rounded outward).
- `strategy()` default `initial_capital` is 1,000,000 (reference Pine).

The remaining gap:

| Area | Columns | Root cause |
| --- | --- | --- |
| Loop/history | `published_pattern` | One `ta.sma` call site reached 3× per bar with different sources; TradingView's loop-series semantics match none of the three readings the harness probes (first reach / last reach / shared state) |

This is a real finding, not a claim that PYNE is TradingView-certified. The
baseline exists so CI can stay green while the list is worked down; run
`--strict` to see the full red set.

## Adding a fixture

1. Put a harness and its export in the same directory, named
   `<harness>.pine` and `<harness>.<SYMBOL>.<TF>.log` (or `.csv`).
2. For a Pine Logs export, keep the `OPSHEAD|` header and one `OPS|` row per
   bar. For a CSV export, include `time,open,high,low,close,volume` plus the
   plot columns.
3. Add the provider/version directory if it is not OpenPineScript v5 (the
   comparator walks `*.log` / `*.csv` recursively).
4. Run `python scripts/compare_tv_goldens.py --update-baseline` and replace any
   `TODO: triage` reason with a concrete root cause.
5. Add the source URL, commit, license, and SHA-256 to `SOURCES.json`.

## Provenance and license

* Upstream: `https://github.com/be-thomas/OpenPineScript`
* Commit: `cbf7ce9183cf46221a76a7453cfa78542d220108` (2026-10-23)
* License: GPL-3.0 (`openpinescript/LICENSE`)
* Per-file SHA-256 and raw URLs: `SOURCES.json`

The GPL-3.0 files are combined with this AGPL-3.0-or-later project under
GPL-3.0 §13; the combined work is distributed under AGPL-3.0-or-later. Keep
`openpinescript/LICENSE` and `SOURCES.json` with the fixtures.

The exports are a **snapshot** of a TradingView chart. Re-exporting the same
symbol later may not reproduce byte-for-byte: realtime bars settle and
historical data is revised. Treat a log/CSV as a test fixture, not a durable
market-data feed.
