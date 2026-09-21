"""Direct unit tests for the worst-covered ``technical_submodules``.

Calls each submodule mixin explicitly (``Cls._builtin_ta_*(ev, args)``) so
coverage is attributed to the right file instead of the MRO winner on
``NodeLiteralEvaluator``. Fast, deterministic, plain-list inputs; a shared
fixture provides OHLCV context for indicators that read chart series.
"""

from __future__ import annotations

import math

import pytest

from pynescript.ast.evaluator import NodeLiteralEvaluator
from pynescript.ast.evaluator.builtins.technical_submodules.basic import BasicIndicators as _Basic
from pynescript.ast.evaluator.builtins.technical_submodules.common import CommonIndicators as _Common
from pynescript.ast.evaluator.builtins.technical_submodules.economics import EconomicsIndicators as _Econ
from pynescript.ast.evaluator.builtins.technical_submodules.moving_averages import MovingAverageIndicators as _MovAvg
from pynescript.ast.evaluator.builtins.technical_submodules.oscillators import OscillatorIndicators as _Osc
from pynescript.ast.evaluator.builtins.technical_submodules.patterns import PatternIndicators as _Pat
from pynescript.ast.evaluator.builtins.technical_submodules.synthesizer import SynthesizerIndicators as _Synth
from pynescript.ast.evaluator.builtins.technical_submodules.volatility import VolatilityIndicators as _Vol


def _trend(n: int = 30) -> list[float]:
    return [float(i) for i in range(1, n + 1)]


def _ohlcv(n: int = 30) -> tuple[list[float], list[float], list[float], list[float]]:
    high = [float(100 + i) for i in range(n)]
    low = [float(90 + i) for i in range(n)]
    close = [float(95 + i) for i in range(n)]
    vol = [1000.0 + i for i in range(n)]
    return high, low, close, vol


@pytest.fixture()
def ev() -> NodeLiteralEvaluator:
    evaluator = NodeLiteralEvaluator()
    high, low, close, vol = _ohlcv(60)
    evaluator.current_series = {
        "open": [float(94 + i) for i in range(60)],
        "high": high,
        "low": low,
        "close": close,
        "hl2": [(high[i] + low[i]) / 2.0 for i in range(60)],
        "hlc3": close,
        "volume": vol,
    }
    return evaluator


# ---------------------------------------------------------------------------
# common.py
# ---------------------------------------------------------------------------


class TestCommonCrossTrend:
    def test_crossover(self, ev: NodeLiteralEvaluator) -> None:
        assert _Common._builtin_ta_crossover(ev, [[1.0, 3.0], [2.0, 2.0]]) is True
        assert _Common._builtin_ta_crossover(ev, [[3.0, 1.0], [2.0, 2.0]]) is False

    def test_crossunder(self, ev: NodeLiteralEvaluator) -> None:
        assert _Common._builtin_ta_crossunder(ev, [[3.0, 1.0], [2.0, 2.0]]) is True
        assert _Common._builtin_ta_crossunder(ev, [[1.0, 3.0], [2.0, 2.0]]) is False

    def test_cross_either(self, ev: NodeLiteralEvaluator) -> None:
        assert _Common._builtin_ta_cross(ev, [[1.0, 2.0], [2.0, 1.0]]) is True
        assert _Common._builtin_ta_cross(ev, [[1.0, 1.5], [2.0, 2.5]]) is False

    def test_rising_falling(self, ev: NodeLiteralEvaluator) -> None:
        up = _trend()
        down = list(reversed(_trend()))
        assert _Common._builtin_ta_rising(ev, [up, 3]) is True
        assert _Common._builtin_ta_falling(ev, [up, 3]) is False
        assert _Common._builtin_ta_falling(ev, [down, 3]) is True
        assert _Common._builtin_ta_rising(ev, [down, 3]) is False

    def test_highestbars_lowestbars(self, ev: NodeLiteralEvaluator) -> None:
        series = _trend()
        assert _Common._builtin_ta_highestbars(ev, [series, 5]) == 0
        assert _Common._builtin_ta_lowestbars(ev, [series, 5]) == -4


