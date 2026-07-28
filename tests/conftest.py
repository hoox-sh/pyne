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

from __future__ import annotations

from pathlib import Path

from pytest import Metafunc
from pytest import Parser


tests_dir = Path(__file__).parent
builtin_scripts_dir = tests_dir / "data" / "builtin_scripts"


def pytest_addoption(parser: Parser):
    parser.addoption("--example-scripts-dir", default=builtin_scripts_dir, type=Path)


def pytest_generate_tests(metafunc: Metafunc):
    if "pinescript_filepath" in metafunc.fixturenames:
        example_scripts_dir: Path = metafunc.config.getoption("--example-scripts-dir")
        pinescript_filepaths_iter = example_scripts_dir.glob("*.pine")
        pinescript_filepaths = list(pinescript_filepaths_iter)
        pinescript_filenames = [path.name for path in pinescript_filepaths]
        metafunc.parametrize(
            argnames="pinescript_filepath",
            argvalues=pinescript_filepaths,
            ids=pinescript_filenames,
        )
