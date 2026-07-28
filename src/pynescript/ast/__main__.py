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

from pynescript.ast.helper import dump
from pynescript.ast.helper import parse


def main():
    import argparse

    parser = argparse.ArgumentParser(prog="python -m pynescript.ast")
    parser.add_argument(
        "infile",
        type=argparse.FileType(mode="rb"),
        nargs="?",
        default="-",
        help="the file to parse; defaults to stdin",
    )
    parser.add_argument(
        "-m",
        "--mode",
        default="exec",
        choices=("exec", "eval"),
        help="specify what kind of code must be parsed",
    )
    parser.add_argument(
        "--no-type-comments",
        default=True,
        action="store_false",
        help="don't add information about type comments",
    )
    parser.add_argument(
        "-a",
        "--include-attributes",
        action="store_true",
        help="include attributes such as line numbers and column offsets",
    )
    parser.add_argument("-i", "--indent", type=int, default=2, help="indentation of nodes (number of spaces)")
    args = parser.parse_args()

    with args.infile as infile:
        source = infile.read()

    tree = parse(source, args.infile.name, args.mode)
    print(dump(tree, include_attributes=args.include_attributes, indent=args.indent))  # noqa:T201


if __name__ == "__main__":
    main()
