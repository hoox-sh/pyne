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

"""Shared Markdown card for hover, completion, and signature-help docs.

VS Code cannot inject CSS into native hover / suggest / peek widgets, so the
card is a Markdown convention that matches AXIS popovers: inline-code kind
chip (theme ``textPreformat``), fenced signature, one-paragraph summary,
compact parameter/field lists, optional example / see-also sections, and a
hairline footer.

Density rules:

- 1–4 named items render as bullets; more render as a two-column table.
- Empty pieces are omitted; sections are separated by one blank line.
- The footer is preceded by a Markdown rule.
"""

from __future__ import annotations


# Shared lowercase vocabulary for the kind chip. Synonyms map to the same
# token so hover, completion, and signature docs read consistently.
_KIND_LABELS: dict[str, str] = {
    "class": "type",
    "const": "variable",
    "ctor": "constructor",
    "decl": "declaration",
    "field": "member",
    "func": "function",
    "module": "namespace",
    "prop": "property",
}

# Above this many described items, a table aligns better than bullets.
_COMPACT_ITEM_LIMIT = 4


def normalize_kind(kind: str) -> str:
    """Normalize a card kind to the shared lowercase vocabulary."""
    token = (kind or "").strip().lower()
    return _KIND_LABELS.get(token, token)


def format_docs_card(
    *,
    kind: str = "",
    fence: str = "",
    body: str = "",
    sections: list[str] | None = None,
    footer: str = "",
) -> str:
    """Assemble a hover/suggest Markdown card.

    Empty pieces are omitted. ``footer`` is preceded by a Markdown rule so it
    reads as the AXIS dialog footer (docs link, etc.).
    """
    parts: list[str] = []
    kicker = normalize_kind(kind)
    if kicker:
        parts.append(f"`{kicker}`")
    sig = fence.strip("\n")
    if sig:
        parts.append(f"```pinescript\n{sig}\n```")
    text = body.strip()
    if text:
        parts.append(text)
    for section in sections or []:
        chunk = section.strip()
        if chunk:
            parts.append(chunk)
    foot = footer.strip()
    if foot:
        parts.append(f"---\n{foot}")
    if not parts:
        return ""
    return "\n\n".join(parts) + "\n"


def format_named_table(title: str, items: list[tuple[str, str]]) -> str:
    """Render a named list compactly.

    Name-only lists stay bullets. Described lists use bullets up to
    :data:`_COMPACT_ITEM_LIMIT` entries and a two-column table above it, so a
    short parameter list does not wrap in a narrow hover or suggest widget.
    """
    if not items:
        return ""
    described = any((desc or "").strip() for _name, desc in items)
    lines = [f"**{title}**", ""]
    if not described:
        for name, _desc in items:
            lines.append(f"- `{name}`")
        return "\n".join(lines)
    if len(items) <= _COMPACT_ITEM_LIMIT:
        for name, desc in items:
            safe = (desc or "").replace("\n", " ").strip()
            lines.append(f"- **`{name}`** — {safe}" if safe else f"- **`{name}`**")
        return "\n".join(lines)
    lines.extend(["| Name | Description |", "| --- | --- |"])
    for name, desc in items:
        safe = (desc or "").replace("\n", " ").replace("|", "\\|").strip()
        lines.append(f"| `{name}` | {safe} |")
    return "\n".join(lines)


def pine_v6_docs_url(name: str) -> str:
    """Public Pine v6 function-reference URL for a dotted builtin label.

    Empty, undotted (``sma``), or whitespace-only names return ``""``.
    """
    label = (name or "").strip()
    if not label or "." not in label:
        return ""
    namespace, _, member = label.partition(".")
    if not namespace or not member:
        return ""
    return f"https://www.tradingview.com/pine-script-reference/v6/#fun_{label}"


def pine_v6_docs_link(name: str) -> str:
    """Markdown link to the public Pine v6 function reference.

    Only dotted builtin labels with a namespace (``ta.sma``,
    ``strategy.entry``, ``line.fill``) get a link. Empty, undotted
    (``sma``), or whitespace-only names return ``""``.
    """
    url = pine_v6_docs_url(name)
    label = (name or "").strip()
    return f"[Pine v6: {label}]({url})\n" if url else ""
