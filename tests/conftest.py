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

"""Pytest configuration for the pynescript test suite.

Provides optional ``--example-scripts-dir`` and parametrizes
``pinescript_filepath`` for corpus-style parse/unparse tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest import Metafunc
from pytest import Parser


tests_dir = Path(__file__).parent
# Optional local-only example dir (not shipped). Prefer tests/fixtures for CI.
default_example_scripts_dir = tests_dir / "data" / "examples"


def pytest_addoption(parser: Parser):
    parser.addoption(
        "--example-scripts-dir",
        default=default_example_scripts_dir,
        type=Path,
        help="Optional directory of *.pine files for pinescript_filepath parametrization (not shipped).",
    )


def pytest_generate_tests(metafunc: Metafunc):
    if "pinescript_filepath" not in metafunc.fixturenames:
        return
    example_scripts_dir: Path = metafunc.config.getoption("--example-scripts-dir")
    pinescript_filepaths: list[Path] = []
    if example_scripts_dir.is_dir():
        pinescript_filepaths = sorted(example_scripts_dir.glob("*.pine"))
    if not pinescript_filepaths:
        # Avoid empty parametrize collection errors when no third-party corpus is present.
        metafunc.parametrize(
            "pinescript_filepath",
            [
                pytest.param(
                    None,
                    marks=pytest.mark.skip(
                        reason="no example *.pine scripts shipped (use --example-scripts-dir for local suites)"
                    ),
                )
            ],
            ids=["no-example-scripts"],
        )
        return
    metafunc.parametrize(
        argnames="pinescript_filepath",
        argvalues=pinescript_filepaths,
        ids=[path.name for path in pinescript_filepaths],
    )
