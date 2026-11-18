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

"""Pine's retired 4,096-character string cap is not enforced.

August 2025 raised TradingView's maximum to 40,960 encoded characters.
Nothing in the evaluator or the linter implements either bound. These
tests pin acceptance past 4,096. They do not add a 40,960 ceiling.
"""

from __future__ import annotations

from pynescript.ast import helper
from pynescript.ast.linter import lint_script


# One past the retired cap, and one past the August 2025 figure. Neither
# number is a limit this runtime enforces.
PAST_OLD_CAP = 4096 + 1
PAST_NEW_FIGURE = 40960 + 1


def _length_of_literal(char: str, count: int) -> str:
    return 'str.length("' + (char * count) + '")'


def test_literal_longer_than_4096_is_accepted() -> None:
    """A 4,097-character literal evaluates; the old cap must not reject it."""
    assert helper.literal_eval(_length_of_literal("a", PAST_OLD_CAP)) == PAST_OLD_CAP


def test_repeat_longer_than_4096_is_accepted() -> None:
    """A computed string past 4,096 is accepted, not only a source literal."""
    expr = f'str.length(str.repeat("a", {PAST_OLD_CAP}))'
    assert helper.literal_eval(expr) == PAST_OLD_CAP


def test_no_40960_cap_is_enforced() -> None:
    """40,961 characters succeed because no ceiling is modeled.

    If a cap is added later, this assertion is the one that must change.
    Do not treat a failure here as a reason to invent the cap in the same change.
    """
    assert helper.literal_eval(_length_of_literal("b", PAST_NEW_FIGURE)) == PAST_NEW_FIGURE


def test_linter_does_not_enforce_a_string_length_cap() -> None:
    """Lint may warn that a long line exceeds 120 characters. That is not a string cap."""
    short = f'//@version=6\nindicator("long string")\nplot(str.length(str.repeat("a", {PAST_OLD_CAP})))\n'
    literal = "//@version=6\n" + 'indicator("' + ("a" * PAST_OLD_CAP) + '")\n'
    findings = (*lint_script(short), *lint_script(literal))
    assert findings
    assert any(item.code == "C002" for item in findings)
    for item in findings:
        text = f"{item.code} {item.message}".lower()
        assert item.code != "E001"
        assert "4096" not in text
        assert "4,096" not in text
        assert "40960" not in text
        assert "40,960" not in text
        assert "maximum length" not in text
