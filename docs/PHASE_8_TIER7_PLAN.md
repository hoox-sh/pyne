# Copyright 2024-2025 Yunseong Hwang, jango_blockchained
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

# Phase 8 Tier 7: Advanced Trading Strategies & Market Timing

**Status**: Planning Phase  
**Version**: 1.0  
**Date**: October 30, 2025  
**Target Completion**: November 13, 2025  
**Estimated Functions**: 14-16 advanced strategy indicators  
**Testing Strategy**: 56-64 comprehensive tests across 16+ test classes

## Overview

Phase 8 Tier 7 implements the final tier of Pine Script v6 technical analysis support, focusing on advanced multi-indicator trading strategies and sophisticated market timing techniques. These indicators synthesize lower-level technical analysis to produce high-level trading signals and strategic recommendations.

**Expected Project Completion After Tier 7**: 98-99%

## Strategic Objectives

1. **Strategy Synthesis**: Combine multiple indicators into unified trading strategies
2. **Market Timing**: Identify optimal entry/exit points using advanced algorithms
3. **Risk Assessment**: Quantify risk/reward and position sizing
4. **Trend Confirmation**: Multi-timeframe and multi-indicator validation
5. **Regime Detection**: Identify market conditions and adapt strategies

## 16 Planned Indicators

### Group A: Multi-Indicator Strategies (4 functions)

#### 1. `ta.trend_confirmation_score()`
**Purpose**: Validates trend strength using multiple indicators simultaneously

```
Signature: ta.trend_confirmation_score(price_momentum, volume_trend, volatility, rsi, macd_strength, ema_slope)
Parameters:
  - price_momentum: float (-100 to 100) - Price rate of change
  - volume_trend: float (-1 to 1) - Volume direction
  - volatility: float (0 to 10) - Market volatility
  - rsi: float (0 to 100) - RSI value
  - macd_strength: float (-1 to 1) - MACD momentum
  - ema_slope: float (-180 to 180) - EMA angle in degrees

Returns: float (0-100) - Trend confirmation strength
  0-25: Weak/no confirmation
  25-50: Mild confirmation
  50-75: Strong confirmation
  75-100: Very strong confirmation

Logic:
- RSI 30-70 range (neutral) reduces score
- RSI <30 or >70 (extreme) boosts score if aligned with momentum
- Volume trend alignment adds 20% to score
- Volatility extremes add 10% (indicates decision making)
- MACD and EMA must align with price momentum for full score
- Returns weighted average of all factors

Use Cases:
- Entry signal confirmation
- Trend strength validation
- Multi-timeframe alignment checking
- High-confidence trade filtering
```

#### 2. `ta.market_structure_pivot()`
**Purpose**: Identifies key support/resistance based on market structure

```
Signature: ta.market_structure_pivot(high_list, low_list, close_list, period, structure_type)
Parameters:
  - high_list: list[float] - Historical highs
  - low_list: list[float] - Historical lows
  - close_list: list[float] - Historical closes
  - period: int (5-50) - Lookback period
  - structure_type: int (0=fractal, 1=swing, 2=block) - Structure detection method

Returns: dict with keys:
  - pivot_price: float - Key pivot level
  - support: float - Calculated support level
  - resistance: float - Calculated resistance level
  - structure: str - "fractal" | "swing" | "block"
  - strength: float (0-100) - Pivot strength (number of touches)

Logic:
- Fractal: Local high/low surrounded by lower/higher bars
- Swing: Higher highs with lower lows (uptrend) or lower lows with higher highs (downtrend)
- Block: Consolidation areas with price stuck in range
- Strength increases with each touch of the level
- Returns current market structure classification

Use Cases:
- Natural support/resistance levels
- Breakout identification
- Range-bound vs trending detection
- Institutional order placement
```

#### 3. `ta.volatility_regime_score()`
**Purpose**: Classifies volatility regime and market conditions

