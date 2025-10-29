# Phase 8: Additional TA Indicators (40+ Remaining)

## Overview

**Current Status**: 92% complete (Phases 1-7)  
**Phase 8 Goal**: Implement 40+ additional technical analysis indicators  
**Target Completion**: ~98% implementation  

---

## Currently Implemented TA Indicators (56 functions)

### Trend Indicators (11)
- ✅ ta.sma - Simple Moving Average
- ✅ ta.ema - Exponential Moving Average
- ✅ ta.rma - Relative Moving Average
- ✅ ta.wma - Weighted Moving Average
- ✅ ta.hma - Hull Moving Average
- ✅ ta.swma - Symmetrically-weighted Moving Average
- ✅ ta.linreg - Linear Regression
- ✅ ta.macd - Moving Average Convergence Divergence
- ✅ ta.supertrend - SuperTrend
- ✅ ta.sar - Parabolic SAR
- ✅ ta.cog - Center of Gravity

### Momentum Indicators (10)
- ✅ ta.rsi - Relative Strength Index
- ✅ ta.stoch - Stochastic
- ✅ ta.roc - Rate of Change
- ✅ ta.mom - Momentum
- ✅ ta.cmo - Chande Momentum Oscillator
- ✅ ta.wpr - Williams %R
- ✅ ta.tsi - True Strength Index
- ✅ ta.rci - Rank Correlation Index
- ✅ ta.change - Change
- ✅ ta.valuewhen - Value When

### Volatility Indicators (6)
- ✅ ta.atr - Average True Range
- ✅ ta.bb - Bollinger Bands
- ✅ ta.bbw - Bollinger Bands Width
- ✅ ta.kc - Keltner Channels
- ✅ ta.kcw - Keltner Channels Width
- ✅ ta.stdev - Standard Deviation

### Volume Indicators (9)
- ✅ ta.obv - On Balance Volume
- ✅ ta.mfi - Money Flow Index
- ✅ ta.vwap - Volume Weighted Average Price
- ✅ ta.vwma - Volume Weighted Moving Average
- ✅ ta.iii - Intraday Intensity Index
- ✅ ta.nvi - Negative Volume Index
- ✅ ta.pvi - Positive Volume Index
- ✅ ta.accdist - Accumulation/Distribution
- ✅ ta.wad - Williams A/D
- ✅ ta.wvad - Williams Volume A/D

### Trend Confirmation (7)
- ✅ ta.adx - Average Directional Index
- ✅ ta.dmi - Directional Movement Index
- ✅ ta.cci - Commodity Channel Index
- ✅ ta.highest - Highest value over period
- ✅ ta.lowest - Lowest value over period
- ✅ ta.cum - Cumulative sum
- ✅ ta.dev - Deviation from SMA

### Oscillators & Pattern (5)
- ✅ ta.zigzag - Zigzag indicator
- ✅ ta.pivothigh - Pivot High
- ✅ ta.pivotlow - Pivot Low
- ✅ ta.pivot_point_levels - Pivot Point Levels
- ✅ ta.range - Range

### Statistical Functions (7)
- ✅ ta.max - Maximum
- ✅ ta.min - Minimum
- ✅ ta.median - Median
- ✅ ta.mode - Mode
- ✅ ta.percentrank - Percentile Rank
- ✅ ta.variance - Variance
- ✅ ta.correlation - Correlation

### Crossover Detection (4)
- ✅ ta.cross - Cross
- ✅ ta.crossover - Crossover
- ✅ ta.crossunder - Crossunder
- ✅ ta.barssince - Bars Since

### Other (1)
- ✅ ta.tr - True Range
- ✅ ta.rising - Rising
- ✅ ta.falling - Falling
- ✅ ta.highestbars - Bars at highest
- ✅ ta.lowestbars - Bars at lowest

---

## Phase 8 Implementation Plan - 40+ Additional Indicators

### Tier 1: High-Priority Indicators (15 functions)

These indicators are commonly used and form the foundation for other strategies.

#### Adaptive Moving Averages (3)
1. **ta.alma** - Arnaud Legoux Moving Average
   - Status: Listed but needs verification
   - Parameters: series, length, offset (0-1), sigma
   - Use: Adaptive smoothing with better lag reduction

