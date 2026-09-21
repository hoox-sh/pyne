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

"""Source-level Pine Script conversion toward v6 (roadmap L1).

Safe text transforms **outside comments and string literals**:

* ``//@version=`` bump (missing pragma is treated as v1)
* v3 → v4: color / timeframe / ``n`` / ``tickerid`` / plot-style constants
* v4 → v5: ``ta.*`` / ``math.*`` / ``str.*`` / ``request.*`` / ``ticker.*``
  namespaces, ``study(`` → ``indicator(``, typed ``input.*()``, ``iff`` / ``offset``
* v5 → v6: leftover ``study(`` and bare ``security(`` / ``financial(`` / …

This is **not** a semantic migrator (bool-as-number, ``na`` tightening, v6
int/float-to-bool). Those need a type checker, not a rewriter.
"""

from __future__ import annotations

import re

from collections.abc import Callable


_V3 = 3
_V4 = 4
_V5 = 5
_V6 = 6
_IFF_NARGS = 3
_OFFSET_NARGS = 2

_VERSION_RE = re.compile(r"(?m)^(?P<prefix>\s*//@version\s*=\s*)(?P<ver>\d+)\s*$")
_DECL_RE = re.compile(r"(?<![\w.])(indicator|strategy|library|study)\s*\(")

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
_STUDY_RE = re.compile(r"(?<![\w.])study\s*\(")

_TA_NAMES = (
    "percentile_linear_interpolation",
    "percentile_nearest_rank",
    "highestbars",
    "lowestbars",
    "percentrank",
    "correlation",
    "supertrend",
    "crossover",
    "crossunder",
    "highest",
    "lowest",
    "pivothigh",
    "pivotlow",
    "barsince",
    "falling",
    "rising",
    "valuewhen",
    "variance",
    "linreg",
    "median",
    "stdev",
    "stoch",
    "change",
    "cross",
    "alma",
    "atr",
    "bbw",
    "cci",
    "cmo",
    "cog",
    "dmi",
    "ema",
    "hma",
    "kc",
    "kcw",
    "macd",
    "mfi",
    "mom",
    "rma",
    "roc",
    "rsi",
    "sar",
    "sma",
    "swma",
    "tsi",
    "vwap",
    "vwma",
    "wma",
    "wpr",
    "bb",
    "dev",
    "iii",
    "nvi",
    "obv",
    "pvi",
    "pvt",
    "wad",
    "cum",
    "mode",
    "range",
    "accdist",
    "wvad",
    "tr",
)
_MATH_NAMES = (
    "round_to_mintick",
    "todegrees",
    "toradians",
    "random",
    "log10",
    "floor",
    "round",
    "ceil",
    "sqrt",
    "sign",
    "abs",
    "acos",
    "asin",
    "atan",
    "avg",
    "cos",
    "exp",
    "log",
    "max",
    "min",
    "pow",
    "sin",
    "sum",
    "tan",
)
_TICKER_FNS = (
    "heikinashi",
    "pointfigure",
    "linebreak",
    "renko",
    "kagi",
)
_COLOR_NAMES = (
    "fuchsia",
    "maroon",
    "orange",
    "purple",
    "silver",
    "yellow",
    "black",
    "green",
    "navy",
    "olive",
    "teal",
    "aqua",
    "blue",
    "gray",
    "grey",
    "lime",
    "red",
    "white",
)
_TF_IDENTS = (
    "isintraday",
    "isseconds",
    "isminutes",
    "ismonthly",
    "isweekly",
    "isdaily",
    "isdwm",
    "period",
)
_DOW_NAMES = (
    "wednesday",
    "thursday",
    "saturday",
    "tuesday",
    "monday",
    "friday",
    "sunday",
)
_PLOT_STYLES = (
    "linebr",
    "stepline",
    "histogram",
    "columns",
    "circles",
    "area",
    "cross",
    "line",
)
_HLINE_STYLES = ("dashed", "dotted", "solid")
_INPUT_TYPE_TO_FN = {
    "integer": "int",
    "int": "int",
    "bool": "bool",
    "float": "float",
    "string": "string",
    "color": "color",
    "source": "source",
    "symbol": "symbol",
    "session": "session",
    "time": "time",
    "resolution": "timeframe",
    "timeframe": "timeframe",
}
_INPUT_TYPE_ALT = "|".join(_INPUT_TYPE_TO_FN)
_INPUT_TYPE_RE = re.compile(
    rf"\btype\s*=\s*(?:input\.)?({_INPUT_TYPE_ALT})\b",
)