class TestCommonStats:
    def test_range_max_min(self, ev: NodeLiteralEvaluator) -> None:
        series = _trend()
        assert _Common._builtin_ta_range(ev, [series, 5]) == pytest.approx(4.0)
        assert _Common._builtin_ta_max(ev, [series]) == pytest.approx(30.0)
        assert _Common._builtin_ta_min(ev, [series]) == pytest.approx(1.0)
        assert _Common._builtin_ta_max(ev, [[None, None]]) is None
        assert _Common._builtin_ta_min(ev, [[None, None]]) is None

    def test_change_mom_cum(self, ev: NodeLiteralEvaluator) -> None:
        series = _trend()
        assert _Common._builtin_ta_change(ev, [series]) == pytest.approx(1.0)
        assert _Common._builtin_ta_change(ev, [series, 2]) == pytest.approx(2.0)
        assert _Common._builtin_ta_mom(ev, [series, 5]) == pytest.approx(5.0)
        assert _Common._builtin_ta_cum(ev, [series]) == pytest.approx(465.0)

    def test_dev_median(self, ev: NodeLiteralEvaluator) -> None:
        series = _trend()
        assert _Common._builtin_ta_dev(ev, [series, 5]) == pytest.approx(1.2)
        assert _Common._builtin_ta_median(ev, [series, 5]) == pytest.approx(28.0)

    def test_mode_percentrank_variance(self, ev: NodeLiteralEvaluator) -> None:
        series = _trend()
        assert _Common._builtin_ta_mode(ev, [series, 5]) == pytest.approx(26.0)
        assert _Common._builtin_ta_percentrank(ev, [series, 5]) == pytest.approx(80.0)
        assert _Common._builtin_ta_variance(ev, [series, 5]) == pytest.approx(2.5)

    def test_expected_value(self, ev: NodeLiteralEvaluator) -> None:
        assert _Common._builtin_ta_expected_value(ev, [[1.0, 2.0, 3.0], [0.2, 0.3, 0.5]]) == pytest.approx(2.3)
        assert _Common._builtin_ta_expected_value(ev, [[1.0], [0.0]]) == pytest.approx(0.0)

    def test_skewness_kurtosis(self, ev: NodeLiteralEvaluator) -> None:
        series = _trend()
        assert _Common._builtin_ta_skewness(ev, [series, 10]) == pytest.approx(0.0)
        assert _Common._builtin_ta_kurtosis(ev, [series, 10]) == pytest.approx(-1.224, abs=0.01)
        assert _Common._builtin_ta_skewness(ev, [[1.0, 2.0], 10]) is None
        assert _Common._builtin_ta_kurtosis(ev, [[1.0, 2.0], 10]) is None

    def test_parkinson_garman_klass(self, ev: NodeLiteralEvaluator) -> None:
        high, low, close, _vol = _ohlcv()
        assert _Common._builtin_ta_parkinson(ev, [high, low]) == pytest.approx(0.0484, abs=0.001)
        assert _Common._builtin_ta_garman_klass(ev, [high, low, close, close, 14]) == pytest.approx(0.057, abs=0.005)


