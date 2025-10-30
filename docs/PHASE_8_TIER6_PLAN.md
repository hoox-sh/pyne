# Phase 8 Tier 6: Market Microstructure & Advanced Economics

**Status**: STARTING  
**Date**: October 30, 2025  
**Target Completion**: November 13, 2025  
**Objectives**: Implement 15-20 advanced economic, market structure, and specialized indicators

---

## Overview

After completing Tiers 1-5 with 54 indicators (150+ tests, ~5,500 lines), Phase 8 Tier 6 focuses on:
- **Market microstructure analysis** - Order flow, volume profile, auction theory
- **Economic indicators** - GDP, inflation, employment tied to trading signals
- **Advanced momentum** - Multi-timeframe momentum, adaptive smoothing
- **Behavioral finance** - Sentiment-based indicators, crowd psychology
- **Specialized trading tools** - Volume-weighted metrics, flow-based analysis

**Current Project Status**: 96.5% completion (54/75 Phase 8 functions)  
**Target After Tier 6**: 98-99% completion

---

## Tier 6 Specifications: 15-20 New Indicators

### Group A: Market Microstructure (4 functions)

#### 1. **ta.order_flow_imbalance** - Order Flow Imbalance Indicator
- **Purpose**: Measures buy vs sell pressure through volume distribution
- **Signature**: `ta.order_flow_imbalance(high, low, close, volume, period) → float`
- **Returns**: Signed imbalance ratio (-1.0 to 1.0)
- **Logic**:
  - If close > midpoint (high+low)/2: Mark as buy, accumulate buy_volume
  - If close < midpoint: Mark as sell, accumulate sell_volume
  - imbalance = (buy_vol - sell_vol) / (buy_vol + sell_vol)
- **Use**: Detect momentum without relying on price direction alone

#### 2. **ta.volume_profile_high** - Volume Profile Highest Volume Level
- **Purpose**: Find price level with highest volume concentration
- **Signature**: `ta.volume_profile_high(close, volume, period, levels) → float`
- **Returns**: Price level with highest volume traded at
- **Logic**:
  - Bin prices into levels (default 10-20 buckets)
  - Sum volume at each price level
  - Return price of highest volume bucket
- **Use**: Find point of control, key support/resistance from volume

#### 3. **ta.volume_profile_low** - Volume Profile Lowest Volume Level
- **Purpose**: Find price level with lowest volume (gap area)
- **Signature**: `ta.volume_profile_low(close, volume, period, levels) → float`
- **Returns**: Price level with lowest volume traded at
- **Logic**: Inverse of volume_profile_high
- **Use**: Find volume gaps, areas of low interest

#### 4. **ta.spread_analysis** - Bid-Ask Spread Analysis
- **Purpose**: Analyze liquidity through spread changes
- **Signature**: `ta.spread_analysis(bid, ask, period) → dict`
- **Returns**:
  - `avg_spread`: Average spread over period
  - `spread_percent`: Spread as % of mid
  - `spread_trend`: Increasing/decreasing/stable
- **Use**: Monitor liquidity changes, early market stress indicators

---

### Group B: Advanced Momentum (4 functions)

#### 5. **ta.momentum_divergence** - Multi-Timeframe Momentum Divergence
- **Purpose**: Detect divergences across multiple timeframes
- **Signature**: `ta.momentum_divergence(price, momentum_fast, momentum_slow) → dict`
- **Returns**:
  - `divergence_type`: "bullish" | "bearish" | "none"
  - `strength`: 0-1 divergence strength
  - `bars_since`: How many bars since divergence started
- **Use**: Multi-timeframe trade confirmation

#### 6. **ta.acceleration_factor** - Acceleration/Deceleration of Momentum
- **Purpose**: Measures if momentum is accelerating or decelerating
- **Signature**: `ta.acceleration_factor(momentum_list, period) → float`
- **Returns**: Factor -2.0 to 2.0 (2.0 = max acceleration, -2.0 = max deceleration)
- **Logic**: Change in momentum of momentum
- **Use**: Detect fading vs strengthening trends

#### 7. **ta.mean_reversion_score** - Mean Reversion Probability
- **Purpose**: Probability of price mean reverting to average
- **Signature**: `ta.mean_reversion_score(close, sma, stdev, period) → float`
- **Returns**: 0-100 score (higher = higher probability of reversion)
- **Logic**: Distance from SMA, deviation from normal distribution
- **Use**: Range trading, fade extreme moves

#### 8. **ta.momentum_filter** - Adaptive Momentum Filter
- **Purpose**: Filter noise from momentum indicators
- **Signature**: `ta.momentum_filter(momentum_raw, volume, period) → float`
- **Returns**: Filtered momentum value
- **Logic**: Volume-weighted smoothing with adaptive threshold
- **Use**: Reduce false signals in choppy markets

---

### Group C: Economic Integration (4 functions)

