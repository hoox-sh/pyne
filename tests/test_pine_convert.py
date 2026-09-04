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
from pynescript.util.pine_convert import convert_v5_to_v6
from pynescript.util.pine_convert import convert_v6_to_v5


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
