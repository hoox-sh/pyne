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

import logging
from typing import Any

from flask import Blueprint
from flask import jsonify
from flask import request

logger = logging.getLogger(__name__)

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
                    "message": "LSP dependencies not installed",
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
        logger.warning("lsp completion: %s", e)
        return jsonify({"status": "error", "message": "Completion request failed"}), 500

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
                    "message": "LSP dependencies not installed",
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
        logger.warning("lsp hover: %s", e)
        return jsonify({"status": "error", "message": "Hover request failed"}), 500

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


def _line_end_col(source: str, line_1based: int, start_col: int) -> int:
    """End column (0-based) for highlighting from *start_col* to end of line."""
    if line_1based < 1:
        return max(start_col + 1, 1)
    lines = source.split("\n")
    idx = line_1based - 1
    if idx < 0 or idx >= len(lines):
        return max(start_col + 1, 1)
    return max(start_col + 1, len(lines[idx]))


@bp.post("/lsp/diagnostics")
@bp.post("/lsp/preevaluate")
def lsp_diagnostics():
    """POST { source } → parse + lint diagnostics for AXIS pre-eval.

    Free endpoint (same CORS surface as completion/hover). Does **not** run the
    script against bars — static parse + linter only. AXIS uses this to mark
    wrong code and block Run when errors are present.

    Response::

        {
          "status": "success",
          "ok": true|false,          # false when any severity=error
          "diagnostics": [
            {
              "line": 1,             # 1-based
              "character": 0,        # 0-based start col
              "endLine": 1,
              "endCharacter": 12,
              "message": "...",
              "severity": "error"|"warning"|"info",
              "code": "E001",
              "source": "preeval"
            }
          ],
          "source": "lsp"
        }
    """
    data = request.get_json(silent=True) or {}
    source = data.get("source") if data.get("source") is not None else data.get("text")
    if not isinstance(source, str):
        return jsonify({"status": "error", "message": "source string required"}), 400

    try:
        from pynescript.ast.linter import lint_script
    except ImportError as e:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Linter not available",
                }
            ),
            503,
        )

    try:
        warnings = lint_script(source, filename="inmemory://axis.pine")
    except Exception as e:  # noqa: BLE001
        logger.warning("lsp lint: %s", e)
        return jsonify({"status": "error", "message": "Lint request failed"}), 500

    diagnostics: list[dict[str, Any]] = []
    has_error = False
    for w in warnings or []:
        sev = str(getattr(w, "severity", None) or "warning").lower()
        if sev not in ("error", "warning", "info", "hint", "information"):
            sev = "warning"
        if sev == "hint":
            sev = "info"
        if sev == "information":
            sev = "info"
        if sev == "error":
            has_error = True
        line = getattr(w, "line", None)
        line_1 = int(line) if isinstance(line, int) and line > 0 else 1
        col = getattr(w, "column", None)
        col_0 = int(col) if isinstance(col, int) and col >= 0 else 0
        end_col = _line_end_col(source, line_1, col_0)
        diagnostics.append(
            {
                "line": line_1,
                "character": col_0,
                "endLine": line_1,
                "endCharacter": end_col,
                "message": str(getattr(w, "message", "") or ""),
                "severity": sev,
                "code": str(getattr(w, "code", "") or ""),
                "source": "preeval",
            }
        )

    return jsonify(
        {
            "status": "success",
            "ok": not has_error,
            "diagnostics": diagnostics,
            "source": "lsp",
        }
    )
