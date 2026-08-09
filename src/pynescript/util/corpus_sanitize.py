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

"""Sanitize messy Pine sources before parse.

Useful when user-supplied text still contains page chrome that is not valid Pine:

- Markdown fences (``` / ```pine / ```pinescript)
- Blockquote chrome (`> Name`, `> Detail`, …)
- ``Expand (N lines)`` UI stubs
- Horizontal rules, bare URLs, publication footers
- Leading write-ups before the real script
- Mis-collected shell / Python / HTML fragments

Markdown for ``//@function`` hover annotations lives only inside ``//`` comments
and is left alone. This module strips *page* chrome, not annotation Markdown.

When a file yields no usable Pine after chrome strip, a minimal parseable stub
is returned so callers can fail softly instead of crashing on empty input.
"""

from __future__ import annotations

import re

# Minimal script used when scrape content is foreign / empty of real Pine.
_MINIMAL_STUB = '//@version=5\nindicator("x")\nplot(close)\n'

# TV community "Expand (N lines)" UI stub — often at EOF; closing ``)`` may be cut.
_EXPAND_RE = re.compile(r"^\s*Expand\s*\(\s*\d+\s*lines?\s*\)?\s*$", re.I)
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

# Apostrophe class: ASCII + curly quotes common in TV docs scrapes (U+2019 / U+2018).
_APOS = r"['\u2019\u2018]"

