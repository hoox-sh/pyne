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

"""Source-level Pine Script v5 ↔ v6 conversion (roadmap L1).

Rewrites that are safe as text transforms (outside comments/strings):

* ``//@version=`` bump
* v4 leftover ``study(`` → ``indicator(`` (v5→v6)
* bare ``security(`` / ``financial(`` / … → ``request.*(`` (v5→v6)
* the reverse ``request.*(`` → bare names (v6→v5)

This is **not** a semantic migrator (bool-as-number, ``na`` tightening).
Those need a type checker, not a rewriter.
"""

from __future__ import annotations

import re

from collections.abc import Callable


_V5 = 5
_V6 = 6

_VERSION_RE = re.compile(r"(?m)^(?P<prefix>\s*//@version\s*=\s*)(?P<ver>\d+)\s*$")

# Longest names first so ``security_lower_tf`` wins over ``security``.
_REQUEST_FNS = (
    "security_lower_tf",
    "currency_rate",
    "financial",
    "economic",
    "dividends",
    "earnings",
    "splits",
    "quandl",
    "security",
    "seed",
)
_REQUEST_ALT = "|".join(re.escape(n) for n in _REQUEST_FNS)
_BARE_REQUEST_RE = re.compile(rf"(?<![\w.])({_REQUEST_ALT})\s*\(")
_NAMESPACED_REQUEST_RE = re.compile(rf"\brequest\.({_REQUEST_ALT})\s*\(")
_STUDY_RE = re.compile(r"\bstudy\s*\(")


def _map_code_spans(source: str, transform: Callable[[str], str]) -> str:
    """Apply *transform* to Pine code; leave comments and string literals alone."""
    ended_nl = source.endswith("\n")
    mapped = [_map_line(line, transform) for line in source.splitlines()]
    body = "\n".join(mapped)
    if ended_nl:
        body += "\n"
    return body


def _map_line(line: str, transform: Callable[[str], str]) -> str:
    pieces: list[str] = []
    code: list[str] = []
    in_str: str | None = None
    escape = False
    i = 0
    n = len(line)

    def flush_code() -> None:
        if code:
            pieces.append(transform("".join(code)))
            code.clear()

    while i < n:
        ch = line[i]
        if in_str is None:
            if ch == "/" and i + 1 < n and line[i + 1] == "/":
                flush_code()
                pieces.append(line[i:])
                return "".join(pieces)
            if ch in "\"'":
                flush_code()
                in_str = ch
                pieces.append(ch)
                i += 1
                continue
            code.append(ch)
            i += 1
            continue
        pieces.append(ch)
        if escape:
            escape = False
        elif ch == "\\":
            escape = True
        elif ch == in_str:
            in_str = None
        i += 1
    flush_code()
    return "".join(pieces)


def _set_version(source: str, version: int) -> str:
    if _VERSION_RE.search(source):
        return _VERSION_RE.sub(rf"\g<prefix>{version}", source, count=1)
    return f"//@version={version}\n{source}"


def convert_v5_to_v6(source: str) -> str:
    """Rewrite v5 (or v4 leftovers) toward v6 namespaces and ``indicator()``."""

    def code(span: str) -> str:
        span = _STUDY_RE.sub("indicator(", span)
        return _BARE_REQUEST_RE.sub(r"request.\1(", span)

    return _set_version(_map_code_spans(source, code), _V6)


def convert_v6_to_v5(source: str) -> str:
    """Rewrite v6 ``request.*`` calls back to bare v5 names; keep ``indicator()``."""

    def code(span: str) -> str:
        return _NAMESPACED_REQUEST_RE.sub(r"\1(", span)

    return _set_version(_map_code_spans(source, code), _V5)


def convert_pine(source: str, *, to: int) -> str:
    """Convert *source* toward Pine version *to* (5 or 6)."""
    if to == _V5:
        return convert_v6_to_v5(source)
    if to == _V6:
        return convert_v5_to_v6(source)
    msg = f"unsupported target version {to}; use 5 or 6"
    raise ValueError(msg)
