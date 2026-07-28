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

"""Normalize copyright/license headers across the pynescript project.

Sole author: jango_blockchained
License: AGPL-3.0-or-later

Removes fictional co-authors, LGPL banners, proprietary stubs, and
orphan mid-header remnants from prior runs.
"""

from __future__ import annotations

import re
import sys

from pathlib import Path


AUTHOR = "jango_blockchained"
YEARS = "2024-2026"
SPDX = "AGPL-3.0-or-later"
PROJECT = "pynescript"

SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "_build",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "test-results",
    ".opencode",
    ".private",
    "coverage",
    "htmlcov",
}

SKIP_PATH_PARTS = (
    "tests/data/",
    "node_modules/",
    "frontend/test-results/",
)

PYTHON_HEADER = f"""\
# Copyright (C) {YEARS} {AUTHOR}
#
# This file is part of {PROJECT}.
#
# {PROJECT} is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# {PROJECT} is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with {PROJECT}.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: {SPDX}
"""

C_STYLE_HEADER = f"""\
// Copyright (C) {YEARS} {AUTHOR}
//
// This file is part of {PROJECT}.
//
// {PROJECT} is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// {PROJECT} is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with {PROJECT}.  If not, see <https://www.gnu.org/licenses/>.
//
// SPDX-License-Identifier: {SPDX}
"""

SHORT_HASH_HEADER = f"""\
# Copyright (C) {YEARS} {AUTHOR}
# SPDX-License-Identifier: {SPDX}
"""

# A comment line that is part of (or remnant of) a license/copyright banner.
# Intentionally unanchored so mid-header leftovers still match.
LICENSE_COMMENT_BODY = re.compile(
    r"""(?ix)
    (
        copyright\b|
        spdx-license-identifier|
        licensed\ under|
        all\ rights\ reserved|
        proprietary\ information|
        use\ is\ subject\ to\ license|
        free\ software\ foundation|
        free\ software:|
        gnu\ (lesser\ |affero\ )?general\ public|
        lesser\ general\ public|
        affero\ general\ public|
        general\ public\ license|
        without\ any\ warranty|
        MERCHANTABILITY|
        FITNESS\ FOR\ A\ PARTICULAR|
        you\ should\ have\ received|
        along\ with\ pynescript|
        along\ with\ this\ program|
        see\ the\ (gnu\ )?(lesser\ |affero\ )?general|
        see\ <https?://www\.gnu\.org|
        https?://www\.gnu\.org/licenses|
        unless\ required\ by\ applicable|
        distributed\ under\ the\ license|
        ["']AS\ IS["']|
        AS\ IS.?BASIS|
        either\ version\ \d+|
        \(at\ your\ option\)|
        this\ file\ is\ part\ of|
        pynescript\ is\ (free\ software|distributed)|
        yunseong|
        jango[_-]blockchained|
        you\ may\ not\ use\ this\ file|
        you\ may\ obtain\ a\ copy|
        compliance\ with\ the\ license|
        limitations\ under\ the\ license|
        without\ warranties\ or\ conditions|
        either\ express\ or\ implied|
        specific\ language\ governing|
        under\ the\ terms\ of\ the\ gnu|
        it\ under\ the\ terms|
        the\ free\ software\ foundation,\ either|
        \(the\ "license"\)|
        license\ terms|
        \bLGPL\b|
        \bAGPL-3\.0
    )
    """
)


def get_header(path: Path) -> str | None:
    suffix = path.suffix.lower()
    name = path.name
    if suffix == ".py":
        return PYTHON_HEADER
    if suffix in {".g4", ".ts", ".tsx", ".js", ".jsx"}:
        return C_STYLE_HEADER
    if suffix in {".md", ".mdx"}:
        return PYTHON_HEADER
    if (
        suffix in {".yml", ".yaml", ".sh"}
        or name
        in {
            "Makefile",
            "Dockerfile",
            "Dockerfile.api",
            "cloudbuild.yaml",
            "docker-compose.yml",
            "docker-compose.yaml",
        }
        or name.startswith("Dockerfile")
    ):
        return SHORT_HASH_HEADER
    return None


def should_skip(path: Path, root: Path) -> bool:
    try:
        rel = path.relative_to(root).as_posix()
    except ValueError:
        return True
    if any(part in SKIP_DIR_NAMES for part in path.parts):
        return True
    if any(seg in rel for seg in SKIP_PATH_PARTS):
        return True
    if rel in {"LICENSE", "COPYING"}:
        return True
    return False


def _line_style(line: str) -> str | None:
    s = line.lstrip()
    if s.startswith("#") and not s.startswith("#!"):
        return "hash"
    if s.startswith("//"):
        return "slash"
    return None


def _comment_text(line: str, style: str) -> str | None:
    if style == "hash":
        if line.lstrip().startswith("#!"):
            return None
        if line.startswith("#") or line.lstrip().startswith("#"):
            # allow indented? we don't
            if line.startswith("#"):
                return line[1:].strip()
        if line.strip() == "":
            return ""
        return None
    if style == "slash":
        s = line.lstrip()
        if s.startswith("//"):
            return s[2:].strip()
        if line.strip() == "":
            return ""
        return None
    return None


