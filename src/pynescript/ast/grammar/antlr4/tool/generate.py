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

import shutil
import subprocess
import sys

from pathlib import Path


def main():
    script_directory_path = Path(__file__).parent

    grammar_source_directory_path = script_directory_path / ".." / "resource"
    grammar_output_directory_path = script_directory_path / ".." / "generated"

    grammar_file_encoding = "utf-8"

    antlr4_executable = Path(sys.executable).parent / "antlr4"
    generate_grammar_command = [
        str(antlr4_executable),
        "-o",
        str(grammar_output_directory_path),
        "-lib",
        str(grammar_source_directory_path),
        "-encoding",
        grammar_file_encoding,
        "-listener",
        "-visitor",
        "-Dlanguage=Python3",
    ] + [str(p) for p in grammar_source_directory_path.glob("*.g4")]

    subprocess.check_call(generate_grammar_command)  # noqa: S603

    for filename in grammar_source_directory_path.glob("*.py"):
        shutil.copy(filename, grammar_output_directory_path)


if __name__ == "__main__":
    main()
