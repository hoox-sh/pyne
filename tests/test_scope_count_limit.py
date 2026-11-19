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

"""Pine's retired 550-scope limit is not enforced.

February 2025 removed TradingView's cap on the number of local blocks in
one script (each ``if``, loop, ``switch``, or function body). Nothing in
the interpreter, compiler, or parser counts those blocks. These tests pin
acceptance past 550. They do not add a cap.

The compiler does not count nesting depth either. The retired limit was
the total number of local blocks, so the pin is successive ``if`` bodies,
each declaring its own local, rather than one chain 551 levels deep.
"""

from __future__ import annotations

import pytest

from pynescript.ast import node as ast
from pynescript.ast.helper import parse
from pynescript.ast.helper import walk
from pynescript.ast.linter import lint_script
from pynescript.runtime import Runtime


# One past the retired cap. This runtime does not enforce the number.
RETIRED_SCOPE_CAP = 550
PAST_OLD_CAP = RETIRED_SCOPE_CAP + 1

_BARS = [
    {
        "open": 1.0,
        "high": 2.0,
        "low": 0.5,
        "close": 1.5,
        "volume": 10.0,
        "time": 1_700_000_000,
    }
]


def _script(count: int) -> str:
    """``count`` successive ``if`` bodies. Each declares ``step``, a local scope."""
    lines = ["//@version=6", 'indicator("scopes")', "acc = 0"]
    for _ in range(count):
        lines.append("if true")
        lines.append("    step = 1")
        lines.append("    acc := acc + step")
    lines.append('plot(acc, "acc")')
    return "\n".join(lines) + "\n"


SRC = _script(PAST_OLD_CAP)


def _acc(mode: str) -> float:
    out = Runtime().run(SRC, _BARS, mode=mode)
    assert not out.get("error"), out.get("error")
    series = out["series"]["acc"]
    assert len(series) == 1
    return float(series[0])


def test_more_than_550_successive_local_scopes_run_on_both_hosts() -> None:
    """551 local ``if`` blocks parse and plot 551 on interpret and compile.

    A later cap must fail this test. Do not treat that failure as a reason
    to invent the cap in the same change. If one host cannot run the script,
    the other must fail the same way rather than return a shorter sum.
    """
    tree = parse(SRC)
    ifs = [node for node in walk(tree) if isinstance(node, ast.If)]
    assert len(ifs) == PAST_OLD_CAP
    assert _acc("interpret") == pytest.approx(float(PAST_OLD_CAP))
    assert _acc("compile") == pytest.approx(float(PAST_OLD_CAP))


def test_linter_does_not_enforce_a_scope_cap() -> None:
    """Lint may be silent. It must not report a scope-count error."""
    findings = lint_script(SRC)
    for item in findings:
        text = f"{item.code} {item.message}".lower()
        assert item.code != "E001"
        assert "550" not in text
        assert "too many local" not in text
        assert "scope limit" not in text
        assert "maximum number of scopes" not in text
