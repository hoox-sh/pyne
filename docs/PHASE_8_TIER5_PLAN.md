# Copyright 2024-2025 jango_blockchained
#
# Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.gnu.org/licenses/lgpl-3.0.en.html
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: LGPL-3.0-or-later

# Phase 8 Tier 5: Advanced Integration & Real-World Indicators

**Status**: STARTING  
**Date**: October 30, 2025  
**Target Completion**: November 6, 2025  
**Objectives**: Implement 10-15 real-world trading indicators and advanced combinations

---

## Overview

After completing Tiers 1-4 with 39 indicators (95 tests, ~3250 lines), Phase 8 Tier 5 focuses on:
- **Real-world trading patterns** not yet covered
- **Multi-timeframe analysis** wrappers
- **Risk management indicators** for practical trading
- **Advanced combinations** of existing indicators
- **Market microstructure analysis** for algo trading

**Current Project Status**: 96.5% completion (39/42 Phase 8 functions)  
**Target After Tier 5**: 97-98% completion

---

## Tier 5 Specifications: 10-15 New Indicators

### Group A: Market Condition Indicators (3-4 functions)

#### 1. **ta.market_condition** - Market Regime Detection
- **Purpose**: Detects current market condition (trending, ranging, volatile)
- **Signature**: `ta.market_condition(close, atr, sma_period, stdev_period) → str`
- **Returns**: "trending_up" | "trending_down" | "ranging" | "volatile"
- **Logic**:
  - If price > SMA and ATR > threshold: "trending_up"
  - If price < SMA and ATR > threshold: "trending_down"
  - If price oscillates around SMA: "ranging"
  - If stdev is very high: "volatile"
- **Use**: Adapt strategy to current market condition

#### 2. **ta.volatility_regime** - Volatility Classification
- **Purpose**: Classifies current volatility level
- **Signature**: `ta.volatility_regime(atr_list, period) → str`
- **Returns**: "low" | "medium" | "high" | "extreme"
- **Logic**: Compare current ATR to historical ranges
- **Use**: Adjust position size, stop loss, or indicator sensitivity

#### 3. **ta.trend_strength** - Quantified Trend Strength
- **Purpose**: Measures how strong current trend is (0-100 scale)
- **Signature**: `ta.trend_strength(close, adx_value, rsi_value) → float`
- **Returns**: 0-100 score
- **Logic**: Combine ADX (trend strength) and RSI (extremeness)
- **Use**: Filter signals based on trend quality

#### 4. **ta.risk_reward_ratio** - Calculated Risk/Reward
- **Purpose**: Calculate R:R ratio for entry/exit levels
- **Signature**: `ta.risk_reward_ratio(entry, stop, target) → float`
- **Returns**: Risk-reward ratio (e.g., 1:3 = 3.0)
- **Logic**: (target - entry) / (entry - stop)
- **Use**: Validate trade setup meets minimum R:R threshold

---

### Group B: Advanced Pattern Recognition (3 functions)

#### 5. **ta.double_top_bottom** - Double Top/Bottom Detection
- **Purpose**: Identifies double top and double bottom reversal patterns
- **Signature**: `ta.double_top_bottom(high, low, period) → dict`
- **Returns**:
  - `pattern_type`: "double_top" | "double_bottom" | "none"
  - `strength`: 0-1 (how perfect the pattern is)
  - `breakout_level`: Price level for breakout confirmation
- **Use**: Classic reversal pattern for trend changes

#### 6. **ta.breakout_detection** - Support/Resistance Breakout
- **Purpose**: Detects breakouts through support/resistance
- **Signature**: `ta.breakout_detection(close, resistance, support) → dict`
- **Returns**:
  - `is_breakout`: bool
  - `breakout_type`: "resistance" | "support" | "none"
  - `breakout_strength`: Percentage above/below level
- **Use**: Confirm breakout strategies

#### 7. **ta.inside_bar_pattern** - Inside Bar Detection
- **Purpose**: Identifies inside bar consolidation patterns
- **Signature**: `ta.inside_bar_pattern(high, low) → bool`
- **Returns**: true if current bar is inside previous bar range
- **Use**: Low volatility periods before breakouts

---

### Group C: Money Management & Risk (3-4 functions)

