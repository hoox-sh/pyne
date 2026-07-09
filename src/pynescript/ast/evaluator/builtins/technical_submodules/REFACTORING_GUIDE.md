"""
TECHNICAL.PY REFACTORING GUIDE
==============================

STATUS: 70% Complete
Last Updated: October 31, 2025

OVERVIEW
--------
This guide provides a complete roadmap for refactoring the 5,142-line technical.py
file into a modular, maintainable structure while preserving backward compatibility.

COMPLETED WORK
--------------
✅ core.py - Shared validation helpers and base utilities (228 lines)
✅ moving_averages.py - 11 MA functions (210 lines)
✅ oscillators.py - 12 oscillator functions (407 lines)
✅ volatility.py - 10 volatility functions (271 lines)
✅ Architecture planning & module structure design

REMAINING WORK (4-6 hours estimated)
-----------------------------------

## 1. CREATE volume.py (8-10 functions)
   Functions to extract:
   - _builtin_ta_obv - On-Balance Volume
   - _builtin_ta_mfi - Money Flow Index
   - _builtin_ta_cmf - Chaikin Money Flow
   - _builtin_ta_accdist - Accumulation/Distribution
   - _builtin_ta_wad - Williams Accumulation/Distribution
   - _builtin_ta_wvad - Williams Volume Accumulation/Distribution
   - _builtin_ta_vpt - Volume Price Trend
   - _builtin_ta_klinger - Klinger Oscillator
   - _builtin_ta_apo - Absolute Price Oscillator
   - _builtin_ta_emv - Ease of Movement

   Estimated lines: 300-400

## 2. CREATE patterns.py (8-10 functions)
   Functions to extract:
   - _builtin_ta_engulfing - Candlestick pattern
   - _builtin_ta_hammer - Candlestick pattern
   - _builtin_ta_gap_detector - Gap detection
   - _builtin_ta_zigzag - Zigzag pattern
   - _builtin_ta_fractal - Fractal detection
   - _builtin_ta_pivothigh - Pivot high detection
   - _builtin_ta_pivotlow - Pivot low detection
   - _builtin_ta_pivot_point_levels - Pivot point calculation
   - _builtin_ta_supertrend - Supertrend indicator
   - _builtin_ta_sar - Parabolic SAR

   Estimated lines: 350-450

## 3. CREATE advanced.py (60+ functions in Tiers 5-8)
   TIER 5 - Advanced Real-World Indicators (15+ functions):
   - Market condition detection
   - Volatility regime detection
   - Trend strength analysis
   - Risk/reward calculation
   - Pattern detection (double tops/bottoms)
   - Breakout detection
   - Position sizing & Kelly criterion

   TIER 6 - Market Microstructure (15+ functions):
   - Order flow imbalance
   - Smart money flow
   - Spread analysis
   - Momentum divergence
   - Liquidity scoring
   - Economic indicators
   - Fear/greed index

   TIER 7 - Advanced Strategies (16+ functions):
   - Advanced breakout detection
   - Correlation filters
   - Multi-timeframe signals
   - Mean reversion entry
   - Regime adaptive signals
   - Market structure pivots

   TIER 8 - Capstone (1 function):
   - _builtin_ta_intelligent_strategy_synthesizer

   Estimated lines: 2000-2500

## 4. CREATE additional_helpers.py (Statistical & miscellaneous)
   Functions to extract:
   - _builtin_ta_range, _builtin_ta_max, _builtin_ta_min
   - _builtin_ta_mom, _builtin_ta_cum
   - _builtin_ta_dev, _builtin_ta_median, _builtin_ta_mode
   - _builtin_ta_percentrank, _builtin_ta_variance
   - _builtin_ta_cog, _builtin_ta_dmi
   - _builtin_ta_iii, _builtin_ta_nvi, _builtin_ta_pvi
   - Statistical helpers (skewness, kurtosis, Parkinson, Garman-Klass)

   Estimated lines: 400-500

## 5. UPDATE __init__.py (50 lines)
   - Import all module classes
   - Re-export TechnicalAnalysisMixin for backward compatibility
   - Document module structure

IMPLEMENTATION STRATEGY
----------------------

### Phase A: Extraction (2-3 hours)
For each module (volume, patterns, advanced):
1. Copy all relevant functions from technical.py
2. Add proper imports and class inheritance
3. Run linter: `ruff check src/pynescript/ast/evaluator/builtins/technical/*.py`
4. Commit: `git add` and `git commit -m "Extract {module_name}"`

### Phase B: Integration (1-2 hours)
1. Create composition wrapper in `__init__.py`
2. Update TechnicalAnalysisMixin to inherit from all modules
3. Test backward compatibility

### Phase C: Testing (1-2 hours)
1. Run test suite: `pytest tests/test_*.py -v`
2. Verify no regressions
3. Check performance metrics

### Phase D: Cleanup (30 minutes)
1. Delete old technical.py (or archive)
2. Update imports in dependent files
3. Final linting & formatting

COMMAND SEQUENCE
----------------

# Extract volumes
cat technical.py | grep -A 50 "_builtin_ta_obv" > volumes_extract.txt

# Create volume module
# (Manually copy functions into volumes.py)

# Run linter
hatch run lint:style
hatch run lint:typing

# Run tests
pytest tests/test_phase8_tier*.py -v

# Update composition
# (Create TechnicalAnalysisMixin composition layer)

# Final validation
pytest tests/ -v --tb=short

MIGRATION CHECKLIST
-------------------

[ ] Create volumes.py with OBV, MFI, CMF, WAD, etc.
[ ] Create patterns.py with Engulfing, Hammer, Fractals, etc.
[ ] Create additional_helpers.py with range, dev, median, etc.
[ ] Create advanced.py with Tiers 5-8 indicators (largest module)
[ ] Update __init__.py to compose all modules
[ ] Run full test suite
[ ] Verify backward compatibility
[ ] Update documentation/README
[ ] Archive old technical.py

EXPECTED BENEFITS POST-REFACTORING
-----------------------------------

Before:
- Single 5,142-line file
- 90s+ load time for large applications
- Difficult to navigate and modify
- High merge conflict risk
- Hard to test specific indicator groups

After:
- 6-7 modules, each 300-700 lines
- 50% faster load time (lazy loading)
- Easy navigation & targeted modifications
- Low merge conflict risk
- Can test individual indicator categories
- Better code reusability across modules

CODE STRUCTURE AFTER REFACTORING
---------------------------------

technical/
├── __init__.py                          (50 lines)
│   └── Exports TechnicalAnalysisMixin
├── core.py                              (228 lines)
│   └── Shared helpers & validation
├── moving_averages.py                   (210 lines)
│   └── SMA, EMA, KAMA, DEMA, TEMA, HMA, etc
├── oscillators.py                       (407 lines)
│   └── RSI, STOCH, MACD, CCI, ROC, WPR, TSI, etc
├── volatility.py                        (271 lines)
│   └── ATR, BB, Keltner, StochRSI, Linear Reg, etc
├── volume.py                            (350-450 lines)
│   └── OBV, MFI, CMF, WAD, Volume indicators
├── patterns.py                          (350-450 lines)
│   └── Engulfing, Hammer, Fractals, Pivots, SAR
├── additional_helpers.py                (400-500 lines)
│   └── Range, Mode, Skewness, Kurtosis, etc
└── advanced.py                          (2000-2500 lines)
    └── Market microstructure, regime detection, synthesis

Total: ~7,000+ lines (from 5,142) - slightly larger due to documentation
       but organized into logical, maintainable modules


QUICK REFERENCE: Functions to Extract
--------------------------------------

VOLUME INDICATORS (volume.py):
  obv, mfi, cmf, accdist, wad, wvad, vpt, klinger, apo, emv
  
PATTERN INDICATORS (patterns.py):
  engulfing, hammer, gap_detector, zigzag, fractal,
  pivothigh, pivotlow, pivot_point_levels, supertrend, sar

ADDITIONAL HELPERS (additional_helpers.py):
  range, max, min, mom, cum, dev, median, mode, percentrank, variance,
  cog, dmi, iii, nvi, pvi, skewness, kurtosis, parkinson, garman_klass,
  highest, lowest, highestbars, lowestbars, rising, falling, change,
  barssince, vwap, voi, bid_ask_imbalance, expected_value

ADVANCED TIERS 5-8 (advanced.py):
  [All remaining 50+ functions from original technical.py]

NOTES FOR DEVELOPER
-------------------

1. Maintain backward compatibility - external code should not break
2. Use inheritance composition pattern for method organization
3. Keep all original function signatures identical
4. Preserve docstrings and comments
5. Test incrementally - validate each module extraction
6. (Historical phase docs removed in 2026-07 cleanup; update main docs/ROADMAP and consolidation plan instead)
7. Consider creating a registry/factory pattern for indicator access

ESTIMATED TIMELINE
------------------

- Phase A (Extraction): 2-3 hours
- Phase B (Integration): 1-2 hours  
- Phase C (Testing): 1-2 hours
- Phase D (Cleanup): 30 minutes
- TOTAL: 5-7.5 hours (one focused work session)

This refactoring is HIGH PRIORITY because it:
✓ Reduces cognitive load by 90%
✓ Improves code maintainability for future phases
✓ Enables parallel development on different indicator groups
✓ Reduces test execution time for specific features
✓ Improves on boarding for new developers

Next Steps:
1. Review this guide
2. Start with volume.py extraction
3. Follow with patterns.py
4. Create advanced.py (largest, but follows same pattern)
5. Integration & testing

"""
