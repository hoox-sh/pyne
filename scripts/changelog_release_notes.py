#!/usr/bin/env python3
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

"""Extract a Keep a Changelog section for GitHub Release notes.

Tag publish must already have moved ``## [Unreleased]`` into ``## [X.Y.Z]``.
The matching heading (em dash or hyphen date suffix) is copied through the
next ``## [`` heading.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def normalize_version(version: str) -> str:
    """Strip a leading ``v`` so ``v0.6.13`` matches ``## [0.6.13]``."""
    raw = version.strip()
    if raw.lower().startswith("v") and raw[1:2].isdigit():
        return raw[1:]
    return raw


def extract_changelog_section(text: str, version: str) -> str:
    """Return the ``## [version]`` section, including the heading.

    Raises:
        ValueError: when that heading is missing (Unreleased was not moved).
    """
    ver = normalize_version(version)
    if not ver:
        raise ValueError("version is empty")
    if ver.lower() == "unreleased":
        raise ValueError(
            "CHANGELOG.md has no ## [Unreleased] section as a release. "
            "Move ## [Unreleased] into ## [X.Y.Z] before tagging."
        )
    heading = re.compile(rf"^## \[{re.escape(ver)}\](?:\s|[—–-]|$)")
    lines = text.splitlines(keepends=True)
    start: int | None = None
    for i, line in enumerate(lines):
        if heading.match(line):
            start = i
            break
    if start is None:
        raise ValueError(
            f"CHANGELOG.md has no ## [{ver}] section. Move ## [Unreleased] into that heading before tagging."
        )
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## ["):
            end = j
            break
    body = "".join(lines[start:end]).strip()
    if not body:
        raise ValueError(f"CHANGELOG.md section ## [{ver}] is empty")
    return body + "\n"


def build_release_notes(changelog: str, version: str, *, install: bool = True) -> str:
    """Changelog section first, then optional install/binary how-to."""
    ver = normalize_version(version)
    notes = extract_changelog_section(changelog, ver)
    if not install:
        return notes
    return (
        notes
        + "\n---\n\n"
        + f"## Install (Python package / CLI)\n\n"
        + "```bash\n"
        + f'pip install "hoox-pyne=={ver}"\n'
        + "# with LSP:\n"
        + f'pip install "hoox-pyne[lsp]=={ver}"\n'
        + "# with Numba compile path:\n"
        + f'pip install "hoox-pyne[compile]=={ver}"\n'
        + "pynescript --help\n"
        + "pynescript info\n"
        + "```\n\n"
        + "Wheel/sdist are attached to this release if PyPI is not yet available:\n"
        + "```bash\n"
        + "pip install ./hoox_pyne-*.whl\n"
        + "```\n\n"
        + "### Standalone CLI binaries\n"
        + "- `pynescript-cli-linux-x86_64` — Linux CLI\n"
        + "- `pynescript-cli-windows-x86_64.exe` — Windows CLI\n"
        + "- `pynescript-cli-macos-arm64` — macOS ARM CLI\n\n"
        + "### Language Server binaries\n"
        + "- `pynescript-lsp-linux-x86_64` — Linux LSP\n"
        + "- `pynescript-lsp-windows-x86_64.exe` — Windows LSP\n"
        + "- `pynescript-lsp-macos-arm64` — macOS ARM LSP\n"
        + "- `pyne-vscode-*.vsix` — VS Code / Open VSX extension (`hoox-sh.pyne`)\n"
    )


def main(argv: list[str] | None = None) -> int:
    """CLI: write GitHub Release notes from CHANGELOG.md."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="X.Y.Z or vX.Y.Z")
    parser.add_argument(
        "--changelog",
        default="CHANGELOG.md",
        type=Path,
        help="Keep a Changelog path",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write notes here (default: stdout)",
    )
    parser.add_argument(
        "--no-install",
        action="store_true",
        help="Omit the install/binary appendix",
    )
    args = parser.parse_args(argv)
    text = args.changelog.read_text(encoding="utf-8")
    try:
        notes = build_release_notes(text, args.version, install=not args.no_install)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    if args.out is not None:
        args.out.write_text(notes, encoding="utf-8")
    else:
        sys.stdout.write(notes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