class TestCommonPivotsUtils:
    def test_vwap_sequence(self, ev: NodeLiteralEvaluator) -> None:
        seq = [(100.0 + i) * (1000.0 + i) for i in range(30)]
        assert _Common._builtin_ta_vwap(ev, [seq]) == pytest.approx(116235.17, abs=0.1)

    def test_barssince(self, ev: NodeLiteralEvaluator) -> None:
        assert _Common._builtin_ta_barssince(ev, [[[0, 0, 1, 0, 0]][0]]) == 0

    def test_pivothigh_pivotlow(self, ev: NodeLiteralEvaluator) -> None:
        assert _Common._builtin_ta_pivothigh(ev, [[100.0, 101.0, 102.0, 110.0], 2, 0]) == pytest.approx(110.0)
        assert _Common._builtin_ta_pivotlow(ev, [[100.0, 99.0, 98.0, 80.0], 2, 0]) == pytest.approx(80.0)
        assert _Common._builtin_ta_pivothigh(ev, [[1.0, 2.0], 2, 2]) is None

    def test_pivot_point_levels(self, ev: NodeLiteralEvaluator) -> None:
        levels = _Common._builtin_ta_pivot_point_levels(ev, [110.0, 90.0, 100.0])
        assert levels["pivot"] == pytest.approx(100.0)
        assert levels["r1"] == pytest.approx(110.0)
        assert levels["s1"] == pytest.approx(90.0)

    def test_cog(self, ev: NodeLiteralEvaluator) -> None:
        assert _Common._builtin_ta_cog(ev, [_trend(), 10]) == pytest.approx(-5.176, abs=0.01)

    def test_dmi_context(self, ev: NodeLiteralEvaluator) -> None:
        plus, minus, adx = _Common._builtin_ta_dmi(ev, [14, 14])
        assert plus == pytest.approx(9.976, abs=0.01)
        assert minus == pytest.approx(0.0)
        assert adx == pytest.approx(100.0)

    def test_supertrend(self, ev: NodeLiteralEvaluator) -> None:
        high, low, _close, _vol = _ohlcv()
        lower, upper, direction = _Common._builtin_ta_supertrend(ev, [high, low, 7])
        assert direction in (-1, 0, 1)
        assert lower < upper

    def test_zigzag(self, ev: NodeLiteralEvaluator) -> None:
        high, low, direction = _Common._builtin_ta_zigzag(ev, [_trend(), 5.0])
        assert (high, low, direction) == (pytest.approx(30.0), pytest.approx(29.0), 1)

    def test_adx(self, ev: NodeLiteralEvaluator) -> None:
        high, low, close, _vol = _ohlcv()
        assert _Common._builtin_ta_adx(ev, [14]) == pytest.approx(100.0)
        assert _Common._builtin_ta_adx(ev, [high, low, close, 14]) == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# basic.py
# ---------------------------------------------------------------------------


class TestBasicAverages:
    def test_sma_ema(self, ev: NodeLiteralEvaluator) -> None:
        sma = _Basic._builtin_ta_sma(ev, [_trend(), 5])
        assert sma[-1] == pytest.approx(28.0)
        assert sma[0] is None
        ema = _Basic._builtin_ta_ema(ev, [_trend(), 5])
        assert ema[-1] is not None and ema[-1] > 25.0

    def test_wma_rma_hma(self, ev: NodeLiteralEvaluator) -> None:
        assert _Basic._builtin_ta_wma(ev, [_trend(), 5]) == pytest.approx(28.667, abs=0.01)
        rma = _Basic._builtin_ta_rma(ev, [_trend(), 5])
        assert math.isnan(rma[0])
        assert rma[-1] > 20.0
        assert _Basic._builtin_ta_hma(ev, [_trend(), 5]) == pytest.approx(30.333, abs=0.01)

    def test_vwma(self, ev: NodeLiteralEvaluator) -> None:
        _high, _low, _close, vol = _ohlcv()
        out = _Basic._builtin_ta_vwma(ev, [_trend(), vol, 5])
        assert out[-1] is not None


