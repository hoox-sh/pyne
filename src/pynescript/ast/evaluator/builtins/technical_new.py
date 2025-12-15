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

"""Comprehensive Technical Analysis Mixin.

This module consolidates all technical indicator functions by composing
specialized submodules.
"""

from __future__ import annotations

from .base import BuiltinDispatchMixin
from .base import BuiltinHandler
from .technical_submodules.advanced import AdvancedIndicators
from .technical_submodules.common import CommonIndicators
from .technical_submodules.moving_averages import MovingAverageIndicators
from .technical_submodules.oscillators import OscillatorIndicators
from .technical_submodules.patterns import PatternIndicators
from .technical_submodules.volatility import VolatilityIndicators
from .technical_submodules.volume import VolumeIndicators


class TechnicalAnalysisMixin(
    CommonIndicators,
    MovingAverageIndicators,
    OscillatorIndicators,
    VolatilityIndicators,
    VolumeIndicators,
    PatternIndicators,
    AdvancedIndicators,
    BuiltinDispatchMixin,
):
    """Technical analysis built-ins composed from submodules."""

    def _technical_builtin_map(self) -> dict[str, BuiltinHandler]:
        """Register all technical analysis indicators."""
        return {
            # Moving averages
            "ta.sma": self._builtin_ta_sma,
            "ta.ema": self._builtin_ta_ema,
            "ta.wma": self._builtin_ta_wma,
            "ta.rma": self._builtin_ta_rma,
            "ta.hma": self._builtin_ta_hma,
            "ta.vwma": self._builtin_ta_vwma,
            "ta.kama": self._builtin_ta_kama,
            "ta.dema": self._builtin_ta_dema,
            "ta.tema": self._builtin_ta_tema,
            "ta.swma": self._builtin_ta_swma,
            "ta.sma_weighted": self._builtin_ta_sma_weighted,
            # Oscillators
            "ta.rsi": self._builtin_ta_rsi,
            "ta.stoch": self._builtin_ta_stoch,
            "ta.macd": self._builtin_ta_macd,
            "ta.cci": self._builtin_ta_cci,
            "ta.roc": self._builtin_ta_roc,
            "ta.wpr": self._builtin_ta_wpr,
            "ta.tsi": self._builtin_ta_tsi,
            "ta.valuewhen": self._builtin_ta_valuewhen,
            "ta.rsi_divergence": self._builtin_ta_rsi_divergence,
            "ta.macd_signal": self._builtin_ta_macd_signal,
            "ta.stoch_smooth": self._builtin_ta_stoch_smooth,
            # Volatility
            "ta.stdev": self._builtin_ta_stdev,
            "ta.atr": self._builtin_ta_atr,
            "ta.tr": self._builtin_ta_tr,
            "ta.bb": self._builtin_ta_bb,
            "ta.bb_pct": self._builtin_ta_bb_pct,
            "ta.kc": self._builtin_ta_kc,
            "ta.kcw": self._builtin_ta_kcw,
            "ta.linreg": self._builtin_ta_linreg,
            "ta.rci": self._builtin_ta_rci,
            "ta.dpo": self._builtin_ta_dpo,
            "ta.stochrsi": self._builtin_ta_stochrsi,
            "ta.atr_stop": self._builtin_ta_atr_stop,
            # Cross
            "ta.crossover": self._builtin_ta_crossover,
            "ta.crossunder": self._builtin_ta_crossunder,
            "ta.cross": self._builtin_ta_cross,
            # Trend/Direction
            "ta.rising": self._builtin_ta_rising,
            "ta.falling": self._builtin_ta_falling,
            "ta.supertrend": self._builtin_ta_supertrend,
            "ta.dmi": self._builtin_ta_dmi,
            "ta.adx": self._builtin_ta_adx,
            "ta.sar": self._builtin_ta_sar,
            # Extremes/Range
            "ta.highestbars": self._builtin_ta_highestbars,
            "ta.lowestbars": self._builtin_ta_lowestbars,
            "ta.range": self._builtin_ta_range,
            "ta.max": self._builtin_ta_max,
            "ta.min": self._builtin_ta_min,
            "ta.highest": self._builtin_ta_max,
            "ta.lowest": self._builtin_ta_min,
            # Statistical/Change
            "ta.change": self._builtin_ta_change,
            "ta.mom": self._builtin_ta_mom,
            "ta.cum": self._builtin_ta_cum,
            "ta.dev": self._builtin_ta_dev,
            "ta.median": self._builtin_ta_median,
            "ta.mode": self._builtin_ta_mode,
            "ta.percentrank": self._builtin_ta_percentrank,
            "ta.variance": self._builtin_ta_variance,
            "ta.beta": self._builtin_ta_beta,
            "ta.r_squared": self._builtin_ta_r_squared,
            "ta.comovement": self._builtin_ta_comovement,
            "ta.skewness": self._builtin_ta_skewness,
            "ta.kurtosis": self._builtin_ta_kurtosis,
            "ta.parkinson": self._builtin_ta_parkinson,
            "ta.garman_klass": self._builtin_ta_garman_klass,
            # Volume
            "ta.obv": self._builtin_ta_obv,
            "ta.mfi": self._builtin_ta_mfi,
            "ta.cmf": self._builtin_ta_cmf,
            "ta.accdist": self._builtin_ta_accdist,
            "ta.wad": self._builtin_ta_wad,
            "ta.wvad": self._builtin_ta_wvad,
            "ta.vpt": self._builtin_ta_vpt,
            "ta.klinger": self._builtin_ta_klinger,
            "ta.apo": self._builtin_ta_apo,
            "ta.emv": self._builtin_ta_emv,
            "ta.iii": self._builtin_ta_iii,
            "ta.nvi": self._builtin_ta_nvi,
            "ta.pvi": self._builtin_ta_pvi,
            "ta.voi": self._builtin_ta_voi,
            "ta.bid_ask_imbalance": self._builtin_ta_bid_ask_imbalance,
            # Utilities
            "ta.vwap": self._builtin_ta_vwap,
            "ta.barssince": self._builtin_ta_barssince,
            "ta.cog": self._builtin_ta_cog,
            # Pivots
            "ta.pivothigh": self._builtin_ta_pivothigh,
            "ta.pivotlow": self._builtin_ta_pivotlow,
            "ta.pivot_point_levels": self._builtin_ta_pivot_point_levels,
            # Patterns
            "ta.engulfing": self._builtin_ta_engulfing,
            "ta.hammer": self._builtin_ta_hammer,
            "ta.gap_detector": self._builtin_ta_gap_detector,
            "ta.zigzag": self._builtin_ta_zigzag,
            "ta.fractal": self._builtin_ta_fractal,
            "ta.double_top_bottom": self._builtin_ta_double_top_bottom,
            # Advanced
            "ta.ichimoku": self._builtin_ta_ichimoku,
            "ta.donchian": self._builtin_ta_donchian,
            "ta.kst": self._builtin_ta_kst,
            "ta.uo": self._builtin_ta_uo,
            "ta.market_condition": self._builtin_ta_market_condition,
            "ta.volatility_regime": self._builtin_ta_volatility_regime,
            "ta.trend_strength": self._builtin_ta_trend_strength,
            "ta.risk_reward_ratio": self._builtin_ta_risk_reward_ratio,
            "ta.breakout_detection": self._builtin_ta_breakout_detection,
            "ta.inside_bar_pattern": self._builtin_ta_inside_bar_pattern,
            "ta.position_sizing": self._builtin_ta_position_sizing,
            "ta.kelly_criterion": self._builtin_ta_kelly_criterion,
            "ta.signal_confluence": self._builtin_ta_signal_confluence,
            "ta.divergence_detector": self._builtin_ta_divergence_detector,
            "ta.strategy_score": self._builtin_ta_strategy_score,
            "ta.probability_of_movement": self._builtin_ta_probability_of_movement,
            "ta.gamma_levels": self._builtin_ta_gamma_levels,
            # Tier 6 placeholders
            "ta.volume_profile_high": self._builtin_ta_volume_profile_high,
            "ta.order_flow_imbalance": self._builtin_ta_order_flow_imbalance,
        }
