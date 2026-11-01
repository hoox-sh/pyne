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

"""Signature help — ``textDocument/signatureHelp`` for builtins and user functions.

Public handler: :func:`handle_signature_help`. Resolves the innermost call
enclosing the cursor (skipping nested parens/brackets), looks up Pine builtins
via :func:`~pynescript.langserver.providers.builtin_metadata.get_builtin`, then
user :class:`~pynescript.ast.node.FunctionDef` nodes. Trigger characters:
``(`` and ``,``.
"""

from __future__ import annotations

import logging
import re

from typing import Any

from lsprotocol import types as lsp

from pynescript.ast import node as ast
from pynescript.ast.helper import parse
from pynescript.ast.helper import walk
from pynescript.langserver.analysis import SymbolIndex
from pynescript.langserver.analysis import ensure_symbol_index
from pynescript.langserver.protocol.utils import offset_from_position
from pynescript.langserver.protocol.utils import trailing_ident
from pynescript.langserver.providers.builtin_metadata import get_builtin


logger = logging.getLogger(__name__)

_SNIPPET_PLACEHOLDER = re.compile(r"\$\{(\d+):([^}]+)\}|\$\{(\d+)\}|\$(\d+)")

# Stack frames that are not function-call parens (brackets / grouping / braces).
_GROUPING = -1


def handle_signature_help(
    params: lsp.SignatureHelpParams,
    source: str | None,
    tree: Any | None = ...,
    *,
    analysis: SymbolIndex | None = None,
) -> lsp.SignatureHelp | None:
    """Return signature help for the call enclosing the cursor, or ``None``.

    Args:
        params: Client signature-help params (document URI + position).
        source: Document text, or ``None``.
        tree: Pre-parsed AST from the workspace cache. Pass ``None`` when the
            workspace already failed to parse. Omit (default ``...``) to parse
            from *source* when a user function must be resolved.
        analysis: Pre-built symbol index for *tree* (resolves UDT methods).

    Returns:
        :class:`~lsprotocol.types.SignatureHelp`, or ``None`` when the cursor
        is not inside a known call / the document is empty.
    """
    if not source:
        return None

    position = params.position
    offset = offset_from_position(source, position.line, position.character)
    call = _enclosing_call(source, offset)
    if call is None:
        return None
    name, active_parameter = call

    info = _lookup_builtin(name)
    if info is not None:
        signature = _signature_from_builtin(name, info, argc=active_parameter + 1)
        labels = [param.label for param in (signature.parameters or [])]
        return lsp.SignatureHelp(
            signatures=[signature],
            active_signature=0,
            active_parameter=_clamp_parameter(active_parameter, labels),
        )

    index = ensure_symbol_index(source, tree, analysis)
    if index is None:
        index = _best_effort_index(source)
    func = _resolve_user_call(name, index, source, position)
    if func is None:
        return None
    signature = _signature_from_function_def(func, method_call=("." in name))
    labels = [param.label for param in (signature.parameters or [])]
    return lsp.SignatureHelp(
        signatures=[signature],
        active_signature=0,
        active_parameter=_clamp_parameter(active_parameter, labels),
    )


def _lookup_builtin(name: str) -> dict[str, Any] | None:
    """Resolve an exact builtin name; never fall back from ``obj.sma`` to ``ta.sma``."""
    return get_builtin(name)


def _clamp_parameter(active: int, labels: list[Any]) -> int:
    if not labels:
        return 0
    return max(0, min(active, len(labels) - 1))


def _resolve_user_call(
    name: str,
    index: SymbolIndex | None,
    source: str,
    position: lsp.Position,
) -> ast.FunctionDef | None:
    """Resolve a user function or UDT method named at the call site."""
    if index is not None:
        scope = index.scope_at(position.line, position.character)
        if "." in name:
            base_name, _, member = name.rpartition(".")
            base = index.resolve(base_name, scope)
            if base is not None and base.type_label:
                method = index.udt_methods.get(_base_type(base.type_label), {}).get(member)
                if method is not None and isinstance(method.node, ast.FunctionDef):
                    return method.node
            # Qualified namespace: ``strategy.risk`` etc. are builtins, not
            # user methods.
            return None
        symbol = index.resolve(name, scope)
        if symbol is not None and isinstance(symbol.node, ast.FunctionDef):
            return symbol.node
        return None
    tree = _resolve_tree(source, ...)
    return _find_function_def(tree, name)


def _base_type(type_label: str) -> str:
    label = type_label.strip()
    for qualifier in ("const", "input", "simple", "series"):
        if label.startswith(qualifier + " "):
            label = label[len(qualifier) + 1 :].strip()
    return label.split("<", 1)[0].strip()