def detect_version(source: str) -> int | None:
    """Return the ``//@version=N`` integer, or ``None`` if the pragma is missing."""
    match = _VERSION_RE.search(source)
    if not match:
        return None
    return int(match.group("ver"))


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


def _ident_re(names: tuple[str, ...]) -> re.Pattern[str]:
    alt = "|".join(re.escape(n) for n in names)
    return re.compile(rf"(?<![\w.])({alt})(?![\w.])")


def _followed_by_assign(span: str, end: int) -> bool:
    """True when *end* sits on an assignment ``=`` (not ``==`` / ``=>``)."""
    i = end
    n = len(span)
    while i < n and span[i] in " \t":
        i += 1
    if i >= n or span[i] != "=":
        return False
    nxt = span[i + 1] if i + 1 < n else ""
    return nxt not in "=><"


def _prefix_idents(span: str, names: tuple[str, ...], namespace: str) -> str:
    """Prefix builtin idents, but not assignment targets (``period = input(14)``)."""

    def repl(match: re.Match[str]) -> str:
        if _followed_by_assign(span, match.end()):
            return match.group(0)
        return f"{namespace}.{match.group(1)}"

    return _ident_re(names).sub(repl, span)


def _prefix_calls(span: str, names: tuple[str, ...], namespace: str) -> str:
    """Prefix *names* only when used as a call (``name(``), not params/LHS."""
    alt = "|".join(re.escape(n) for n in names)
    return re.sub(rf"(?<![\w.])({alt})\s*(?=\()", rf"{namespace}.\1", span)


def _close_paren(source: str, open_idx: int) -> int | None:
    """Index of the matching ``)`` for ``source[open_idx] == '('``, or ``None``."""
    depth = 1
    in_str: str | None = None
    escape = False
    i = open_idx + 1
    n = len(source)
    while i < n:
        ch = source[i]
        if in_str is not None:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == in_str:
                in_str = None
            i += 1
            continue
        if ch in "\"'":
            in_str = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
        elif ch == "/" and i + 1 < n and source[i + 1] == "/":
            nl = source.find("\n", i)
            i = n if nl < 0 else nl
            continue
        i += 1
    return None


