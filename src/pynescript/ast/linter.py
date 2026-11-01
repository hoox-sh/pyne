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

"""Lightweight static checks for Pine Script source.

Public API:

* :class:`LintWarning` — one finding (code, message, location, severity)
* :class:`PineLinter` — stateful linter; call :meth:`PineLinter.lint`
* :func:`lint_script` / :func:`lint_file` — one-shot helpers

Rules are heuristic (regex + :func:`~pynescript.ast.helper.parse` for syntax).
This is not a full type checker; see :mod:`pynescript.ast.type_system` for
type modeling used by the evaluator.

Rule code prefixes: ``E`` errors, ``W`` warnings (version/deprecated), ``C`` style.
"""

from __future__ import annotations

import re

from dataclasses import dataclass
from typing import Any

from pynescript.ast import parse
from pynescript.ast.helper import walk
from pynescript.ast.node import Arg
from pynescript.ast.node import Attribute
from pynescript.ast.node import Call
from pynescript.ast.node import Conditional
from pynescript.ast.node import Constant
from pynescript.ast.node import If
from pynescript.ast.node import Name
from pynescript.ast.node import While


_VERSION_PRAGMA_RE = re.compile(r"(?m)^[ \t]*//\s*@version\s*=\s*(\d+)")
_ASSIGN_OP_RE = re.compile(r"(?<![=!<>:])=(?!=|>)")
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")


def _trailing_ident_span(s: str) -> tuple[int, int] | None:
    """ASCII identifier at the end of ``s``, or ``None``.

    Linear scan (not ``[A-Za-z0-9_]*$``) so C001 never runs a user-controlled
    regex — CodeQL ``py/polynomial-redos``.
    """
    end = len(s)
    i = end
    while i > 0:
        c = s[i - 1]
        if ("A" <= c <= "Z") or ("a" <= c <= "z") or ("0" <= c <= "9") or c == "_":
            i -= 1
            continue
        break
    if i == end:
        return None
    first = s[i]
    if not (("A" <= first <= "Z") or ("a" <= first <= "z") or first == "_"):
        return None
    return i, end


def _detect_version(source: str) -> int | None:
    """Return the declared ``//@version=N``, or ``None`` when absent."""
    match = _VERSION_PRAGMA_RE.search(source)
    return int(match.group(1)) if match else None


def _mask_comments_and_strings(source: str, *, mask_strings: bool = True) -> str:
    """Return *source* with comments (and optionally strings) replaced by spaces.

    Newlines are preserved so line/column positions still line up with the
    original text. Used by regex-based lint rules (W101/C001) so prose in a
    comment or a URL in a string cannot produce a finding. W101 needs the
    quoted symbol argument, so it masks comments only.
    """
    if not source:
        return source
    out = list(source)
    i = 0
    n = len(source)
    while i < n:
        ch = source[i]
        if ch in "\"'":
            triple = source[i : i + 3]
            if triple in ('"""', "'''"):
                end = source.find(triple, i + 3)
                end = n if end < 0 else end + 3
                if mask_strings:
                    for j in range(i, end):
                        if out[j] != "\n":
                            out[j] = " "
                i = end
                continue
            quote = ch
            j = i + 1
            while j < n:
                c = source[j]
                if c == "\\":
                    j += 2
                    continue
                if c == quote:
                    j += 1
                    break
                if c == "\n":
                    break
                j += 1
            if mask_strings:
                for k in range(i, min(j, n)):
                    if out[k] != "\n":
                        out[k] = " "
            i = j
            continue
        if ch == "/" and i + 1 < n:
            nxt = source[i + 1]
            if nxt == "/":
                end = source.find("\n", i)
                end = n if end < 0 else end
                for j in range(i, end):
                    out[j] = " "
                i = end
                continue
            if nxt == "*":
                end = source.find("*/", i + 2)
                end = n if end < 0 else end + 2
                for j in range(i, end):
                    if out[j] != "\n":
                        out[j] = " "
                i = end
                continue
        if ch == "#":
            nxt = source[i + 1] if i + 1 < n else ""
            is_comment = not nxt or nxt in " \t\f\r\n" or nxt not in _HEX_DIGITS
            if is_comment:
                end = source.find("\n", i)
                end = n if end < 0 else end
                for j in range(i, end):
                    out[j] = " "
                i = end
                continue
        i += 1
    return "".join(out)


