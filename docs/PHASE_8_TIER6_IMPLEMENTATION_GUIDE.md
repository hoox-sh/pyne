# Phase 8 Tier 6 - Implementation Guide

**Status**: Ready for Implementation  
**Date**: October 30, 2025  
**Target**: Add 20 new indicators to NodeLiteralEvaluator

---

## Implementation Location

**File**: `/src/pynescript/ast/evaluator/builtins/technical.py`

This file contains:
- `TechnicalAnalysisMixin` class
- `_technical_builtin_map()` dictionary mapping function names to handlers
- 100+ technical indicator functions (phases 1-5)
- Current total: ~3516 lines

---

## Implementation Tasks

### Task 1: Update `_technical_builtin_map()` Dictionary

**Location**: Lines 22-120 (approximately)

Add these 20 entries in **alphabetical order** within the dictionary:

```python
# Phase 8 Tier 6: Market Microstructure & Advanced Economics
"ta.acceleration_factor": self._builtin_ta_acceleration_factor,
"ta.contrarian_signal": self._builtin_ta_contrarian_signal,
"ta.crowd_sentiment": self._builtin_ta_crowd_sentiment,
"ta.cumulative_delta": self._builtin_ta_cumulative_delta,
"ta.economic_impact_score": self._builtin_ta_economic_impact_score,
"ta.employment_cycle_indicator": self._builtin_ta_employment_cycle_indicator,
"ta.fear_greed_index": self._builtin_ta_fear_greed_index,
"ta.gdp_growth_proxy": self._builtin_ta_gdp_growth_proxy,
"ta.inflation_proxy_indicator": self._builtin_ta_inflation_proxy_indicator,
"ta.liquidity_score": self._builtin_ta_liquidity_score,
"ta.mean_reversion_score": self._builtin_ta_mean_reversion_score,
"ta.momentum_divergence": self._builtin_ta_momentum_divergence,
"ta.momentum_filter": self._builtin_ta_momentum_filter,
"ta.order_flow_imbalance": self._builtin_ta_order_flow_imbalance,
"ta.smart_money_flow": self._builtin_ta_smart_money_flow,
"ta.spread_analysis": self._builtin_ta_spread_analysis,
"ta.volume_momentum": self._builtin_ta_volume_momentum,
"ta.volume_profile_high": self._builtin_ta_volume_profile_high,
"ta.volume_profile_low": self._builtin_ta_volume_profile_low,
"ta.volume_thrust": self._builtin_ta_volume_thrust,
```

---

## Implementation Patterns

### Simple Functions (No Collections)

```python
def _builtin_ta_volume_momentum(self, args: list[Any]) -> float:
    """Volume Momentum - Measures rate of change of volume.
    
    ta.volume_momentum(volume, period)
    
    Parameters:
        volume: List of volume values
        period: Number of periods for momentum calculation
    
    Returns:
        float: Momentum value (-100 to 100)
    
    Edge Cases:
        - Empty or insufficient data returns 0.0
        - Very small volumes handled with epsilon checks
    """
    msg = "ta.volume_momentum() requires 2 arguments"
    if len(args) < 2 or len(args) > 2:
        self._error(msg)
    
    volume = self._expect_list(args[0], msg)
    period = self._expect_int(args[1], msg)
    
    if len(volume) < period + 1 or period <= 0:
        return 0.0
    
    # Filter None and non-numeric values
    volume = [v for v in volume if isinstance(v, (int, float))]
    if len(volume) < period + 1:
        return 0.0
    
    # Calculate rate of change
    old_vol = sum(volume[-period-1:-1]) / period if len(volume) > period else 1.0
    new_vol = sum(volume[-period:]) / period
    
    if old_vol == 0:
        return 0.0
    
    momentum = ((new_vol - old_vol) / old_vol) * 100.0
    return max(-100.0, min(100.0, momentum))
```

### Dictionary-Returning Functions