```
Signature: ta.volatility_regime_score(atr, historical_vol, vix_proxy, volume_profile)
Parameters:
  - atr: list[float] - Average true range values
  - historical_vol: list[float] - Historical volatility values
  - vix_proxy: list[float] - VIX or implied volatility proxy
  - volume_profile: float (0-100) - Volume concentration level

Returns: dict with keys:
  - regime: str - "low" | "normal" | "high" | "extreme"
  - volatility_score: float (0-100) - Current volatility percentile
  - regime_probability: float (0-1) - Confidence in regime classification
  - momentum: str - "accelerating" | "stable" | "decelerating"

Logic:
- Low: ATR < 33rd percentile, VIX <15, volume spread
- Normal: ATR in 33-67th percentile, normal activity
- High: ATR > 67th percentile, concentrated volume
- Extreme: ATR > 90th percentile, VIX >25, or volume spike
- Momentum detected by comparing current to previous ATR/vol readings

Use Cases:
- Strategy adaptation by regime
- Position sizing based on volatility
- Stop-loss placement
- Mean reversion vs breakout selection
```

#### 4. `ta.correlation_filter()`
**Purpose**: Cross-correlates multiple indicators to filter false signals

```
Signature: ta.correlation_filter(signal1_list, signal2_list, signal3_list, period, threshold)
Parameters:
  - signal1_list: list[float] - Primary signal series
  - signal2_list: list[float] - Confirmation signal series
  - signal3_list: list[float] - Secondary confirmation series
  - period: int (5-50) - Correlation lookback period
  - threshold: float (0-1) - Correlation strength threshold

Returns: dict with keys:
  - is_correlated: bool - All signals correlated above threshold
  - correlation_strength: float (0-1) - Average correlation coefficient
  - signal_agreement: float (0-100) - Percentage of signal alignment
  - divergence_count: int - Number of signal divergences in period

Logic:
- Calculate Pearson correlation between all signal pairs
- Signal agreement: % of bars where all 3 signals have same direction
- Divergence count: bars where signals conflict
- Returns true only if min(correlation) > threshold
- Useful for filtering out noise and low-conviction signals

Use Cases:
- Multi-indicator confirmation
- False signal elimination
- Signal strength validation
- Consensus building
```

### Group B: Advanced Trend & Breakout (4 functions)

#### 5. `ta.advanced_breakout_detector()`
**Purpose**: Detects true breakouts vs fake-outs using pattern analysis

```
Signature: ta.advanced_breakout_detector(price_list, volume_list, resistance, lookback, sensitivity)
Parameters:
  - price_list: list[float] - Price series
  - volume_list: list[float] - Volume series
  - resistance: float - Resistance level to break
  - lookback: int (10-50) - Historical context period
  - sensitivity: float (0-1) - Breakout sensitivity (lower = stricter)

Returns: dict with keys:
  - breakout_detected: bool - True breakout vs fake-out
  - breakout_strength: float (0-100) - Breakout power
  - breakout_type: str - "gap" | "close_above" | "volume_break"
  - pullback_probability: float (0-1) - Likelihood of pullback

Logic:
- Gap breakout: Opens above resistance
- Close breakout: Closes above resistance on volume
- Volume breakout: Breakout on >150% average volume
- Strength: (price_above_resistance / resistance_distance) * volume_ratio
- Fake-out: If pullback below resistance within 2 bars
- Pullback probability: Historical rate of pullbacks post-breakout

Use Cases:
- Entry timing for breakout strategies
- True breakout identification
- Fake-out avoidance
- Trend acceleration confirmation
```

#### 6. `ta.pullback_bounce_level()`
**Purpose**: Finds optimal pullback/bounce levels within trends

```
Signature: ta.pullback_bounce_level(high_list, low_list, close_list, trend_direction, period)
Parameters:
  - high_list: list[float] - Historical highs
  - low_list: list[float] - Historical lows
  - close_list: list[float] - Historical closes
  - trend_direction: int (1=up, -1=down) - Current trend direction
  - period: int (10-50) - Trend analysis period

Returns: dict with keys:
  - primary_level: float - Most likely pullback level (Fibonacci)
  - secondary_level: float - Alternative pullback level
  - bounce_probability: float (0-1) - Likelihood of bounce
  - support_strength: float (0-100) - Support level strength

Logic:
- Uptrend: Calculate Fibonacci retracements (23.6%, 38.2%, 50%, 61.8%)
- Downtrend: Mirror logic for upside bounces
- Strength based on historical level touches and volume profile
- Returns most probable based on historical behavior
- Bounce probability based on trend strength and volatility

Use Cases:
- Entry on pullbacks
- Stop-loss placement
- Risk/reward calculation
- Trend-following optimization
```

