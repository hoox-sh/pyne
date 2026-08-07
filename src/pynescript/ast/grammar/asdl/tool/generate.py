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

"""Generate ASDL-backed AST node modules for pynescript."""

from __future__ import annotations


import shutil
import subprocess
import sys

from pathlib import Path


def main():
    script_directory_path = Path(__file__).parent

    asdl_generate_script_path = script_directory_path / "asdlgen.py"

    asdl_source_directory_path = script_directory_path / ".." / "resource"
    asdl_source_path = asdl_source_directory_path / "Pinescript.asdl"
    asdl_output_directory_path = script_directory_path / ".." / "generated"
    asdl_output_path = asdl_output_directory_path / "PinescriptASTNode.py"

    generate_ast_nodes_command = [
        sys.executable,
        str(asdl_generate_script_path),
        str(asdl_source_path),
        "-o",
        str(asdl_output_path),
    ]

    subprocess.check_call(generate_ast_nodes_command)  # noqa: S603

    ruff = shutil.which("ruff")

    if ruff:
        format_ast_nodes_command = [
            ruff,
            "format",
            "--silent",
            str(asdl_output_path),
        ]

        subprocess.call(format_ast_nodes_command)  # noqa: S603

    for filename in asdl_source_directory_path.glob("*.py"):
        shutil.copy(filename, asdl_output_directory_path)


if __name__ == "__main__":
    main()