```python
def _builtin_ta_spread_analysis(self, args: list[Any]) -> dict[str, Any]:
    """Spread Analysis - Bid-ask spread tracking.
    
    ta.spread_analysis(bid, ask, period)
    
    Returns:
        dict: {
            'avg_spread': float,
            'spread_percent': float,
            'spread_trend': str ('stable' | 'increasing' | 'decreasing')
        }
    """
    msg = "ta.spread_analysis() requires 3 arguments"
    if len(args) < 3 or len(args) > 3:
        self._error(msg)
    
    bid = self._expect_list(args[0], msg)
    ask = self._expect_list(args[1], msg)
    period = self._expect_int(args[2], msg)
    
    if len(bid) < period or len(ask) < period or period <= 0:
        return {"avg_spread": 0.0, "spread_percent": 0.0, "spread_trend": "stable"}
    
    # Calculate spreads for last period bars
    spreads = []
    for i in range(-period, 0):
        b = bid[i] if isinstance(bid[i], (int, float)) else 0
        a = ask[i] if isinstance(ask[i], (int, float)) else 0
        if a > b > 0:
            spreads.append(a - b)
    
    if not spreads:
        return {"avg_spread": 0.0, "spread_percent": 0.0, "spread_trend": "stable"}
    
    avg_spread = sum(spreads) / len(spreads)
    mid_price = (ask[-1] + bid[-1]) / 2 if isinstance(ask[-1], (int, float)) and isinstance(bid[-1], (int, float)) else 100.0
    spread_percent = (avg_spread / mid_price * 100) if mid_price > 0 else 0.0
    
    # Determine trend
    if len(spreads) >= 2:
        if spreads[-1] > spreads[0] * 1.1:
            trend = "increasing"
        elif spreads[-1] < spreads[0] * 0.9:
            trend = "decreasing"
        else:
            trend = "stable"
    else:
        trend = "stable"
    
    return {
        "avg_spread": avg_spread,
        "spread_percent": spread_percent,
        "spread_trend": trend
    }
```

---

## Implementation Order

**Recommended order by complexity (simple → complex)**:

1. **Simple numeric outputs** (0-2 hours each):
   - `ta.volume_momentum`
   - `ta.economic_impact_score`
   - `ta.acceleration_factor`
   - `ta.cumulative_delta`

2. **Medium complexity** (2-3 hours each):
   - `ta.momentum_filter`
   - `ta.mean_reversion_score`
   - `ta.momentum_divergence`
   - `ta.smart_money_flow`
   - `ta.liquidity_score`

3. **Dictionary returns** (2-3 hours each):
   - `ta.spread_analysis`
   - `ta.contrarian_signal`

4. **Complex calculations** (3-4 hours each):
   - `ta.order_flow_imbalance`
   - `ta.volume_profile_high`
   - `ta.volume_profile_low`
   - `ta.inflation_proxy_indicator`
   - `ta.employment_cycle_indicator`
   - `ta.gdp_growth_proxy`
   - `ta.fear_greed_index`
   - `ta.crowd_sentiment`
   - `ta.volume_thrust`

---

## Validation Requirements

### For Every Function

1. **Parameter validation**:
   - Check argument count
   - Use `_expect_list()`, `_expect_int()`, `_expect_float()` utilities
   - Return None or default on invalid input

2. **Edge cases**:
   - Empty lists: return 0.0 or None
   - Single bar: handle gracefully
   - None values in lists: filter them out
   - Division by zero: use epsilon checks
   - Extreme values: clamp to reasonable ranges

3. **Documentation**:
   - Full docstring with ta.function_name
   - Parameter descriptions
   - Return value documentation
   - Edge case notes

4. **Testing readiness**:
   - Function should match test expectations
   - 72 tests in test_phase8_tier6.py
   - All return types should match test assertions

---

## Reference Helper Methods

**Available in BuiltinHandler base class**:

```python
# List handling
self._expect_list(value, msg)      # Returns list or errors

# Type conversion
self._expect_int(value, msg)       # Returns int or errors
self._expect_float(value, msg)     # Returns float or errors
self._expect_bool(value, msg)      # Returns bool or errors

# Error reporting
self._error(message)               # Raises error with message

# Statistical operations
sum(), min(), max()                # Python built-ins
statistics.mean(), statistics.stdev()  # Available imports
math.sqrt(), math.log(), etc.     # Math functions
```

---

## Phase 8 Tier 6 Function Details

### Group A: Market Microstructure

**1. ta.order_flow_imbalance(high, low, close, volume, period) → float**
- Detect buy/sell pressure through volume distribution
- if close > (high+low)/2: buy; else: sell
- Return: (buy_vol - sell_vol) / (buy_vol + sell_vol)
- Range: -1.0 to 1.0