#### 7. `ta.multi_timeframe_signal()`
**Purpose**: Combines signals from multiple timeframe periods

```
Signature: ta.multi_timeframe_signal(signal_1h, signal_4h, signal_1d, weight_1h, weight_4h, weight_1d)
Parameters:
  - signal_1h: int (-1 to 1) - 1-hour timeframe signal
  - signal_4h: int (-1 to 1) - 4-hour timeframe signal
  - signal_1d: int (-1 to 1) - Daily timeframe signal
  - weight_1h: float (0-1) - Weight for 1h signal
  - weight_4h: float (0-1) - Weight for 4h signal
  - weight_1d: float (0-1) - Weight for daily signal

Returns: dict with keys:
  - combined_signal: float (-1 to 1) - Weighted signal
  - signal_agreement: int (0-3) - Number of aligned timeframes
  - alignment_quality: float (0-100) - Signal harmony metric

Logic:
- Normalize weights to sum to 1.0
- Calculate weighted average of signals
- Signal agreement: count of signals with same direction as combined
- Alignment quality: 100 * (agreement / 3)
- Higher weight to longer timeframes for bias

Use Cases:
- Multi-timeframe trading
- Signal strength validation
- Conflicting timeframe resolution
- Risk assessment across timeframes
```

#### 8. `ta.position_sizing_score()`
**Purpose**: Calculates optimal position size based on market conditions

```
Signature: ta.position_sizing_score(account_risk_percent, volatility, risk_reward, correlation)
Parameters:
  - account_risk_percent: float (0.1-5) - Risk per trade as % of account
  - volatility: float (0-100) - Market volatility percentile
  - risk_reward: float (0.1-5) - Expected risk/reward ratio
  - correlation: float (0-1) - Correlation to existing positions

Returns: dict with keys:
  - position_size_ratio: float (0-1) - Position size as fraction of risk amount
  - kelly_fraction: float (0-0.5) - Kelly criterion position sizing
  - volatility_adjustment: float (0-2) - Size multiplier based on volatility
  - correlation_adjustment: float (0-1) - Reduction for correlated positions

Logic:
- Base: risk_reward adjusted sizing (higher reward = larger position)
- Kelly criterion: f = (p*b - q) / b (for expected win rate)
- Volatility: Reduce size in high volatility (multiply by vol_adjustment)
- Correlation: Reduce size if adding to correlated positions
- Final size: base * volatility_adj * correlation_adj

Use Cases:
- Risk management
- Position sizing optimization
- Portfolio construction
- Kelly criterion implementation
```

### Group C: Advanced Entry/Exit (4 functions)

#### 9. `ta.optimal_entry_zone()`
**Purpose**: Identifies optimal entry price zone with confluence

```
Signature: ta.optimal_entry_zone(support_level, fibonacci_level, volume_profile, vwap)
Parameters:
  - support_level: float - Technical support level
  - fibonacci_level: float - Fibonacci retracement level
  - volume_profile: float - Volume-weighted price level
  - vwap: float - Volume-weighted average price

Returns: dict with keys:
  - entry_zone_low: float - Lower bound of entry zone
  - entry_zone_high: float - Upper bound of entry zone
  - zone_strength: float (0-100) - Zone confidence (confluence factor)
  - best_entry: float - Single optimal entry price

Logic:
- Zone strength increases with each confluence point:
  - Support level: +25%
  - Fibonacci level: +25%
  - Volume profile match: +25%
  - VWAP proximity: +25%
- Entry zone: ±0.5% of confluence point
- Best entry: Lowest point in zone (conservative) or midpoint (balanced)

Use Cases:
- Entry placement optimization
- Confluence identification
- Zone-based trading
- Risk/reward calculation base
```

#### 10. `ta.trailing_exit_level()`
**Purpose**: Dynamically calculates trailing exit levels protecting profits

