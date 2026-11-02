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
card is a Markdown convention that matches AXIS popovers: italic kind kicker,
fenced signature, body, optional sections, hairline footer.
"""

from __future__ import annotations


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
    kicker = kind.strip()
    if kicker:
        parts.append(f"*{kicker}*")
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


def pine_v6_docs_link(name: str) -> str:
    """Markdown link to the public Pine v6 function reference.

    Only dotted builtin labels with a namespace (``ta.sma``,
    ``strategy.entry``, ``line.fill``) get a link. Empty, undotted
    (``sma``), or whitespace-only names return ``""``.
    """
    label = (name or "").strip()
    if not label or "." not in label:
        return ""
    namespace, _, member = label.partition(".")
    if not namespace or not member:
        return ""
    return f"[Pine v6: {label}](https://www.tradingview.com/pine-script-reference/v6/#fun_{label})\n"