# English / docs prose that appears after a real script on scraped TV pages.
_PROSE_CONTINUE_RE = re.compile(
    r"^\s*("
    r"Note that:?|"
    r"Tips?:?|"
    rf"Let{_APOS}s\s|"
    r"We\s+(use|set|provide|define|call|populate|offer|create|do|pass)|"
    r"To\s+(color|plot|use|create|exit|exit|build|learn)|"
    r"You\s+(can|may|will|should)|"
    r"This\s+(example|plots?|script|configuration|function|parameter)|"
    r"When\s+(creating|populating|the|using)|"
    r"The\s+(signature|script|color|maximum|initialization|first|second|third|next|last)|"
    r"There\s+are\s+|"
    rf"It{_APOS}s\s+(important|also|possible|useful)|"
    r"Take note of|"
    r"Specifies\s+|"
    r"Controls\s+the\s+|"
    r"Looking\s+(two|one|at)\s+|"
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

# TV / GitHub UI chrome lines that often appear between a truncated preview and
# the full script copy (set05 hasnocool scrapes).
_UI_CHROME_LINE_RE = re.compile(
    r"^\s*("
    r"PineScript\s+code\s*:?|"
    r"Pine\s+Script\s*(?:strategy|indicator|library|code)?\s*:?|"
    r"Copy\s+code|"
    r"Copied|"
    r"loading\.\.\.|"
    r"//\s*This source code is subject to the terms"
    r")\s*$",
    re.I,
)
# Standalone line-number gutter from "Copy code" widgets: ``1`` .. ``999``.
_LINE_NUMBER_ONLY_RE = re.compile(r"^\s*\d{1,4}\s*$")

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


# Invisible / exotic spaces that break the ANTLR lexer as unknown tokens.
_UNICODE_SPACE_RE = re.compile(
    "[\u00a0\u1680\u2000-\u200b\u202f\u205f\u3000\ufeff]"  # nbsp, hair, ZWSP, BOM, …
)


def _normalize_chrome(text: str) -> str:
    """Drop HTML comments and trademark noise that breaks the lexer."""
    text = _strip_html_comments(text)
    # ® / ™ only appear as Pine Script®/™ chrome in this corpus — strip globally.
    text = text.replace("®", "").replace("™", "").replace("\u2122", "")
    # Normalize exotic unicode spaces (hair space in ``import x as y`` scrapes).
    text = _UNICODE_SPACE_RE.sub(" ", text)
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
# Case-sensitive Capitalized nav words after ≥2 spaces; may be followed by more
# title-case sidebar junk (``Previous Strategies Next Techniques …``).
# Do NOT use IGNORECASE — English ``next to`` must not match.
_DOCS_NAV_TRAIL_RE = re.compile(
    r"[ \t]{2,}(Next|Previous|On this page)\b.*$"
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
    # Mid-call docs ellipsis without a closer: ``input.int(55, "EMA 5", minval=1,...``
    # Strip the ellipsis so paren-balance repair can close the call.
    if not line.lstrip().startswith("//"):
        line = re.sub(r",\s*\.\.\.\s*$", "", line)
        line = re.sub(r"\(\s*\.\.\.\s*$", "(", line)
    # TV library import UI residual: ``import x/y/1 as eta loading...``
    if not line.lstrip().startswith("//"):
        line = re.sub(r"\s+loading\.\.\.\s*$", "", line, flags=re.I)
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
    if _UI_CHROME_LINE_RE.match(line):
        return None
    if _LINE_NUMBER_ONLY_RE.match(line):
        return None
    if _HTML_COMMENT_OPEN_RE.match(line):
        return None
    if stripped.startswith("##") or stripped.startswith("# "):
        return None
    # Fence / inline-code residue common in multi-example docs scrapes.
    if stripped in ("`", "``", "```", "````"):
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


def _string_state_after_line(line: str, state: str | None) -> str | None:
    """Track open quote state across lines for sanitize (``None`` | ``\"`` | ``'`` | ``\"\"\"`` | ``'''``).

    Used so prose / chrome heuristics do not fire *inside* multiline string literals.
    Best-effort; escape handling mirrors the truncated-syntax paren scanner.
    """
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if state is None:
            if ch == "/" and i + 1 < n and line[i + 1] == "/":
                break  # rest of line is comment
            if ch in "\"'":
                if line.startswith(ch * 3, i):
                    state = ch * 3
                    i += 3
                    continue
                state = ch
                i += 1
                continue
            i += 1
            continue
        # Inside a string
        if state in ('"""', "'''"):
            if line.startswith(state, i):
                state = None
                i += 3
                continue
            i += 1
            continue
        # Single-quoted / double-quoted (may span lines only if unclosed scrape)
        if ch == "\\" and i + 1 < n:
            i += 2
            continue
        if ch == state:
            state = None
        i += 1
    return state


def _line_filter(source: str) -> str:
    """Line-oriented chrome removal when no reliable fence body is available."""
    out: list[str] = []
    saw_pine = False
    str_state: str | None = None
    for line in source.splitlines():
        # Inside an open multiline / unclosed string: keep the line verbatim and
        # never apply prose/chrome stops (content often looks like English docs).
        if str_state is not None:
            out.append(line)
            str_state = _string_state_after_line(line, str_state)
            continue

        if _FENCE_RE.match(line):
            # Opening fence before real pine: skip. Closing fence after pine: stop.
            if saw_pine:
                break
            continue

        # ``Expand (N lines)`` after real code = collapsed / truncated UI residual.
        # Drop the stub and stop so any trailing page chrome cannot re-enter.
        if _EXPAND_RE.match(line):
            if saw_pine:
                break
            continue

        # UI chrome between truncated preview and full copy (``Copy code``, gutters).
        if saw_pine and (
            _UI_CHROME_LINE_RE.match(line)
            or _LINE_NUMBER_ONLY_RE.match(line)
            or _TV_PINE_LABEL_RE.match(line)
        ):
            break

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
                or _UI_CHROME_LINE_RE.match(line)
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
        str_state = _string_state_after_line(cleaned, None)

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


def _is_type_or_enum_declaration(ns: str) -> bool:
    """True for UDT/enum declaration lines — not soft-keyword identifier use.

    Pine allows ``type`` / ``enum`` as ordinary names (``type == "SMA"``). Only
    ``type Name`` / ``enum Name`` (optional trailing comment) are declarations.
    """
    return bool(re.match(r"^(type|enum)\s+[A-Za-z_]\w*\s*(//.*)?$", ns))


def _is_method_declaration(ns: str) -> bool:
    """True for ``method [retType] name(`` declarations, not ``method ==`` etc."""
    return bool(
        re.match(
            r"^method\s+(?:(?:series|simple|const)\s+)?"
            r"(?:[A-Za-z_]\w*(?:<[^>\n]*>)?(?:\[\])?\s+)?"
            r"[A-Za-z_]\w*\s*\(",
            ns,
        )
    )


def _starts_structural_statement(ns: str) -> bool:
    """True if *ns* begins a control/decl statement (not soft-keyword as identifier)."""
    if not ns:
        return False
    if re.match(r"^(if|for|while|switch|else|import|export|var|varip)\b", ns):
        return True
    if _is_type_or_enum_declaration(ns) or re.match(r"^(type|enum)\s*$", ns):
        return True
    if _is_method_declaration(ns):
        return True
    return False


def _looks_like_expr_continuation(ns: str) -> bool:
    """True if *ns* (lstripped) continues a binary/logical expression, not a new stmt."""
    if not ns or ns.startswith("//"):
        return False
    # Hard structural keywords only — soft keywords (``type``/``method``/``enum``)
    # may head expression arms: ``type == "SMA" ? … :``.
    if _starts_structural_statement(ns):
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


def _code_without_line_comment(line: str) -> str:
    """Strip a trailing ``//`` line comment, respecting quotes (best-effort)."""
    in_str: str | None = None
    esc = False
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if esc:
            esc = False
            i += 1
            continue
        if in_str:
            if ch == "\\":
                esc = True
            elif ch == in_str:
                in_str = None
            i += 1
            continue
        if ch in "\"'":
            # Triple quotes: treat as string open and skip the rest of the line
            # content for comment-strip purposes (multiline handled elsewhere).
            if line.startswith(ch * 3, i):
                return line  # open triple — do not strip // inside
            in_str = ch
            i += 1
            continue
        if ch == "/" and i + 1 < n and line[i + 1] == "/":
            return line[:i].rstrip()
        i += 1
    return line.rstrip()


def _incomplete_ternary_suffix(code: str) -> str | None:
    """If *code* is a truncated ternary, return the suffix to append; else None.

    Quote-aware: question marks inside string literals (``"Highlight ?"``) are
    ignored so complete input lines are never corrupted.
    """
    in_str: str | None = None
    esc = False
    last_q = -1
    last_colon_after_q = -1
    i = 0
    n = len(code)
    while i < n:
        ch = code[i]
        if esc:
            esc = False
            i += 1
            continue
        if in_str:
            if ch == "\\":
                esc = True
            elif ch == in_str:
                in_str = None
            i += 1
            continue
        if ch in "\"'":
            # Triple quotes: skip to close or EOL (best-effort)
            if code.startswith(ch * 3, i):
                i += 3
                while i < n and not code.startswith(ch * 3, i):
                    i += 1
                i = min(n, i + 3)
                continue
            in_str = ch
            i += 1
            continue
        if ch == "?":
            last_q = i
            last_colon_after_q = -1
        elif ch == ":" and last_q >= 0:
            last_colon_after_q = i
        i += 1
    if last_q < 0:
        return None
    stripped = code.rstrip()
    if not stripped:
        return None
    if last_colon_after_q >= 0:
        # Trailing ``:`` with no false-branch token after it.
        if stripped.endswith(":") and last_colon_after_q == len(stripped) - 1:
            return " na"
        return None  # complete ternary on this line
    # Unquoted ``?`` with no following ``:``
    if re.search(r"\?\s*$", stripped):
        return " na : na"
    # True branch present, false missing: ``… ? expr``
    if last_q < len(stripped) - 1:
        return " : na"
    return None


def _next_line_is_new_statement(lines: list[str], index: int) -> bool:
    """True if the next non-empty non-comment line starts a new statement (or EOF)."""
    j = index + 1
    while j < len(lines) and (not lines[j].strip() or lines[j].lstrip().startswith("//")):
        j += 1
    if j >= len(lines):
        return True
    ns = lines[j].lstrip()
    # Soft keywords ``type``/``method``/``enum`` are identifiers unless declaration form.
    if re.match(
        r"^(if|for|while|switch|else|import|export|var|varip|"
        r"indicator|strategy|library|study|plot|plotshape|plotchar|plotcandle|"
        r"plotbar|fill|bgcolor|barcolor|hline|alertcondition|alert)\b",
        ns,
    ):
        return True
    if _starts_structural_statement(ns):
        return True
    # Assignment / reassignment statement
    if re.match(r"^[A-Za-z_]\w*(?:\.\w+|\[[^\]]*\])*\s*:=?", ns) and not re.match(
        r"^[A-Za-z_]\w*\s*==", ns
    ):
        # ``name =`` / ``name :=`` but not ``name ==``
        if re.match(r"^[A-Za-z_]\w*(?:\.\w+|\[[^\]]*\])*\s*:=", ns):
            return True
        if re.match(r"^[A-Za-z_]\w*(?:\.\w+|\[[^\]]*\])*\s*=(?![=<>])", ns):
            return True
    return False


def _line_has_arg_continuation(line: str, lines: list[str], index: int) -> bool:
    """True if a following non-empty line continues this statement (indent/join)."""
    j = index + 1
    while j < len(lines) and (not lines[j].strip() or lines[j].lstrip().startswith("//")):
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
    prev_code = _code_without_line_comment(prev)

    # Multi-line call / paren wrap: bare open ``(`` means any following non-empty
    # non-comment line is an argument (Pine allows zero-indent args inside parens).
    #   plot(
    #   median,
    #     "Median")
    # Without this, truncate-repair rewrote valid wraps to ``plot(na)``.
    if prev_code.endswith("(") or prev_code.endswith("["):
        return True

    # Function / lambda body after ``=>`` (optionally ``=> //{`` region comment).
    # Multi-line signatures often indent the closing ``) =>`` deeper than the body:
    #   f(a,
    #          b) =>
    #       body   # indent 4 < base 7 — still a real body
    # Same-indent next line is *not* a valid Pine body (needs INDENT); treat as
    # no continuation so empty-arrow repair can inject ``na`` rather than leave
    # a parse-failing nested UDF (common scrape of local functions under ``if``).
    if re.search(r"=>\s*$", prev_code):
        if nxt_indent > base_indent:
            return True
        if 0 < nxt_indent < base_indent:
            return True

    # Same-indent ternary arm continuation: ``x = a ? b :`` / next ``c ? d : e``.
    # Soft-keyword identifiers (esp. ``type``) commonly head MA-selector arms:
    #   type == "SMA" ? ta.sma(...) :
    #   type == "EMA" ? ta.ema(...) :
    # Only structural statements break the chain (not bare ``type `` prefix).
    if nxt_indent == base_indent and prev_code.endswith(("?", ":")):
        if not _starts_structural_statement(ns):
            return True
    # Same-indent arithmetic / logical / concat after a trailing binary op:
    #   ``… +`` / ``… -`` / ``… *`` / ``… /`` / ``… and`` / ``… or``
    # next term may start with a digit (``2 * x``) or identifier (``td == …``).
    mop = _TRAILING_BINOP_RE.match(prev_code)
    if mop and _looks_like_expr_continuation(ns):
        if nxt_indent >= base_indent:
            return True
        # Scrape often reduces indent mid-expression under a function body:
        #   ``    a and``
        #   ``  b and``   (2 spaces < 4, still part of the same bool chain)
        if base_indent >= 2 and 1 <= nxt_indent < base_indent:
            return True
    # Also bare endswith for ops that may have no space: ``x+`` rare but ``x +`` covered.
    if prev_code.endswith(("+", "-", "*", "/")) and _looks_like_expr_continuation(ns):
        if nxt_indent >= base_indent or (base_indent >= 2 and 1 <= nxt_indent < base_indent):
            return True
    return False


# Dangling binary/logical op immediately before a closer after scrape repair:
# ``str.tostring(a) +)`` / ``"session " +)`` / ``cond and)``.
# Space-bounded so identifiers like ``foo+)`` are untouched; mirrors line polish.
_DANGLING_BINOP_BEFORE_CLOSER_RE = re.compile(
    r"\s+(?:and|or|\+|\-|\*|/)\s*(?=[\)\]])"
)


def _strip_dangling_binop_before_closers(text: str) -> str:
    """Drop incomplete trailing binops glued to ``)`` / ``]`` by closer injection."""
    return _DANGLING_BINOP_BEFORE_CLOSER_RE.sub("", text)


def _close_trailing_opens_on_line(core: str) -> str:
    """Close unclosed ``(`` / ``[`` on a truncated line.

    Empty calls (``log.info(``) / trailing commas get a ``na`` placeholder.
    Partial args that already end with a value (``input.int(1, minval=1``) only
    need the matching closers — injecting ``na`` would produce invalid syntax.

    Mid-expression docs scrapes often cut after a binary/logical op inside an
    open call (``label.new(..., str.tostring(a) +``). Drop that dangling op so
    the last complete operand remains, then close — never emit invalid ``+)``.
    """
    # High-confidence truncated scrape: incomplete ``… +`` / ``… and`` at EOL
    # inside an unclosed call. Prefer stripping the op over inventing ``na`` so
    # the left operand (already a full string/expr) stays the final arg.
    mop = _TRAILING_BINOP_RE.match(core.rstrip())
    if mop:
        core = mop.group("head")

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
    stripped = core.rstrip()
    needs_placeholder = bool(re.search(r"[(,]\s*$", stripped))
    if depth_p > 0:
        if needs_placeholder:
            core = core + "na" + (")" * depth_p)
        else:
            core = core + (")" * depth_p)
    if depth_b > 0:
        depth_b = 0
        for ch in core:
            if ch == "[":
                depth_b += 1
            elif ch == "]":
                depth_b = max(0, depth_b - 1)
        if depth_b > 0:
            if needs_placeholder or core.rstrip().endswith("["):
                core = core + "na" + ("]" * depth_b)
            else:
                core = core + ("]" * depth_b)
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

        # Incomplete call / open paren: ``log.info(`` / ``label.new(`` at EOF,
        # or mid-file truncated calls after ellipsis strip: ``input.int(55, minval=1``
        # when the next line is a new statement (not an arg continuation).
        if not stripped_nl.lstrip().startswith("//") and not _line_has_arg_continuation(
            line, lines, i
        ):
            code_core = _code_without_line_comment(stripped_nl)
            depth_p, depth_b = _code_paren_bracket_depth(code_core)
            bare_open = bool(re.search(r"[\(\[]\s*$", code_core))
            # Partial-arg truncated line only when the following line is clearly a
            # new statement (or EOF) — never glue free-indent multi-line args.
            if depth_p > 0 or depth_b > 0:
                if bare_open or _next_line_is_new_statement(lines, i):
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

        # Empty function / lambda body: ``f(...) =>`` at cut, ``f() =>  // comment``,
        # or body is only //@variable / comments until next real stmt / EOF.
        code_no_comment = _code_without_line_comment(stripped_nl)
        if re.search(r"=>\s*$", code_no_comment) and not stripped_nl.lstrip().startswith("//"):
            j = i + 1
            only_comments = True
            while j < len(lines):
                nxt = lines[j]
                if not nxt.strip():
                    j += 1
                    continue
                if nxt.lstrip().startswith("//"):
                    j += 1
                    continue
                only_comments = False
                break
            if only_comments:
                # Keep header + comment-only body, then inject ``na``.
                out.append(line if line.endswith("\n") else line + "\n")
                k = i + 1
                while k < len(lines):
                    nxt = lines[k]
                    if not nxt.strip() or nxt.lstrip().startswith("//"):
                        out.append(nxt if nxt.endswith("\n") else nxt + "\n")
                        k += 1
                        continue
                    break
                indent = re.match(r"^(\s*)", stripped_nl).group(1)  # type: ignore[union-attr]
                child = "\t" if "\t" in stripped_nl else "    "
                out.append(indent + child + "na\n")
                i = k
                continue
            if not _line_has_arg_continuation(line, lines, i):
                # Preserve trailing // comment if present.
                if "//" in stripped_nl:
                    head, _, cmt = stripped_nl.partition("//")
                    out.append(head.rstrip() + " na  //" + cmt + eol)
                else:
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

        # Incomplete ternary at scrape cut (quote-aware — ``"Highlight ?"`` is NOT ternary):
        #   ``c = open > close ? color.red :``  → append ``na``
        #   ``x = cond ? weekdaySession``       → append `` : na``
        # Never fires when a same-indent ternary arm continues on the next line.
        if not stripped_nl.lstrip().startswith("//") and not _line_has_arg_continuation(
            line, lines, i
        ):
            code_t = _code_without_line_comment(stripped_nl).rstrip()
            tern_fix = _incomplete_ternary_suffix(code_t)
            if tern_fix is not None:
                out.append(stripped_nl.rstrip() + tern_fix + eol)
                i += 1
                continue

        # Assignment to empty structure: ``x = switch`` / ``x = if c`` / ``x = for …`` /
        # ``x = while …`` with no body (truncated TV docs demos).
        m_as = re.match(
            r"^(\s*.*?\S)\s*=\s*(switch|if|for|while)\b(.*)$",
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
    repaired = _append_missing_closers("".join(out))
    # Closer injection can recreate ``expr +)`` when a multi-line unclosed call
    # ends on a trailing binop that only got ``na`` on a later pass, or when a
    # residual ``+`` survived line-local close. Strip dangling ops before closers.
    repaired = _strip_dangling_binop_before_closers(repaired)
    repaired = _collapse_na_only_control_expr_assignments(repaired)
    return _ensure_truncated_function_arrow(repaired)


# Statement / expression leaves that do not constitute a real truncated-demo body.
_NA_ONLY_LEAF_RE = re.compile(r"^(na|continue|break)\s*$")
_CTRL_HEAD_RE = re.compile(r"^(if|else if|else|for|while|switch)\b")


def _collapse_na_only_control_expr_assignments(text: str) -> str:
    """Collapse ``lhs = for|while|if|switch …`` bodies that are only ``na`` / empty ctrls.

    Truncated TV docs leave expression-for loops such as::

        string finalLabelText = for number in randomArray
            if number == 8
                na

    These parse after empty-body injection but the compiler cannot emit
    ``x = for …`` as Python. When every non-comment leaf under the RHS is bare
    ``na`` / ``continue`` / ``break`` (or nested empty controls), rewrite to
    ``lhs = na``. Real expression-for bodies (any other statement/expr) are kept.
    """
    lines = text.splitlines(keepends=True)
    if not lines:
        return text
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.rstrip("\n")
        m = re.match(
            r"^(\s*)(.*?\S)\s*=\s*(for|while|if|switch)\b(.*)$",
            stripped,
        )
        if (
            m
            and not stripped.lstrip().startswith("//")
            and "=>" not in m.group(4)
        ):
            indent, lhs = m.group(1), m.group(2)
            j = i + 1
            has_code = False
            only_na_or_ctrl = True
            while j < len(lines):
                nxt = lines[j]
                if not nxt.strip():
                    j += 1
                    continue
                ni = len(nxt) - len(nxt.lstrip(" \t"))
                if ni <= len(indent) and nxt.strip():
                    break
                if nxt.lstrip().startswith("//"):
                    j += 1
                    continue
                has_code = True
                ns = nxt.lstrip().rstrip("\n").rstrip()
                if _CTRL_HEAD_RE.match(ns) or _NA_ONLY_LEAF_RE.match(ns):
                    j += 1
                    continue
                only_na_or_ctrl = False
                break
            if not has_code or only_na_or_ctrl:
                eol = "\n" if line.endswith("\n") else ""
                out.append(f"{indent}{lhs} = na{eol}")
                i = j
                continue
        out.append(line)
        i += 1
    return "".join(out)


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


def _dedent_if_leading_indent(body: str) -> str:
    """Strip a shared leading indent when the first code line is indented.

    Docs / error examples often paste whole scripts indented under a fence::

        //@version=4
            study("My Script")
            plot(close)

    The lexer rejects a first statement that starts with INDENT.
    """
    lines = body.splitlines(keepends=True)
    code_idxs: list[int] = []
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s or s.startswith("//"):
            continue
        # Skip version pragma for indent measurement
        if re.match(r"^//@version\b", s):
            continue
        code_idxs.append(i)
    if not code_idxs:
        return body
    first = lines[code_idxs[0]]
    if not first[:1].isspace():
        return body
    # Common prefix of pure whitespace across all code lines
    indents = []
    for i in code_idxs:
        ln = lines[i]
        if not ln.strip():
            continue
        m = re.match(r"^([ \t]+)", ln)
        if not m:
            return body  # mixed: some code at column 0
        indents.append(m.group(1))
    if not indents:
        return body
    # Longest common prefix of indent strings
    prefix = indents[0]
    for ind in indents[1:]:
        while prefix and not ind.startswith(prefix):
            prefix = prefix[:-1]
        if not prefix:
            return body
    if not prefix:
        return body
    n = len(prefix)
    out: list[str] = []
    for ln in lines:
        if ln.startswith(prefix):
            out.append(ln[n:])
        else:
            out.append(ln)
    return "".join(out)


# Field-ish lines after ``type Name`` when docs scrapes lose the INDENT:
#   type pivotPoint
#   int x
#   float y = close
_TYPE_FIELD_LINE_RE = re.compile(
    r"^(?:"
    r"(?:(?:series|simple|const)\s+)?"
    r"(?:int|float|bool|string|color|line|label|box|table|array|map|matrix|"
    r"chart\.point)"
    r"(?:\s*<[^>\n]*>)?"
    r"(?:\[\])?"
    r"\s+[A-Za-z_]\w*"
    r"(?:\s*=.*)?"
    r"|"
    r"[A-Za-z_]\w*\s+[A-Za-z_]\w*"  # UDT-typed field: ``pivotPoint p``
    r"(?:\s*=.*)?"
    r")\s*$"
)


def _fix_empty_type_body(body: str) -> str:
    """Repair empty / same-indent ``type`` bodies from truncated docs scrapes.

    - ``type Wrapper`` with no fields → dummy ``float _pad = na``
    - Fields pasted at the *same* indent as ``type`` (lost INDENT) → promote
    """
    lines = body.splitlines(keepends=True)
    if not lines:
        return body
    out: list[str] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        m = re.match(r"^(\s*)type\s+([A-Za-z_]\w*)\s*$", ln.rstrip("\n"))
        if m and not ln.lstrip().startswith("//"):
            indent, _name = m.group(1), m.group(2)
            child = "\t" if "\t" in ln else "    "
            j = i + 1
            has_indented_field = False
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
                has_indented_field = True
                break
            out.append(ln if ln.endswith("\n") else ln + "\n")
            if has_indented_field:
                i += 1
                continue
            # Promote same-indent type fields (docs HTML→text lost indent).
            if first_same is not None:
                k = first_same
                promoted = 0
                while k < len(lines):
                    nxt = lines[k]
                    if not nxt.strip():
                        # Blank inside a field block — keep and continue
                        out.append(nxt if nxt.endswith("\n") else nxt + "\n")
                        k += 1
                        continue
                    ni = len(nxt) - len(nxt.lstrip(" \t"))
                    if ni < len(indent):
                        break
                    ns = nxt.lstrip().rstrip("\n")
                    if ni == len(indent):
                        if ns.startswith(
                            (
                                "type ",
                                "enum ",
                                "import ",
                                "export ",
                                "method ",
                                "if ",
                                "for ",
                                "while ",
                                "switch ",
                                "indicator(",
                                "strategy(",
                                "library(",
                                "study(",
                            )
                        ) or re.match(r"^//@version\b", ns):
                            break
                        if not _TYPE_FIELD_LINE_RE.match(ns):
                            # Non-field sibling (e.g. ``pivotHighPrice = …``)
                            break
                        piece = indent + child + ns
                        out.append(piece if piece.endswith("\n") else piece + "\n")
                        promoted += 1
                        k += 1
                        continue
                    # Already deeper — keep
                    out.append(nxt if nxt.endswith("\n") else nxt + "\n")
                    k += 1
                    promoted += 1
                if promoted:
                    i = k
                    continue
            # Truly empty type body
            out.append(f"{indent}{child}float _pad = na\n")
            i += 1
            continue
        out.append(ln)
        i += 1
    return "".join(out)


def _split_version_islands(body: str) -> list[str]:
    """Split on ``//@version=`` so multi-copy scrapes can pick the best island."""
    lines = body.splitlines()
    if not lines:
        return []
    islands: list[list[str]] = []
    current: list[str] = []
    version_count = 0
    for ln in lines:
        if re.match(r"^\s*//@version\s*=", ln):
            version_count += 1
            if current and version_count > 1:
                islands.append(current)
                current = [ln]
                continue
        current.append(ln)
    if current:
        islands.append(current)
    return ["\n".join(isl) for isl in islands]


# Top-level script declaration on a non-comment line (not ``//indicator(...)``).
_TOP_SCRIPT_DECL_RE = re.compile(
    r"^\s*(strategy|indicator|library|study)\s*\(",
    re.MULTILINE,
)


def _island_has_top_script_decl(island: str) -> bool:
    """True if *island* has a live ``strategy``/``indicator``/… declaration."""
    return _TOP_SCRIPT_DECL_RE.search(island) is not None


def _merge_version_islands(islands: list[str]) -> str:
    """Rejoin version islands that form one continuous multi-section script.

    Mid-file ``//@version=`` often comes from pasted snippets (helpers + body).
    Keep the first version pragma; drop subsequent ones so the parser sees one
    script and retains UDF defs from early sections.
    """
    if not islands:
        return ""
    if len(islands) == 1:
        return islands[0]
    parts: list[str] = [islands[0].rstrip("\n")]
    for isl in islands[1:]:
        lines = isl.splitlines()
        # Drop leading //@version= from continuation islands.
        while lines and re.match(r"^\s*//@version\s*=", lines[0]):
            lines.pop(0)
        while lines and not lines[0].strip():
            lines.pop(0)
        if lines:
            parts.append("\n".join(lines).rstrip("\n"))
    return "\n".join(parts) + ("\n" if islands[0].endswith("\n") else "")


def _pick_best_version_island(body: str) -> str:
    """Resolve multi-``//@version`` scrapes: merge continuous sections or pick best.

    Two common shapes:

    1. **Continuous multi-section paste** — only one island has a live
       ``strategy``/``indicator``/… declaration; later islands are body/helpers
       glued with a second ``//@version`` (often next to a *commented*
       declaration). Merging preserves UDF defs (e.g. ``f_priorBarsSatisfied``)
       that would otherwise be dropped when the longer tail island wins.
    2. **True multi-copy** — two or more islands each declare a script
       (truncated preview + full copy). Prefer the higher-scoring island.

    Only activates when ≥2 ``//@version`` markers exist.
    """
    islands = _split_version_islands(body)
    if len(islands) < 2:
        return body

    decl_count = sum(1 for isl in islands if _island_has_top_script_decl(isl))
    # Zero or one live declaration → continuous paste (or header-only first).
    # Merge so early UDF/helper islands are not discarded for a longer tail.
    if decl_count <= 1:
        return _merge_version_islands(islands)

    best = islands[0]
    best_score = _score_pine_block(best)
    # Prefer longer complete copies when scores are close.
    for isl in islands[1:]:
        sc = _score_pine_block(isl)
        # Bonus: no mid-call ellipsis residual
        if ",..." not in isl and re.search(r",\s*\.\.\.\s*$", isl, re.M) is None:
            sc += 5
        # Bonus: balanced-ish paren depth
        dp, db = _code_paren_bracket_depth(isl)
        if dp == 0 and db == 0:
            sc += 10
        # Prefer islands with a live script declaration when both score.
        if _island_has_top_script_decl(isl):
            sc += 8
        if sc > best_score or (sc == best_score and len(isl) > len(best)):
            best_score = sc
            best = isl
    return best


def _finalize(provenance: list[str], body: str, ends_with_nl: bool) -> str:
    body = _pick_best_version_island(body)
    body = _dedent_if_leading_indent(body)
    body = _fix_truncated_syntax(_fix_missing_decl_commas(body))
    body = _fix_empty_type_body(body)
    # Only substitute the minimal stub for *non-Pine* / empty chrome.
    # Truncated real scripts (indicator/strategy/library + partial body) must
    # keep their declaration + remaining statements — never overwrite with
    # ``indicator("x"); plot(close)``. Broken bare ``library().`` tails are the
    # sole declaration-shaped exception via ``_is_effectively_empty_script``.
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


def _clean_and_score_island(text: str) -> tuple[str, int]:
    """Line-filter an island and return (cleaned_body, score)."""
    filtered = _line_filter(text)
    filt_lines = filtered.splitlines()
    while filt_lines and _is_provenance(filt_lines[0]):
        filt_lines.pop(0)
    while filt_lines and not filt_lines[0].strip():
        filt_lines.pop(0)
    body = "\n".join(filt_lines)
    sc = _score_pine_block(body)
    dp, db = _code_paren_bracket_depth(body)
    if dp == 0 and db == 0:
        sc += 10
    if re.search(r",\s*\.\.\.\s*$", body, re.M):
        sc -= 15
    return body, sc


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

    # Multi-copy / multi-section scrapes with more than one //@version.
    # Split *before* line-filter so UI chrome between copies cannot drop the full one.
    # Continuous pastes (one live declaration) are merged so early UDF defs survive.
    version_islands = _split_version_islands(body_text if body_text.strip() else source)
    if len(version_islands) >= 2:
        decl_count = sum(1 for isl in version_islands if _island_has_top_script_decl(isl))
        if decl_count <= 1:
            merged = _merge_version_islands(version_islands)
            cand, sc = _clean_and_score_island(merged)
            if _has_usable_pine(cand) and sc >= 40:
                return _finalize(provenance, cand, ends_with_nl)
        else:
            best_body: str | None = None
            best_sc = -10**9
            for isl in version_islands:
                cand, sc = _clean_and_score_island(isl)
                if not _has_usable_pine(cand):
                    continue
                if _island_has_top_script_decl(cand):
                    sc += 8
                if sc > best_sc or (sc == best_sc and best_body is not None and len(cand) > len(best_body)):
                    best_sc = sc
                    best_body = cand
            if best_body is not None and best_sc >= 40:
                return _finalize(provenance, best_body, ends_with_nl)

    # No usable fence: line-filter the whole file (also cuts trailing chrome).
    filtered = _line_filter(source)
    filt_lines = filtered.splitlines()
    while filt_lines and _is_provenance(filt_lines[0]):
        filt_lines.pop(0)
    while filt_lines and not filt_lines[0].strip():
        filt_lines.pop(0)
    filtered_body = "\n".join(filt_lines)
    return _finalize(provenance, filtered_body, ends_with_nl)