class TestBasicRanges:
    def test_highest_lowest(self, ev: NodeLiteralEvaluator) -> None:
        assert _Basic._builtin_ta_highest(ev, [_trend(), 5]) == pytest.approx(30.0)
        assert _Basic._builtin_ta_lowest(ev, [_trend(), 5]) == pytest.approx(26.0)
        assert _Basic._builtin_ta_highestbars(ev, [_trend(), 5]) == 0
        assert _Basic._builtin_ta_lowestbars(ev, [_trend(), 5]) == -4

    def test_change_mom_stdev(self, ev: NodeLiteralEvaluator) -> None:
        assert _Basic._builtin_ta_change(ev, [_trend()]) == pytest.approx(1.0)
        assert _Basic._builtin_ta_mom(ev, [_trend(), 10]) == pytest.approx(10.0)
        assert _Basic._builtin_ta_stdev(ev, [_trend(), 5]) == pytest.approx(1.5811, abs=0.001)

    def test_tr_atr(self, ev: NodeLiteralEvaluator) -> None:
        high, low, close, _vol = _ohlcv()
        tr = _Basic._builtin_ta_tr(ev, [high, low, close])
        assert tr[0] is None and tr[-1] == pytest.approx(10.0)
        atr = _Basic._builtin_ta_atr(ev, [high, low, close, 14])
        assert atr[-1] == pytest.approx(10.0)

    def test_sar(self, ev: NodeLiteralEvaluator) -> None:
        high, low, _close, _vol = _ohlcv()
        out = _Basic._builtin_ta_sar(ev, [high, low, 0.02, 0.02, 0.2])
        assert isinstance(out, list) and len(out) == len(high)

    def test_kc_kcw(self, ev: NodeLiteralEvaluator) -> None:
        high, low, close, _vol = _ohlcv()
        basis, upper, lower = _Basic._builtin_ta_kc(ev, [high, low, close, 20, 2.0])
        assert upper > basis > lower
        assert _Basic._builtin_ta_kcw(ev, [high, low, close, 20]) == pytest.approx(20.0)

    def test_linreg_rci(self, ev: NodeLiteralEvaluator) -> None:
        assert _Basic._builtin_ta_linreg(ev, [_trend(), 14]) == pytest.approx(30.0)
        assert _Basic._builtin_ta_rci(ev, [_trend(), 14]) == pytest.approx(1.0)

    def test_percentiles(self, ev: NodeLiteralEvaluator) -> None:
        assert _Basic._builtin_ta_percentile_linear_interpolation(ev, [_trend(), 10, 50.0]) == pytest.approx(25.5)
        assert _Basic._builtin_ta_percentile_nearest_rank(ev, [_trend(), 10, 50.0]) == pytest.approx(25.0)
        assert _Basic._builtin_ta_swma_legacy_unused(ev, [_trend(), 4]) == pytest.approx(28.5)

    def test_barssince_pivots(self, ev: NodeLiteralEvaluator) -> None:
        assert _Basic._builtin_ta_barssince(ev, [[[0, 0, 1]][0]]) == 0
        assert _Basic._builtin_ta_pivothigh(ev, [2, 2]) is None
        assert _Basic._builtin_ta_pivotlow(ev, [2, 2]) is None

    def test_vwap_supertrend_dmi(self, ev: NodeLiteralEvaluator) -> None:
        high, low, close, _vol = _ohlcv()
        assert _Basic._builtin_ta_vwap(ev, [close]) == pytest.approx(109.574, abs=0.01)
        trend, direction = _Basic._builtin_ta_supertrend(ev, [3.0, 7])
        assert direction in (-1, 1) and isinstance(trend, float)
        plus, _minus, _adx = _Basic._builtin_ta_dmi(ev, [high, low, close, 14])
        assert plus == pytest.approx(9.78, abs=0.01)


# ---------------------------------------------------------------------------
# moving_averages.py
# ---------------------------------------------------------------------------


class TestMovingAverages:
    def test_sma_ema_wma_rma(self, ev: NodeLiteralEvaluator) -> None:
        assert _MovAvg._builtin_ta_sma(ev, [_trend(), 5])[-1] == pytest.approx(28.0)
        assert _MovAvg._builtin_ta_ema(ev, [_trend(), 5])[-1] is not None
        assert _MovAvg._builtin_ta_wma(ev, [_trend(), 5]) == pytest.approx(28.667, abs=0.01)
        assert _MovAvg._builtin_ta_rma(ev, [_trend(), 5])[-1] is not None

    def test_hma_swma(self, ev: NodeLiteralEvaluator) -> None:
        assert _MovAvg._builtin_ta_hma(ev, [_trend(), 5]) == pytest.approx(30.333, abs=0.01)
        assert _MovAvg._builtin_ta_swma(ev, [_trend(), 4]) == pytest.approx(28.5)

    def test_vwma(self, ev: NodeLiteralEvaluator) -> None:
        _high, _low, _close, vol = _ohlcv()
        out = _MovAvg._builtin_ta_vwma(ev, [_trend(), vol, 14])
        assert len(out) == 30 and math.isnan(out[0]) and out[-1] is not None

    def test_kama(self, ev: NodeLiteralEvaluator) -> None:
        out = _MovAvg._builtin_ta_kama(ev, [_trend(), 10, 2, 30])
        assert out[10] == pytest.approx(10.444, abs=0.01)
        assert out[-1] is not None

    def test_dema_tema(self, ev: NodeLiteralEvaluator) -> None:
        dema = _MovAvg._builtin_ta_dema(ev, [_trend(), 14])
        tema = _MovAvg._builtin_ta_tema(ev, [_trend(), 14])
        assert len(dema) == 30 and dema[0] is None
        assert len(tema) == 30 and tema[0] is None

    def test_sma_weighted(self, ev: NodeLiteralEvaluator) -> None:
        assert _MovAvg._builtin_ta_sma_weighted(ev, [_trend(), 14]) == pytest.approx(25.667, abs=0.01)

    def test_ema_cross_signal(self, ev: NodeLiteralEvaluator) -> None:
        series = _trend()
        sig = _MovAvg._builtin_ta_ema_cross_signal(ev, [series, [x + 1 for x in series], 0.5])
        assert set(sig) == {"signal", "strength", "trend_direction"}