def extract_shebang_and_coding(lines: list[str]) -> tuple[list[str], list[str]]:
    """Pull shebang/coding from the first ~60 lines; return (prefix, remaining)."""
    prefix: list[str] = []
    remaining: list[str] = []
    coding_re = re.compile(r"^#.*coding[:=]")
    for i, line in enumerate(lines):
        if line.startswith("#!") and not prefix:
            prefix.append(line)
            continue
        if coding_re.match(line) and len(prefix) <= 1:
            prefix.append(line)
            continue
        remaining.append(line)
    # If shebang was after content, we already moved it only when seen first...
    # Second pass: shebang buried after old headers
    if not prefix:
        new_remaining: list[str] = []
        for line in remaining:
            if line.startswith("#!") and not prefix:
                prefix.append(line)
                continue
            if coding_re.match(line) and len(prefix) == 1:
                prefix.append(line)
                continue
            new_remaining.append(line)
        remaining = new_remaining
    return prefix, remaining


def is_license_comment_line(line: str) -> bool:
    style = _line_style(line)
    if style is None:
        if line.strip() == "":
            return False  # blanks handled by caller
        return False
    text = _comment_text(line, style)
    if text is None:
        return False
    if text == "":
        return False
    return bool(LICENSE_COMMENT_BODY.search(text))


def strip_leading_license_blocks(lines: list[str]) -> list[str]:
    """Remove all leading license/copyright comment blocks and their blanks."""
    i = 0
    n = len(lines)

    def skip_blanks(idx: int) -> int:
        while idx < n and lines[idx].strip() == "":
            idx += 1
        return idx

    # Repeatedly strip license blocks that appear at the top
    while i < n:
        i = skip_blanks(i)
        if i >= n:
            break

        # HTML comment license
        if lines[i].lstrip().startswith("<!--"):
            block = []
            j = i
            while j < n:
                block.append(lines[j])
                if "-->" in lines[j]:
                    j += 1
                    break
                j += 1
            blob = "".join(block)
            if any(
                m in blob
                for m in ("Copyright", "SPDX", "License", "jango", "Yunseong", "AGPL", "LGPL")
            ):
                i = j
                continue
            break

        # Block comment /* ... */
        if lines[i].lstrip().startswith("/*"):
            j = i
            while j < n and "*/" not in lines[j]:
                j += 1
            if j < n:
                j += 1
            blob = "".join(lines[i:j])
            if "Copyright" in blob or "SPDX" in blob or "License" in blob:
                i = j
                continue
            break

        style = _line_style(lines[i])
        if style is None:
            break

        # Must start a license-ish comment (or be orphan remnant)
        if not is_license_comment_line(lines[i]) and "Copyright" not in lines[i]:
            break

        j = i
        saw_license = False
        while j < n:
            if lines[j].strip() == "":
                # peek ahead: more license comments?
                k = j + 1
                while k < n and lines[k].strip() == "":
                    k += 1
                if k < n and is_license_comment_line(lines[k]):
                    j = k
                    continue
                # end of block
                j += 1
                break

            if _line_style(lines[j]) != style and _line_style(lines[j]) is not None:
                # style switch mid-banner (unlikely)
                if is_license_comment_line(lines[j]):
                    j += 1
                    saw_license = True
                    continue
                break

            if is_license_comment_line(lines[j]) or lines[j].strip() in {"#", "//"}:
                saw_license = True
                j += 1
                if j - i > 50:
                    break
                continue

            # Non-license comment → stop before it (keep it)
            break

        if not saw_license:
            break
        i = j

    return lines[i:]


def update_file(path: Path) -> str:
    header = get_header(path)
    if not header:
        return "skipped"

    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return f"error:{exc}"

    if not content.strip():
        return "skipped"

    # Normalize newlines for processing; preserve final newline
    had_final_nl = content.endswith("\n")
    lines = content.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n") and had_final_nl is False:
        pass

    prefix, body_lines = extract_shebang_and_coding(lines)
    body_lines = strip_leading_license_blocks(body_lines)

    # Drop leading blanks before real content
    while body_lines and body_lines[0].strip() == "":
        body_lines.pop(0)

    rest = "".join(body_lines)
    updated = "".join(prefix) + header + "\n" + rest
    if had_final_nl and not updated.endswith("\n"):
        updated += "\n"

    if updated == content:
        return "unchanged"

    path.write_text(updated, encoding="utf-8")
    return "updated"


def find_candidates(root: Path) -> list[Path]:
    allowed_prefixes = (
        "src/",
        "tests/",
        "examples/",
        "backend/",
        "scripts/",
        "docs/",
        "pine-worker/src/",
        "pine-worker/scripts/",
        "pine-worker/test/",
        "vscode-extension/src/",
        "frontend/worker/src/",
        "frontend/src/",
        "Makefile",
        "Dockerfile",
        "Dockerfile.api",
        "cloudbuild.yaml",
        "docker-compose.yml",
        "docker-compose.yaml",
    )
    found: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if should_skip(path, root):
            continue
        rel = path.relative_to(root).as_posix()
        if not any(rel == p or rel.startswith(p) for p in allowed_prefixes):
            continue
        if get_header(path) is None:
            continue
        if path.name in {"package.json", "package-lock.json", "tsconfig.json"}:
            continue
        found.append(path)
    return sorted(found)


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    selected = find_candidates(root)
    counts = {"updated": 0, "unchanged": 0, "skipped": 0, "error": 0}
    for path in selected:
        status = update_file(path)
        if status.startswith("error:"):
            counts["error"] += 1
            print(f"ERROR {path.relative_to(root)}: {status}")
        else:
            counts[status] = counts.get(status, 0) + 1
            if status == "updated":
                print(f"updated {path.relative_to(root)}")

    print(
        f"\nDone: {counts.get('updated', 0)} updated, "
        f"{counts.get('unchanged', 0)} unchanged, "
        f"{counts.get('skipped', 0)} skipped, "
        f"{counts.get('error', 0)} errors "
        f"(of {len(selected)} candidates)"
    )
    return 1 if counts.get("error", 0) else 0


if __name__ == "__main__":
    sys.exit(main())
