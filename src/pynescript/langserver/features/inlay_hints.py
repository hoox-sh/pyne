# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

"""Inlay hints feature — textDocument/inlayHint handler.

Shows inferred types inline next to variable declarations. For example:

    length = 14                       →   length: const int = 14
    rsi   = ta.rsi(close, 14)         →   rsi:   series float = ta.rsi(close, 14)
    n     = input.int(5, "n")         →   n:     input int = input.int(5, "n")

The hint is positioned at the end of the target identifier (just before `=`).
Type inference is intentionally simple — it looks at the shape of the RHS
expression and only emits a hint when confident enough to be useful.
"""

from __future__ import annotations

import logging

from lsprotocol import types as lsp

from pynescript.ast import node as ast
from pynescript.ast import parse
from pynescript.langserver.providers.builtin_metadata import get_builtin


logger = logging.getLogger(__name__)


# Built-in variable → return type. Only the ones the parser/builder treats as
# plain `Name` nodes (so they can appear bare on the RHS of an Assign).
_BUILTIN_VAR_TYPES: dict[str, str] = {
    "open": "series float",
    "high": "series float",
    "low": "series float",
    "close": "series float",
    "volume": "series float",
    "hl2": "series float",
    "hlc3": "series float",
    "ohlc4": "series float",
    "time": "series int",
    "time_close": "series int",
    "bar_index": "series int",
    "last_bar_index": "series int",
    "na": "na",
}


def handle_inlay_hints(
    params: lsp.InlayHintParams,
    source: str | None,
) -> list[lsp.InlayHint] | None:
    """Handle textDocument/inlayHint request.

    Args:
        params: The inlay-hint params from the LSP client.
        source: The source text of the document.

    Returns:
        A list of `lsp.InlayHint` for variables whose type can be inferred, or
        None if the document could not be parsed.
    """
    if not source:
        return []

    try:
        tree = parse(source, params.text_document.uri)
    except Exception as exc:
        logger.debug("inlay_hints: parse failed: %s", exc)
        return None

    hints: list[lsp.InlayHint] = []
    _collect_hints(tree, source, hints)
    return hints


def _collect_hints(
    node: ast.AST | None,
    source: str,
    hints: list[lsp.InlayHint],
) -> None:
    """Walk an AST node, adding inlay hints for inferable assignments."""
    if node is None:
        return

    if isinstance(node, ast.Assign):
        hint = _hint_for_assign(node, source)
        if hint is not None:
            hints.append(hint)

    # Recurse into all child AST nodes (matches the simple visitor pattern used
    # elsewhere in the langserver; e.g. `_collect_workspace_symbols` in
    # `server.py`).
    for field in getattr(node, "_fields", []):
        child = getattr(node, field, None)
        if isinstance(child, list):
            for item in child:
                if isinstance(item, ast.AST):
                    _collect_hints(item, source, hints)
        elif isinstance(child, ast.AST):
            _collect_hints(child, source, hints)


def _hint_for_assign(
    node: ast.Assign,
    source: str,
) -> lsp.InlayHint | None:
    """Build an inlay hint for a single `Assign`, or None if not inferable."""
    # Only emit hints for simple `name = expr` (no tuple destructuring, no
    # attribute targets, no explicit type annotation that we could be wrong
    # about).
    if not isinstance(node.target, ast.Name):
        return None
    if node.type is not None:
        # User wrote an explicit `name: type = ...`; let the code stand.
        return None
    if node.value is None:
        return None

    type_label = _infer_type(node.value)
    if type_label is None:
        return None

    # Position the hint at the end of the target identifier (just before `=`).
    line = node.target.lineno - 1
    col = node.target.col_offset + len(node.target.id or "")
    return lsp.InlayHint(
        position=lsp.Position(line=line, character=col),
        label=f": {type_label}",
        kind=lsp.InlayHintKind.Type,
        tooltip=f"Inferred type: {type_label}",
    )


def _infer_type(value: ast.expr) -> str | None:
    """Return a human-readable type label for a value expression, or None."""
    if isinstance(value, ast.Constant):
        return _constant_type(value.value)
    if isinstance(value, ast.Name):
        return _BUILTIN_VAR_TYPES.get(value.id or "")
    if isinstance(value, ast.Call):
        return _call_type(value)
    # BinOp, BoolOp, UnaryOp, Compare, Conditional: skip — too easy to be
    # wrong without running the evaluator.
    return None


def _constant_type(v: object) -> str | None:
    """Map a Python literal to a Pine Script type label."""
    if isinstance(v, bool):
        return "const bool"
    if isinstance(v, int):
        return "const int"
    if isinstance(v, float):
        return "const float"
    if isinstance(v, str):
        return "const string"
    return None


def _call_type(call: ast.Call) -> str | None:
    """Map a Call to a type label, when the function is recognisable."""
    if not isinstance(call.func, ast.Attribute):
        return None
    if not isinstance(call.func.value, ast.Name):
        return None

    module = call.func.value.id
    attr = call.func.attr

    # `input.int(...)` → `input int`, `input.float(...)` → `input float`, etc.
    if module == "input":
        if attr in (
            "int",
            "float",
            "bool",
            "string",
            "color",
            "symbol",
            "session",
            "source",
            "time",
            "timeframe",
            "price",
        ):
            return f"input {attr}"

    # `ta.sma(...)` etc.: look up the metadata's `label` and `detail` for the
    # return type. Fall back to `series` if not in metadata.
    if module in ("ta", "math", "str", "color"):
        info = get_builtin(f"{module}.{attr}")
        if info is not None:
            detail = info.get("detail", "")
            # `ta.sma(series, int) → series float` — take everything after `→`.
            if "→" in detail:
                return detail.split("→", 1)[1].strip()
        return f"series"

    return None