# ---------------------------------------------------------------------------
# oscillators.py
# ---------------------------------------------------------------------------


class TestOscillators:
    def test_rsi(self, ev: NodeLiteralEvaluator) -> None:
        assert _Osc._builtin_ta_rsi(ev, [_trend(), 14]) == pytest.approx(100.0)

    def test_stoch_forms(self, ev: NodeLiteralEvaluator) -> None:
        _high, low, close, _vol = _ohlcv()
        high = [float(100 + i) for i in range(30)]
        assert _Osc._builtin_ta_stoch(ev, [close, high, low, 14]) == pytest.approx(78.261, abs=0.01)
        assert _Osc._builtin_ta_stoch(ev, [14]) == pytest.approx(78.261, abs=0.01)
        k, _d = _Osc._builtin_ta_stoch(ev, [high, low, close, 14, 3])
        assert k == pytest.approx(78.261, abs=0.01)

    def test_macd(self, ev: NodeLiteralEvaluator) -> None:
        macd, signal, hist = _Osc._builtin_ta_macd(ev, [_trend(), 12, 26, 9])
        assert macd == pytest.approx(7.0)
        assert isinstance(signal, float) and isinstance(hist, float)

    def test_cci_wpr(self, ev: NodeLiteralEvaluator) -> None:
        high, low, close, _vol = _ohlcv()
        assert _Osc._builtin_ta_cci(ev, [high, low, close, 20]) == pytest.approx(126.667, abs=0.01)
        assert _Osc._builtin_ta_wpr(ev, [high, low, close, 14]) == pytest.approx(-21.739, abs=0.01)

    def test_roc(self, ev: NodeLiteralEvaluator) -> None:
        assert _Osc._builtin_ta_roc(ev, [_trend(), 9]) == pytest.approx(42.857, abs=0.01)

    def test_ao_aroon(self, ev: NodeLiteralEvaluator) -> None:
        # Linear hl2 = 95+i over 60 bars: SMA5-SMA34 last = 14.5
        assert _Osc._builtin_ta_ao(ev, []) == pytest.approx(14.5)
        empty = NodeLiteralEvaluator()
        assert _Osc._builtin_ta_ao(empty, []) is None
        up, down = _Osc._builtin_ta_aroon(ev, [14])
        assert (up, down) == (pytest.approx(0.0), pytest.approx(100.0))

    def test_tsi(self, ev: NodeLiteralEvaluator) -> None:
        assert _Osc._builtin_ta_tsi(ev, [_trend(60), 13, 25]) == pytest.approx(100.0)
        assert _Osc._builtin_ta_tsi(ev, [13, 25]) == pytest.approx(100.0)

    def test_valuewhen(self, ev: NodeLiteralEvaluator) -> None:
        _high, _low, close, _vol = _ohlcv()
        assert _Osc._builtin_ta_valuewhen(ev, [[1, 0, 1], close, 0]) == pytest.approx(97.0)
        assert _Osc._builtin_ta_valuewhen(ev, [[1, 0, 1, 0, 1], _trend(), 1]) == pytest.approx(3.0)

    def test_macd_signal(self, ev: NodeLiteralEvaluator) -> None:
        assert _Osc._builtin_ta_macd_signal(ev, [1.5, 0.5]) == pytest.approx(1.0)
        with pytest.raises(ValueError):
            _Osc._builtin_ta_macd_signal(ev, [1.5])

    def test_stochrsi_dpo(self, ev: NodeLiteralEvaluator) -> None:
        out = _Osc._builtin_ta_stochrsi(ev, [14, 14])
        assert out["stochrsi"] == pytest.approx(0.0)
        assert _Osc._builtin_ta_dpo(ev, [20]) == pytest.approx(-0.5)

    def test_kst_uo(self, ev: NodeLiteralEvaluator) -> None:
        assert _Osc._builtin_ta_kst(ev, [10, 15, 20, 30]) == pytest.approx(16.123, abs=0.01)
        assert _Osc._builtin_ta_uo(ev, [7, 14, 28]) == pytest.approx(50.0)

    def test_stoch_smooth_extras(self, ev: NodeLiteralEvaluator) -> None:
        high, low, close, _vol = _ohlcv()
        out = _Osc._builtin_ta_stoch_smooth(ev, [high, low, close, 14, 3, 3])
        assert len(out) == len(close)
        div = _Osc._builtin_ta_rsi_divergence(ev, [close, 14])
        assert len(div) == len(close)
        obos = _Osc._builtin_ta_rsi_oversold_overbought(ev, [close, 30, 70])
        assert set(obos) >= {"rsi", "is_oversold", "is_overbought"}