**2. ta.volume_profile_high(close, volume, period, levels) → float**
- Find price level with highest volume
- Bin prices into (levels) buckets
- Return: Price of highest volume bucket

**3. ta.volume_profile_low(close, volume, period, levels) → float**
- Find price level with lowest volume
- Opposite of volume_profile_high
- Return: Price of lowest volume bucket

**4. ta.spread_analysis(bid, ask, period) → dict**
- Track bid-ask spread changes
- Return dict with avg_spread, spread_percent, spread_trend

### Group B: Advanced Momentum

**5. ta.momentum_divergence(price, momentum_fast, momentum_slow) → dict**
- Detect divergences across timeframes
- Return dict with divergence_type, strength, bars_since

**6. ta.acceleration_factor(momentum_list, period) → float**
- Measure momentum acceleration/deceleration
- Calculate change in momentum
- Range: -2.0 to 2.0

**7. ta.mean_reversion_score(close, sma, stdev, period) → float**
- Probability of price reverting to mean
- Distance from SMA, deviation from normal distribution
- Range: 0-100

**8. ta.momentum_filter(momentum_raw, volume, period) → float**
- Filter noise from momentum
- Volume-weighted smoothing
- Adaptive threshold

### Group C: Economic Integration

**9. ta.economic_impact_score(price_change, volatility, volume_change) → float**
- Impact score for economic data events
- Range: 0-100

**10. ta.inflation_proxy_indicator(usd_index, commodity_prices, bond_yields) → float**
- Estimate inflation from technicals
- Range: -100 to 100

**11. ta.employment_cycle_indicator(cyclical_stocks, defensive_stocks, unemployment_proxy) → str**
- Estimate employment cycle
- Returns: "early_cycle" | "mid_cycle" | "late_cycle" | "recession"

**12. ta.gdp_growth_proxy(market_breadth, market_volume, price_momentum) → float**
- Estimate GDP growth from market signals
- Range: -2 to 4

### Group D: Behavioral Finance

**13. ta.fear_greed_index(rsi, vix_proxy, put_call_ratio, breadth) → float**
- Market psychology measurement
- Range: -100 (fear) to 100 (greed)

**14. ta.crowd_sentiment(price_agreement, volume_agreement, time_agreement) → float**
- Crowd consensus strength
- Range: 0-100

**15. ta.contrarian_signal(sentiment, volatility, time_since_extreme) → dict**
- Contrarian trading signals
- Return dict with signal, strength, confidence

### Group E: Volume & Flow Analysis

**16. ta.cumulative_delta(close, volume, period) → float**
- Cumulative buy-sell volume
- Sum of signed volumes

**17. ta.volume_momentum(volume, period) → float**
- Rate of change of volume
- Range: -100 to 100

**18. ta.smart_money_flow(price_change, volume, time_since_high, time_since_low) → float**
- Institutional money flow estimation
- Range: -1.0 to 1.0

**19. ta.liquidity_score(volume, volatility, bid_ask_spread, period) → float**
- Market liquidity measurement
- Range: 0-100

### Group F: Advanced Patterns

**20. ta.volume_thrust(close, volume, volume_sma, sensitivity) → bool**
- Volume surge pattern detection
- true if volume > (volume_sma * (1 + sensitivity)) AND price moves

---

## Testing Integration

All 72 tests in `test_phase8_tier6.py` should pass:

```bash
# Run only Tier 6 tests
pytest tests/test_phase8_tier6.py -v

# Run with coverage
pytest tests/test_phase8_tier6.py --cov=pynescript.ast.evaluator --cov-report=html

# Run all tests (verify no regressions)
pytest tests/ -v
```

---

## Completion Checklist

- [ ] All 20 functions implemented
- [ ] All functions added to `_technical_builtin_map()`
- [ ] 72/72 tests passing
- [ ] No regressions in existing 815+ tests
- [ ] All docstrings complete
- [ ] Parameter validation on all functions
- [ ] Edge cases handled
- [ ] Implementation documentation created
- [ ] Integration tests passing

---

## Timeline

- **Implementation**: 4-6 hours estimated
- **Testing**: 1-2 hours estimated
- **Documentation**: 1 hour estimated
- **Total**: 6-9 hours to completion

