# Copyright (C) 2024-2026 jango_blockchained
#
# This file is part of pynescript.
#
# pynescript is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pynescript is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Round 9 residual parity: stoch slot stability + Heikin-Ashi security."""

from __future__ import annotations

from backend.runtime import Runtime


def _bars(n: int = 200) -> list[dict]:
    bars: list[dict] = []
    price = 100.0
    for i in range(n):
        o = round(price, 2)
        c = round(price + (1.0 if i % 3 else -0.5), 2)
        h = round(max(o, c) + 0.8, 2)
        lo = round(min(o, c) - 0.8, 2)
        bars.append(
            {
                "open": o,
                "high": h,
                "low": max(lo, 0.01),
                "close": c,
                "time": 1_000_000 + i * 86_400_000,
                "volume": 1000.0 + i,
            }
        )
        price = c
    return bars


class TestStochSlotDoesNotStealEmaSeed:
    def test_ema_after_stoch_on_rsi(self) -> None:
        """stoch must always consume a TA slot even when rsi is still na."""
        src = """//@version=4
study("t")
src = input(close)
rsi1 = rsi(src, 14)
k = stoch(rsi1, rsi1, rsi1, 14)
plot(ema(close, 200), "e")
plot(k, "k")
"""
        r = Runtime().run(src, _bars(200), mode="interpret")
        assert "error" not in r, r.get("error")
        e = r["series"]["e"]
        assert sum(1 for x in e if x is not None) >= 1
        assert e[-1] is not None
        assert abs(float(e[-1]) - 149.7475) < 1e-2


class TestHeikinAshiSecurityParity:
    def test_ha_security_tuple_interp_compile(self) -> None:
        src = """//@version=5
indicator("t")
[haopen, haclose, hahigh,halow] = request.security(
     ticker.heikinashi(syminfo.tickerid), timeframe.period, [open, close, high, low])
plot(haopen, "o")
plot(haclose, "c")
plot(hahigh, "h")
plot(halow, "l")
"""
        bars = _bars(40)
        ri = Runtime().run(src, bars, mode="interpret")
        rc = Runtime().run(src, bars, mode="compile")
        assert "error" not in ri and "error" not in rc
        for key in ("o", "c", "h", "l"):
            si, sc = ri["series"][key], rc["series"][key]
            assert len(si) == len(sc) == len(bars)
            for a, b in zip(si, sc, strict=True):
                assert a is not None and b == b  # not nan
                assert abs(float(a) - float(b)) < 1e-6

    def test_corpus_ha_ssl_strategy_parity(self) -> None:
        from pathlib import Path

        path = Path("tests/data/set01/strategies/045_str_ha_univlong_and_short_futures.pine")
        if not path.is_file():
            return
        import importlib.util
        from pathlib import Path as P

        root = P(".").resolve()
        spec = importlib.util.spec_from_file_location("h", root / "scripts" / "compare_interp_compile.py")
        assert spec and spec.loader
        h = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(h)
        r = h.run_one_script(str(path.resolve()), 200, ignore_hline_keys=True, ignore_fill_keys=True)
        assert r["status"] in ("OK", "fill_background_only", "both_error_same", "expected_error"), r


class TestStochRsiSupertrendCorpus:
    def test_strategy_073_parity(self) -> None:
        from pathlib import Path
        import importlib.util

        path = Path("tests/data/set01/strategies/073_str_stochrsi_plus_supertrend_strategy.pine")
        if not path.is_file():
            return
        root = Path(".").resolve()
        spec = importlib.util.spec_from_file_location("h", root / "scripts" / "compare_interp_compile.py")
        assert spec and spec.loader
        h = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(h)
        r = h.run_one_script(str(path.resolve()), 200, ignore_hline_keys=True, ignore_fill_keys=True)
        assert r["status"] in ("OK", "fill_background_only"), r


class TestTypedFloatArrayRingBuffer:
    def test_bbi_style_ring_matches_compile(self) -> None:
        src = """//@version=6
indicator("t")
f(series float source, simple int p) =>
    var array<float> buf = array.new_float(p, na)
    var int head = 0
    var float sum = 0.0
    var int cnt = 0
    float val = nz(source)
    float old = array.get(buf, head)
    if not na(old)
        sum -= old
    else
        cnt += 1
    sum += val
    array.set(buf, head, val)
    head := (head + 1) % p
    sum / math.max(1, cnt)
plot(f(close, 3), "s")
plot(ta.sma(close, 3), "sma")
"""
        bars = _bars(30)
        ri = Runtime().run(src, bars, mode="interpret")
        rc = Runtime().run(src, bars, mode="compile")
        assert "error" not in ri and "error" not in rc
        for i in range(2, 30):
            assert abs(float(ri["series"]["s"][i]) - float(rc["series"]["s"][i])) < 1e-6
            assert abs(float(ri["series"]["s"][i]) - float(ri["series"]["sma"][i])) < 1e-6


class TestUdfCallSiteSeriesIsolation:
    def test_multi_kahlman_sites_match_compile(self) -> None:
        src = """//@version=4
study("t")
kahlman(x, g) =>
    kf = 0.0
    dk = x - nz(kf[1], x)
    smooth = nz(kf[1], x) + dk * sqrt(g * 2)
    velo = 0.0
    velo := nz(velo[1], 0) + (g * dk)
    kf := smooth + velo
    kf
plot(kahlman(close, 0.7), "kc")
plot(kahlman(hl2, 0.7), "kh")
"""
        bars = _bars(40)
        ri = Runtime().run(src, bars, mode="interpret")
        rc = Runtime().run(src, bars, mode="compile")
        assert "error" not in ri and "error" not in rc
        for k in ("kc", "kh"):
            for a, b in zip(ri["series"][k], rc["series"][k], strict=True):
                assert a is not None and b == b
                assert abs(float(a) - float(b)) < 1e-5