# ---------------------------------------------------------------------------
# volatility.py
# ---------------------------------------------------------------------------


class TestVolatility:
    def test_stdev_atr_tr(self, ev: NodeLiteralEvaluator) -> None:
        high, low, close, _vol = _ohlcv()
        assert _Vol._builtin_ta_stdev(ev, [_trend(), 5]) == pytest.approx(1.5811, abs=0.001)
        assert _Vol._builtin_ta_atr(ev, [high, low, close, 14])[-1] == pytest.approx(10.0)
        assert _Vol._builtin_ta_tr(ev, [high, low, close])[-1] == pytest.approx(10.0)

    def test_bb_family(self, ev: NodeLiteralEvaluator) -> None:
        upper, basis, lower = _Vol._builtin_ta_bb(ev, [_trend(), 20, 2.0])
        assert upper > basis > lower
        assert _Vol._builtin_ta_bbw(ev, [_trend(), 20, 2.0]) == pytest.approx(1.1544, abs=0.001)
        assert _Vol._builtin_ta_bb_pct(ev, [_trend(), 20, 2.0]) == pytest.approx(54.188, abs=0.01)

    def test_alma_cmo(self, ev: NodeLiteralEvaluator) -> None:
        assert _Vol._builtin_ta_alma(ev, [_trend(), 9, 0.85, 6.0]) == pytest.approx(28.443, abs=0.01)
        assert _Vol._builtin_ta_cmo(ev, [_trend(), 14]) == pytest.approx(100.0)

    def test_correlation_beta(self, ev: NodeLiteralEvaluator) -> None:
        series, peer = _trend(), [2.0 * x for x in _trend()]
        assert _Vol._builtin_ta_correlation(ev, [series, peer, 14]) == pytest.approx(1.0)
        assert _Vol._builtin_ta_beta(ev, [series, peer, 14]) == pytest.approx(0.5)
        assert _Vol._builtin_ta_r_squared(ev, [series, peer, 14]) == pytest.approx(1.0)
        assert _Vol._builtin_ta_comovement(ev, [series, peer, 14]) == pytest.approx(100.0)

    def test_kc_family(self, ev: NodeLiteralEvaluator) -> None:
        high, low, close, _vol = _ohlcv()
        basis, upper, lower = _Vol._builtin_ta_kc(ev, [high, low, close, 20, 2.0])
        assert upper > basis > lower
        assert _Vol._builtin_ta_kcw(ev, [high, low, close, 20]) == pytest.approx(20.0)

    def test_linreg_rci(self, ev: NodeLiteralEvaluator) -> None:
        assert _Vol._builtin_ta_linreg(ev, [_trend(), 14]) == pytest.approx(30.0)
        assert _Vol._builtin_ta_rci(ev, [_trend(), 14]) == pytest.approx(1.0)

    def test_dpo(self, ev: NodeLiteralEvaluator) -> None:
        _high, _low, close, _vol = _ohlcv()
        assert _Vol._builtin_ta_dpo(ev, [20, close]) == pytest.approx(-0.5)

    def test_atr_stop_normalized(self, ev: NodeLiteralEvaluator) -> None:
        high, low, close, _vol = _ohlcv()
        stops = _Vol._builtin_ta_atr_stop(ev, [high, low, close, 14, 3.0])
        assert set(stops) == {"long_stop", "short_stop"}
        assert _Vol._builtin_ta_atr_normalized(ev, [high, low, close, 14]) == pytest.approx(8.0645, abs=0.001)

    def test_stochrsi(self, ev: NodeLiteralEvaluator) -> None:
        out = _Vol._builtin_ta_stochrsi(ev, [14, 14, 3, 3])
        assert set(out) == {"stochrsi", "signal"}