2. **ta.kama** - Kaufman's Adaptive Moving Average (NEW)
   - Parameters: series, fast_period, slow_period
   - Use: Adapts based on market volatility
   - Formula: KAMA = prev_KAMA + smoothing_factor * (price - prev_KAMA)

3. **ta.dema** - Double Exponential Moving Average (NEW)
   - Parameters: series, length
   - Use: EMA of EMA, reduces lag
   - Formula: DEMA = 2 * EMA(close) - EMA(EMA(close))

#### Volume & Flow Indicators (4)
4. **ta.ad** - Accumulation/Distribution Line (ENHANCED)
   - Verify current implementation completeness
   - Parameters: (high, low, close, volume) - 4 arg version

5. **ta.cmf** - Chaikin Money Flow (NEW)
   - Parameters: close, high, low, volume, period
   - Use: Money flow in/out of security
   - Formula: CMF = SUM((CLV * volume), period) / SUM(volume, period)

6. **ta.emv** - Ease of Movement (NEW)
   - Parameters: high, low, close, volume, period
   - Use: Measures ease of price movement
   - Formula: EOM = Distance moved / (High-Low) / Volume

7. **ta.klinger** - Klinger Oscillator (NEW)
   - Parameters: high, low, close, volume, fast_period, slow_period
   - Use: Volume-based momentum oscillator
   - Formula: KO = EMA(volume_sum, fast) - EMA(volume_sum, slow)

#### Trend & Momentum Extensions (4)
8. **ta.bb_adaptive** - Adaptive Bollinger Bands (NEW)
   - Parameters: series, basis_length, band_length
   - Use: Dynamic bands based on recent volatility
   - Enhancement to standard BB

9. **ta.tema** - Triple Exponential Moving Average (NEW)
   - Parameters: series, length
   - Use: Even less lag than DEMA
   - Formula: TEMA = 3*EMA - 3*EMA(EMA) + EMA(EMA(EMA))

10. **ta.t3** - T3 Moving Average (NEW)
    - Parameters: series, length, volume_factor
    - Use: Smooth trend indicator
    - Uses cubic polynomial with volume weighting

11. **ta.keltner_adaptive** - Adaptive Keltner Channels (NEW)
    - Parameters: close, period, mult, use_atr
    - Use: Dynamic channels with adaptive width
    - Enhancement to standard KC

#### Oscillator Enhancements (4)
12. **ta.stoch_smooth** - Smoothed Stochastic (NEW)
    - Parameters: high, low, close, period, smooth_k, smooth_d
    - Use: Smoother stochastic with less noise
    - Enhancement to standard stochastic

13. **ta.rsi_divergence** - RSI Divergence Detector (NEW)
    - Parameters: rsi_series, period
    - Use: Detects bullish/bearish divergences
    - Returns: divergence_strength

14. **ta.macd_signal** - MACD Signal Line Strength (NEW)
    - Parameters: macd_line, signal_line
    - Use: Measures MACD momentum
    - Enhancement to standard MACD

15. **ta.apo** - Absolute Price Oscillator (NEW)
    - Parameters: close, fast_period, slow_period
    - Use: Difference between fast and slow EMAs
    - Formula: APO = EMA(fast) - EMA(slow)

---

### Tier 2: Medium-Priority Indicators (15 functions)

Commonly used but more specialized for specific strategies.

#### Market Profile & Distribution (3)
16. **ta.market_profile** - Market Profile/TPO (NEW)
    - Parameters: high, low, close, volume, resolution
    - Use: Distribution of prices in time period
    - Complex: needs aggregation logic

17. **ta.vpt** - Volume Price Trend (NEW)
    - Parameters: close, volume
    - Use: Combines price and volume trend
    - Formula: VPT = prev_VPT + volume * (close_change / close)

18. **ta.price_distribution** - Price Distribution (NEW)
    - Parameters: prices, volume, period, bins
    - Use: Shows where price spends most time
    - Returns: distribution array

#### Advanced Trend Analysis (4)
19. **ta.ichimoku** - Ichimoku Cloud (NEW)
    - Parameters: high, low, close, tenkan_period, kijun_period, senkou_period
    - Use: Japanese multi-component trend system
    - Returns: (tenkan, kijun, senkou_a, senkou_b)

20. **ta.donchian** - Donchian Channels (NEW)
    - Parameters: high, low, period
    - Use: Highest high and lowest low over period
    - Returns: (channel_high, channel_low, channel_mid)

