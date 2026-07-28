# Copyright (C) 2025 jango-blockchained
#
# SPDX-License-Identifier: LGPL-3.0-or-later

"""Sanitize scraped Pine corpus sources before parse.

Many set01–set05 files include TradingView / FMZ / markdown / docs chrome that is
not valid Pine:

- Markdown fences (``` / ```pine / ```pinescript)
- Blockquote chrome (`> Name`, `> Detail`, `> Source (PineScript)`, …)
- ``Expand (N lines)`` UI stubs from community pages
- Horizontal rules, bare URLs, publication footers
- Leading bilingual strategy write-ups before the real script

TradingView Markdown for //@function hover annotations lives only inside //
comments and is left alone. This module strips *page* chrome, not annotation
Markdown.
"""

from __future__ import annotations

import re

_EXPAND_RE = re.compile(r"^\s*Expand\s*\(\s*\d+\s*lines?\s*\)\s*$", re.I)
_HR_RE = re.compile(r"^\s*([-*_])\1{2,}\s*$")  # --- *** ___
_URL_ONLY_RE = re.compile(r"^\s*https?://\S+\s*$", re.I)
_FENCE_RE = re.compile(r"^\s*```")
_ISO_DT_RE = re.compile(r"^\s*\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?\s*$")
_IMG_MD_RE = re.compile(r"^\s*!\[.*?\]\(.*?\)\s*$")
_MD_LINK_LINE_RE = re.compile(r"^\s*\[.*?\]\(https?://.*?\)\s*$")

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

# Lines that look like executable Pine (or annotations / version).
_PINE_START_RE = re.compile(
    r"^\s*("
    r"//@|"
    r"//#|"
    r"indicator\s*\(|"
    r"strategy\s*\(|"
    r"library\s*\(|"
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

_CODEISH_RE = re.compile(
    r"^[a-zA-Z_@/\[]|"
    r"^//|"
    r"^[0-9]|"
    r"^[\(\{\[]|"
    r"^(if|for|while|switch|var|varip|type|enum|import|export|strategy|"
    r"indicator|library|plot|plotshape|line|label|box|table|array|map|"
    r"matrix|request|ta\.|math\.|str\.|color\.|input)"
)

_PROVENANCE_RE = re.compile(
    r"^\s*//\s*(set\d+|source_|content_hash|collected|corpus)\b",
    re.I,
)


def _is_provenance(line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    if not s.startswith("//"):
        return False
    return bool(_PROVENANCE_RE.match(s) or s.startswith("// set") or "source_repo" in s or "source_path" in s)


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


def _score_pine_block(text: str) -> int:
    """Heuristic: higher = more likely real Pine script body."""
    score = 0
    if re.search(r"//@version\s*=", text):
        score += 50
    if re.search(r"\b(indicator|strategy|library)\s*\(", text):
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
    return score


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
    if stripped.startswith("##") or stripped.startswith("# "):
        return None
    if stripped in ("[trans]", "[/trans]", "||"):
        return None
    if _PROSE_LABEL_RE.match(line):
        return None
    if _FOOTER_LABELS.match(line) or _ISO_DT_RE.match(line):
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
            return inner
        return None

    return line


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
            # Footer after substantial pine body → stop
            if saw_pine and (
                _FOOTER_LABELS.match(line)
                or _ISO_DT_RE.match(line)
                or _PROSE_LABEL_RE.match(line)
            ):
                break
            continue

        if not saw_pine and not _is_provenance(cleaned) and not _PINE_START_RE.match(cleaned):
            # Skip leading prose until first pine-like line
            if cleaned.lstrip().startswith("//"):
                # Keep non-provenance comments only after pine starts
                continue
            # Blank lines before pine are fine to skip
            if not cleaned.strip():
                continue
            # Non-pine prose before script
            continue

        if _PINE_START_RE.match(cleaned) or (
            cleaned.strip()
            and not cleaned.lstrip().startswith("//")
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


def sanitize_corpus_source(source: str) -> str:
    """Drop or unwrap non-Pine chrome common in scraped corpus scripts."""
    lines = source.splitlines()

    # Preserve leading provenance comments for readability / debugging.
    provenance: list[str] = []
    for line in lines:
        if _is_provenance(line):
            provenance.append(line)
        elif line.strip() == "" and provenance:
            provenance.append(line)
        else:
            break

    blocks = _extract_fenced_blocks(lines)
    best: str | None = None
    best_score = 0
    for block in blocks:
        sc = _score_pine_block(block)
        if sc > best_score:
            best_score = sc
            best = block

    # Prefer fenced body when it looks like real Pine.
    if best is not None and best_score >= 40:
        body = _line_filter(best)
        # If filter emptied a good fence, use raw fence body with light cleanup
        if not any(ln.strip() and not ln.lstrip().startswith("//") for ln in body.splitlines()):
            body = "\n".join(
                c for ln in best.splitlines() if (c := _strip_line_chrome(ln)) is not None
            )
        parts = [p for p in ("\n".join(provenance).rstrip(), body.strip()) if p]
        text = "\n\n".join(parts)
        if source.endswith("\n"):
            text += "\n"
        return _fix_missing_decl_commas(text)

    # No usable fence: line-filter the whole file (also cuts trailing chrome).
    return _fix_missing_decl_commas(_line_filter(source))