```
Signature: ta.trailing_exit_level(entry_price, current_price, volatility, atr, trail_distance)
Parameters:
  - entry_price: float - Trade entry price
  - current_price: float - Current price
  - volatility: float (0-100) - Current volatility level
  - atr: float - Current ATR value
  - trail_distance: float (0.5-3) - Trailing distance multiplier

Returns: dict with keys:
  - trail_stop: float - Current trailing stop level
  - stop_distance: float - Distance from current price
  - protected_profit: float - Locked-in profit amount
  - risk_reward_current: float - Current trade risk/reward

Logic:
- Base trail: entry_price + profit_amount - (volatility_adjusted * atr * trail_distance)
- Adjustment: Higher volatility = wider trail to avoid whipsaws
- Protected profit: Current profit - max drawdown that triggers stop
- Triggers tightens as profit increases (accelerating trail)
- Moves only upward (never trails down)

Use Cases:
- Profit protection
- Dynamic stop-loss management
- Trailing stop implementation
- Risk management
```

#### 11. `ta.mean_reversion_entry()`
**Purpose**: Identifies mean reversion trade opportunities

```
Signature: ta.mean_reversion_entry(price, mean_level, standard_deviation, period, z_score_threshold)
Parameters:
  - price: float - Current price
  - mean_level: float - Mean price level
  - standard_deviation: float - Standard deviation of price
  - period: int (10-50) - Statistical period
  - z_score_threshold: float (2-3) - Z-score trigger (2=95%, 3=99.7% confidence)

Returns: dict with keys:
  - z_score: float - Current z-score
  - is_mean_reversion_setup: bool - Valid mean reversion setup
  - reversion_probability: float (0-1) - Probability of reversion
  - target_price: float - Expected mean reversion target

Logic:
- Z-score = (price - mean) / stdev
- Setup valid if: abs(z-score) > threshold AND price near extreme
- Probability: confidence level of z-score (95% or 99.7%)
- Target: mean_level + (stdev * sign(z_score) / 2) = midpoint to mean

Use Cases:
- Mean reversion trade identification
- Overbought/oversold detection
- Statistical arbitrage
- Range-bound trading
```

#### 12. `ta.breakeven_level()`
**Purpose**: Calculates break-even levels accounting for slippage and fees

```
Signature: ta.breakeven_level(entry_price, position_size, slippage_percent, fee_percent, direction)
Parameters:
  - entry_price: float - Trade entry price
  - position_size: float - Position size in units
  - slippage_percent: float (0.01-1) - Expected slippage as %
  - fee_percent: float (0.01-0.5) - Trading fees as % of trade
  - direction: int (1=long, -1=short) - Trade direction

Returns: dict with keys:
  - breakeven_price: float - Price needed to break even
  - total_cost: float - Total trade cost including fees and slippage
  - move_required: float - Price move required in ticks
  - move_required_percent: float - Price move required as %

Logic:
- Total fees/slippage: position_size * entry_price * (fee% + slippage%)
- Long: breakeven = entry + (total_cost / position_size)
- Short: breakeven = entry - (total_cost / position_size)
- Move required: abs(breakeven - entry)
- Percent: (move_required / entry) * 100

Use Cases:
- Trade management
- Entry quality validation
- Risk awareness
- Profit target setting
```

### Group D: Risk & Regime (2 functions)

#### 13. `ta.drawdown_recovery_level()`
**Purpose**: Calculates expected recovery after drawdown

```
Signature: ta.drawdown_recovery_level(peak_price, current_price, recovery_percentile, lookback)
Parameters:
  - peak_price: float - Previous peak price
  - current_price: float - Current price
  - recovery_percentile: float (0.5-2) - Recovery expectation multiplier
  - lookback: int (20-100) - Historical lookback period

Returns: dict with keys:
  - drawdown_percent: float - Current drawdown %
  - expected_recovery_level: float - Expected recovery price
  - recovery_timeframe: int - Estimated bars to recovery
  - recovery_confidence: float (0-1) - Confidence in recovery

Logic:
- Drawdown% = ((peak - current) / peak) * 100
- Recovery level: current + (peak - current) * recovery_percentile
- Timeframe: Historical average time from similar drawdowns
- Confidence: Based on recovery success rate at this drawdown %

Use Cases:
- Loss recovery planning
- Patience in drawdowns
- Trend continuity assessment
- Position holding decisions
```

#### 14. `ta.risk_reward_asymmetry()`
**Purpose**: Analyzes risk/reward asymmetry in current market setup

