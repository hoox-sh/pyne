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

"""Inlay hints — ``textDocument/inlayHint`` (display-only).

Public handler: :func:`handle_inlay_hints` — assignment types and builtin
parameter names. Hints never modify the document: no ``text_edits`` and no
``data`` payload, so there is no inferred-type injection or resolve step.

Shows simple inferred types next to variable declarations, e.g.::

    length = 14                       →   length: const int = 14
    rsi   = ta.rsi(close, 14)         →   rsi:   series float = ta.rsi(close, 14)
    n     = input.int(5, "n")         →   n:     input int = input.int(5, "n")

and parameter names before positional args of dotted builtins::

    ta.sma(close, 14)                 →   ta.sma(source: close, length: 14)

Type hints sit at the end of the target identifier (just before ``=``).
Parameter hints sit at the start of each positional argument. Inference is
shape-based on the RHS (literals, builtins, ``ta.*`` / ``input.*`` metadata);
only confident cases are emitted. Hints are display-only; the server does not
advertise or implement ``inlayHint/resolve``.
"""

from __future__ import annotations

import logging
import re

from typing import Any

from lsprotocol import types as lsp

from pynescript.ast import node as ast
from pynescript.ast import parse
from pynescript.langserver.analysis import SymbolIndex
from pynescript.langserver.analysis import ensure_symbol_index
from pynescript.langserver.providers.builtin_metadata import get_builtin


logger = logging.getLogger(__name__)


# Snippet placeholders ``${1:source}`` / ``${2}`` / ``$3``.
_SNIPPET_PLACEHOLDER = re.compile(r"\$\{(\d+):([^}]+)\}|\$\{(\d+)\}|\$(\d+)")
_GENERIC_PARAM = re.compile(r"^(?:param|arg)\d*$", re.I)
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Pine v6 names when metadata snippets are generic ``paramN``. Multi-arity
# entries use the longest common positional prefix (TV signatures). 1-arg
# ``ta.cci(14)`` / ``ta.adx(14)`` / ``ta.mfi(14)`` / ``ta.bbw(14)`` are
# length-only (not ``source`` / ``diLength``). 2-arg ``ta.bbw(20, 2)`` is
# ``length`` / ``mult`` (not a prefix of ``source`` / ``length`` / ``mult``).
_WELL_KNOWN_PARAMS: dict[str, tuple[str, ...]] = {
    "ta.sma": ("source", "length"),
    "ta.ema": ("source", "length"),
    "ta.rma": ("source", "length"),
    "ta.wma": ("source", "length"),
    "ta.vwma": ("source", "length"),
    "ta.hma": ("source", "length"),
    "ta.rsi": ("source", "length"),
    "ta.stdev": ("source", "length"),
    "ta.atr": ("length",),
    "ta.cci": ("source", "length"),
    "ta.roc": ("source", "length"),
    "ta.mom": ("source", "length"),
    "ta.linreg": ("source", "length", "offset"),
    "ta.adx": ("diLength", "adxSmoothing"),
    "ta.mfi": ("source", "length"),
    "ta.bbw": ("source", "length", "mult"),
    "ta.dpo": ("length",),
    "ta.correlation": ("source1", "source2", "length"),
    "ta.crossover": ("source1", "source2"),
    "ta.crossunder": ("source1", "source2"),
    "strategy.entry": ("id", "direction", "qty"),
    "input.int": ("defval", "title"),
}

# 1-arg overloads whose single positional is ``length`` (typical price / OHLC
# from context). 2-arg forms keep the map above except ``ta.bbw(length, mult)``.
_LENGTH_ONLY_1ARG: frozenset[str] = frozenset({"ta.adx", "ta.cci", "ta.mfi", "ta.bbw"})

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
    tree: Any | None = ...,
    *,
    analysis: SymbolIndex | None = None,
    show_types: bool = True,
    show_parameters: bool = True,
) -> list[lsp.InlayHint] | None:
    """Handle textDocument/inlayHint request.

    Args:
        params: The inlay-hint params from the LSP client.
        source: The source text of the document.
        tree: Pre-parsed AST from the workspace cache. Pass ``None`` when the
            workspace already failed to parse (skips a redundant re-parse).
            Omit (default ``...``) to parse from *source*.
        analysis: Pre-built symbol index for *tree*.
        show_types: Emit inferred assignment type hints.
        show_parameters: Emit parameter-name hints.

    Returns:
        A list of `lsp.InlayHint` for inferred assignment types and parameter
        names, or None if the document could not be parsed.
    """
    if tree is ...:
        if not source:
            return []
        try:
            tree = parse(source, params.text_document.uri)
        except Exception as exc:
            logger.debug("inlay_hints: parse failed: %s", exc)
            return None
    if tree is None:
        return None

    index = ensure_symbol_index(source, tree, analysis)
    hints: list[lsp.InlayHint] = []
    _collect_hints(
        tree,
        hints,
        index=index,
        show_types=show_types,
        show_parameters=show_parameters,
    )
    # The client asks for the visible range; returning every hint in a large
    # script is wasted work and can make the editor feel sluggish.
    start = params.range.start
    end = params.range.end
    hints = [
        hint
        for hint in hints
        if (hint.position.line, hint.position.character) >= (start.line, start.character)
        and (hint.position.line, hint.position.character) < (end.line, end.character)
    ]
    return hints