def _kwarg_column(lines: list[str], lineno: int | None, name: str) -> int:
    """0-based column of ``name=`` on 1-based *lineno*, or 0 when unknown."""
    if not lineno or lineno < 1 or lineno > len(lines):
        return 0
    match = re.search(rf"\b{re.escape(name)}\s*=", lines[lineno - 1])
    return match.start() if match else 0


@dataclass
class LintWarning:
    """A single lint finding.

    Attributes:
        code: Stable rule id (e.g. ``E001``, ``W001``, ``C002``).
        message: Human-readable description.
        line: 1-based line if known.
        column: 0-based column if known.
        severity: ``"error"``, ``"warning"``, ``"info"``, or ``"hint"``.
        end_line: Optional 1-based end line for a precise range.
        end_column: Optional 0-based exclusive end column.
    """

    code: str
    message: str
    line: int | None = None
    column: int | None = None
    severity: str = "warning"
    end_line: int | None = None
    end_column: int | None = None

    def __str__(self) -> str:
        location = f"line {self.line}" if self.line else "unknown location"
        return f"{self.severity}: [{self.code}] {self.message} at {location}"


class PineLinter:
    """Run built-in static analysis rules on Pine Script source.

    Each :meth:`lint` call resets :attr:`warnings` and returns the new list.
    Source is expected as a decoded Unicode string (UTF-8 when loaded from disk).
    """

    def __init__(self) -> None:
        """Create a linter with an empty :attr:`warnings` list."""
        self.warnings: list[LintWarning] = []

    def lint(self, source: str, filename: str = "<input>", *, tree: Any | None = None) -> list[LintWarning]:
        """Run all rules on *source* and return findings.

        Args:
            source: Full script text.
            filename: Label passed to the parser for syntax diagnostics.
            tree: Pre-parsed AST. When given, the syntax rule reuses it
                instead of re-parsing *source* (halves parse cost for
                callers that already have the tree, e.g. the language
                server workspace).

        Returns:
            List of :class:`LintWarning` (also stored on :attr:`warnings`).
        """
        self.warnings = []
        version = _detect_version(source)

        if tree is None:
            tree = self._check_syntax(source, filename)
        self._check_version(source)
        self._check_deprecated(source, version)
        self._check_naming(source)
        self._check_style(source)
        if tree is not None:
            self._check_v6_kwargs(tree, source, version)
            self._check_bool_conditions(tree, version)

        return self.warnings

    def _add_warning(
        self,
        code: str,
        message: str,
        line: int | None = None,
        column: int | None = None,
        severity: str = "warning",
        end_line: int | None = None,
        end_column: int | None = None,
    ) -> None:
        """Append a :class:`LintWarning` to :attr:`warnings`."""
        self.warnings.append(
            LintWarning(
                code=code,
                message=message,
                line=line,
                column=column,
                severity=severity,
                end_line=end_line,
                end_column=end_column,
            )
        )

    def _check_syntax(self, source: str, filename: str) -> Any | None:
        """Parse *source*; emit ``E001`` if :func:`~pynescript.ast.helper.parse` fails.

        Returns the parsed tree on success (reused by AST-based rules),
        else ``None``.
        """
        try:
            return parse(source, filename)
        except Exception as e:
            line: int | None = None
            column: int | None = None
            end_line: int | None = None
            end_column: int | None = None
            # Prefer structured location from pynescript.ast.error.SyntaxError
            details = getattr(e, "details", None)
            if details is not None:
                lineno = getattr(details, "lineno", None)
                offset = getattr(details, "offset", None)
                if isinstance(lineno, int) and lineno > 0:
                    line = lineno
                if isinstance(offset, int) and offset >= 0:
                    column = offset
                end_lineno = getattr(details, "end_lineno", None)
                end_offset = getattr(details, "end_offset", None)
                if isinstance(end_lineno, int) and end_lineno > 0:
                    end_line = end_lineno
                if isinstance(end_offset, int) and end_offset >= 0:
                    end_column = end_offset
            if line is None:
                # Fallback: "line N" / "line: N" in the message
                match = re.search(r"line[:\s]+(\d+)", str(e), re.IGNORECASE)
                if match:
                    line = int(match.group(1))
            # Prefer the short .message when available (avoid caret dump in chips)
            msg = getattr(e, "message", None)
            if not isinstance(msg, str) or not msg.strip():
                msg = str(e).split("\n", 1)[0].strip() or str(e)
            self._add_warning(
                code="E001",
                message=f"Syntax error: {msg}",
                line=line,
                column=column,
                severity="error",
                end_line=end_line,
                end_column=end_column,
            )
        return None

    def _check_version(self, source: str) -> None:
        """Require ``//@version=…``; warn if version is below 5 (``W001``/``W002``)."""
        version_match = _VERSION_PRAGMA_RE.search(source)
        if not version_match:
            self._add_warning(
                code="W001",
                message="Missing @version declaration. Add '//@version=6' at the top.",
                line=1,
                column=0,
            )
        else:
            version = int(version_match.group(1))
            if version < 5:
                line_num = source[: version_match.start()].count("\n") + 1
                line_text = source.split("\n")[line_num - 1]
                self._add_warning(
                    code="W002",
                    message=f"Pine Script v{version} is deprecated. Consider upgrading to v6.",
                    line=line_num,
                    column=max(0, version_match.start() - source.rfind("\n", 0, version_match.start()) - 1),
                    end_line=line_num,
                    end_column=len(line_text),
                )

    def _check_deprecated(self, source: str, version: int | None) -> None:
        """Flag known deprecated call patterns (``W101``).

        Only v5/v6 scripts can use ``request.security``; ``security()`` is a
        v4 spelling. Unversioned snippets are skipped to avoid false
        positives. Comments and string literals are masked before matching.

        Retired: ``W102`` (histogram → plotcandle was wrong guidance —
        plotcandle is not a histogram substitute) and ``W103``
        (``var int x = na`` → 0 changes semantics; na-init is idiomatic).
        Codes stay retired so history stays greppable.
        """
        if version is None or version < 5:
            return
        # Find ``security`` outside comments/strings via the masked text, then
        # verify the quoted symbol argument in the original source (the
        # argument itself is a string, so a single regex cannot do both).
        masked = _mask_comments_and_strings(source)
        call_re = re.compile(r"(?<![\w.])security\s*\(", re.IGNORECASE)
        arg_re = re.compile(r"security\s*\(\s*['\"][A-Z]+:[A-Z]+['\"]", re.IGNORECASE)
        for match in call_re.finditer(masked):
            tail = source[match.start() : match.start() + 120]
            if arg_re.match(tail) is None:
                continue
            line_num = source[: match.start()].count("\n") + 1
            line_start = source.rfind("\n", 0, match.start()) + 1
            column = match.start() - line_start
            self._add_warning(
                "W101",
                "Use request.security() with explicit parameters",
                line=line_num,
                column=column,
                end_line=line_num,
                end_column=column + len("security"),
            )

    def _check_v6_kwargs(self, tree: Any, source: str, version: int | None) -> None:
        """Flag v6-removed kwargs that the evaluator silently ignores (``W104``).

        * ``when=`` on ``strategy.*`` order calls (removed in v6; gate with
          an ``if`` block instead).
        * ``transp=`` on drawing/plot calls (removed in v6; use
          ``color.new(color, transp)`` instead). ``color.new`` / ``color()``
          keep a valid ``transp`` and are never flagged.

        These kwargs are valid in v4/v5, so the rule only runs when the
        script explicitly declares ``//@version=6``.
        """
        if version != 6:
            return
        lines = source.split("\n")
        for node in walk(tree):
            if not isinstance(node, Call):
                continue
            func = _call_func_name(node.func)
            if func is None:
                continue
            kwargs = {a.name for a in node.args if isinstance(a, Arg) and a.name}
            if not kwargs:
                continue
            line = getattr(node, "lineno", None)
            head, _, _ = func.partition(".")
            if head == "strategy" and "when" in kwargs:
                self._add_warning(
                    code="W104",
                    message="strategy.* 'when=' was removed in v6 and is ignored; gate with an 'if' block instead",
                    line=line,
                    column=_kwarg_column(lines, line, "when"),
                    end_line=line,
                    end_column=_kwarg_column(lines, line, "when") + len("when="),
                )
            if "transp" in kwargs and func not in ("color.new", "color"):
                if head in ("line", "box", "label", "table", "polyline", "linefill") or func in (
                    "plot",
                    "plotarrow",
                    "plotbar",
                    "plotcandle",
                    "plotchar",
                    "plotshape",
                    "fill",
                    "bgcolor",
                    "barcolor",
                    "hline",
                ):
                    column = _kwarg_column(lines, line, "transp")
                    self._add_warning(
                        code="W104",
                        message="'transp=' was removed in v6 and is ignored; use color.new(color, transp) instead",
                        line=line,
                        column=column,
                        end_line=line,
                        end_column=column + len("transp="),
                    )

    def _check_bool_conditions(self, tree: Any, version: int | None) -> None:
        """Flag numeric literals in boolean positions (``W105``).

        The evaluator stays permissive (``if 1`` runs the body), so v6
        strictness — explicit comparisons or ``bool()`` casts — is nudged
        here rather than enforced at runtime. v5 allowed numeric truthiness,
        so the rule is v6-only.
        """
        if version != 6:
            return
        for node in walk(tree):
            if not isinstance(node, (If, While, Conditional)):
                continue
            test = node.test
            if isinstance(test, Constant) and isinstance(test.value, (int, float)) and not isinstance(test.value, bool):
                line = getattr(test, "lineno", None) or getattr(node, "lineno", None)
                column = getattr(test, "col_offset", None)
                end_line = getattr(test, "end_lineno", None) or line
                end_column = getattr(test, "end_col_offset", None)
                if column is not None and end_column is None:
                    end_column = column + 1
                self._add_warning(
                    code="W105",
                    message="Numeric literal in boolean condition; use an explicit comparison or bool() cast",
                    line=line,
                    column=column,
                    end_line=end_line,
                    end_column=end_column,
                )

    def _check_naming(self, source: str) -> None:
        """Heuristic naming checks for ``ta.*`` assignments (``C001``).

        Comments and strings are masked so prose such as
        ``// old_name = ta.sma(...)`` never produces a finding. Only a real
        assignment operator (``=``, not ``==`` / ``=>`` / ``:=``) counts.
        """
        masked = _mask_comments_and_strings(source)
        for i, line in enumerate(masked.split("\n"), 1):
            match = _ASSIGN_OP_RE.search(line)
            if match is None or match.start() <= 0:
                continue
            lhs = line[: match.start()].rstrip(" \t")
            span = _trailing_ident_span(lhs)
            if span is None:
                continue
            ident_start, ident_end = span
            var_name = lhs[ident_start:ident_end]
            rhs = line[match.end() :].lstrip(" \t")
            if not rhs.startswith("ta."):
                continue
            # snake_case only — ``fastMA`` / ``sma`` are already camel/short.
            if "_" in var_name and "a" <= var_name[0] <= "z":
                self._add_warning(
                    code="C001",
                    message=f"Variable '{var_name}' should use camelCase (e.g., '{_to_camel(var_name)}')",
                    line=i,
                    column=ident_start,
                    end_line=i,
                    end_column=ident_end,
                )

    def _check_style(self, source: str) -> None:
        """Line length and trailing-newline style rules (``C002``, ``C004``).

        Retired: ``C003`` (indented ``if`` without “braces” — Pine has no
        braces, so the rule fired on every normal block). Code stays
        retired so history stays greppable.
        """
        lines = source.split("\n")
        for i, line in enumerate(lines, 1):
            if len(line.rstrip()) > 120:
                self._add_warning(
                    code="C002",
                    message=f"Line exceeds 120 characters ({len(line.rstrip())})",
                    line=i,
                    column=0,
                    end_line=i,
                    end_column=len(line.rstrip()),
                )

        # Do not strip() before the check — strip removes the trailing newline.
        if source and not source.endswith("\n"):
            last_line = len(lines)
            last_col = len(lines[-1])
            self._add_warning(
                code="C004",
                message="File should end with a newline",
                line=last_line,
                column=last_col,
                end_line=last_line,
                end_column=last_col,
            )