```
Signature: ta.risk_reward_asymmetry(entry_price, stop_price, target_price, entry_probability)
Parameters:
  - entry_price: float - Proposed entry price
  - stop_price: float - Stop-loss price
  - target_price: float - Profit target price
  - entry_probability: float (0-1) - Probability of reaching target (0-1)

Returns: dict with keys:
  - risk_per_contract: float - Absolute risk per contract
  - reward_per_contract: float - Absolute reward per contract
  - risk_reward_ratio: float - Reward/Risk ratio
  - expected_value: float - Expected value per contract
  - kelly_percentage: float - Kelly criterion position % 

Logic:
- Risk = abs(entry - stop)
- Reward = abs(target - entry)
- Ratio = reward / risk
- Expected value = (prob_win * reward) - (prob_loss * risk)
- Kelly% = (win_rate * reward - loss_rate * risk) / reward

Use Cases:
- Trade idea evaluation
- Entry rejection/acceptance
- Position sizing
- Portfolio optimization
```

### Group E: Market Timing & Regime (2 functions)

#### 15. `ta.market_timing_index()`
**Purpose**: Comprehensive market timing indicator combining multiple factors

```
Signature: ta.market_timing_index(trend_score, volatility_score, volume_score, sentiment_score)
Parameters:
  - trend_score: float (0-100) - Trend strength
  - volatility_score: float (0-100) - Volatility level
  - volume_score: float (0-100) - Volume participation
  - sentiment_score: float (-100 to 100) - Market sentiment

Returns: dict with keys:
  - timing_index: float (-100 to 100) - Overall market timing score
  - market_condition: str - "optimal_long" | "favorable_long" | "neutral" | "favorable_short" | "optimal_short"
  - confidence: float (0-1) - Timing confidence
  - recommendation: str - "strong_buy" | "buy" | "hold" | "sell" | "strong_sell"

Logic:
- Composite: 30% trend + 20% volatility + 20% volume + 30% sentiment
- Optimal: trend>75 & vol<40 & volume>50 & sentiment aligned
- Favorable: trend>50 & vol<60 & volume>40
- Neutral: No clear direction
- Confidence: Min of individual component confidences

Use Cases:
- Portfolio timing
- Cash/invested ratio adjustment
- Strategy selection (trend vs mean-reversion)
- Market state classification
```

#### 16. `ta.regime_adaptive_signal()`
**Purpose**: Adapts trading signals based on current market regime

```
Signature: ta.regime_adaptive_signal(raw_signal, volatility_regime, trend_regime, regime_duration)
Parameters:
  - raw_signal: float (-1 to 1) - Original trading signal
  - volatility_regime: str - "low" | "normal" | "high" | "extreme"
  - trend_regime: str - "trending_up" | "ranging" | "trending_down"
  - regime_duration: int - Bars in current regime

Returns: dict with keys:
  - adapted_signal: float (-1 to 1) - Adjusted signal for regime
  - signal_confidence: float (0-1) - Confidence of adapted signal
  - regime_fit: float (0-1) - How well signal fits current regime
  - strategy_recommendation: str - Recommended strategy for regime

Logic:
- Trending regime: Favor trend-following signals
- Ranging regime: Favor mean-reversion signals
- High volatility: Reduce signal strength, favor wider stops
- Low volatility: Increase signal strength, tighter stops
- Regime duration: Longer duration = stronger signal if persistent
- Regime fit: Scoring system for signal type vs regime match

Use Cases:
- Strategy adaptation
- Signal filtering by regime
- Entry condition adjustment
- Stop-loss placement
```

## Testing Strategy

### 56+ Unit Tests Organized by Group

**Group A: Multi-Indicator Strategies (16 tests)**
- Trend confirmation: Weak/mild/strong/extreme scenarios
- Market structure pivots: Fractal/swing/block detection
- Volatility regimes: Low/normal/high/extreme classification
- Correlation filtering: Single/dual/triple signal validation

**Group B: Trend & Breakout (16 tests)**
- Breakout detection: Gap/close/volume breakouts
- Pullback levels: Fibonacci retracement validation
- Multi-timeframe: Single/dual/triple timeframe agreement
- Position sizing: Risk-based, Kelly criterion, volatility adjustment

**Group C: Entry/Exit (16 tests)**
- Entry zones: Low/medium/high confluence
- Trailing exits: Stop tightening, profit protection
- Mean reversion: Z-score extremes, reversion probability
- Breakeven levels: Slippage and fee calculations

