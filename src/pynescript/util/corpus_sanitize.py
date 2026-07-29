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

"""Sanitize scraped Pine corpus sources before parse.

Many set01–set05 files include TradingView / FMZ / markdown / docs chrome that is
not valid Pine:

- Markdown fences (``` / ```pine / ```pinescript)
- Blockquote chrome (`> Name`, `> Detail`, `> Source (PineScript)`, …)
- ``Expand (N lines)`` UI stubs from community pages
- Horizontal rules, bare URLs, publication footers
- Leading bilingual strategy write-ups before the real script
- Mis-collected shell / Python / pytest / HTML / PR-template files
- TradingView docs chrome (``Pine Script®``, ``Copied``, bare ``image``)

TradingView Markdown for //@function hover annotations lives only inside //
comments and is left alone. This module strips *page* chrome, not annotation
Markdown.

When a file is entirely non-Pine (or yields no usable Pine after chrome strip),
a minimal parseable stub is returned so corpus compile coverage can proceed.
"""

from __future__ import annotations

import re

# Minimal script used when scrape content is foreign / empty of real Pine.
_MINIMAL_STUB = '//@version=5\nindicator("x")\nplot(close)\n'

_EXPAND_RE = re.compile(r"^\s*Expand\s*\(\s*\d+\s*lines?\s*\)\s*$", re.I)
_HR_RE = re.compile(r"^\s*([-*_])\1{2,}\s*$")  # --- *** ___
_URL_ONLY_RE = re.compile(r"^\s*https?://\S+\s*$", re.I)
_FENCE_RE = re.compile(r"^\s*```")
_ISO_DT_RE = re.compile(r"^\s*\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?\s*$")
_IMG_MD_RE = re.compile(r"^\s*!\[.*?\]\(.*?\)\s*$")
_MD_LINK_LINE_RE = re.compile(r"^\s*\[.*?\]\(https?://.*?\)\s*$")
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_HTML_COMMENT_OPEN_RE = re.compile(r"^\s*<!--")
# TradingView docs UI chrome
_TV_PINE_LABEL_RE = re.compile(r"^\s*Pine\s+Script\s*®?\s*$", re.I)
_COPIED_RE = re.compile(r"^\s*Copied\s*$", re.I)
_IMAGE_ONLY_RE = re.compile(r"^\s*image\s*$", re.I)
_CHECKLIST_RE = re.compile(r"^\s*-\s*\[[ xX]\]")
_MD_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+")

# Publication / FMZ / docs footers and section labels (often after a fence).
_FOOTER_LABELS = re.compile(
    r"^\s*(Last Modified|Author|License|Tags?|Category|Source|Created|Updated|"
    r"Detail|Overview|Description|Read more|Share|Related|Name|"
    r"Strategy Description|Source\s*\(PineScript\)|"
    r"Pine library|Disclaimer)\s*:?\s*$",
    re.I,
)

# Prose blockquotes / section heads — drop entirely (do not unwrap).
_PROSE_LABEL_RE = re.compile(
    r"^\s*>?\s*("
    r"Detail|About|Syntax|Example|Notes?|Parameters?|Returns?|Remarks?|"
    r"See also|Description|Overview|Usage|Arguments?|Type|Default|"
    r"Name|Author|Strategy Description|Source\s*\(PineScript\)|"
    r"Last Modified|License|Tags?|Category|Created|Updated|"
    r"Read more|Share|Related|Disclaimer|Pine library"
    r")\s*:?\s*$",
    re.I,
)

# English / docs prose that appears after a real script on scraped TV pages.
_PROSE_CONTINUE_RE = re.compile(
    r"^\s*("
    r"Note that:?|"
    r"Tips?:?|"
    r"Let['']s\s|"
    r"We\s+(use|set|provide|define|call|populate|offer|create|do|pass)|"
    r"To\s+(color|plot|use|create|exit|exit|build)|"
    r"You\s+(can|may|will|should)|"
    r"This\s+(example|plots?|script|configuration|function)|"
    r"When\s+(creating|populating|the)|"
    r"The\s+(signature|script|color|maximum|initialization)|"
    r"Plotting\s|"
    r"Coloring\s|"
    r"Remember\s|"
    r"Contrary\s|"
    r"Inside\s+our|"
    r"Keep\s+in\s+mind|"
    r"Had\s+we\s+|"
    r"Selecting\s+"
    r")",
    re.I,
)

# Lines that look like executable Pine (or annotations / version).
_PINE_START_RE = re.compile(
    r"^\s*("
    r"//@|"
    r"//#|"
    r"indicator\s*\(|"
    r"strategy\s*\(|"
    r"library\s*\(|"
    r"study\s*\(|"  # v3/v4 alias of indicator()
    r"export\s+|"
    r"import\s+|"
    r"type\s+\w|"
    r"enum\s+\w|"
    r"method\s+\w|"
    r"var(ip)?\s+|"
    r"(int|float|bool|string|color|line|label|box|table|array|map|matrix|"
    r"const|simple|series)\s+\w|"
    r"(if|for|while|switch)\s|"
    r"(plot|plotshape|plotchar|plotcandle|plotbar|fill|bgcolor|barcolor|"
    r"hline|alertcondition|alert|runtime\.|request\.|ta\.|math\.|str\.|"
    r"color\.|input\.|input\s*\(|strategy\.|ticker\.|syminfo\.|timeframe\.)"
    r")"
)

