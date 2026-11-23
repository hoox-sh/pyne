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

"""Audit a local Pine corpus for scrape truncation/chrome.

This is a local test-data hygiene tool. It never downloads anything and does
not touch TradingView endpoints. ``tests/data`` is gitignored and not shipped.

Usage::

    python scripts/audit_pine_corpus.py                 # report only
    python scripts/audit_pine_corpus.py --quarantine    # move bad files aside

Exit code is 1 when any issue is found, so a local pre-sweep can gate on it.
"""

# ruff: noqa: T201

from __future__ import annotations

import argparse
import json
import re
import shutil

from datetime import datetime
from datetime import timezone
from pathlib import Path


MARKER = re.compile(r"^\s*Expand\s*\((\d+)\s+lines?\)\s*$", re.I)
CHROME = re.compile(
    r"^>\s*(Detail|Last Modified|Author|Source|Tags?|Category|License|Created|Updated)\s*$",
    re.I,
)
SKIP_DIRS = {"_truncated", "_truncated_backup"}


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _claim(text: str) -> int | None:
    lines = text.splitlines()
    for line in reversed([ln.strip() for ln in lines if ln.strip()][-8:]):
        match = MARKER.match(line)
        if match:
            return int(match.group(1))
    return None


def _has_chrome(text: str) -> bool:
    return any(CHROME.match(line.strip()) for line in text.splitlines()[-40:])


def _has_docs_tail(text: str) -> bool:
    """A script code fence followed by markdown docs prose."""
    lines = text.splitlines()
    for i in range(max(0, len(lines) - 80), len(lines)):
        if lines[i].strip() != "```":
            continue
        tail = "\n".join(lines[i + 1 : i + 30])
        if re.search(r"^#{1,6}\s|^-\s+\*\*|https?://", tail, re.M):
            return True
    return False


def audit(root: Path) -> dict[str, object]:
    truncated: list[dict[str, object]] = []
    chrome: list[str] = []
    docs_pages: list[str] = []
    empty: list[str] = []
    total = 0
    for path in root.rglob("*.pine"):
        if SKIP_DIRS.intersection(path.parts):
            continue
        total += 1
        text = _read(path)
        rel = path.relative_to(root).as_posix()
        if not text.strip():
            empty.append(rel)
            continue
        claim = _claim(text)
        if claim is not None:
            truncated.append(
                {
                    "path": rel,
                    "claim": claim,
                    "actual": len(text.splitlines()),
                }
            )
        elif _has_chrome(text):
            chrome.append(rel)
        elif _has_docs_tail(text):
            docs_pages.append(rel)
    return {
        "generated": datetime.now(timezone.utc).isoformat(),
        "root": root.as_posix(),
        "files": total,
        "truncated": truncated,
        "chrome": chrome,
        "docs_pages": docs_pages,
        "empty": empty,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="tests/data", type=Path)
    parser.add_argument("--quarantine", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = audit(args.root)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"scanned: {result['files']}")
        print(f"truncated (Expand marker): {len(result['truncated'])}")
        print(f"trailing scrape chrome: {len(result['chrome'])}")
        print(f"docs pages with markdown tail (sanitizer handles): {len(result['docs_pages'])}")
        print(f"empty: {len(result['empty'])}")

    if args.quarantine:
        target = args.root / "_truncated"
        target.mkdir(exist_ok=True)
        for entry in result["truncated"]:  # type: ignore[assignment]
            rel = str(entry["path"])
            src = args.root / rel
            dst = target / (rel + ".truncated")
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
        for rel in result["empty"]:  # type: ignore[assignment]
            src = args.root / rel
            dst = target / (rel + ".empty")
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
        print(f"quarantined under {target}")

    issues = bool(result["truncated"] or result["chrome"] or result["empty"])
    raise SystemExit(1 if issues else 0)


if __name__ == "__main__":
    main()