def _enclosing_call(source: str, offset: int) -> tuple[str, int] | None:
    """Innermost named call containing *offset*: ``(callee, active_parameter)``."""
    stack = _call_stack_at(source, min(offset, len(source)))
    while stack:
        open_idx, commas = stack.pop()
        if open_idx < 0:
            continue
        name = trailing_ident(source[:open_idx].rstrip())
        if name:
            return name, commas
    return None


def _call_stack_at(source: str, offset: int) -> list[tuple[int, int]]:
    """Call/group stack after scanning *source* up to *offset*."""
    scanner = _CallScanner(source)
    i = 0
    n = len(source)
    while i < offset:
        nxt = source[i + 1] if i + 1 < n else ""
        i = scanner.feed(source[i], i, nxt)
    return scanner.stack


class _CallScanner:
    """Forward scan that tracks nested ``(`` calls and grouping brackets."""

    __slots__ = ("block_comment", "escape", "in_str", "line_comment", "source", "stack", "triple")

    def __init__(self, source: str = "") -> None:
        self.source = source
        self.stack: list[tuple[int, int]] = []
        self.in_str: str | None = None
        self.triple: str | None = None
        self.escape = False
        self.line_comment = False
        self.block_comment = False

    def feed(self, ch: str, index: int, nxt: str) -> int:
        """Consume *ch* at *index*; return the next index to read."""
        if self.block_comment:
            if ch == "*" and nxt == "/":
                self.block_comment = False
                return index + 2
            return index + 1
        if self.line_comment:
            if ch == "\n":
                self.line_comment = False
            return index + 1
        if self.triple is not None:
            if self.source[index : index + 3] == self.triple:
                self.triple = None
                return index + 3
            return index + 1
        if self.in_str is not None:
            self._feed_string(ch)
            return index + 1
        if ch == "/" and nxt == "/":
            self.line_comment = True
            return index + 2
        if ch == "/" and nxt == "*":
            self.block_comment = True
            return index + 2
        if ch == "#" and (not nxt or nxt in " \t\f\r\n" or not (nxt.isdigit() or nxt.lower() in "abcdef")):
            self.line_comment = True
            return index + 1
        if ch in ("'", '"'):
            triple = self.source[index : index + 3]
            if triple in ('"""', "'''"):
                self.triple = triple
                return index + 3
            self.in_str = ch
            return index + 1
        self._feed_code(ch, index)
        return index + 1

    def _feed_string(self, ch: str) -> None:
        if self.escape:
            self.escape = False
        elif ch == "\\":
            self.escape = True
        elif ch == self.in_str:
            self.in_str = None

    def _feed_code(self, ch: str, index: int) -> None:
        if ch == "(":
            self.stack.append((index, 0))
        elif ch in ")]}" and self.stack:
            self.stack.pop()
        elif ch in "[{":
            self.stack.append((_GROUPING, 0))
        elif ch == "," and self.stack:
            open_idx, commas = self.stack[-1]
            if open_idx >= 0:
                self.stack[-1] = (open_idx, commas + 1)


def _param_labels_from_info(info: dict[str, Any]) -> list[str]:
    """Parameter labels from a real ``detail`` signature, else snippet placeholders."""
    detail = (info.get("detail") or "").strip()
    if detail and not detail.endswith("(...)"):
        parsed = _params_from_call_signature(detail)
        if parsed:
            return parsed
    snippet = (info.get("snippet") or "").strip()
    if snippet:
        parsed = _params_from_snippet(snippet)
        if parsed:
            return parsed
    typed = info.get("params")
    if typed is None:
        typed = info.get("parameters")
    return _params_from_typed_list(typed)


def _params_from_call_signature(sig: str) -> list[str]:
    start = sig.find("(")
    end = sig.rfind(")")
    if start < 0 or end <= start:
        return []
    inner = sig[start + 1 : end].strip()
    if not inner or inner == "...":
        return []
    labels: list[str] = []
    for chunk in _split_top_level(inner):
        piece = chunk.strip()
        if not piece or piece == "...":
            continue
        labels.append(piece)
    return labels


def _params_from_snippet(snippet: str) -> list[str]:
    labels: list[str] = []
    for match in _SNIPPET_PLACEHOLDER.finditer(snippet):
        named = match.group(2)
        if named:
            labels.append(named)
        else:
            labels.append(f"arg{match.group(1) or match.group(3) or match.group(4) or ''}")
    return labels


def _params_from_typed_list(params: Any) -> list[str]:
    if not params:
        return []
    labels: list[str] = []
    if isinstance(params, dict):
        labels.extend(str(k) for k in params)
    elif isinstance(params, list):
        for item in params:
            if isinstance(item, str):
                labels.append(item)
            elif isinstance(item, dict):
                name = item.get("name") or item.get("label") or ""
                if name:
                    labels.append(str(name))
    return labels


