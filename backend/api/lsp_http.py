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

"""HTTP bridge to langserver completion/hover for AXIS (browser).

Full LSP is stdio/TCP; AXIS cannot spawn pygls in-tab. These free endpoints
reuse the same handlers as ``pynescript-lsp``.
"""

from __future__ import annotations

from typing import Any

from flask import Blueprint
from flask import jsonify
from flask import request

bp = Blueprint("lsp_http", __name__)


def _doc_value(doc: Any) -> str:
    if doc is None:
        return ""
    if hasattr(doc, "value"):
        return str(doc.value or "")
    return str(doc)


def _serialize_completion_item(item: Any) -> dict[str, Any] | None:
    label = getattr(item, "label", None) or ""
    if not label or str(label).startswith("─"):
        return None  # skip category headers
    kind = getattr(item, "kind", None)
    kind_name = getattr(kind, "name", None) or str(kind or "Function")
    insert = getattr(item, "insert_text", None) or label
    fmt = getattr(item, "insert_text_format", None)
    # InsertTextFormat.Snippet == 2
    is_snippet = int(fmt) == 2 if fmt is not None else ("${" in str(insert))
    return {
        "label": str(label),
        "detail": str(getattr(item, "detail", None) or ""),
        "documentation": _doc_value(getattr(item, "documentation", None)),
        "insertText": str(insert),
        "insertTextFormat": "snippet" if is_snippet else "plaintext",
        "kind": kind_name,
    }


@bp.post("/lsp/completion")
def lsp_completion():
    """POST { source, line, character } → { items: [...] } (0-based position)."""
    data = request.get_json(silent=True) or {}
    source = data.get("source") if data.get("source") is not None else data.get("text")
    if not isinstance(source, str):
        return jsonify({"status": "error", "message": "source string required"}), 400
    try:
        line = int(data.get("line", 0))
        character = int(data.get("character", 0))
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "line/character must be int"}), 400

    try:
        from lsprotocol import types as lsp
        from pynescript.langserver.features.completion import handle_completion
    except ImportError as e:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": f"LSP deps missing (pip install \"hoox-pyne[lsp]\"): {e}",
                }
            ),
            503,
        )

    params = lsp.CompletionParams(
        text_document=lsp.TextDocumentIdentifier(uri="inmemory://axis.pine"),
        position=lsp.Position(line=max(0, line), character=max(0, character)),
    )
    try:
        result = handle_completion(params, source)
    except Exception as e:  # noqa: BLE001
        return jsonify({"status": "error", "message": f"completion failed: {e}"}), 500

    items: list[dict[str, Any]] = []
    for raw in getattr(result, "items", None) or []:
        ser = _serialize_completion_item(raw)
        if ser:
            items.append(ser)

    return jsonify(
        {
            "status": "success",
            "items": items[:120],
            "isIncomplete": bool(getattr(result, "is_incomplete", False)),
            "source": "lsp",
        }
    )


@bp.post("/lsp/hover")
def lsp_hover():
    """POST { source, line, character } → { contents, range? } or null hover."""
    data = request.get_json(silent=True) or {}
    source = data.get("source") if data.get("source") is not None else data.get("text")
    if not isinstance(source, str):
        return jsonify({"status": "error", "message": "source string required"}), 400
    try:
        line = int(data.get("line", 0))
        character = int(data.get("character", 0))
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "line/character must be int"}), 400

    try:
        from lsprotocol import types as lsp
        from pynescript.langserver.features.hover import handle_hover
    except ImportError as e:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": f"LSP deps missing (pip install \"hoox-pyne[lsp]\"): {e}",
                }
            ),
            503,
        )

    params = lsp.HoverParams(
        text_document=lsp.TextDocumentIdentifier(uri="inmemory://axis.pine"),
        position=lsp.Position(line=max(0, line), character=max(0, character)),
    )
    try:
        result = handle_hover(params, source)
    except Exception as e:  # noqa: BLE001
        return jsonify({"status": "error", "message": f"hover failed: {e}"}), 500

    if result is None:
        return jsonify({"status": "success", "hover": None, "source": "lsp"})

    contents = getattr(result, "contents", None)
    text = _doc_value(contents)
    rng = getattr(result, "range", None)
    range_out = None
    if rng is not None:
        range_out = {
            "start": {
                "line": rng.start.line,
                "character": rng.start.character,
            },
            "end": {
                "line": rng.end.line,
                "character": rng.end.character,
            },
        }

    return jsonify(
        {
            "status": "success",
            "hover": {"contents": text, "range": range_out},
            "source": "lsp",
        }
    )
