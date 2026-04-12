# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

"""Hover feature — textDocument/hover handler.

Provides hover documentation for Pine Script symbols.
"""

from __future__ import annotations

from lsprotocol import types as lsp

from pynescript.langserver.protocol.utils import get_word_at_position
from pynescript.langserver.providers.builtin_metadata import get_builtin


def handle_hover(params: lsp.HoverParams, source: str | None) -> lsp.Hover | None:
    """Handle textDocument/hover request.

    Args:
        params: The hover params from the LSP client.
        source: The source text of the document.

    Returns:
        Hover with documentation or None if not found.
    """
    position = params.position

    if not source:
        return None

    # Get the word at cursor position
    lines = source.split("\n")
    if position.line >= len(lines):
        return None

    line_text = lines[position.line]
    word, start, end = get_word_at_position(source, position.line, position.character)

    if not word:
        return None

    # Try to find builtin documentation
    builtin_info = get_builtin(word)
    if builtin_info:
        return _build_builtin_hover(builtin_info, position.line, start, end)

    # Try with module prefix (e.g., "sma" -> "ta.sma")
    # Check if the word is preceded by a module name
    text_before = line_text[:start]
    words_before = text_before.rstrip().split()
    if words_before:
        last_word = words_before[-1]
        if last_word.endswith("."):
            module = last_word.rstrip(".")
            full_name = f"{module}.{word}"
            builtin_info = get_builtin(full_name)
            if builtin_info:
                return _build_builtin_hover(builtin_info, position.line, start, end)

    return None


def _build_builtin_hover(info: dict, line: int, start: int, end: int) -> lsp.Hover:
    """Build a Hover for a builtin function.

    Args:
        info: Metadata dict from builtin_metadata.
        line: The line number (0-indexed).
        start: Start character position.
        end: End character position.

    Returns:
        LSP Hover with documentation.
    """
    label = info.get("label", "")
    detail = info.get("detail", "")
    brief = info.get("brief", "")
    documentation = info.get("documentation", "")

    # Build markdown content
    content = f"""```pinescript
{detail}
```

{brief}

"""

    if documentation and documentation != brief:
        content += f"---\n{_format_documentation(documentation)}\n\n"

    content += _build_examples(info)
    content += _build_see_also(info)

    # Add TradingView docs link
    content += _build_docs_link(label)

    return lsp.Hover(
        contents=lsp.MarkupContent(
            kind=lsp.MarkupKind.Markdown,
            value=content,
        ),
        range=lsp.Range(
            start=lsp.Position(line=line, character=start),
            end=lsp.Position(line=line, character=end),
        ),
    )


def _format_documentation(doc: str) -> str:
    """Format documentation text for display."""
    # Take first paragraph if it's long
    paragraphs = doc.split("\n\n")
    first_para = paragraphs[0] if paragraphs else doc
    # Limit to 500 chars
    if len(first_para) > 500:
        first_para = first_para[:497] + "..."
    return first_para


def _build_examples(info: dict) -> str:
    """Build examples section for hover."""
    label = info.get("label", "")
    if not label.startswith(("ta.", "strategy.", "plot")):
        return ""

    examples = {
        "ta.sma": "```pinescript\nplot(ta.sma(close, 14))\n```",
        "ta.ema": "```pinescript\nplot(ta.ema(close, 14))\n```",
        "ta.rsi": "```pinescript\nplot(ta.rsi(close, 14))\n```",
        "ta.macd": "```pinescript\n[macdLine, signalLine, histLine] = ta.macd(close, 12, 26, 9)\nplot(macdLine, color=color.blue)\nplot(signalLine, color=color.orange)\n```",
        "strategy.entry": '```pinescript\nstrategy.entry("Long", strategy.long)\n```',
        "strategy.exit": '```pinescript\nstrategy.exit("Exit", profit=100, loss=50)\n```',
    }

    example = examples.get(label, "")
    if example:
        return f"**Example:**\n{example}\n\n"
    return ""


def _build_see_also(info: dict) -> str:
    """Build 'See also' section."""
    related_map = {
        "ta.sma": ["ta.ema", "ta.rma", "ta.wma"],
        "ta.ema": ["ta.sma", "ta.rma", "ta.wma"],
        "ta.rsi": ["ta.stoch", "ta.mfi"],
        "ta.macd": ["ta.rsi", "ta.bb"],
        "ta.bb": ["ta.macd", "ta.kc"],
        "ta.atr": ["ta.tr"],
        "strategy.entry": ["strategy.exit", "strategy.close"],
    }

    label = info.get("label", "")
    related = related_map.get(label, [])

    if not related:
        return ""

    links = ", ".join(f"`{r}`" for r in related)
    return f"**See also:** {links}\n\n"


def _build_docs_link(name: str) -> str:
    """Build a link to TradingView documentation.

    Note: TradingView docs links require the full function reference.
    This is a placeholder that shows how to structure the link.
    """
    # Don't include external links in basic hover
    return ""