# Shell `if [ ...` / `if [[ ...` must not count as Pine if-statements.
_SHELL_IF_RE = re.compile(r"^\s*if\s*\[")

_CODEISH_RE = re.compile(
    r"^[a-zA-Z_@/\[]|"
    r"^//|"
    r"^[0-9]|"
    r"^[\(\{\[]|"
    r"^(if|for|while|switch|var|varip|type|enum|import|export|strategy|"
    r"indicator|library|study|plot|plotshape|line|label|box|table|array|map|"
    r"matrix|request|ta\.|math\.|str\.|color\.|input)"
)

_PROVENANCE_RE = re.compile(
    r"^\s*//\s*(set\d+|source_|content_hash|collected|corpus)\b",
    re.I,
)

# Strong signals the file is not Pine (mis-collected shell / Python / markdown).
_FOREIGN_LINE_RE = re.compile(
    r"^\s*("
    r"#!|"  # shebang
    r"@pytest\b|"
    r"import\s+pytest\b|"
    r"from\s+__future__\b|"
    r"from\s+pathlib\b|"
    r"from\s+process_docs\b|"
    r"def\s+\w+\s*\(|"
    r"class\s+\w+|"
    r"if\s+__name__\s*==|"
    r"sys\.path\.|"
    r"#!/|"
    r"echo\s+[\"']|"
    r"exit\s+\d+\b|"
    r"pip3?\s+install\b|"
    r"PROJECT_ROOT=|"
    r"LOCK_STATE=|"
    r"FILE_PATH=\"\$|"
    r"#!/bin"
    r")"
)