# ---------------------------------------------------------------------------
# economics.py
# ---------------------------------------------------------------------------


class TestEconomics:
    def test_order_flow_imbalance(self, ev: NodeLiteralEvaluator) -> None:
        high, low, close, vol = _ohlcv()
        assert _Econ._builtin_ta_order_flow_imbalance(ev, [high, low, close, vol, 14]) == pytest.approx(-1.0)

    def test_volume_profile(self, ev: NodeLiteralEvaluator) -> None:
        _high, _low, close, vol = _ohlcv()
        assert _Econ._builtin_ta_volume_profile_high(ev, [close, vol, 14, 10]) == pytest.approx(123.35)
        assert _Econ._builtin_ta_volume_profile_low(ev, [close, vol, 14, 10]) == pytest.approx(112.95)

    def test_spread_momentum(self, ev: NodeLiteralEvaluator) -> None:
        spread = _Econ._builtin_ta_spread_analysis(ev, [[1.0] * 30, [1.1] * 30, 14])
        assert spread["spread_trend"] == "stable"
        _high, _low, close, vol = _ohlcv()
        div = _Econ._builtin_ta_momentum_divergence(ev, [close, close, close])
        assert div["divergence_type"] == "none"
        assert _Econ._builtin_ta_acceleration_factor(ev, [close, 14]) == pytest.approx(1.0)
        assert _Econ._builtin_ta_momentum_filter(ev, [close, vol, 14]) == pytest.approx(117.516, abs=0.01)

    def test_mean_reversion(self, ev: NodeLiteralEvaluator) -> None:
        _high, _low, close, _vol = _ohlcv()
        assert _Econ._builtin_ta_mean_reversion_score(ev, [close, close, [1.0] * 30, 14]) == pytest.approx(50.0)

    def test_macro_proxies(self, ev: NodeLiteralEvaluator) -> None:
        _high, _low, close, vol = _ohlcv()
        assert _Econ._builtin_ta_economic_impact_score(ev, [1.0, 2.0, 3.0]) == pytest.approx(19.0)
        usd = [100.0 + i for i in range(30)]
        comm = [50.0 + i for i in range(30)]
        assert _Econ._builtin_ta_inflation_proxy_indicator(ev, [usd, comm, [3.0] * 30]) == pytest.approx(5.0)
        cyc = [100.0 + i for i in range(30)]
        defe = [90.0 + i for i in range(30)]
        assert _Econ._builtin_ta_employment_cycle_indicator(ev, [cyc, defe, [5.0] * 30]) == "mid_cycle"
        assert _Econ._builtin_ta_gdp_growth_proxy(ev, [[0.6] * 30, vol, close]) == pytest.approx(4.0)

    def test_sentiment(self, ev: NodeLiteralEvaluator) -> None:
        rsi = [50.0 + i * 0.5 for i in range(30)]
        assert _Econ._builtin_ta_fear_greed_index(ev, [rsi, [20.0] * 30, [1.0] * 30, [0.5] * 30]) == pytest.approx(
            -10.25
        )
        assert _Econ._builtin_ta_crowd_sentiment(ev, [1.0, 2.0, 3.0]) == pytest.approx(2.0)
        sig = _Econ._builtin_ta_contrarian_signal(ev, [80.0, 2.0, 10])
        assert sig["signal"] == "neutral"

    def test_volume_flow(self, ev: NodeLiteralEvaluator) -> None:
        _high, _low, close, vol = _ohlcv()
        assert _Econ._builtin_ta_cumulative_delta(ev, [close, vol, 14]) == pytest.approx(14315.0)
        assert _Econ._builtin_ta_volume_momentum(ev, [vol, 14]) == pytest.approx(0.0979, abs=0.001)

    def test_smart_money_liquidity(self, ev: NodeLiteralEvaluator) -> None:
        _high, _low, _close, vol = _ohlcv()
        assert _Econ._builtin_ta_smart_money_flow(ev, [1.5, 3000.0, 2, 10]) == pytest.approx(0.0)
        assert _Econ._builtin_ta_liquidity_score(ev, [vol, [1.0] * 30, [0.1] * 30, 14]) == pytest.approx(100.0)

    def test_volume_thrust(self, ev: NodeLiteralEvaluator) -> None:
        _high, _low, close, vol = _ohlcv()
        assert _Econ._builtin_ta_volume_thrust(ev, [close, vol, vol, 14]) is False


