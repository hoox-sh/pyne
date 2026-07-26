# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

from __future__ import annotations

from .base import BuiltinDispatchMixin
from .base import BuiltinHandler
from .technical_submodules.advanced import AdvancedIndicators
from .technical_submodules.basic import BasicIndicators
from .technical_submodules.common import CommonIndicators
from .technical_submodules.economics import EconomicsIndicators
from .technical_submodules.moving_averages import MovingAverageIndicators
from .technical_submodules.oscillators import OscillatorIndicators
from .technical_submodules.patterns import PatternIndicators
from .technical_submodules.strategies import StrategiesIndicators
from .technical_submodules.synthesizer import SynthesizerIndicators
from .technical_submodules.volatility import VolatilityIndicators
from .technical_submodules.volume import VolumeIndicators


class TechnicalAnalysisMixin(
    AdvancedIndicators,
    BasicIndicators,
    CommonIndicators,
    MovingAverageIndicators,
    OscillatorIndicators,
    PatternIndicators,
    EconomicsIndicators,
    StrategiesIndicators,
    SynthesizerIndicators,
    VolatilityIndicators,
    VolumeIndicators,
    BuiltinDispatchMixin,
):
    """Technical analysis built-ins and supporting utilities."""

    def _technical_builtin_map(self) -> dict[str, BuiltinHandler]:
        m: dict[str, BuiltinHandler] = {
            "ta.sma": self._builtin_ta_sma,
            "ta.ema": self._builtin_ta_ema,
            "ta.rsi": self._builtin_ta_rsi,
            "ta.stdev": self._builtin_ta_stdev,
            "ta.change": self._builtin_ta_change,
            "ta.highest": self._builtin_ta_highest,
            "ta.lowest": self._builtin_ta_lowest,
            "ta.wma": self._builtin_ta_wma,
            "ta.bb": self._builtin_ta_bb,
            "ta.bbw": self._builtin_ta_bbw,
            "ta.alma": self._builtin_ta_alma,
            "ta.cmo": self._builtin_ta_cmo,
            "ta.correlation": self._builtin_ta_correlation,
            "ta.macd": self._builtin_ta_macd,
            "ta.atr": self._builtin_ta_atr,
            "ta.stoch": self._builtin_ta_stoch,
            "ta.adx": self._builtin_ta_adx,
            "ta.cci": self._builtin_ta_cci,
            "ta.roc": self._builtin_ta_roc,
            "ta.wpr": self._builtin_ta_wpr,
            "ta.obv": self._builtin_ta_obv,
            "ta.mfi": self._builtin_ta_mfi,
            "ta.crossover": self._builtin_ta_crossover,
            "ta.crossunder": self._builtin_ta_crossunder,
            "ta.cross": self._builtin_ta_cross,
            "ta.falling": self._builtin_ta_falling,
            "ta.highestbars": self._builtin_ta_highestbars,
            "ta.lowestbars": self._builtin_ta_lowestbars,
            "ta.rising": self._builtin_ta_rising,
            "ta.rma": self._builtin_ta_rma,
            "ta.vwap": self._builtin_ta_vwap,
            "ta.vwma": self._builtin_ta_vwma,
            "ta.hma": self._builtin_ta_hma,
            "ta.sar": self._builtin_ta_sar,
            "ta.tsi": self._builtin_ta_tsi,
            "ta.valuewhen": self._builtin_ta_valuewhen,
            "ta.tr": self._builtin_ta_tr,
            "ta.cog": self._builtin_ta_cog,
            "ta.dmi": self._builtin_ta_dmi,
            "ta.kc": self._builtin_ta_kc,
            "ta.kcw": self._builtin_ta_kcw,
            "ta.linreg": self._builtin_ta_linreg,
            "ta.rci": self._builtin_ta_rci,
            "ta.supertrend": self._builtin_ta_supertrend,
            "ta.swma": self._builtin_ta_swma,
            "ta.zigzag": self._builtin_ta_zigzag,
            "ta.range": self._builtin_ta_range,
            "ta.max": self._builtin_ta_max,
            "ta.min": self._builtin_ta_min,
            "ta.mom": self._builtin_ta_mom,
            "ta.cum": self._builtin_ta_cum,
            "ta.dev": self._builtin_ta_dev,
            "ta.median": self._builtin_ta_median,
            "ta.mode": self._builtin_ta_mode,
            "ta.percentrank": self._builtin_ta_percentrank,
            "ta.percentile_linear_interpolation": self._builtin_ta_percentile_linear_interpolation,
            "ta.percentile_nearest_rank": self._builtin_ta_percentile_nearest_rank,
            "ta.variance": self._builtin_ta_variance,
            "ta.barssince": self._builtin_ta_barssince,
            "ta.pivothigh": self._builtin_ta_pivothigh,
            "ta.pivotlow": self._builtin_ta_pivotlow,
            "ta.pivot_point_levels": self._builtin_ta_pivot_point_levels,
            # Phase 7 enhancements: Missing indicators
            "ta.iii": self._builtin_ta_iii,
            "ta.nvi": self._builtin_ta_nvi,
            "ta.pvi": self._builtin_ta_pvi,
            "ta.accdist": self._builtin_ta_accdist,
            "ta.wad": self._builtin_ta_wad,
            "ta.wvad": self._builtin_ta_wvad,
            # Phase 8 Tier 1: High-priority indicators
            "ta.kama": self._builtin_ta_kama,
            "ta.dema": self._builtin_ta_dema,
            "ta.tema": self._builtin_ta_tema,
            "ta.cmf": self._builtin_ta_cmf,
            "ta.klinger": self._builtin_ta_klinger,
            "ta.apo": self._builtin_ta_apo,
            "ta.stoch_smooth": self._builtin_ta_stoch_smooth,
            "ta.rsi_divergence": self._builtin_ta_rsi_divergence,
            "ta.macd_signal": self._builtin_ta_macd_signal,
            # Phase 8 Tier 2: Medium-priority indicators
            "ta.ichimoku": self._builtin_ta_ichimoku,
            "ta.donchian": self._builtin_ta_donchian,
            "ta.stochrsi": self._builtin_ta_stochrsi,
            "ta.dpo": self._builtin_ta_dpo,
            "ta.kst": self._builtin_ta_kst,
            "ta.uo": self._builtin_ta_uo,
            "ta.bb_pct": self._builtin_ta_bb_pct,
            "ta.vpt": self._builtin_ta_vpt,
            "ta.beta": self._builtin_ta_beta,
            "ta.r_squared": self._builtin_ta_r_squared,
            "ta.comovement": self._builtin_ta_comovement,
            "ta.atr_stop": self._builtin_ta_atr_stop,
            "ta.fractal": self._builtin_ta_fractal,
            "ta.emv": self._builtin_ta_emv,
            # Phase 8 Tier 3: Specialized indicators
            "ta.engulfing": self._builtin_ta_engulfing,
            "ta.hammer": self._builtin_ta_hammer,
            "ta.gap_detector": self._builtin_ta_gap_detector,
            "ta.voi": self._builtin_ta_voi,
            "ta.bid_ask_imbalance": self._builtin_ta_bid_ask_imbalance,
            "ta.expected_value": self._builtin_ta_expected_value,
            "ta.skewness": self._builtin_ta_skewness,
            "ta.kurtosis": self._builtin_ta_kurtosis,
            "ta.parkinson": self._builtin_ta_parkinson,
            "ta.garman_klass": self._builtin_ta_garman_klass,
            # Phase 8 Tier 4: Enhancement Variants
            "ta.sma_weighted": self._builtin_ta_sma_weighted,
            "ta.ema_cross_signal": self._builtin_ta_ema_cross_signal,
            "ta.rsi_oversold_overbought": self._builtin_ta_rsi_oversold_overbought,
            "ta.atr_normalized": self._builtin_ta_atr_normalized,
            "ta.volume_weighted_momentum": self._builtin_ta_volume_weighted_momentum,
            # Phase 8 Tier 5: Advanced Integration & Real-World Indicators
            "ta.market_condition": self._builtin_ta_market_condition,
            "ta.volatility_regime": self._builtin_ta_volatility_regime,
            "ta.trend_strength": self._builtin_ta_trend_strength,
            "ta.risk_reward_ratio": self._builtin_ta_risk_reward_ratio,
            "ta.double_top_bottom": self._builtin_ta_double_top_bottom,
            "ta.breakout_detection": self._builtin_ta_breakout_detection,
            "ta.inside_bar_pattern": self._builtin_ta_inside_bar_pattern,
            "ta.position_sizing": self._builtin_ta_position_sizing,
            "ta.kelly_criterion": self._builtin_ta_kelly_criterion,
            "ta.max_loss_level": self._builtin_ta_max_loss_level,
            "ta.profit_lock_level": self._builtin_ta_profit_lock_level,
            "ta.signal_confluence": self._builtin_ta_signal_confluence,
            "ta.divergence_detector": self._builtin_ta_divergence_detector,
            "ta.strategy_score": self._builtin_ta_strategy_score,
            "ta.probability_of_movement": self._builtin_ta_probability_of_movement,
            "ta.gamma_levels": self._builtin_ta_gamma_levels,
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
            # Phase 8 Tier 7: Advanced Trading Strategies & Market Timing
            "ta.advanced_breakout_detector": self._builtin_ta_advanced_breakout_detector,
            "ta.breakeven_level": self._builtin_ta_breakeven_level,
            "ta.correlation_filter": self._builtin_ta_correlation_filter,
            "ta.drawdown_recovery_level": self._builtin_ta_drawdown_recovery_level,
            "ta.market_structure_pivot": self._builtin_ta_market_structure_pivot,
            "ta.market_timing_index": self._builtin_ta_market_timing_index,
            "ta.mean_reversion_entry": self._builtin_ta_mean_reversion_entry,
            "ta.multi_timeframe_signal": self._builtin_ta_multi_timeframe_signal,
            "ta.optimal_entry_zone": self._builtin_ta_optimal_entry_zone,
            "ta.position_sizing_score": self._builtin_ta_position_sizing_score,
            "ta.pullback_bounce_level": self._builtin_ta_pullback_bounce_level,
            "ta.regime_adaptive_signal": self._builtin_ta_regime_adaptive_signal,
            "ta.risk_reward_asymmetry": self._builtin_ta_risk_reward_asymmetry,
            "ta.trailing_exit_level": self._builtin_ta_trailing_exit_level,
            "ta.trend_confirmation_score": self._builtin_ta_trend_confirmation_score,
            "ta.volatility_regime_score": self._builtin_ta_volatility_regime_score,
            # Phase 8 Tier 8: Final Capstone Indicator
            "ta.intelligent_strategy_synthesizer": (self._builtin_ta_intelligent_strategy_synthesizer),
        }
        # Pine v3/v4 used bare names (sma, ema, rsi, …) before the ta. namespace.
        # Mirror every ta.* entry as a bare alias unless already registered.
        # Skip names that are also built-in series (tr) or clash with math (max/min).
        skip_bare = {"max", "min", "tr", "range"}
        for key, handler in list(m.items()):
            if not key.startswith("ta."):
                continue
            bare = key[3:]
            if bare in skip_bare or bare in m:
                continue
            m[bare] = handler
        return m
