# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

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