def _call_func_name(func: Any) -> str | None:
    """Build ``a.b.c`` from Attribute/Name nodes without evaluating values."""
    parts: list[str] = []
    cur = func
    while isinstance(cur, Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if not isinstance(cur, Name):
        return None
    parts.append(cur.id)
    parts.reverse()
    return ".".join(parts)


def _to_camel(name: str) -> str:
    """Convert snake_case *name* to camelCase for suggestion messages."""
    components = name.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def lint_script(source: str, filename: str = "<input>", *, tree: Any | None = None) -> list[LintWarning]:
    """Lint a source string; convenience wrapper around :class:`PineLinter`.

    Args:
        source: Decoded Pine Script text.
        filename: Label for diagnostics.
        tree: Pre-parsed AST; skips the internal re-parse when given.

    Returns:
        Findings from a fresh linter instance.
    """
    linter = PineLinter()
    return linter.lint(source, filename, tree=tree)


def lint_file(filepath: str) -> list[LintWarning]:
    """Lint a file read as UTF-8.

    Args:
        filepath: Path to a ``.pine`` (or other) source file.

    Returns:
        Findings; *filepath* is used as the diagnostic filename.
    """
    with open(filepath, encoding="utf-8") as f:
        source = f.read()

    return lint_script(source, filepath)