**Group D: Risk & Regime (8 tests)**
- Drawdown recovery: Expectation and confidence
- Risk/reward analysis: Asymmetry evaluation, Kelly sizing

**Group E: Timing & Regime (8 tests)**
- Market timing: Index and recommendation generation
- Regime adaptation: Signal transformation by regime

**Edge Cases & Integration (8 tests)**
- Edge case handling: Empty inputs, single values, extremes
- Integration tests: Multi-indicator combinations
- Real scenario simulations: Complete trading workflows

## Implementation Guidelines

### Code Pattern Example

```python
def _builtin_ta_market_timing_index(self, args: list[Any]) -> dict[str, Any]:
    """Market Timing Index - Comprehensive market timing indicator.
    
    ta.market_timing_index(trend_score, volatility_score, volume_score, sentiment_score)
    
    Returns: dict with timing_index, market_condition, confidence, recommendation
    """
    msg = "ta.market_timing_index() requires 4 arguments"
    if len(args) < 4:
        self._error(msg)
    
    # Extract and validate parameters
    trend = args[0] if isinstance(args[0], (int, float)) else 50.0
    volatility = args[1] if isinstance(args[1], (int, float)) else 50.0
    volume = args[2] if isinstance(args[2], (int, float)) else 50.0
    sentiment = args[3] if isinstance(args[3], (int, float)) else 0.0
    
    # Clamp to valid ranges
    trend = max(0.0, min(100.0, trend))
    volatility = max(0.0, min(100.0, volatility))
    volume = max(0.0, min(100.0, volume))
    sentiment = max(-100.0, min(100.0, sentiment))
    
    # Composite calculation
    timing_index = (trend * 0.30 + (100 - volatility) * 0.20 + 
                   volume * 0.20 + (sentiment + 100) / 2 * 0.30)
    
    # Determine market condition and recommendation
    if trend > 75 and volatility < 40 and volume > 50:
        if sentiment > 50:
            condition = "optimal_long"
            recommendation = "strong_buy"
            confidence = 0.9
        else:
            condition = "favorable_long"
            recommendation = "buy"
            confidence = 0.75
    elif trend < 25 and volatility < 40 and volume > 50:
        if sentiment < -50:
            condition = "optimal_short"
            recommendation = "strong_sell"
            confidence = 0.9
        else:
            condition = "favorable_short"
            recommendation = "sell"
            confidence = 0.75
    else:
        condition = "neutral"
        recommendation = "hold"
        confidence = 0.5
    
    return {
        "timing_index": timing_index,
        "market_condition": condition,
        "confidence": confidence,
        "recommendation": recommendation
    }
```

### Validation Checklist

- [ ] All 16 functions fully implemented with docstrings
- [ ] Parameter validation using `_expect_*()` helpers
- [ ] Edge case handling (None, empty, single values)
- [ ] Appropriate return types (float, bool, dict, str)
- [ ] Value range clamping where needed
- [ ] Dictionary return keys consistent with specification
- [ ] 56+ unit tests all passing
- [ ] Zero regressions on existing tests (>890 tests)
- [ ] Code follows existing technical.py patterns
- [ ] Docstrings include ta.function_name format
- [ ] All edge cases covered by tests
- [ ] Integration tests validate cross-function workflows

## Timeline

- **Day 1**: Specification review, test suite creation
- **Day 2**: Function implementation (Groups A-B)
- **Day 3**: Function implementation (Groups C-D-E)
- **Day 4**: Test execution, bug fixes, documentation
- **Day 5**: Final validation, completion documentation

## Success Criteria

1. ✅ All 16 advanced strategy functions implemented
2. ✅ 56+ comprehensive unit tests created and passing
3. ✅ 100% pass rate on new tests
4. ✅ Zero regressions (>890 existing tests passing)
5. ✅ Complete documentation for all functions
6. ✅ Project completion: 98-99%
7. ✅ Production-ready code with full error handling

## Notes

- Tier 7 focuses on synthesis and strategy rather than raw technical analysis
- Functions integrate results from lower tiers (Tiers 1-6)
- Dictionary returns enable complex multi-value results
- Regime-aware design adapts to market conditions
- Kelly criterion and risk management principles built-in
- Real-world trading considerations (fees, slippage) included