def _split_top_level(inner: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    in_str: str | None = None
    escape = False
    for ch in inner:
        in_str, escape, consumed = _step_string(ch, in_str=in_str, escape=escape)
        if consumed:
            buf.append(ch)
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def _step_string(ch: str, *, in_str: str | None, escape: bool) -> tuple[str | None, bool, bool]:
    """Advance string state. *consumed* is True when *ch* is inside / opens a string."""
    if in_str is not None:
        if escape:
            return in_str, False, True
        if ch == "\\":
            return in_str, True, True
        if ch == in_str:
            return None, False, True
        return in_str, False, True
    if ch in ("'", '"'):
        return ch, False, True
    return None, False, False


def _signature_label(name: str, info: dict[str, Any], labels: list[str]) -> str:
    detail = (info.get("detail") or "").strip()
    if detail and not detail.endswith("(...)"):
        return detail
    if labels:
        return f"{name}({', '.join(labels)})"
    snippet = (info.get("snippet") or "").strip()
    if snippet:
        cleaned = _SNIPPET_PLACEHOLDER.sub(lambda m: m.group(2) if m.group(2) else "", snippet)
        if cleaned:
            return cleaned
    return detail or f"{name}(...)"


def _signature_from_builtin(
    name: str,
    info: dict[str, Any],
    *,
    argc: int = 0,
) -> lsp.SignatureInformation:
    labels = _param_labels_from_info(info)
    labels = _arity_labels(name, labels, argc)
    parameters = [lsp.ParameterInformation(label=label) for label in labels]
    brief = (info.get("brief") or info.get("documentation") or "").strip()
    documentation = None
    if brief:
        documentation = lsp.MarkupContent(kind=lsp.MarkupKind.Markdown, value=brief)
    label = f"{name}({', '.join(labels)})" if labels else _signature_label(name, info, labels)
    return lsp.SignatureInformation(
        label=label,
        documentation=documentation,
        parameters=parameters,
    )


def _arity_labels(name: str, labels: list[str], argc: int) -> list[str]:
    """Apply the few Pine overloads whose arity changes parameter meaning."""
    if argc == 1 and name in {"ta.cci", "ta.adx", "ta.mfi", "ta.bbw"}:
        return ["length"]
    if argc == 2 and name == "ta.bbw":
        return ["length", "mult"]
    if argc == 2 and name == "ta.cci":
        return ["source", "length"]
    if argc == 2 and name == "ta.adx":
        return ["diLength", "adxSmoothing"]
    if argc == 2 and name == "ta.mfi":
        return ["source", "length"]
    return labels


def _signature_from_function_def(node: ast.FunctionDef, *, method_call: bool = False) -> lsp.SignatureInformation:
    params = list(node.args or [])
    if method_call and node.method and params:
        # The receiver is implicit at the call site.
        params = params[1:]
    labels: list[str] = []
    for param in params:
        pname = getattr(param, "name", None)
        if not pname:
            continue
        type_label = _type_label(getattr(param, "type", None))
        labels.append(f"{type_label} {pname}".strip() if type_label else str(pname))
    prefix = ""
    if node.export:
        prefix += "export "
    if node.method:
        prefix += "method "
    sig = f"{prefix}{node.name}({', '.join(labels)})"
    parameters = [lsp.ParameterInformation(label=label) for label in labels]
    return lsp.SignatureInformation(label=sig, parameters=parameters)


def _type_label(type_node: Any) -> str:
    if type_node is None:
        return ""
    if isinstance(type_node, ast.Name):
        return type_node.id or ""
    if isinstance(type_node, ast.Attribute):
        base = _type_label(type_node.value)
        attr = type_node.attr or ""
        return f"{base}.{attr}" if base else attr
    if isinstance(type_node, ast.Qualify):
        inner = _type_label(type_node.value)
        qual = type(type_node.qualifier).__name__.lower() if type_node.qualifier is not None else ""
        return f"{qual} {inner}".strip() if inner else qual
    return ""


def _find_function_def(tree: Any | None, name: str) -> ast.FunctionDef | None:
    if tree is None or not name:
        return None
    for node in walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _resolve_tree(source: str | None, tree: Any | None) -> Any | None:
    if tree is not ...:
        return tree
    if not source:
        return None
    try:
        return parse(source)
    except Exception:
        return None


def _best_effort_index(source: str) -> SymbolIndex | None:
    """Build an index from a minimally repaired mid-edit buffer."""
    from pynescript.langserver.analysis import build_symbol_index

    trimmed = source.rstrip()
    candidates = [source, trimmed + "\n"]
    if trimmed.endswith("."):
        candidates.extend([trimmed + "x", trimmed + "x)"])
    elif trimmed.endswith(("(", ",", "[")):
        candidates.extend([trimmed + "x)", trimmed + "0)"])
    for candidate in candidates:
        try:
            tree = parse(candidate)
        except Exception as exc:
            logger.debug("signature_help: repair parse failed: %s", exc)
            continue
        try:
            return build_symbol_index(tree, source)
        except Exception as exc:
            logger.debug("signature_help: repair index failed: %s", exc)
    return None
