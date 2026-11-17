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

"""Pre-publish assertion for the sdist: no secrets, under PyPI's size limit.

Hatchling's sdist target packages the working tree, not the git tree, so a
gitignored local file (`.env`, `scripts/build/.metadata.key`, `.coverage`) is
shipped unless `pyproject.toml` excludes it. This guard is the second line of
defence: it fails before publish if a secret-bearing member or an oversized
archive reappears, instead of letting the defect return silently.

Usage:
    python scripts/build/assert_sdist_clean.py                # every dist/*.tar.gz
    python scripts/build/assert_sdist_clean.py dist/x.tar.gz  # explicit archive
    python scripts/build/assert_sdist_clean.py --list         # also dump members
    python scripts/build/assert_sdist_clean.py --max-mb 50    # tighter limit

Exits 0 and prints a PASS line when every archive is clean; exits 1 otherwise.
Stdlib only, so it runs anywhere a build can.
"""

from __future__ import annotations

import argparse
import fnmatch
import sys
import tarfile

from pathlib import Path


# PyPI rejects a file above 100 MB. Warehouse compares bytes, so use 100 MiB.
MAX_BYTES = 100 * 1024 * 1024

# Matched against the member's basename. Every pattern is either a credential or
# a local environment file that must never reach an index. `.env.example` is
# matched by `.env.*` on purpose: the guard treats the whole `.env*` family as a
# leak rather than trying to decide which variants are harmless.
SECRET_PATTERNS = (
    ".env",
    ".env.*",
    "*.key",
    "*.pem",
    "id_rsa",
    "*.metadata.key",
    ".coverage",
    ".coverage.*",
)


def basename(member: str) -> str:
    """Return the last path segment of an archive member."""
    return member.rstrip("/").rsplit("/", 1)[-1]


def is_secret(member: str) -> bool:
    """True when the member looks like a credential or local env file."""
    name = basename(member)
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in SECRET_PATTERNS)


def inspect(path: Path, max_bytes: int, show_members: bool) -> tuple[list[str], int, int]:
    """Return (problems, member_count, leak_count) for one archive."""
    problems: list[str] = []

    size = path.stat().st_size
    if size > max_bytes:
        problems.append(f"{path}: {size / 1048576:.1f} MiB exceeds the {max_bytes / 1048576:.0f} MB limit")

    with tarfile.open(path, "r:*") as archive:
        members = [member.name for member in archive.getmembers() if not member.isdir()]

    if show_members:
        for member in members:
            print(f"  {member}")

    leaks = [member for member in members if is_secret(member)]
    for member in leaks:
        problems.append(f"{path}: secret-bearing member: {member}")

    print(f"{path.name}: {size / 1048576:.2f} MiB, {len(members)} files, {len(leaks)} secret match(es)")
    return problems, len(members), len(leaks)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Assert an sdist carries no secrets and stays under the size limit.")
    parser.add_argument("archives", nargs="*", type=Path, help="sdist paths (default: dist/*.tar.gz)")
    parser.add_argument("--max-mb", type=float, default=MAX_BYTES / 1048576, help="size limit in MB (default: 100)")
    parser.add_argument("--list", action="store_true", help="print every archive member")
    args = parser.parse_args(argv)

    max_bytes = int(args.max_mb * 1048576)
    archives = args.archives or sorted(Path("dist").glob("*.tar.gz"))
    if not archives:
        print("FAIL no sdist found (looked for dist/*.tar.gz)", file=sys.stderr)
        return 1

    problems: list[str] = []
    for path in archives:
        if not path.is_file():
            problems.append(f"{path}: not a file")
            continue
        try:
            found, _count, _leaks = inspect(path, max_bytes, args.list)
        except (tarfile.TarError, OSError) as exc:
            problems.append(f"{path}: cannot read archive: {exc}")
            continue
        problems.extend(found)

    if problems:
        print(file=sys.stderr)
        for problem in problems:
            print(f"FAIL {problem}", file=sys.stderr)
        print(f"\nFAILED: {len(problems)} problem(s) across {len(archives)} archive(s)", file=sys.stderr)
        return 1

    print(
        f"PASS {len(archives)} sdist(s) clean: no .env*/*.key/*.pem/id_rsa/.coverage members, "
        f"all under {args.max_mb:g} MB"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