#### 8. **ta.position_sizing** - Position Size Calculator
- **Purpose**: Calculate position size based on risk parameters
- **Signature**: `ta.position_sizing(account_size, risk_percent, entry, stop) → float`
- **Returns**: Number of shares/contracts to trade
- **Logic**: (account_size * risk_percent) / (entry - stop)
- **Use**: Risk management - never risk more than intended

#### 9. **ta.kelly_criterion** - Kelly Criterion Position Size
- **Purpose**: Optimal position size using Kelly formula
- **Signature**: `ta.kelly_criterion(win_rate, avg_win, avg_loss) → float`
- **Returns**: Fraction of account to risk (0-1)
- **Logic**: f* = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
- **Use**: Mathematical optimal sizing (often halved for safety)

#### 10. **ta.max_loss_level** - Maximum Loss Stop Level
- **Purpose**: Calculate stop loss to limit maximum loss
- **Signature**: `ta.max_loss_level(entry, account_size, max_loss_percent) → float`
- **Returns**: Stop price to limit loss
- **Logic**: entry - (account_size * max_loss_percent) / shares
- **Use**: Absolute loss protection

#### 11. **ta.profit_lock_level** - Trailing Profit Lock
- **Purpose**: Dynamic trailing stop for profit protection
- **Signature**: `ta.profit_lock_level(entry, current, trail_pct, direction) → float`
- **Returns**: Stop price that trails behind price
- **Direction**: 1 for longs, -1 for shorts
- **Use**: Lock in profits while staying in trend

---

### Group D: Multi-Indicator Combinations (3 functions)

#### 12. **ta.signal_confluence** - Multi-Signal Confirmation
- **Purpose**: Count overlapping signals from multiple indicators
- **Signature**: `ta.signal_confluence(signals_dict) → dict`
- **Returns**:
  - `signal_count`: Number of buy/sell signals
  - `confluence_level`: 0-1 strength (count/total_indicators)
  - `primary_signal`: Strongest signal
- **Use**: Require multiple confirms before trading

#### 13. **ta.divergence_detector** - General Divergence Finder
- **Purpose**: Generic divergence detection between price and indicator
- **Signature**: `ta.divergence_detector(price, indicator, lookback) → dict`
- **Returns**:
  - `is_bullish`: Bullish divergence detected
  - `is_bearish`: Bearish divergence detected
  - `strength`: 0-1 divergence strength
- **Use**: Early warning of momentum failure

#### 14. **ta.strategy_score** - Overall Strategy Signal Score
- **Purpose**: Combines multiple indicators into single score
- **Signature**: `ta.strategy_score(rsi, macd, ema_cross, trend) → float`
- **Returns**: -100 to +100 score
- **Logic**: Weighted combination of normalized indicator signals
- **Use**: Single metric for strategy performance

---

### Group E: Volatility & Probability (2-3 functions)

#### 15. **ta.probability_of_movement** - Expected Movement Probability
- **Purpose**: Calculate probability of reaching target based on ATR/volatility
- **Signature**: `ta.probability_of_movement(current, target, atr, period) → float`
- **Returns**: 0-1 probability estimate
- **Logic**: Based on volatility and distance to target
- **Use**: Trade probability assessment

#### 16. **ta.gamma_levels** - Options-Style Gamma Exposure
- **Purpose**: Calculate price levels with highest gamma (options terminology)
- **Signature**: `ta.gamma_levels(volatility, current_price, period) → list`
- **Returns**: [high_gamma_level, low_gamma_level]
- **Use**: Identify price levels with maximum volatility concentration

---

## Implementation Details

### Pattern: Standard Builtin Handler

```python
def _builtin_ta_<name>(self, args: list[Any]) -> return_type:
    """
    Comprehensive docstring.
    
    Parameters: [descriptions]
    
    Returns:
        - Detailed return format
    
    Edge Cases:
        - Handles None values
        - Validates parameters
    """
    
    # Argument validation
    msg = "ta.<name>() requires X arguments: ..."
    if len(args) < required or len(args) > maximum:
        self._error(msg)
    
    # Extract and validate parameters
    param1 = self._expect_list(args[0], msg)
    param2 = self._expect_int(args[1], msg)
    
    # Edge case handling
    if len(param1) < 2:
        return None  # Or appropriate default
    
    # Calculation
    result = _detailed_calculation(param1, param2, ...)
    
    return result
```