21. **ta.atr_stop** - ATR-based Stop Loss (NEW)
    - Parameters: close, atr_value, multiplier, direction
    - Use: Dynamic stop levels based on ATR
    - Returns: stop_price

22. **ta.fractal** - Fractal Detector (NEW)
    - Parameters: high, low, period
    - Use: Identifies fractal patterns
    - Returns: fractal_high, fractal_low boolean series

#### Correlation & Comovement (3)
23. **ta.beta** - Beta Coefficient (NEW)
    - Parameters: asset_returns, market_returns, period
    - Use: Systematic risk measurement
    - Formula: beta = covariance(asset, market) / variance(market)

24. **ta.r_squared** - R-Squared (NEW)
    - Parameters: series1, series2, period
    - Use: Coefficient of determination
    - Measures how well series2 explains series1

25. **ta.comovement** - Co-movement Index (NEW)
    - Parameters: series1, series2, period
    - Use: How closely two series move together
    - Returns: -1 to 1 correlation coefficient

#### Momentum & Rate Analysis (5)
26. **ta.dpo** - Detrended Price Oscillator (NEW)
    - Parameters: close, period
    - Use: Removes trend to identify cycles
    - Formula: DPO = close - sma(close, period) shifted back

27. **ta.kst** - Know Sure Thing (NEW)
    - Parameters: close, roc_periods (4 values), sma_periods (4 values)
    - Use: Multi-timeframe momentum indicator
    - Uses ROC at different scales

28. **ta.stochrsi** - Stochastic RSI (NEW)
    - Parameters: close, rsi_period, stoch_period, smooth_k, smooth_d
    - Use: Stochastic applied to RSI values
    - Ranges: 0-100

29. **ta.uo** - Ultimate Oscillator (NEW)
    - Parameters: high, low, close, period1, period2, period3
    - Use: Multi-period momentum oscillator
    - Formula: weighted sum of true range

30. **ta.bb_pct** - Bollinger Bands %B (NEW)
    - Parameters: close, period, stdev_mult
    - Use: Where price sits within bands (0-1)
    - Formula: (close - lower_band) / (upper_band - lower_band)

---

### Tier 3: Specialized Indicators (10 functions)

Advanced or niche indicators for specific trading systems.

#### Pattern Recognition (3)
31. **ta.engulfing** - Engulfing Pattern Detector (NEW)
    - Parameters: open, high, low, close
    - Use: Identifies bullish/bearish engulfing patterns
    - Returns: pattern_type (-1, 0, 1)

32. **ta.hammer** - Hammer/Doji Pattern Detector (NEW)
    - Parameters: open, high, low, close
    - Use: Identifies hammer and doji patterns
    - Returns: pattern_strength (0-1)

33. **ta.gap_detector** - Gap Pattern Detector (NEW)
    - Parameters: high, low, previous_close
    - Use: Identifies and measures price gaps
    - Returns: gap_size, gap_type

#### Order Flow & Microstructure (2)
34. **ta.voi** - Volume of Imbalance (NEW)
    - Parameters: buy_volume, sell_volume
    - Use: Imbalance in buy vs sell volume
    - Formula: (buy_vol - sell_vol) / (buy_vol + sell_vol)

35. **ta.bid_ask_imbalance** - Bid-Ask Imbalance (NEW)
    - Parameters: bid_size, ask_size, bid_price, ask_price
    - Use: Market microstructure analysis
    - Returns: imbalance_ratio

#### Advanced Statistical (3)
36. **ta.expected_value** - Expected Value (NEW)
    - Parameters: returns, probabilities
    - Use: Statistical expected value calculation
    - Formula: sum(return * probability)

37. **ta.skewness** - Skewness (NEW)
    - Parameters: series, period
    - Use: Measures asymmetry in distribution
    - Returns: skewness value

38. **ta.kurtosis** - Kurtosis (NEW)
    - Parameters: series, period
    - Use: Measures tail risk
    - Returns: kurtosis value

#### Volatility Extensions (2)
39. **ta.parkinson** - Parkinson Volatility (NEW)
    - Parameters: high, low
    - Use: Volatility from high-low range
    - Formula: sqrt(ln(high/low)²/(4*ln(2)))

40. **ta.garman_klass** - Garman-Klass Volatility (NEW)
    - Parameters: high, low, close, open
    - Use: Leverages OHLC for volatility
    - More accurate than simple HLC volatility

