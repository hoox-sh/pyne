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

"""v5 ↔ v6 source conversion (roadmap L1)."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from pynescript.__main__ import cli
from pynescript.ast.helper import parse
from pynescript.util.pine_convert import convert_pine
from pynescript.util.pine_convert import convert_to_v6
from pynescript.util.pine_convert import convert_v5_to_v6
from pynescript.util.pine_convert import convert_v6_to_v5
from pynescript.util.pine_convert import detect_version


V5 = """//@version=5
study("x")
s = security("BINANCE:BTCUSDT", "D", close)
plot(s)
"""

V6 = """//@version=6
indicator("x")
s = request.security("BINANCE:BTCUSDT", "D", close)
plot(s)
"""


def test_v5_to_v6_rewrites_study_security_and_version() -> None:
    out = convert_v5_to_v6(V5)
    assert "//@version=6" in out
    assert "indicator(" in out
    assert "study(" not in out
    assert "request.security(" in out
    assert "request.request." not in out
    parse(out)


def test_v6_to_v5_keeps_indicator_strips_request_prefix() -> None:
    out = convert_v6_to_v5(V6)
    assert "//@version=5" in out
    assert "indicator(" in out
    assert "request.security(" not in out
    assert "security(" in out
    parse(out)


def test_does_not_rewrite_comments_or_strings() -> None:
    src = """//@version=5
indicator("x")
// security(sym, tf, close) leftover docs
plot("security(")
"""
    out = convert_v5_to_v6(src)
    assert "// security(sym, tf, close) leftover docs" in out
    assert 'plot("security(")' in out
    assert out.count("request.security") == 0


def test_security_lower_tf_not_partial() -> None:
    src = '//@version=5\nindicator("x")\nv = security_lower_tf(syminfo.tickerid, "1", close)\n'
    out = convert_v5_to_v6(src)
    assert "request.security_lower_tf(" in out
    assert "request.security(" not in out


def test_roundtrip_request_names() -> None:
    src = '//@version=5\nindicator("x")\na = financial("NASDAQ:AAPL", "FY", "NET_INCOME")\n'
    v6 = convert_pine(src, to=6)
    v5 = convert_pine(v6, to=5)
    assert "request.financial(" in v6
    assert "request.financial(" not in v5
    assert "financial(" in v5


def test_cli_convert_to_v6(tmp_path: Path) -> None:
    p = tmp_path / "s.pine"
    p.write_text(V5, encoding="utf-8")
    r = CliRunner().invoke(cli, ["convert", str(p), "--to", "6"])
    assert r.exit_code == 0, r.output
    assert "request.security(" in r.output
    assert "//@version=6" in r.output


def test_detect_version_missing_is_none() -> None:
    assert detect_version("study('x')\nplot(close)\n") is None
    assert detect_version("//@version=4\nstudy('x')\n") == 4


def test_v4_to_v6_namespaces_and_indicator() -> None:
    src = """//@version=4
study("x")
s = sma(close, 14)
h = security(tickerid, "D", close)
plot(s)
"""
    out = convert_to_v6(src)
    assert "//@version=6" in out
    assert "indicator(" in out
    assert "study(" not in out
    assert "ta.sma(" in out
    assert "request.security(" in out
    assert "syminfo.tickerid" in out
    assert "request.request." not in out
    parse(out)


def test_v3_to_v6_colors_bar_index_and_ta() -> None:
    src = """//@version=3
study("old")
len = input(14, type=integer)
s = sma(close, len)
plot(s, color=red, style=line)
bgcolor(n == 0 ? green : na)
"""
    out = convert_to_v6(src)
    assert "//@version=6" in out
    assert "indicator(" in out
    assert "input.int(" in out
    assert "ta.sma(" in out
    assert "color.red" in out
    assert "plot.style_line" in out
    assert "bar_index" in out
    assert "color.green" in out
    parse(out)


def test_v1_missing_pragma_inserts_indicator() -> None:
    src = "plot(close)\n"
    out = convert_to_v6(src)
    assert out.startswith("//@version=6")
    assert 'indicator("Converted")' in out
    assert "plot(close)" in out
    parse(out)


def test_iff_and_offset_rewrite() -> None:
    src = """//@version=4
study("x")
v = iff(close > open, offset(close, 1), open)
plot(v)
"""
    out = convert_to_v6(src)
    assert "iff(" not in out
    assert "offset(" not in out
    assert "close[1]" in out
    assert "?" in out
    parse(out)


def test_tostring_math_and_heikinashi() -> None:
    src = """//@version=4
study("x")
t = heikinashi(tickerid("BINANCE", "BTCUSDT"))
s = tostring(close)
m = abs(close - open)
plot(close)
"""
    out = convert_to_v6(src)
    assert "ticker.heikinashi(" in out
    assert "ticker.new(" in out
    assert "str.tostring(" in out
    assert "math.abs(" in out
    parse(out)


def test_does_not_prefix_udf_defs_or_params() -> None:
    src = """//@version=4
study("x")
hma(src, len) => wma(src, len)
minimax(X, p, min, max) => max - min
[rsi, dev] = rsi(close, 14)
plot(hma(close, 9))
"""
    out = convert_to_v6(src)
    assert "hma(src, len) =>" in out
    assert "ta.wma(" in out
    assert "minimax(X, p, min, max) =>" in out
    assert "[rsi, dev] =" in out
    assert "ta.rsi(" in out
    parse(out)


def test_v6_is_idempotent() -> None:
    src = """//@version=6
indicator("x")
plot(ta.sma(close, 14))
"""
    out = convert_to_v6(src)
    assert out == src
    assert convert_pine(src, to=6) == src


def test_does_not_double_prefix_namespaces() -> None:
    src = """//@version=5
indicator("x")
plot(ta.sma(close, 14), color=color.red)
"""
    out = convert_to_v6(src)
    assert "ta.ta." not in out
    assert "color.color." not in out
    assert "ta.sma(" in out
    parse(out)