---

## Testing Strategy

### Test File: `tests/test_phase8_tier5.py`

**Test Structure**:
- 2-4 tests per function (40-60 total tests)
- Unit tests with synthetic data
- Integration tests combining multiple functions
- Edge case tests (empty, None, boundary values)

**Test Categories**:

1. **Market Condition Tests** (10 tests)
   - Each condition type: trending up/down, ranging, volatile
   - Multiple market periods
   - Integration with ADX/RSI

2. **Pattern Recognition Tests** (8 tests)
   - Double top/bottom formation
   - Breakout at various levels
   - Inside bar formation

3. **Risk Management Tests** (12 tests)
   - Position sizing calculations
   - Kelly criterion edge cases
   - Stop loss levels
   - Profit lock trailing

4. **Multi-Indicator Tests** (10 tests)
   - Signal confluence with 2-5 indicators
   - Divergence detection scenarios
   - Strategy score aggregation

5. **Volatility Tests** (8 tests)
   - Probability calculations
   - Gamma levels computation
   - Edge case volatility extremes

6. **Integration Tests** (5 tests)
   - Full strategy combining multiple Tier 5 functions
   - Multi-indicator strategies
   - Risk-adjusted signal generation

**Expected Coverage**: 45-55 tests total

---

## Code Statistics (Target)

| Metric | Value |
|--------|-------|
| Functions to Implement | 10-15 |
| Estimated Lines of Code | ~1000-1200 |
| Average Lines per Function | ~80-100 |
| Test Methods | 45-55 |
| Docstring Coverage | 100% |
| Expected Pass Rate | 100% |

---

## Integration Points

### With Previous Tiers
- Use Tier 1-4 indicators in combinations (KAMA, EMA cross signals, etc.)
- Build on established patterns (RSI, MACD, BB, ATR)
- Maintain backward compatibility

### Builtin Map Updates
- Add ~12-15 new entries to `_technical_builtin_map()`
- Total TA functions: 95+ → 107+
- Maintain alphabetical organization

### No Breaking Changes
- All existing tests continue to pass
- No modifications to previous function signatures
- Pure additions to capability

---

## Success Criteria

1. ✅ 10-15 new indicators implemented
2. ✅ 45-55 passing tests
3. ✅ Zero regressions (all 765 existing tests pass)
4. ✅ 100% docstring coverage
5. ✅ Comprehensive parameter validation
6. ✅ Full round-trip parsing stability
7. ✅ Integration with Tier 1-4 functions

---

## Project Completion Path

| Phase | Functions | Tests | Completion | Status |
|-------|-----------|-------|-----------|--------|
| Phases 1-7 | 56 | 670 | 92% | ✅ COMPLETE |
| Phase 8 Tier 1 | 9 | 31 | 92.5% | ✅ COMPLETE |
| Phase 8 Tier 2 | 15 | 16 | 93.5% | ✅ COMPLETE |
| Phase 8 Tier 3 | 10 | 20 | 94.8% | ✅ COMPLETE |
| Phase 8 Tier 4 | 5 | 28 | 96.5% | ✅ COMPLETE |
| **Phase 8 Tier 5** | **12-15** | **50-55** | **97-98%** | 🟡 STARTING |
| **TOTAL** | **107-110** | **815-820** | **97-98%** | **🟡 IN PROGRESS** |

---

## Timeline

- **Start**: October 30, 2025, 9:00 AM
- **Implementation**: October 30 - November 2 (3-4 days)
- **Testing & Validation**: November 2-4
- **Documentation**: November 4-5
- **Final Review**: November 5-6
- **Target Completion**: November 6, 2025

---

## Next Steps

1. ✅ Create this specification document
2. Create `tests/test_phase8_tier5.py` test file
3. Implement 12-15 new indicator functions in `technical.py`
4. Register functions in `_technical_builtin_map()`
5. Run full test suite and validate
6. Create completion documentation

---

**Created**: October 30, 2025  
**Status**: SPECIFICATION COMPLETE - READY FOR IMPLEMENTATION  
**Phase 8 Progress**: 96.5% → Target 97.5-98% with Tier 5  
**Overall Project**: On track for 98% completion by November 6, 2025