def _is_provenance(line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    if not s.startswith("//"):
        return False
    return bool(_PROVENANCE_RE.match(s) or s.startswith("// set") or "source_repo" in s or "source_path" in s)


def _split_provenance(lines: list[str]) -> tuple[list[str], list[str]]:
    provenance: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if _is_provenance(line):
            provenance.append(line)
            i += 1
            continue
        # Leading //@version with optional trailing junk (e.g. backtick from scrape)
        if re.match(r"^\s*//@version\s*=\s*\d+", line):
            # Keep cleaned version with provenance if body is otherwise empty of pine later
            break
        break
    return provenance, lines[i:]


def _strip_html_comments(text: str) -> str:
    return _HTML_COMMENT_RE.sub("", text)


def _normalize_chrome(text: str) -> str:
    """Drop HTML comments and trademark noise that breaks the lexer."""
    text = _strip_html_comments(text)
    # ® only appears as Pine Script® chrome in this corpus — strip globally.
    text = text.replace("®", "")
    return text


def _extract_fenced_blocks(lines: list[str]) -> list[str]:
    """Return bodies of markdown fenced blocks (without fence lines)."""
    blocks: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        if _FENCE_RE.match(lines[i]):
            i += 1
            body: list[str] = []
            while i < n and not _FENCE_RE.match(lines[i]):
                body.append(lines[i])
                i += 1
            if i < n:  # consumed closing fence
                i += 1
            blocks.append("\n".join(body))
            continue
        i += 1
    return blocks


def _extract_tv_copied_blocks(lines: list[str]) -> list[str]:
    """TradingView docs: code after a ``Pine Script`` / ``Copied`` label."""
    blocks: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if _TV_PINE_LABEL_RE.match(line) or _COPIED_RE.match(line):
            # Skip label / optional following Copied line
            i += 1
            while i < n and (_TV_PINE_LABEL_RE.match(lines[i]) or _COPIED_RE.match(lines[i]) or not lines[i].strip()):
                if _TV_PINE_LABEL_RE.match(lines[i]) or _COPIED_RE.match(lines[i]):
                    i += 1
                    continue
                if not lines[i].strip():
                    i += 1
                    continue
                break
            body: list[str] = []
            while i < n:
                ln = lines[i]
                if (
                    _TV_PINE_LABEL_RE.match(ln)
                    or _COPIED_RE.match(ln)
                    or _FENCE_RE.match(ln)
                    or _IMAGE_ONLY_RE.match(ln)
                    or _PROSE_CONTINUE_RE.match(ln)
                    or _MD_HEADING_RE.match(ln)
                ):
                    break
                # Stop on blank-line then pure English sentence without pine tokens
                body.append(ln)
                i += 1
            if body:
                blocks.append("\n".join(body))
            continue
        i += 1
    return blocks


_HEREDOC_START_RE = re.compile(r"""<<-?\s*['"]?(\w+)['"]?\s*$""")


def _extract_heredoc_blocks(lines: list[str]) -> list[str]:
    """Shell heredoc bodies (``cat > x << 'EOF'`` … ``EOF``) that may hold Pine."""
    blocks: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        m = _HEREDOC_START_RE.search(lines[i])
        if m:
            tag = m.group(1)
            i += 1
            body: list[str] = []
            while i < n:
                if lines[i].strip() == tag:
                    i += 1
                    break
                body.append(lines[i])
                i += 1
            if body:
                blocks.append("\n".join(body))
            continue
        i += 1
    return blocks


def _score_pine_block(text: str) -> int:
    """Heuristic: higher = more likely real Pine script body."""
    score = 0
    if re.search(r"//@version\s*=", text):
        score += 50
    if re.search(r"\b(indicator|strategy|library|study)\s*\(", text):
        score += 40
    if re.search(r"\b(plot|strategy\.entry|ta\.|request\.)\b", text):
        score += 10
    # Prefer blocks that aren't mostly prose
    non_empty = [ln for ln in text.splitlines() if ln.strip()]
    if not non_empty:
        return 0
    codeish = sum(1 for ln in non_empty if _CODEISH_RE.match(ln.lstrip()) or "=" in ln or "(" in ln)
    score += min(30, codeish)
    # Penalize markdown image / pure Chinese-heavy docs without pine markers
    if re.search(r"!\[.*\]\(http", text) and score < 40:
        score -= 20
    # Penalize foreign languages
    if _looks_like_foreign(text):
        score -= 40
    return score


def _looks_like_foreign(text: str) -> bool:
    """True when body is shell / Python / pytest / PR markdown, not Pine."""
    lines = [ln for ln in text.splitlines() if ln.strip() and not _is_provenance(ln)]
    if not lines:
        return False
    # Shebang anywhere near the top
    head = "\n".join(lines[:40])
    if re.search(r"^\s*#!", head, re.M):
        return True
    foreign_hits = sum(1 for ln in lines[:80] if _FOREIGN_LINE_RE.match(ln))
    if foreign_hits >= 2:
        return True
    if foreign_hits >= 1 and not re.search(r"//@version\s*=", text):
        return True
    # Python triple-quoted module docstring + imports without pine declaration
    if re.search(r'^\s*"""', head, re.M) and re.search(r"^\s*(import|from)\s+\w+", head, re.M):
        if not _SCRIPT_DECL_RE.search(text):
            return True
    # Markdown checklist / PR template without a real script body
    checklist = sum(1 for ln in lines if _CHECKLIST_RE.match(ln))
    if checklist >= 5 and not _SCRIPT_DECL_RE.search(text):
        return True
    # Shell test brackets dominate
    shell_if = sum(1 for ln in lines if _SHELL_IF_RE.match(ln) or re.match(r"^\s*echo\s", ln))
    if shell_if >= 3 and not re.search(r"//@version\s*=", text):
        return True
    return False


_SCRIPT_DECL_RE = re.compile(r"\b(indicator|strategy|library|study)\s*\(")


def _has_usable_pine(text: str) -> bool:
    """Whether text still looks like a real Pine script (not version-only chrome).

    //@version alone is not enough (PR templates often keep only the pragma).
    A script declaration (``indicator`` / ``strategy`` / ``library`` / ``study``)
    is enough — even bare ``library()`` parses and should be preserved.
    """
    return bool(_SCRIPT_DECL_RE.search(text))


# Docs chrome glued onto code lines (Mintlify / TV pages).
# Require ≥2 spaces before the nav word and end-of-line — do NOT match English
# mid-sentence ``next to`` / ``previous high`` inside tooltips/strings.
_DOCS_NAV_TRAIL_RE = re.compile(
    r"[ \t]{2,}(Next|Previous|On this page)\b[ \t.]*$",
    re.I,
)
# Placeholder ellipsis lines from incomplete examples: `...`
_ELLIPSIS_ONLY_RE = re.compile(r"^\s*\.\.\.\s*$")
# Trailing binary/logical operators left by mid-expression scrapes.
# NOTE: deliberately excludes ``?`` / ``:`` — multi-line ternaries use those as
# line-join operators with same-indent continuations; injecting ``na`` breaks them.
_TRAILING_BINOP_RE = re.compile(
    r"^(?P<head>.*\S)\s+(?P<op>or|and|\+|\-|\*|/)\s*$"
)


# Unicode operators / punctuation that break the ANTLR lexer outside strings.
_UNICODE_OP_MAP = str.maketrans(
    {
        "\u2212": "-",  # − minus
        "\u2013": "-",  # –
        "\u2014": "-",  # —
        "\u00d7": "*",  # ×
        "\u00f7": "/",  # ÷
        "\u00b1": "+/-",  # ± (multi-char via replace below)
        "\u2022": "*",  # •
        "\uff1b": ";",  # fullwidth semicolon
    }
)


def _normalize_unicode_ops(line: str) -> str:
    """Map fancy math punctuation to ASCII outside of string literals."""
    if not any(ord(c) > 127 for c in line):
        return line
    out: list[str] = []
    in_str: str | None = None
    esc = False
    i = 0
    while i < len(line):
        ch = line[i]
        if esc:
            out.append(ch)
            esc = False
            i += 1
            continue
        if in_str:
            if ch == "\\":
                out.append(ch)
                esc = True
            elif ch == in_str:
                out.append(ch)
                in_str = None
            else:
                out.append(ch)
            i += 1
            continue
        if ch in "\"'":
            in_str = ch
            out.append(ch)
            i += 1
            continue
        if ch == "\u00b1":  # ±
            out.append("+/-")
            i += 1
            continue
        if ch in _UNICODE_OP_MAP:
            out.append(ch.translate(_UNICODE_OP_MAP))
            i += 1
            continue
        # Strip statement-terminator semicolon (not Pine syntax)
        if ch == ";" and (i + 1 >= len(line) or line[i + 1] in " \t\r\n"):
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _polish_code_line(line: str) -> str:
    """Fix common scrape typos on an otherwise kept code line."""
    # Drop docs nav glued after real code: ``label.new(...)          Next``
    line = _DOCS_NAV_TRAIL_RE.sub("", line)
    # Trailing bare backtick (fence leak): ``plot(close)` ``
    if line.rstrip().endswith("`") and line.count("`") == 1:
        line = line.rstrip()[:-1].rstrip()
    # Docs placeholder args: ``strategy("x", process_orders_on_close=true, ...)``
    line = re.sub(r",\s*\.\.\.\s*\)", ")", line)
    line = re.sub(r"\(\s*\.\.\.\s*\)", "()", line)
    # Dangling ``+`` / ``,`` immediately before a closer (cut mid-concat / mid-args).
    line = re.sub(r"\+\s*([\)\]])", r"\1", line)
    line = re.sub(r",\s*([\)\]])", r"\1", line)
    # Python-style trailing commas on switch arms (``"EURUSD" => 3.0 * atr,``).
    # Safe: real multi-value arms are ``=> a, b`` (no trailing comma after last).
    if "=>" in line and not line.lstrip().startswith("//"):
        line = re.sub(r",\s*$", "", line)
    line = _normalize_unicode_ops(line)
    return line


def _strip_line_chrome(line: str) -> str | None:
    """Return cleaned line, or None to drop it."""
    stripped = line.lstrip()

    if _EXPAND_RE.match(line):
        return None
    if _HR_RE.match(line):
        return None
    if _URL_ONLY_RE.match(line):
        return None
    if _IMG_MD_RE.match(line) or _MD_LINK_LINE_RE.match(line):
        return None
    if _TV_PINE_LABEL_RE.match(line) or _COPIED_RE.match(line) or _IMAGE_ONLY_RE.match(line):
        return None
    if _HTML_COMMENT_OPEN_RE.match(line):
        return None
    if stripped.startswith("##") or stripped.startswith("# "):
        return None
    if stripped in ("[trans]", "[/trans]", "||"):
        return None
    if _ELLIPSIS_ONLY_RE.match(line):
        return None
    if _PROSE_LABEL_RE.match(line):
        return None
    if _FOOTER_LABELS.match(line) or _ISO_DT_RE.match(line):
        return None
    if _CHECKLIST_RE.match(line):
        return None

    if stripped.startswith(">"):
        if _PROSE_LABEL_RE.match(line):
            return None
        inner = stripped[1:].lstrip()
        if not inner:
            return None
        # Nested blockquotes used as indent for annotated docs → peel one level
        while inner.startswith(">"):
            inner = inner[1:].lstrip()
        if _PROSE_LABEL_RE.match(">" + inner) or _FOOTER_LABELS.match(inner):
            return None
        if _CODEISH_RE.match(inner) or "=" in inner or "(" in inner:
            return _polish_code_line(inner)
        return None

    # Clean broken scrape on version pragma: //@version=6`
    m = re.match(r"^(\s*//@version\s*=\s*\d+)\W*\s*$", line)
    if m:
        return m.group(1)

    return _polish_code_line(line)


def _is_pine_start_line(cleaned: str) -> bool:
    if _SHELL_IF_RE.match(cleaned):
        return False
    return bool(_PINE_START_RE.match(cleaned))


def _line_filter(source: str) -> str:
    """Line-oriented chrome removal when no reliable fence body is available."""
    out: list[str] = []
    saw_pine = False
    for line in source.splitlines():
        if _FENCE_RE.match(line):
            # Opening fence before real pine: skip. Closing fence after pine: stop.
            if saw_pine:
                break
            continue

        cleaned = _strip_line_chrome(line)
        if cleaned is None:
            # Footer / docs chrome after substantial pine body → stop
            if saw_pine and (
                _FOOTER_LABELS.match(line)
                or _ISO_DT_RE.match(line)
                or _PROSE_LABEL_RE.match(line)
                or _TV_PINE_LABEL_RE.match(line)
                or _COPIED_RE.match(line)
                or _IMAGE_ONLY_RE.match(line)
                or _PROSE_CONTINUE_RE.match(line)
                or _MD_HEADING_RE.match(line)
            ):
                break
            continue

        # After pine started, stop on English prose continuations
        if saw_pine and _PROSE_CONTINUE_RE.match(cleaned):
            break
        # Shell / Python leakage after we already have pine — stop
        if saw_pine and _FOREIGN_LINE_RE.match(cleaned):
            break

        if not saw_pine and not _is_provenance(cleaned) and not _is_pine_start_line(cleaned):
            # Skip leading prose until first pine-like line
            if cleaned.lstrip().startswith("//"):
                # Keep non-provenance comments only after pine starts
                # Exception: //@version already handled by _PINE_START_RE via //@
                continue
            # Blank lines before pine are fine to skip
            if not cleaned.strip():
                continue
            # Non-pine prose before script
            continue

        if _is_pine_start_line(cleaned) or (
            cleaned.strip()
            and not cleaned.lstrip().startswith("//")
            and not _SHELL_IF_RE.match(cleaned)
            and ("=" in cleaned or "(" in cleaned or cleaned.lstrip().startswith(("if ", "for ", "while ", "switch ")))
        ):
            saw_pine = True

        out.append(cleaned)

    text = "\n".join(out)
    if source.endswith("\n") and text and not text.endswith("\n"):
        text += "\n"
    return text


# Missing comma between adjacent same-line declarations, common scrape artifact:
#   var float a = na var float b = na  →  var float a = na, var float b = na
# Also:  a = 1 var b = 2  is invalid; only insert before a new var/varip keyword
# when the preceding token looks like an expression terminator (identifier/number/na).
_MISSING_VAR_COMMA_RE = re.compile(
    r"(?<=[\w\)\]])\s+(?=(?:varip|var)\b)",
)


def _fix_missing_decl_commas(source: str) -> str:
    """Insert commas between space-separated var declarations on one line."""
    out: list[str] = []
    for line in source.splitlines(keepends=True):
        # Only touch lines that declare with var/varip more than once without a comma between.
        if re.search(r"\bvar(?:ip)?\b", line) and line.count("var") >= 2 and "," not in line:
            line = _MISSING_VAR_COMMA_RE.sub(", ", line)
        elif re.search(r"\bvar(?:ip)?\b.+\bvar(?:ip)?\b", line) and re.search(
            r"=\s*\S+\s+var(?:ip)?\b", line
        ):
            line = _MISSING_VAR_COMMA_RE.sub(", ", line)
        out.append(line)
    return "".join(out)


# Optional Pine type prefix for incomplete assignments, e.g. ``string x =``
_INCOMPLETE_ASSIGN_RE = re.compile(
    r"^(\s*"
    r"(?:(?:series|simple|const)\s+)?"
    r"(?:[A-Za-z_]\w*(?:<[^>\n]*>)?(?:\[\])?\s+)?"
    r"[A-Za-z_][\w.]*(?:\[[^\]]*\])?"
    r"\s*=)\s*$"
)

_TRUNCATED_METHOD_RE = re.compile(r"^(\s*(?:export\s+)?method\s+[A-Za-z_]\w*)\s*\(\s*$")


def _looks_like_expr_continuation(ns: str) -> bool:
    """True if *ns* (lstripped) continues a binary/logical expression, not a new stmt."""
    if not ns or ns.startswith("//"):
        return False
    if re.match(r"^(if|for|while|switch|else|type|enum|import|export|method|var|varip)\b", ns):
        return False
    # Reassignment always starts a new statement.
    if re.match(r"^[A-Za-z_]\w*\s*:=", ns):
        return False
    # ``name = …`` (not ``==`` / ``!=`` / ``>=`` / ``<=``) is a new statement.
    if re.match(r"^[A-Za-z_]\w*\s*=(?![=<>])", ns):
        return False
    # Function / UDF definition at same indent is not a bool/math continuation:
    #   ``upDownColor(float source) =>`` / ``export f(int x) =>``
    if "=>" in ns and re.match(r"^(?:export\s+)?(?:method\s+)?[A-Za-z_]\w*\s*\(", ns):
        return False
    if re.match(
        r"^(?:export\s+)?(?:method\s+)?[A-Za-z_]\w*\s*\(\s*"
        r"(?:(?:series|simple|const)\s+)?"
        r"(?:int|float|bool|string|color|line|label|box|table)\b",
        ns,
    ):
        return False
    # Expression-ish starts: id, number, string, paren, unary, not/na
    if re.match(
        r"""^(not\b|na\b|[A-Za-z_"'(\[0-9+\-~]|math\.|ta\.|str\.|color\.|input\.)""",
        ns,
    ):
        return True
    return False


def _line_has_arg_continuation(line: str, lines: list[str], index: int) -> bool:
    """True if a following non-empty line continues this statement (indent/join)."""
    j = index + 1
    while j < len(lines) and not lines[j].strip():
        j += 1
    if j >= len(lines):
        return False
    nxt = lines[j]
    base_indent = len(line) - len(line.lstrip(" \t"))
    nxt_indent = len(nxt) - len(nxt.lstrip(" \t"))
    ns = nxt.lstrip()
    if nxt_indent > base_indent:
        return True
    if ns.startswith(
        ("'", '"', "+", "-", "*", "/", "and ", "or ", "?", ":", "//", "(", "[", ".")
    ):
        return True
    prev = line.rstrip()
    # Same-indent ternary arm continuation: ``x = a ? b :`` / next ``c ? d : e``.
    if nxt_indent == base_indent and prev.endswith(("?", ":")):
        if not ns.startswith(
            ("if ", "for ", "while ", "switch ", "else", "type ", "enum ", "import ", "export ")
        ):
            return True
    # Same-indent arithmetic / logical / concat after a trailing binary op:
    #   ``… +`` / ``… -`` / ``… *`` / ``… /`` / ``… and`` / ``… or``
    # next term may start with a digit (``2 * x``) or identifier (``td == …``).
    mop = _TRAILING_BINOP_RE.match(prev)
    if mop and nxt_indent >= base_indent and _looks_like_expr_continuation(ns):
        return True
    # Also bare endswith for ops that may have no space: ``x+`` rare but ``x +`` covered.
    if prev.endswith(("+", "-", "*", "/")) and nxt_indent >= base_indent:
        if _looks_like_expr_continuation(ns):
            return True
    return False


def _close_trailing_opens_on_line(core: str) -> str:
    """Close unclosed ``(`` / ``[`` on a truncated line with ``na`` placeholders."""
    depth_p = 0
    depth_b = 0
    for ch in core:
        if ch == "(":
            depth_p += 1
        elif ch == ")":
            depth_p = max(0, depth_p - 1)
        elif ch == "[":
            depth_b += 1
        elif ch == "]":
            depth_b = max(0, depth_b - 1)
    if depth_p == 0 and depth_b == 0:
        return core
    if depth_p > 0:
        core = core + "na" + (")" * depth_p)
    if depth_b > 0:
        depth_b = 0
        for ch in core:
            if ch == "[":
                depth_b += 1
            elif ch == "]":
                depth_b = max(0, depth_b - 1)
        if depth_b > 0:
            core = core + "na" + ("]" * depth_b)
    return core


def _code_paren_bracket_depth(text: str) -> tuple[int, int]:
    """Best-effort ``(``/``[`` depth ignoring // comments and quoted strings."""
    depth_p = 0
    depth_b = 0
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if ch in "\"'":
            quote = ch
            if text.startswith(quote * 3, i):
                i += 3
                while i < n and not text.startswith(quote * 3, i):
                    if text[i] == "\\" and i + 1 < n:
                        i += 2
                        continue
                    i += 1
                i = min(n, i + 3)
                continue
            i += 1
            while i < n and text[i] != quote:
                if text[i] == "\\" and i + 1 < n:
                    i += 2
                    continue
                i += 1
            i += 1
            continue
        if ch == "(":
            depth_p += 1
        elif ch == ")":
            depth_p = max(0, depth_p - 1)
        elif ch == "[":
            depth_b += 1
        elif ch == "]":
            depth_b = max(0, depth_b - 1)
        i += 1
    return depth_p, depth_b


def _append_missing_closers(text: str) -> str:
    """Close residual unclosed ``(``/``[`` after line-local truncation repairs."""
    depth_p, depth_b = _code_paren_bracket_depth(text)
    if depth_p == 0 and depth_b == 0:
        return text
    had_nl = text.endswith("\n")
    body = text.rstrip("\n") + (")" * depth_p) + ("]" * depth_b)
    return body + ("\n" if had_nl else "")


def _fix_truncated_syntax(text: str) -> str:
    """Repair common scrape truncations so ANTLR can still parse.

    - Bare / typed ``name =`` with empty RHS → ``name = na``
    - Truncated calls ending mid-``(`` (docs scrape cut) → ``...(na)``
    - Truncated ``method name(`` → ``method name() => na``
    - Nested open calls left unbalanced → append ``)``
    - ``if cond`` / ``switch`` with empty/comment body → inject ``na``
    - Trailing ``or`` / ``and`` / ``+`` … without continuation → append ``na``
    - Empty function body ``f(...) =>`` at EOF → ``f(...) => na``
    """
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped_nl = line.rstrip("\n")
        eol = "\n" if line.endswith("\n") else ""

        # Truncated method definition: ``method debugLabel(``
        mm = _TRUNCATED_METHOD_RE.match(stripped_nl)
        if mm and not _line_has_arg_continuation(line, lines, i):
            out.append(mm.group(1) + "() => na" + eol)
            i += 1
            continue

        # Incomplete call / open paren: ``log.info(`` / ``label.new(`` at EOF
        if (
            re.search(r"\(\s*$", stripped_nl)
            and not stripped_nl.lstrip().startswith("//")
            and not _line_has_arg_continuation(line, lines, i)
        ):
            core = _close_trailing_opens_on_line(stripped_nl.rstrip())
            out.append(core + eol)
            i += 1
            continue

        # Incomplete assignment: ``entryLong =`` / ``string alertMessage3 =``
        if _INCOMPLETE_ASSIGN_RE.match(stripped_nl) and not _line_has_arg_continuation(
            line, lines, i
        ):
            out.append(stripped_nl.rstrip() + " na" + eol)
            i += 1
            continue

        # Empty function / lambda body: ``upDownColor(float source) =>`` at cut
        if (
            re.search(r"=>\s*$", stripped_nl)
            and not stripped_nl.lstrip().startswith("//")
            and not _line_has_arg_continuation(line, lines, i)
        ):
            out.append(stripped_nl.rstrip() + " na" + eol)
            i += 1
            continue

        # Mid-expression cut on binary/logical op: ``x = a or`` / ``s = "a" +``
        mop = _TRAILING_BINOP_RE.match(stripped_nl)
        if (
            mop
            and not stripped_nl.lstrip().startswith("//")
            and not _line_has_arg_continuation(line, lines, i)
        ):
            out.append(stripped_nl.rstrip() + " na" + eol)
            i += 1
            continue

        # Assignment to empty structure: ``x = switch`` / ``x = switch expr`` / ``x = if c``
        m_as = re.match(
            r"^(\s*.*?\S)\s*=\s*(switch|if)\b(.*)$",
            stripped_nl,
        )
        if (
            m_as
            and not stripped_nl.lstrip().startswith("//")
            and "=>" not in m_as.group(3)
            and not _line_has_arg_continuation(line, lines, i)
        ):
            indent = re.match(r"^(\s*)", stripped_nl).group(1)  # type: ignore[union-attr]
            j = i + 1
            has_body = False
            while j < len(lines):
                nxt = lines[j]
                if not nxt.strip():
                    j += 1
                    continue
                if len(nxt) - len(nxt.lstrip(" \t")) <= len(indent) and nxt.strip():
                    break
                if nxt.lstrip().startswith("//"):
                    j += 1
                    continue
                has_body = True
                break
            if not has_body:
                # Replace RHS structure with na (structure body was truncated).
                out.append(m_as.group(1) + " = na" + eol)
                i += 1
                continue

        # Control header with empty/comment-only body (includes switch)
        m = re.match(r"^(\s*)(if|else if|else|for|while|switch)\b(.*)$", stripped_nl)
        if m and not stripped_nl.rstrip().endswith(("=>", ":")):
            indent, kw, rest = m.group(1), m.group(2), m.group(3)
            if "=>" not in rest:
                j = i + 1
                has_body = False
                first_same: int | None = None
                while j < len(lines):
                    nxt = lines[j]
                    if not nxt.strip():
                        j += 1
                        continue
                    ni = len(nxt) - len(nxt.lstrip(" \t"))
                    if ni <= len(indent) and nxt.strip():
                        first_same = j
                        break
                    if nxt.lstrip().startswith("//"):
                        j += 1
                        continue
                    has_body = True
                    break
                if not has_body:
                    child = (
                        "\t"
                        if any("\t" in ln for ln in lines[i : min(i + 5, len(lines))])
                        else "    "
                    )
                    # Docs scrapes often put the then/else body at the *same* indent
                    # as ``if`` / ``else if`` (no INDENT tokens). Promote those lines
                    # as a real body until the next sibling ``else`` / control / dedent.
                    if (
                        first_same is not None
                        and kw in {"if", "else if", "else", "for", "while"}
                        and not lines[first_same].lstrip().startswith(
                            ("else", "else if", "if ", "for ", "while ", "switch ", "type ", "enum ")
                        )
                    ):
                        out.append(line if line.endswith("\n") else line + "\n")
                        k = first_same
                        while k < len(lines):
                            ln = lines[k]
                            if not ln.strip():
                                out.append(ln if ln.endswith("\n") else ln + "\n")
                                k += 1
                                continue
                            li = len(ln) - len(ln.lstrip(" \t"))
                            if li < len(indent):
                                break
                            ns = ln.lstrip()
                            if li == len(indent) and ns.startswith(
                                ("else", "else if", "if ", "for ", "while ", "switch ", "type ", "enum ")
                            ):
                                break
                            if li == len(indent):
                                piece = indent + child + ns
                                out.append(piece if piece.endswith("\n") else piece + "\n")
                                k += 1
                                continue
                            # Already deeper than if — keep as-is
                            out.append(ln if ln.endswith("\n") else ln + "\n")
                            k += 1
                        i = k
                        continue
                    if kw == "switch":
                        out.append(indent + "na" + eol)
                    else:
                        out.append(line if line.endswith("\n") else line + "\n")
                        out.append(indent + child + "na" + eol)
                    i += 1
                    continue
        out.append(line)
        i += 1
    return _ensure_truncated_function_arrow(_append_missing_closers("".join(out)))


# A single typed parameter line inside a function signature (docs scrape cut).
_TYPED_PARAM_LINE_RE = re.compile(
    r"^\s*(?:(?:series|simple|const)\s+)?"
    r"(?:int|float|bool|string|color|line|label|box|table|chart\.point|"
    r"array(?:\s*<[^>\n]*>)?|matrix(?:\s*<[^>\n]*>)?|map(?:\s*<[^>\n]*>)?)"
    r"\s+[A-Za-z_]\w*"
)
_FUNC_OPEN_LINE_RE = re.compile(
    r"^\s*(?:export\s+)?(?:method\s+)?[A-Za-z_]\w*\s*\(\s*$"
)


def _ensure_truncated_function_arrow(text: str) -> str:
    """Append `` => na`` when a typed multi-line function header has no body.

    Matches only this shape at EOF (after paren closers may have been added)::

        timeWithinAllowedRange(
             int    startTime, int endTime,
             bool   useDateFilter = true,
             string timeZone      = "GMT-0")

    Never treats ``plot(...)`` / ``hline(...)`` / method *calls* as definitions:
    those lack typed ``int x`` parameter lines between ``name(`` and ``)``.
    """
    if re.search(r"=>\s*\S", text.rstrip()[-120:]):
        return text

    lines = text.splitlines()
    code_idxs = [
        i for i, ln in enumerate(lines) if ln.strip() and not ln.lstrip().startswith("//")
    ]
    if len(code_idxs) < 3:
        return text

    last_i = code_idxs[-1]
    last = lines[last_i].rstrip()
    if not last.endswith(")"):
        return text

    # Walk back over typed param lines (last line may be ``string x = "GMT-0")``).
    def _is_param_line(ln: str) -> bool:
        # Strip trailing ``)`` / ``,`` for the closing param line.
        core = ln.rstrip()
        if core.endswith(")"):
            core = core[:-1].rstrip()
        core = core.rstrip(",").rstrip()
        if not core:
            return False
        return bool(_TYPED_PARAM_LINE_RE.match(core))

    # Last line must itself be a typed param (with optional closing paren).
    if not _is_param_line(lines[last_i]):
        return text

    k = len(code_idxs) - 2  # index into code_idxs
    while k >= 0 and _is_param_line(lines[code_idxs[k]]):
        k -= 1
    if k < 0:
        return text

    header_i = code_idxs[k]
    if not _FUNC_OPEN_LINE_RE.match(lines[header_i]):
        return text

    # At least one typed param between header and close (already verified last).
    if (len(code_idxs) - 1) - k < 2:
        return text

    eol = "\n" if text.endswith("\n") else ""
    return text.rstrip("\n") + " => na" + eol


def _compose(provenance: list[str], body: str, ends_with_nl: bool) -> str:
    body = body.strip()
    parts = [p for p in ("\n".join(provenance).rstrip(), body) if p]
    text = "\n\n".join(parts)
    if ends_with_nl and text and not text.endswith("\n"):
        text += "\n"
    elif not text.endswith("\n"):
        text += "\n"
    return text


def _is_effectively_empty_script(body: str) -> bool:
    """True for stubs like bare ``library().`` / ``library(...)`` with no body."""
    # Strip comments and blanks
    code = []
    for ln in body.splitlines():
        s = ln.strip()
        if not s or s.startswith("//"):
            continue
        code.append(s)
    if not code:
        return True
    if len(code) == 1 and re.match(r"^(indicator|strategy|library|study)\s*\(.*\)\s*\.?\s*$", code[0]):
        # ``library().`` or ``strategy("x", ...)`` alone with no executable body — keep
        # declaration-only scripts that already parse; only stub broken tails.
        if code[0].endswith(").") or code[0].endswith("..."):
            return True
    return False


def _finalize(provenance: list[str], body: str, ends_with_nl: bool) -> str:
    body = _fix_truncated_syntax(_fix_missing_decl_commas(body))
    if not _has_usable_pine(body) or _is_effectively_empty_script(body):
        body = _MINIMAL_STUB
    return _compose(provenance, body, ends_with_nl)


def _pick_best_block(blocks: list[str]) -> tuple[str | None, int]:
    best: str | None = None
    best_score = 0
    for block in blocks:
        sc = _score_pine_block(block)
        if sc > best_score:
            best_score = sc
            best = block
    return best, best_score


def _clean_block_body(best: str) -> str:
    body = _line_filter(best)
    # If filter emptied a good fence, use raw fence body with light cleanup
    if not any(ln.strip() and not ln.lstrip().startswith("//") for ln in body.splitlines()):
        body = "\n".join(c for ln in best.splitlines() if (c := _strip_line_chrome(ln)) is not None)
    return body


def sanitize_corpus_source(source: str) -> str:
    """Drop or unwrap non-Pine chrome common in scraped corpus scripts."""
    ends_with_nl = source.endswith("\n")
    source = _normalize_chrome(source)
    lines = source.splitlines()

    provenance, body_lines = _split_provenance(lines)
    body_text = "\n".join(body_lines)

    # Candidate extractable Pine islands (fences, TV "Copied", shell heredocs).
    blocks: list[str] = []
    blocks.extend(_extract_fenced_blocks(lines))
    blocks.extend(_extract_tv_copied_blocks(lines))
    blocks.extend(_extract_heredoc_blocks(lines))

    best, best_score = _pick_best_block(blocks)

    # Prefer an extracted island when it looks like real Pine.
    if best is not None and best_score >= 40:
        return _finalize(provenance, _clean_block_body(best), ends_with_nl)

    # Foreign scrape (shell / Python / pytest / PR markdown): never feed whole file
    # to the line filter — embedded //@version in strings would partially leak.
    if _looks_like_foreign(body_text):
        return _finalize(provenance, _MINIMAL_STUB, ends_with_nl)

    # No usable fence: line-filter the whole file (also cuts trailing chrome).
    filtered = _line_filter(source)
    filt_lines = filtered.splitlines()
    while filt_lines and _is_provenance(filt_lines[0]):
        filt_lines.pop(0)
    while filt_lines and not filt_lines[0].strip():
        filt_lines.pop(0)
    filtered_body = "\n".join(filt_lines)
    return _finalize(provenance, filtered_body, ends_with_nl)