def _collect_hints(
    node: ast.AST | None,
    hints: list[lsp.InlayHint],
    *,
    index: SymbolIndex | None = None,
    show_types: bool = True,
    show_parameters: bool = True,
) -> None:
    """Walk an AST node, adding type and parameter inlay hints."""
    if node is None:
        return

    if show_types and isinstance(node, ast.Assign):
        hint = _hint_for_assign(node, index)
        if hint is not None:
            hints.append(hint)
    elif show_parameters and isinstance(node, ast.Call):
        _collect_call_param_hints(node, hints, index)

    # Recurse into all child AST nodes (matches the simple visitor pattern used
    # elsewhere in the langserver; e.g. `_collect_workspace_symbols` in
    # `server.py`).
    for field in getattr(node, "_fields", []):
        child = getattr(node, field, None)
        if isinstance(child, list):
            for item in child:
                if isinstance(item, ast.AST):
                    _collect_hints(
                        item,
                        hints,
                        index=index,
                        show_types=show_types,
                        show_parameters=show_parameters,
                    )
        elif isinstance(child, ast.AST):
            _collect_hints(
                child,
                hints,
                index=index,
                show_types=show_types,
                show_parameters=show_parameters,
            )


def _hint_for_assign(
    node: ast.Assign,
    index: SymbolIndex | None = None,
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

    type_label = None
    if index is not None:
        scope = index.scope_at(node.target.lineno - 1, node.target.col_offset)
        type_label = index.infer_type(node.value, scope)
    if type_label is None:
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


def _collect_call_param_hints(
    call: ast.Call,
    hints: list[lsp.InlayHint],
    index: SymbolIndex | None = None,
) -> None:
    """Append parameter-name hints for positional args of builtins/user calls."""
    args = list(call.args or [])
    if not args:
        return
    names: list[str] = []
    qualified = _qualified_call_name(call.func)
    if qualified:
        info = get_builtin(qualified)
        if info:
            names = _param_names_from_info(qualified, info, len(args))
    if not names and index is not None:
        names = _user_call_param_names(call, index)
    if not names:
        return

    positional_index = 0
    for arg in args:
        if getattr(arg, "name", None):
            continue
        if positional_index >= len(names) or not names[positional_index]:
            positional_index += 1
            continue
        loc = _arg_start_position(arg)
        positional_index += 1
        if loc is None:
            continue
        lineno, col = loc
        hints.append(
            lsp.InlayHint(
                position=lsp.Position(line=lineno - 1, character=col),
                label=f"{names[positional_index - 1]}: ",
                kind=lsp.InlayHintKind.Parameter,
            )
        )


def _user_call_param_names(call: ast.Call, index: SymbolIndex) -> list[str]:
    """Parameter names for a user function/method call, if resolvable."""
    line = getattr(call, "lineno", 1) or 1
    col = getattr(call, "col_offset", 0) or 0
    scope = index.scope_at(line - 1, col)
    func = call.func
    node = None
    method_call = False
    if isinstance(func, ast.Name):
        symbol = index.resolve(func.id or "", scope)
        if symbol is not None and isinstance(symbol.node, ast.FunctionDef):
            node = symbol.node
    elif isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        base = index.resolve(func.value.id or "", scope)
        if base is not None and base.type_label:
            member = index.udt_methods.get(_base_type_name(base.type_label), {}).get(func.attr or "")
            if member is not None and isinstance(member.node, ast.FunctionDef):
                node = member.node
                method_call = True
    if node is None:
        return []
    params = list(node.args or [])
    if method_call and params:
        params = params[1:]
    return [str(param.name) for param in params if getattr(param, "name", None)]  # type: ignore[attr-defined]


def _base_type_name(type_label: str) -> str:
    label = type_label.strip()
    for qualifier in ("const", "input", "simple", "series"):
        if label.startswith(qualifier + " "):
            label = label[len(qualifier) + 1 :].strip()
    return label.split("<", 1)[0].strip()


def _qualified_call_name(func: ast.expr) -> str | None:
    """Return ``ta.sma`` for ``Attribute(Name('ta'), 'sma')``, else None."""
    if not isinstance(func, ast.Attribute) or not isinstance(func.value, ast.Name):
        return None
    module = func.value.id or ""
    attr = func.attr or ""
    if not module or not attr:
        return None
    return f"{module}.{attr}"


def _arg_start_position(arg: ast.AST) -> tuple[int, int] | None:
    """``(lineno, col_offset)`` of a call arg, falling back to its value."""
    lineno = getattr(arg, "lineno", None)
    col = getattr(arg, "col_offset", None)
    if isinstance(lineno, int) and isinstance(col, int):
        return lineno, col
    value = getattr(arg, "value", None)
    lineno = getattr(value, "lineno", None)
    col = getattr(value, "col_offset", None)
    if isinstance(lineno, int) and isinstance(col, int):
        return lineno, col
    return None


def _param_names_from_info(qualified: str, info: dict[str, Any], argc: int = 0) -> list[str]:
    """Parameter names: real snippet placeholders, else longest of detail/docs/well-known.

    *argc* is ``len(call.args)``. 1-arg ``ta.cci`` / ``ta.adx`` / ``ta.mfi`` /
    ``ta.bbw`` use ``length``; 2-arg ``ta.bbw`` uses ``length`` / ``mult``;
    well-known names are sliced to *argc*.
    """
    # Arity-specific overloads must win over a generated one-parameter
    # signature (``ta.cci(length)`` is the 1-arg form, but 2-arg is
    # ``ta.cci(source, length)``).
    if argc == 1 and qualified in _LENGTH_ONLY_1ARG:
        return ["length"]
    if argc == 2 and qualified == "ta.bbw":
        return ["length", "mult"]
    if argc == 2 and qualified in {"ta.cci", "ta.adx", "ta.mfi"}:
        return list(_WELL_KNOWN_PARAMS.get(qualified) or ())
    snippet_names = _names_from_snippet(info.get("snippet") or "")
    if snippet_names and not any(_GENERIC_PARAM.fullmatch(n) for n in snippet_names):
        return snippet_names
    # Generic ``paramN`` snippets fall through. Prefer the longest positional
    # prefix so well-known 2-arg names beat a 1-arg docs match (e.g. ``ta.cci``).
    candidates = [
        _names_from_call_signature(info.get("detail") or ""),
        _names_from_documentation(info.get("documentation") or "", qualified),
        _well_known_names(qualified, argc),
    ]
    best = max(candidates, key=len)
    return best if best else snippet_names


def _well_known_names(qualified: str, argc: int) -> list[str]:
    """Arity-sliced well-known Pine v6 names; extra slots are not shown."""
    if argc == 2 and qualified == "ta.bbw":
        return ["length", "mult"]
    names = list(_WELL_KNOWN_PARAMS.get(qualified) or ())
    if argc > 0:
        return names[:argc]
    return names


def _names_from_snippet(snippet: str) -> list[str]:
    names: list[str] = []
    for match in _SNIPPET_PLACEHOLDER.finditer(snippet):
        named = match.group(2)
        if named:
            ident = named.strip()
            if ident:
                names.append(ident)
    return names


def _names_from_call_signature(sig: str) -> list[str]:
    head = sig.split("→", 1)[0]
    start = head.find("(")
    end = head.rfind(")")
    if start < 0 or end <= start:
        return []
    inner = head[start + 1 : end].strip()
    if not inner or inner == "...":
        return []
    names: list[str] = []
    for chunk in _split_top_level_args(inner):
        ident = _ident_from_param_chunk(chunk)
        if ident:
            names.append(ident)
    return names


def _names_from_documentation(doc: str, qualified: str) -> list[str]:
    if not doc or not qualified:
        return []
    pattern = re.escape(qualified) + r"\s*\(([^)]*)\)"
    match = re.search(pattern, doc)
    if match is None:
        bare = qualified.rsplit(".", 1)[-1]
        match = re.search(r"\b" + re.escape(bare) + r"\s*\(([^)]*)\)", doc)
    if match is None:
        return []
    inner = match.group(1).strip()
    if not inner or inner == "...":
        return []
    names: list[str] = []
    for chunk in _split_top_level_args(inner):
        ident = _ident_from_param_chunk(chunk)
        if ident:
            names.append(ident)
    return names


def _ident_from_param_chunk(chunk: str) -> str | None:
    piece = chunk.strip()
    if not piece or piece == "...":
        return None
    name = piece.split("=", 1)[0].strip().lstrip("*").strip()
    if not name:
        return None
    token = name.split()[-1]
    if _IDENT.fullmatch(token):
        return token
    return None


def _split_top_level_args(inner: str) -> list[str]:
    """Split a flat ``(a, b, c)`` param list; metadata signatures are un-nested."""
    return [part.strip() for part in inner.split(",") if part.strip()]


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
                return str(detail).split("→", 1)[1].strip()
        return "series"

    return None