---

### Tier 4: Enhancement Variants (5+ functions)

Variations and enhancements of existing indicators.

41. **ta.sma_weighted** - Weighted SMA (NEW)
    - Parameters: series, period, weight_func
    - Use: SMA with custom weighting scheme

42. **ta.ema_cross_signal** - EMA Cross Signal (NEW)
    - Parameters: close, fast_period, slow_period
    - Use: Returns crossover/crossunder signals

43. **ta.rsi_oversold_overbought** - RSI Levels (NEW)
    - Parameters: rsi_series, oversold, overbought
    - Use: Custom RSI threshold detection

44. **ta.atr_normalized** - Normalized ATR (NEW)
    - Parameters: high, low, close, period
    - Use: ATR as % of price
    - Formula: (ATR / close) * 100

45. **ta.volume_weighted_momentum** - Volume-Weighted Momentum (NEW)
    - Parameters: close, volume, period
    - Use: Momentum adjusted for volume
    - Formula: (price_change * volume) / avg_volume

---

## Implementation Strategy

### Phase 8a: Tier 1 & Enhanced Existing (Weeks 1-2)
- Implement 15 high-priority indicators
- Enhance existing indicators with additional parameters
- Priority: KAMA, DEMA, TEMA, Klinger, CMF
- Expected: +15 functions

### Phase 8b: Tier 2 Medium-Priority (Weeks 3-4)
- Implement 15 medium-priority indicators
- Focus on market profile, ichimoku, donchian
- Add correlation and comovement functions
- Expected: +15 functions

### Phase 8c: Tier 3 Specialized (Week 5)
- Implement 10 specialized indicators
- Pattern recognition, order flow, advanced stats
- Expected: +10 functions

### Phase 8d: Tier 4 & Refinement (Week 6)
- Implement 5+ enhancement variants
- Full test coverage for all new functions
- Documentation and examples
- Expected: +5-10 functions

---

## Testing Strategy

### Unit Tests
- Individual indicator tests with mock data
- Edge case handling (empty series, NaN, zero division)
- Boundary conditions and parameter validation
- Expected coverage: 3-5 tests per indicator

### Integration Tests
- Combinations of indicators
- Multi-indicator strategies
- Data validation and types
- Expected coverage: 10-15 integration tests

### Validation Tests
- Compare results with TradingView Pine Script
- Historical data verification
- Performance benchmarks
- Expected coverage: Key indicators validated

### Total Expected Tests
- Base: 670 tests (current)
- Phase 8: ~150-200 new tests
- Target: 820-870 tests at completion

---

## Success Criteria

1. ✅ All 40+ new indicators implemented
2. ✅ Unit tests for each function (2-3 tests minimum)
3. ✅ Integration tests for multi-indicator scenarios
4. ✅ Zero breaking changes to existing code
5. ✅ Documentation for each new function
6. ✅ Round-trip parsing stability maintained
7. ✅ Performance benchmarks acceptable
8. ✅ 95%+ code coverage maintained

---

## Risk Mitigation

### Complexity Risk
- Start with simpler indicators first
- Build on existing patterns
- Iterative testing and validation

### Performance Risk
- Profile hot paths during development
- Consider caching for expensive calculations
- Limit array operations in loops

### Correctness Risk
- Compare multiple indicator libraries
- Use well-known test data
- Peer review implementations

### Documentation Risk
- Document as you implement
- Add examples with each function
- Update MISSING_FEATURES.md regularly

---

## Timeline

- **Start**: October 29, 2025
- **Phase 8a**: October 30 - November 6 (Tier 1: 15 functions)
- **Phase 8b**: November 7 - November 20 (Tier 2: 15 functions)
- **Phase 8c**: November 21 - November 27 (Tier 3: 10 functions)
- **Phase 8d**: November 28 - December 4 (Tier 4+: 5-10 functions)
- **Completion Target**: December 4, 2025
- **Overall Target**: 98% completion (up from 92%)

---

## Next Steps

1. ✅ Finalize Phase 8 specification (THIS DOCUMENT)
2. Create test framework for Phase 8
3. Begin Tier 1 implementation
4. Add Tier 1 unit tests
5. Iterative: Implement → Test → Validate → Document
6. Final: Comprehensive test run and documentation update