#### 9. **ta.economic_impact_score** - Economic Data Impact on Price
- **Purpose**: Calculate impact of economic calendar data on price
- **Signature**: `ta.economic_impact_score(price_change, volatility, volume_change) → float`
- **Returns**: Impact score 0-100 (higher = more impact)
- **Logic**: Combine price move, volatility spike, and volume spike
- **Use**: Identify economically-driven moves vs noise

#### 10. **ta.inflation_proxy_indicator** - Inflation Indicator (from technicals)
- **Purpose**: Estimate inflation pressure from market behavior
- **Signature**: `ta.inflation_proxy_indicator(usd_index, commodity_prices, bond_yields) → float`
- **Returns**: -100 to 100 inflation pressure score
- **Logic**: USD weakness + rising commodities + rising yields = inflation
- **Use**: Macro-level trading decisions

#### 11. **ta.employment_cycle_indicator** - Employment Cycle from Market Signals
- **Purpose**: Estimate employment cycle strength from market proxies
- **Signature**: `ta.employment_cycle_indicator(cyclical_stocks, defensive_stocks, unemployment_proxy) → str`
- **Returns**: "early_cycle" | "mid_cycle" | "late_cycle" | "recession"
- **Logic**: Compare cyclical vs defensive performance, breadth
- **Use**: Sector rotation and macro timing

#### 12. **ta.gdp_growth_proxy** - GDP Growth Proxy Indicator
- **Purpose**: Estimate GDP growth from technical and volume data
- **Signature**: `ta.gdp_growth_proxy(market_breadth, market_volume, price_momentum) → float`
- **Returns**: -2 to 4 (estimated % GDP growth range)
- **Logic**: Combine breadth, volume, and momentum into economic proxy
- **Use**: Estimate economic health without waiting for official data

---

### Group D: Behavioral Finance (3 functions)

#### 13. **ta.fear_greed_index** - Market Fear/Greed from Technicals
- **Purpose**: Measure market psychology from price and volume action
- **Signature**: `ta.fear_greed_index(rsi, vix_proxy, put_call_ratio, breadth) → float`
- **Returns**: -100 (extreme fear) to 100 (extreme greed)
- **Logic**: Combine RSI, volatility, options data, breadth
- **Use**: Contrarian trading, overbought/oversold extremes

#### 14. **ta.crowd_sentiment** - Crowd Sentiment Detector
- **Purpose**: Detect if crowd consensus is building or fading
- **Signature**: `ta.crowd_sentiment(price_agreement, volume_agreement, time_agreement) → float`
- **Returns**: 0-100 consensus strength
- **Logic**: All indicators pointing same way? Crowd agrees? (0=disagree, 100=strong agreement)
- **Use**: Fade weak consensus, follow strong consensus

#### 15. **ta.contrarian_signal** - Contrarian Trading Signal
- **Purpose**: Identify when crowd is likely wrong (extreme positioning)
- **Signature**: `ta.contrarian_signal(sentiment, volatility, time_since_extreme) → dict`
- **Returns**:
  - `signal`: "strong_contrarian" | "mild_contrarian" | "follow_crowd" | "neutral"
  - `strength`: 0-1
  - `confidence`: 0-1
- **Use**: Contrarian entry points, trade fades

---

### Group E: Volume & Flow Analysis (3-4 functions)

#### 16. **ta.cumulative_delta** - Cumulative Delta (Buy-Sell Volume)
- **Purpose**: Cumulative net of buy vs sell volume
- **Signature**: `ta.cumulative_delta(close, volume, period) → float`
- **Returns**: Cumulative signed volume
- **Logic**: Estimate buy/sell from close position in bar, cumulative sum
- **Use**: Detect accumulation/distribution periods

#### 17. **ta.volume_momentum** - Volume Momentum Indicator
- **Purpose**: Measures if volume is increasing or decreasing trend
- **Signature**: `ta.volume_momentum(volume, period) → float`
- **Returns**: -100 to 100 (negative = declining volume, positive = increasing)
- **Logic**: ROC of volume over period
- **Use**: Confirm trends (strong trends have increasing volume)

#### 18. **ta.smart_money_flow** - Smart Money Flow Estimation
- **Purpose**: Estimate institutional/smart money activity
- **Signature**: `ta.smart_money_flow(price_change, volume, time_since_high, time_since_low) → float`
- **Returns**: Flow intensity -1.0 to 1.0
- **Logic**: Large volume moves + price proximity to extremes = smart money
- **Use**: Follow smart money, trade like institutions

#### 19. **ta.liquidity_score** - Market Liquidity Score
- **Purpose**: Measure how easy/hard it is to trade (liquidity)
- **Signature**: `ta.liquidity_score(volume, volatility, bid_ask_spread, period) → float`
- **Returns**: 0-100 liquidity score (higher = more liquid)
- **Logic**: High volume + low volatility + tight spread = high liquidity
- **Use**: Avoid illiquid periods, time entries better