class TestVwapHlc3AndAnchor:
    def test_vwap_hlc3_and_anchor_parity(self) -> None:
        src = """//@version=6
indicator("t")
plot(ta.vwap(hlc3), "v1")
plot(ta.vwap(), "v0")
newDay = bar_index % 5 == 0
plot(ta.vwap(hlc3, newDay), "v2")
"""
        bars = _bars(25)
        ri = Runtime().run(src, bars, mode="interpret")
        rc = Runtime().run(src, bars, mode="compile")
        assert "error" not in ri and "error" not in rc
        for k in ("v1", "v0", "v2"):
            for a, b in zip(ri["series"][k], rc["series"][k], strict=True):
                assert abs(float(a) - float(b)) < 1e-6


class TestCallExprHistorySubscript:
    def test_time_session_prev_bar(self) -> None:
        src = """//@version=6
indicator("t")
wasInSession = not na(time(timeframe.period, "0930-1600", "America/New_York")[1])
nowInSession = not na(time(timeframe.period, "0930-1600", "America/New_York"))
sessionStart = nowInSession and not wasInSession
plot(wasInSession ? 1 : 0, "was")
plot(sessionStart ? 1 : 0, "ss")
"""
        bars = _bars(5)
        ri = Runtime().run(src, bars, mode="interpret")
        rc = Runtime().run(src, bars, mode="compile")
        assert ri["series"]["was"] == [0, 1, 1, 1, 1] or ri["series"]["was"][0] == 0
        assert ri["series"]["was"][1] == 1
        assert ri["series"]["ss"][0] == 1
        assert ri["series"]["ss"][1] == 0
        for a, b in zip(ri["series"]["was"], rc["series"]["was"], strict=True):
            assert abs(float(a) - float(b)) < 1e-9


class TestStrategyPositionHistory:
    def test_position_size_history_and_entry_viz(self) -> None:
        src = """//@version=6
strategy("t")
if bar_index == 0
    strategy.entry("S", strategy.short)
bool in_position = strategy.position_size != 0
bool new_position = strategy.position_size != 0 and strategy.position_size[1] == 0
bool pyramid_entry = in_position and not new_position and strategy.position_avg_price != strategy.position_avg_price[1]
bool exit_hit = strategy.position_size == 0 and strategy.position_size[1] != 0
bool show_viz = in_position and (new_position or pyramid_entry or not exit_hit[1])
plot(nz(strategy.position_size[1], -999), "sz1")
plot(pyramid_entry ? 1 : 0, "py")
plot(show_viz ? 1 : 0, "sv")
plot(show_viz ? strategy.position_avg_price : na, "pe")
"""
        bars = _bars(3)
        ri = Runtime().run(src, bars, mode="interpret")
        rc = Runtime().run(src, bars, mode="compile")
        assert "error" not in ri and "error" not in rc, (ri.get("error"), rc.get("error"))
        # Bar 0: no prior size → [1] is na; pyramid false; show_viz false → pe na
        assert ri["series"]["sz1"][0] == -999
        assert rc["series"]["sz1"][0] == -999.0
        assert ri["series"]["py"][0] == 0
        assert rc["series"]["py"][0] == 0.0
        assert ri["series"]["pe"][0] is None
        assert rc["series"]["pe"][0] is None or (
            isinstance(rc["series"]["pe"][0], float) and rc["series"]["pe"][0] != rc["series"]["pe"][0]
        )
        # Bar 1+: prior size available; pe tracks entry while short
        assert ri["series"]["sz1"][1] == -1.0
        assert rc["series"]["sz1"][1] == -1.0
        assert abs(float(ri["series"]["pe"][1]) - float(rc["series"]["pe"][1])) < 1e-9

    def test_multi_vwap_071_parity(self) -> None:
        from pathlib import Path
        import importlib.util

        path = Path("tests/data/set02/strategies/071_str_multi_vwap_crossover.pine")
        if not path.is_file():
            return
        root = Path(".").resolve()
        spec = importlib.util.spec_from_file_location("h", root / "scripts" / "compare_interp_compile.py")
        assert spec and spec.loader
        h = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(h)
        r = h.run_one_script(str(path.resolve()), 200, ignore_hline_keys=True, ignore_fill_keys=True)
        assert r["status"] in ("OK", "fill_background_only"), r


class TestCorpusResidualsParity:
    def test_hma_kahlman_245(self) -> None:
        from pathlib import Path
        import importlib.util

        path = Path("tests/data/set01/indicators/245_ind_hma_kahlman_trend_clipping_and_trendlines.pine")
        if not path.is_file():
            return
        root = Path(".").resolve()
        spec = importlib.util.spec_from_file_location("h", root / "scripts" / "compare_interp_compile.py")
        assert spec and spec.loader
        h = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(h)
        r = h.run_one_script(str(path.resolve()), 200, ignore_hline_keys=True, ignore_fill_keys=True)
        assert r["status"] in ("OK", "fill_background_only"), r

    def test_bbi_178(self) -> None:
        from pathlib import Path
        import importlib.util

        path = Path("tests/data/set02/indicators/178_ind_bulls_bears_index_bbi_2.pine")
        if not path.is_file():
            return
        root = Path(".").resolve()
        spec = importlib.util.spec_from_file_location("h", root / "scripts" / "compare_interp_compile.py")
        assert spec and spec.loader
        h = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(h)
        r = h.run_one_script(str(path.resolve()), 200, ignore_hline_keys=True, ignore_fill_keys=True)
        assert r["status"] in ("OK", "fill_background_only"), r
