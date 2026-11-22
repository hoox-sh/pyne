#!/usr/bin/env bash
# Assertion wrapper for the 2026-11-14 numeric-coverage slice parity proof.
# Runs the 7 unlocked scripts + 7 distinct object-mode controls, then asserts
# the expected parity buckets. The TTM Wave interpret mismatch is pre-existing
# (numeric and forced-object compile agree), so it is expected here.
set -euo pipefail
cd "$(dirname "$0")/../.."

OUT=".openorchestrate/proof/pyne-numeric-2026-11-14/parity_14.json"
PYTHONPATH=src .venv/bin/python scripts/compare_interp_compile.py \
  --bars 120 --workers 4 --strict-errors --out "$OUT" \
  --files \
    tests/data/set01/indicators/205_ind_supertrend_from_scratch.pine \
    tests/data/set03/indicators/0449_ind_ttm_wave_ttm_wave.pine \
    tests/data/set04/indicators/0740_ind_plot_fill_demo.pine \
    tests/data/set04/indicators/0258_ind_accumulation_swing_index_asi_2.pine \
    tests/data/set04/indicators/0699_ind_example_2.pine \
    tests/data/set04/indicators/0909_ind_plot_2.pine \
    tests/data/set04/indicators/0257_ind_accumulation_swing_index_asi.pine \
    tests/data/set01/indicators/135_ind_asymmetrical_rsi.pine \
    tests/data/set01/indicators/163_ind_mean_absolute_deviation_bands.pine \
    tests/data/set01/indicators/208_ind_candle_percent_volatility.pine \
    tests/data/set02/indicators/116_ind_wavelet_denoising_filter_wavelet.pine \
    tests/data/set02/indicators/154_ind_christiano_fitzgerald_band_pass_filter_cfitz.pine \
    tests/data/set03/indicators/0430_ind_ehlers_voss_predictive_filter_voss.pine \
    tests/data/set04/indicators/0853_ind_matrix_row_example.pine \
  >"${OUT%.json}.log" 2>&1 || true

PYTHONPATH=src .venv/bin/python - "$OUT" <<'PY'
import json
import sys

data = json.load(open(sys.argv[1], encoding="utf-8"))
counts = data["counts"]
ok = counts.get("OK", 0)
mismatch = counts.get("MISMATCH", 0)
errors = sum(counts.get(k, 0) for k in ("both_error", "interp_error", "compile_error", "TIMEOUT", "FAIL"))
assert ok == 13, counts
assert mismatch == 1, counts
assert errors == 0, counts
print(f"PARITY_OK={ok} PARITY_MISMATCH={mismatch} PARITY_ERRORS={errors}")
PY