---

### Group F: Advanced Pattern Recognition (1-2 functions)

#### 20. **ta.volume_thrust** - Volume Thrust Pattern
- **Purpose**: Detects strong volume surge indicating momentum shift
- **Signature**: `ta.volume_thrust(close, volume, volume_sma, sensitivity) → bool`
- **Returns**: true if volume thrust detected
- **Logic**: Volume > (volume_sma * (1 + sensitivity)) AND close move is significant
- **Use**: Confirm breakouts with volume, detect supply/demand shifts

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

### Test File: `tests/test_phase8_tier6.py`

**Test Structure**:
- 3-4 tests per function (50-60 total tests)
- Unit tests with synthetic data
- Integration tests with multiple functions
- Edge case tests (None, empty, boundary values)

**Test Categories**:

1. **Microstructure Tests** (10 tests)
   - Order flow imbalance scenarios
   - Volume profile calculations
   - Spread analysis edge cases

2. **Advanced Momentum Tests** (10 tests)
   - Multi-timeframe divergences
   - Acceleration/deceleration patterns
   - Mean reversion scoring

3. **Economic Integration Tests** (8 tests)
   - Economic impact scoring
   - Inflation/employment proxies
   - GDP estimation

4. **Behavioral Finance Tests** (8 tests)
   - Fear/greed index extremes
   - Crowd sentiment detection
   - Contrarian signals

5. **Volume & Flow Tests** (12 tests)
   - Cumulative delta calculations
   - Volume momentum trends
   - Smart money flow patterns
   - Liquidity scoring

6. **Pattern Recognition Tests** (4 tests)
   - Volume thrust detection
   - Integration with other indicators

7. **Edge Case Tests** (8 tests)
   - Empty inputs
   - None values
   - Single bar scenarios
   - Extreme values

**Expected Coverage**: 55-65 tests total

---

## Code Statistics (Target)

| Metric | Value |
|--------|-------|
| Functions to Implement | 15-20 |
| Estimated Lines of Code | ~1200-1500 |
| Average Lines per Function | ~75-85 |
| Test Methods | 55-65 |
| Docstring Coverage | 100% |
| Expected Pass Rate | 100% |

---

## Integration Points

### With Previous Tiers
- Use Tier 1-4 indicators (EMA, RSI, MACD, ATR, etc.)
- Build on Tier 5 market condition indicators
- Maintain backward compatibility

### Builtin Map Updates
- Add ~15-20 new entries to `_technical_builtin_map()`
- Total TA functions: 107+ → 122-127
- Maintain alphabetical organization

### No Breaking Changes
- All existing tests continue to pass
- No modifications to previous function signatures
- Pure additions to capability

---

## Success Criteria

1. ✅ 15-20 new indicators implemented
2. ✅ 55-65 passing tests
3. ✅ Zero regressions (all 815+ existing tests pass)
4. ✅ 100% docstring coverage
5. ✅ Comprehensive parameter validation
6. ✅ Full round-trip parsing stability
7. ✅ Integration with Tier 1-5 functions

---

## Project Completion Path

| Phase | Functions | Tests | Completion | Status |
|-------|-----------|-------|-----------|--------|
| Phases 1-7 | 56 | 670 | 92% | ✅ COMPLETE |
| Phase 8 Tier 1 | 9 | 31 | 92.5% | ✅ COMPLETE |
| Phase 8 Tier 2 | 15 | 16 | 93.5% | ✅ COMPLETE |
| Phase 8 Tier 3 | 10 | 20 | 94.8% | ✅ COMPLETE |
| Phase 8 Tier 4 | 5 | 28 | 96.5% | ✅ COMPLETE |
| Phase 8 Tier 5 | 12-15 | 50-55 | 97-98% | 🔄 IN PROGRESS |
| **Phase 8 Tier 6** | **15-20** | **55-65** | **98-99%** | 🟡 STARTING |
| **TOTAL** | **122-127** | **870-880** | **98-99%** | **🟡 IN PROGRESS** |

---

## Timeline

- **Start**: October 30, 2025, 3:00 PM
- **Implementation**: October 30 - November 6 (3-4 days)
- **Testing & Validation**: November 6-9
- **Documentation**: November 9-11
- **Final Review**: November 11-13
- **Target Completion**: November 13, 2025

---

## Next Steps

1. ✅ Create this specification document
2. Create `tests/test_phase8_tier6.py` test file
3. Implement 15-20 new indicator functions in `technical.py`
4. Register functions in `_technical_builtin_map()`
5. Run full test suite and validate
6. Create completion documentation

---

**Created**: October 30, 2025  
**Status**: SPECIFICATION COMPLETE - READY FOR IMPLEMENTATION  
**Phase 8 Progress**: 96.5% → Target 98-99% with Tier 6  
**Overall Project**: On track for 99% completion by November 13, 2025

