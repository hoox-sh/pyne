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

"""The CLI carries the (c) / (tm) attribution notice.

The notice is printed by the bare banner, appended to ``--help``, and exposed
as ``notice`` in ``pyne info`` / ``pyne info --json``.
"""

from __future__ import annotations

import json
import re

from click.testing import CliRunner

from pynescript.__main__ import _NOTICE
from pynescript.__main__ import cli


_NOTICE_RE = re.compile(r"jango_blockchained.*Pine Script™?.*TradingView", re.IGNORECASE | re.DOTALL)


def test_help_prints_notice() -> None:
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert _NOTICE in result.output or _NOTICE_RE.search(result.output)


def test_bare_invocation_prints_notice() -> None:
    # Bare `pyne` prints banner + help epilog; both must carry the notice.
    result = CliRunner().invoke(cli, [])
    assert result.exit_code == 0
    assert _NOTICE in result.output or _NOTICE_RE.search(result.output)


def test_info_prints_notice_plain_and_json() -> None:
    runner = CliRunner()
    plain = runner.invoke(cli, ["info"])
    assert plain.exit_code == 0
    assert _NOTICE in plain.output or _NOTICE_RE.search(plain.output)

    as_json = runner.invoke(cli, ["info", "--json"])
    assert as_json.exit_code == 0
    payload = json.loads(as_json.output)
    assert payload.get("notice") == _NOTICE