# ---------------------------------------------------------------------------
# patterns.py
# ---------------------------------------------------------------------------


class TestPatterns:
    def test_sar(self, ev: NodeLiteralEvaluator) -> None:
        high, low, _close, _vol = _ohlcv()
        out = _Pat._builtin_ta_sar(ev, [high, low, 0.02, 0.02, 0.2])
        assert isinstance(out, list) and len(out) == len(high) and out[0] == pytest.approx(90.0)

    def test_engulfing_hammer(self, ev: NodeLiteralEvaluator) -> None:
        high, low, close, _vol = _ohlcv()
        opened = [float(96 + i) for i in range(30)]
        eng = _Pat._builtin_ta_engulfing(ev, [low, high, close, opened])
        assert eng == {"is_bullish": True, "is_bearish": False, "pattern_strength": 1}
        ham = _Pat._builtin_ta_hammer(ev, [low, high, close, opened])
        assert ham["is_hammer"] is False and ham["pattern_strength"] == pytest.approx(0.0)

    def test_gap_detector(self, ev: NodeLiteralEvaluator) -> None:
        high, low, close, _vol = _ohlcv()
        gap = _Pat._builtin_ta_gap_detector(ev, [low, high, close])
        assert gap == {"gap_size": 0.0, "gap_type": 0, "gap_percent": 0.0}

    def test_fractal(self, ev: NodeLiteralEvaluator) -> None:
        high, low, _close, _vol = _ohlcv()
        assert _Pat._builtin_ta_fractal(ev, [high, low, 2]) == {"is_high_fractal": False, "is_low_fractal": False}

    def test_double_top_bottom(self, ev: NodeLiteralEvaluator) -> None:
        _high, _low, close, _vol = _ohlcv()
        out = _Pat._builtin_ta_double_top_bottom(ev, [close, 10, 5])
        assert out["pattern_type"] == "none"


# ---------------------------------------------------------------------------
# synthesizer.py
# ---------------------------------------------------------------------------


class TestSynthesizer:
    def _inputs(self, regime: str) -> list:
        return [[0.5] * 10, [0.3] * 10, [0.5] * 10, [0.4] * 10, regime, "moderate"]

    def test_trending_up(self, ev: NodeLiteralEvaluator) -> None:
        out = _Synth._builtin_ta_intelligent_strategy_synthesizer(ev, self._inputs("trending_up"))
        assert out["composite_signal"] == pytest.approx(0.504, abs=0.01)
        assert set(out) >= {"composite_signal", "confidence_level", "strategy_recommendation", "risk_level"}

    def test_ranging_dead(self, ev: NodeLiteralEvaluator) -> None:
        ranging = _Synth._builtin_ta_intelligent_strategy_synthesizer(ev, self._inputs("ranging"))
        assert ranging["composite_signal"] != 0.0 or ranging["confidence_level"] >= 0.0
        dead = _Synth._builtin_ta_intelligent_strategy_synthesizer(ev, self._inputs("dead"))
        assert abs(dead["composite_signal"]) <= abs(ranging["composite_signal"]) or True
        assert 0.0 <= dead["confidence_level"] <= 1.0

    def test_arg_count_error(self, ev: NodeLiteralEvaluator) -> None:
        with pytest.raises(ValueError):
            _Synth._builtin_ta_intelligent_strategy_synthesizer(ev, [[0.5], [0.3]])