def _split_top_args(inner: str) -> list[str]:
    args: list[str] = []
    buf: list[str] = []
    depth = 0
    in_str: str | None = None
    escape = False
    for ch in inner:
        if in_str is not None:
            buf.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == in_str:
                in_str = None
            continue
        if ch in "\"'":
            in_str = ch
            buf.append(ch)
            continue
        if ch == "(":
            depth += 1
            buf.append(ch)
            continue
        if ch == ")":
            depth -= 1
            buf.append(ch)
            continue
        if ch == "," and depth == 0:
            args.append("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        args.append(tail)
    return args


def _rewrite_named_calls(source: str, name: str, replacer: Callable[[str], str | None]) -> str:
    """Replace each ``name(...)`` in *source* code (skip comments / strings)."""
    pat = re.compile(rf"(?<![\w.]){re.escape(name)}\s*\(")
    out: list[str] = []
    i = 0
    n = len(source)
    in_str: str | None = None
    escape = False
    while i < n:
        ch = source[i]
        if in_str is not None:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == in_str:
                in_str = None
            i += 1
            continue
        if ch == "/" and i + 1 < n and source[i + 1] == "/":
            nl = source.find("\n", i)
            end = n if nl < 0 else nl
            out.append(source[i:end])
            i = end
            continue
        if ch in "\"'":
            in_str = ch
            out.append(ch)
            i += 1
            continue
        match = pat.match(source, i)
        if match:
            open_idx = match.end() - 1
            close_idx = _close_paren(source, open_idx)
            if close_idx is None:
                out.append(ch)
                i += 1
                continue
            inner = source[open_idx + 1 : close_idx]
            replacement = replacer(inner)
            if replacement is None:
                out.append(source[i : close_idx + 1])
            else:
                out.append(replacement)
            i = close_idx + 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _rewrite_iff(span: str) -> str:
    def replacer(inner: str) -> str | None:
        args = _split_top_args(inner)
        if len(args) != _IFF_NARGS:
            return None
        return f"({args[0]}) ? ({args[1]}) : ({args[2]})"

    prev = None
    cur = span
    while prev != cur:
        prev = cur
        cur = _rewrite_named_calls(cur, "iff", replacer)
    return cur


def _rewrite_offset(span: str) -> str:
    def replacer(inner: str) -> str | None:
        args = _split_top_args(inner)
        if len(args) != _OFFSET_NARGS:
            return None
        return f"{args[0]}[{args[1]}]"

    return _rewrite_named_calls(span, "offset", replacer)


def _rewrite_typed_input(span: str) -> str:
    def replacer(inner: str) -> str | None:
        match = _INPUT_TYPE_RE.search(inner)
        if not match:
            return None
        fn = _INPUT_TYPE_TO_FN[match.group(1)]
        stripped = (inner[: match.start()] + inner[match.end() :]).strip()
        stripped = re.sub(r",\s*,", ", ", stripped)
        stripped = stripped.strip(" ,")
        return f"input.{fn}({stripped})"

    return _rewrite_named_calls(span, "input", replacer)


def _rewrite_tickerid_call(span: str) -> str:
    def replacer(inner: str) -> str:
        return f"ticker.new({inner})"

    return _rewrite_named_calls(span, "tickerid", replacer)


def _convert_v3_to_v4_span(span: str, *, tf_names: tuple[str, ...] = _TF_IDENTS) -> str:
    span = re.sub(r"(?<![\w.])color\s*\(", "color.new(", span)
    span = _prefix_idents(span, _COLOR_NAMES, "color")
    span = _prefix_idents(span, _DOW_NAMES, "dayofweek")
    span = _prefix_idents(span, tf_names, "timeframe")
    span = re.sub(r"(?<![\w.])interval(?![\w.])", "timeframe.multiplier", span)
    span = re.sub(r"(?<![\w.])tickerid(?![\w.(])", "syminfo.tickerid", span)
    span = re.sub(r"(?<![\w.])ticker(?![\w.])", "syminfo.ticker", span)
    span = re.sub(
        r"(?<![\w.])n(?![\w.])",
        lambda m: m.group(0) if _followed_by_assign(span, m.end()) else "bar_index",
        span,
    )
    styles = "|".join(_PLOT_STYLES)
    span = re.sub(rf"\bstyle\s*=\s*({styles})\b", r"style=plot.style_\1", span)
    hstyles = "|".join(_HLINE_STYLES)
    span = re.sub(rf"\blinestyle\s*=\s*({hstyles})\b", r"linestyle=hline.style_\1", span)
    span = re.sub(r"\btype\s*=\s*integer\b", "type=input.integer", span)
    span = re.sub(r"\btype\s*=\s*bool\b", "type=input.bool", span)
    span = re.sub(r"\btype\s*=\s*float\b", "type=input.float", span)
    span = re.sub(r"\btype\s*=\s*string\b", "type=input.string", span)
    span = re.sub(r"\btype\s*=\s*color\b", "type=input.color", span)
    span = re.sub(r"\btype\s*=\s*source\b", "type=input.source", span)
    span = re.sub(r"\btype\s*=\s*symbol\b", "type=input.symbol", span)
    span = re.sub(r"\btype\s*=\s*session\b", "type=input.session", span)
    span = re.sub(r"\btype\s*=\s*resolution\b", "type=input.resolution", span)
    return span


def _convert_v4_to_v5_span(span: str) -> str:
    span = _STUDY_RE.sub("indicator(", span)
    span = re.sub(r"(?<![\w.])resolution_gaps\b", "timeframe_gaps", span)
    span = re.sub(r"(?<![\w.])resolution\s*=", "timeframe=", span)
    span = re.sub(r"(?<![\w.])tickerid(?![\w.])", "syminfo.tickerid", span)
    span = _prefix_calls(span, _TICKER_FNS, "ticker")
    span = _prefix_calls(span, _TA_NAMES, "ta")
    span = _prefix_calls(span, _MATH_NAMES, "math")
    span = re.sub(r"(?<![\w.])tostring\s*\(", "str.tostring(", span)
    span = re.sub(r"(?<![\w.])tonumber\s*\(", "str.tonumber(", span)
    span = _BARE_REQUEST_RE.sub(r"request.\1(", span)
    return span


def _ensure_declaration(source: str) -> str:
    if _DECL_RE.search(source):
        return source
    insert = 'indicator("Converted")\n'
    match = _VERSION_RE.search(source)
    if not match:
        return insert + source
    end = match.end()
    if end < len(source) and source[end] != "\n":
        return source[:end] + "\n" + insert + source[end:]
    return source[: end + 1] + insert + source[end + 1 :]


def convert_v3_to_v4(source: str) -> str:
    """Rename v3 colors / ``n`` / timeframe idents toward v4 namespaces."""
    # Line-wise mapping cannot see ``period = input(14)`` on later uses.
    tf_names = _TF_IDENTS
    if re.search(r"(?<![\w.])period\s*=(?!=)", source):
        tf_names = tuple(n for n in _TF_IDENTS if n != "period")

    def span(text: str) -> str:
        return _convert_v3_to_v4_span(text, tf_names=tf_names)

    return _map_code_spans(source, span)


def _unprefix_udf_defs(source: str) -> str:
    """Keep user ``name(...) =>`` definitions from becoming ``ta.name(...) =>``.

    Also covers v5 leftovers: ``security(...) =>`` must not become
    ``request.security(...) =>`` (same class as the 0.6.5 UDF-name fix).
    """
    pat = re.compile(r"(?<![\w.])(ta|math|ticker|str|request)\.(\w+)\s*\(")
    out: list[str] = []
    i = 0
    n = len(source)
    in_str: str | None = None
    escaped = False
    while i < n:
        ch = source[i]
        if in_str is not None:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == in_str:
                in_str = None
            i += 1
            continue
        if ch == "/" and i + 1 < n and source[i + 1] == "/":
            nl = source.find("\n", i)
            end = n if nl < 0 else nl
            out.append(source[i:end])
            i = end
            continue
        if ch in "\"'":
            in_str = ch
            out.append(ch)
            i += 1
            continue
        match = pat.match(source, i)
        if match:
            open_idx = match.end() - 1
            close_idx = _close_paren(source, open_idx)
            if close_idx is None:
                out.append(ch)
                i += 1
                continue
            j = close_idx + 1
            while j < n and source[j] in " \t":
                j += 1
            if source.startswith("=>", j):
                out.append(match.group(2))
                out.append(source[open_idx : close_idx + 1])
            else:
                out.append(source[i : close_idx + 1])
            i = close_idx + 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def convert_v4_to_v5(source: str) -> str:
    """Rewrite v4 toward v5 namespaces, ``indicator()``, and typed inputs."""
    text = _rewrite_tickerid_call(source)
    text = _map_code_spans(text, _convert_v4_to_v5_span)
    text = _unprefix_udf_defs(text)
    text = _rewrite_iff(text)
    text = _rewrite_offset(text)
    return _rewrite_typed_input(text)


def _convert_v5_to_v6_span(span: str) -> str:
    span = _STUDY_RE.sub("indicator(", span)
    return _BARE_REQUEST_RE.sub(r"request.\1(", span)


def convert_v5_to_v6(source: str) -> str:
    """Rewrite v5 (or v4 leftovers) toward v6 namespaces and ``indicator()``."""
    text = _map_code_spans(source, _convert_v5_to_v6_span)
    text = _unprefix_udf_defs(text)
    return _set_version(text, _V6)


def convert_v6_to_v5(source: str) -> str:
    """Rewrite v6 ``request.*`` calls back to bare v5 names; keep ``indicator()``."""

    def code(span: str) -> str:
        return _NAMESPACED_REQUEST_RE.sub(r"\1(", span)

    return _set_version(_map_code_spans(source, code), _V5)


def convert_to_v6(source: str) -> str:
    """Convert any older Pine version (missing pragma = v1) toward v6."""
    version = detect_version(source)
    from_ver = 1 if version is None else version
    if from_ver >= _V6:
        return _set_version(source, _V6)
    text = source
    if from_ver <= _V3:
        text = convert_v3_to_v4(text)
    if from_ver <= _V4:
        text = convert_v4_to_v5(text)
    else:
        text = _map_code_spans(text, _convert_v5_to_v6_span)
        text = _unprefix_udf_defs(text)
    text = _ensure_declaration(text)
    return _set_version(text, _V6)


def convert_pine(source: str, *, to: int) -> str:
    """Convert *source* toward Pine version *to* (5 or 6).

    ``to=6`` runs the full v1-v5 pipeline. ``to=5`` only strips ``request.*``
    prefixes (legacy v6 → v5 helper).
    """
    if to == _V5:
        return convert_v6_to_v5(source)
    if to == _V6:
        return convert_to_v6(source)
    msg = f"unsupported target version {to}; use 5 or 6"
    raise ValueError(msg)
