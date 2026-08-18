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

"""Hover — ``textDocument/hover`` for builtins, types, namespaces, and locals.

Public handler: :func:`handle_hover`. Resolves the identifier under the cursor
(and optional ``module.member`` form) in this order: namespace prefix, type /
qualifier, builtin metadata, user enums, user declarations, then
:data:`~pynescript.langserver.providers.completion_items.PINE_KEYWORDS`.
"""

from __future__ import annotations

import re

from typing import Any

from lsprotocol import types as lsp

from pynescript.ast import node as ast
from pynescript.langserver.protocol.utils import get_identifier_segment_at_position
from pynescript.langserver.providers.builtin_metadata import get_builtin
from pynescript.langserver.providers.completion_items import PINE_KEYWORDS
from pynescript.langserver.providers.completion_items import collect_user_enums


_KEYWORD_DOCS = dict(PINE_KEYWORDS)

# Built-in types vs type/declaration qualifiers — distinct hover cards.
_TYPE_DOCS: dict[str, str] = {
    "int": "Built-in type. Integer numeric value.",
    "float": "Built-in type. Floating-point numeric value.",
    "bool": "Built-in type. Boolean value (`true` or `false`).",
    "string": "Built-in type. Text value.",
    "color": "Built-in type. RGBA color value.",
}

_QUALIFIER_DOCS: dict[str, str] = {
    "series": "Type qualifier. The value may change from bar to bar.",
    "simple": "Type qualifier. The value is fixed for a script execution (not bar-to-bar).",
    "const": "Type qualifier. The value is known at compile time.",
    "input": "Type qualifier. The value comes from a script input.",
    "var": "Declaration mode. Initialized once and kept across bars.",
    "varip": "Declaration mode. Like `var`, but also updates on every intra-bar tick.",
}

# Module names shown when the cursor is on the left of ``module.member``.
_NAMESPACE_DOCS: dict[str, str] = {
    "ta": "Namespace. Technical-analysis functions (`ta.sma`, `ta.ema`, `ta.rsi`, …).",
    "math": "Namespace. Mathematical functions (`math.abs`, `math.max`, `math.log`, …).",
    "strategy": "Namespace. Strategy orders, positions, and properties.",
    "input": "Namespace. Script input widgets (`input.int`, `input.float`, …).",
    "request": "Namespace. Data requests from other contexts (`request.security`, …).",
    "color": "Namespace. Color constants and helpers (`color.new`, `color.rgb`, `color.red`, …).",
}

_SNIPPET_PLACEHOLDER = re.compile(r"\$\{(\d+):([^}]+)\}|\$\{(\d+)\}|\$(\d+)")


def handle_hover(
    params: lsp.HoverParams,
    source: str | None,
    tree: Any | None = ...,
) -> lsp.Hover | None:
    """Return markdown hover for a symbol at the cursor, or ``None``.

    Args:
        params: Client hover params (document URI + position).
        source: Document text, or ``None``.
        tree: Pre-parsed AST from the workspace cache. Pass ``None`` when the
            workspace already failed to parse. Omit (default ``...``) to parse
            from *source*.

    Returns:
        :class:`~lsprotocol.types.Hover` with docs, or ``None`` if the
        symbol is unknown / out of range.
    """
    position = params.position

    if not source:
        return None

    lines = source.split("\n")
    if position.line >= len(lines):
        return None

    line_text = lines[position.line]
    segment, seg_start, seg_end, word = get_identifier_segment_at_position(
        source, position.line, position.character
    )
    if not word:
        return None

    ns_hover = _hover_namespace(segment, word, line_text, position.line, seg_start, seg_end)
    if ns_hover is not None:
        return ns_hover

    type_hover = _hover_type_or_qualifier(segment, line_text, seg_end, position.line, seg_start)
    if type_hover is not None:
        return type_hover

    builtin_hover = _hover_builtin(word, line_text, seg_start, position.line, seg_end)
    if builtin_hover is not None:
        return builtin_hover

    resolved = _resolve_tree(source, tree)
    enums = collect_user_enums(resolved, source)
    enum_hover = _hover_user_enum(word, enums, position.line, seg_start, seg_end)
    if enum_hover is not None:
        return enum_hover

    decl_hover = _hover_user_decl(segment, resolved, source, position.line, seg_start, seg_end)
    if decl_hover is not None:
        return decl_hover

    return _hover_keyword(segment, position.line, seg_start, seg_end)


def _followed_by_paren(line_text: str, end: int) -> bool:
    return line_text[end:].lstrip().startswith("(")


def _markdown_hover(fence: str, brief: str, line: int, start: int, end: int) -> lsp.Hover:
    return lsp.Hover(
        contents=lsp.MarkupContent(
            kind=lsp.MarkupKind.Markdown,
            value=f"```pinescript\n{fence}\n```\n\n{brief}\n",
        ),
        range=lsp.Range(
            start=lsp.Position(line=line, character=start),
            end=lsp.Position(line=line, character=end),
        ),
    )


def _hover_namespace(
    segment: str,
    word: str,
    line_text: str,
    line: int,
    start: int,
    end: int,
) -> lsp.Hover | None:
    """Hover when the cursor is on a module name (`ta` in `ta.sma`)."""
    brief = _NAMESPACE_DOCS.get(segment)
    if brief is None:
        return None
    dotted = word.startswith(segment + ".") or (end < len(line_text) and line_text[end] == ".")
    if not dotted:
        # Bare `ta` / `math` still document the module; `strategy(` / `input(` /
        # `color(` are declaration or constructor builtins.
        if _followed_by_paren(line_text, end) or segment in ("strategy", "input", "color"):
            return None
    return _markdown_hover(segment, brief, line, start, end)


def _hover_type_or_qualifier(
    segment: str,
    line_text: str,
    end: int,
    line: int,
    start: int,
) -> lsp.Hover | None:
    """Hover for a type or qualifier that is not being called as a function."""
    if _followed_by_paren(line_text, end):
        return None
    if segment in _TYPE_DOCS:
        return _markdown_hover(segment, _TYPE_DOCS[segment], line, start, end)
    if segment in _QUALIFIER_DOCS:
        return _markdown_hover(segment, _QUALIFIER_DOCS[segment], line, start, end)
    return None


def _hover_user_decl(
    name: str,
    tree: Any | None,
    source: str,
    line: int,
    start: int,
    end: int,
) -> lsp.Hover | None:
    """Hover for a user function, assignment, type, or enum from the AST."""
    if not name or tree is None:
        return None
    try:
        decls = _collect_user_decls(tree, source)
    except Exception:
        return None
    info = decls.get(name)
    if info is None:
        return None
    kind = info.get("kind", "declaration")
    signature = info.get("signature") or name
    return _markdown_hover(signature, f"User-defined {kind}.", line, start, end)


def _collect_user_decls(tree: Any, source: str) -> dict[str, dict[str, str]]:
    """Map identifier → first declaration (kind + source signature)."""
    found: dict[str, dict[str, str]] = {}

    def add(name: str | None, kind: str, node: Any, fallback: str) -> None:
        if not name or name in found:
            return
        snippet = _line_snippet(source, getattr(node, "lineno", None))
        found[name] = {"kind": kind, "signature": snippet or fallback}

    def walk(node: Any) -> None:
        if node is None:
            return
        if isinstance(node, ast.FunctionDef) and node.name:
            kind = "method" if node.method else "function"
            add(node.name, kind, node, _function_fallback(node))
        elif isinstance(node, ast.TypeDef) and node.name:
            export = "export " if node.export else ""
            add(node.name, "type", node, f"{export}type {node.name}")
        elif isinstance(node, ast.EnumDef) and node.name:
            export = "export " if node.export else ""
            add(node.name, "enum", node, f"{export}enum {node.name}")
        elif isinstance(node, ast.Assign) and isinstance(node.target, ast.Name):
            add(node.target.id, "variable", node, node.target.id)
        elif isinstance(node, ast.Assign) and isinstance(node.target, ast.Tuple):
            for elt in node.target.elts or []:
                if isinstance(elt, ast.Name):
                    add(elt.id, "variable", node, elt.id)

        for field in getattr(node, "_fields", ()) or ():
            value = getattr(node, field, None)
            if value is None:
                continue
            if isinstance(value, list):
                for child in value:
                    if child is not None and hasattr(child, "_fields"):
                        walk(child)
            elif hasattr(value, "_fields"):
                walk(value)

    walk(tree)
    return found


def _function_fallback(node: ast.FunctionDef) -> str:
    args: list[str] = []
    for param in node.args or []:
        pname = getattr(param, "name", None)
        if pname:
            args.append(str(pname))
    prefix = ""
    if node.export:
        prefix += "export "
    if node.method:
        prefix += "method "
    return f"{prefix}{node.name}({', '.join(args)}) =>"


def _line_snippet(source: str, lineno: int | None) -> str:
    if not source or not lineno:
        return ""
    lines = source.split("\n")
    idx = lineno - 1
    if 0 <= idx < len(lines):
        return lines[idx].strip()
    return ""


def _hover_builtin(word: str, line_text: str, start: int, line: int, end: int) -> lsp.Hover | None:
    """Resolve a builtin from the full word, leaf, or preceding ``module.``."""
    builtin_info = get_builtin(word)
    if builtin_info:
        return _build_builtin_hover(builtin_info, line, start, end)

    if "." in word:
        leaf = word.rsplit(".", 1)[-1]
        for candidate in (word, leaf):
            builtin_info = get_builtin(candidate)
            if builtin_info:
                return _build_builtin_hover(builtin_info, line, start, end)

    text_before = line_text[:start]
    words_before = text_before.rstrip().split()
    if words_before:
        last_word = words_before[-1]
        if last_word.endswith("."):
            module = last_word.rstrip(".")
            builtin_info = get_builtin(f"{module}.{word}")
            if builtin_info:
                return _build_builtin_hover(builtin_info, line, start, end)
    return None


def _resolve_tree(source: str | None, tree: Any | None) -> Any | None:
    if tree is not ...:
        return tree
    if not source:
        return None
    try:
        from pynescript.ast.helper import parse

        return parse(source)
    except Exception:
        return None


def _hover_user_enum(
    word: str,
    enums: dict[str, dict[str, Any]],
    line: int,
    start: int,
    end: int,
) -> lsp.Hover | None:
    """Hover for a user enum type or ``Enum.member`` path."""
    if word in enums:
        return _build_enum_hover(enums[word], member=None, line=line, start=start, end=end)
    if "." in word:
        enum_name, _, member = word.partition(".")
        info = enums.get(enum_name)
        if info is not None:
            return _build_enum_hover(info, member=member, line=line, start=start, end=end)
    return None


def _hover_keyword(word: str, line: int, start: int, end: int) -> lsp.Hover | None:
    brief = _KEYWORD_DOCS.get(word)
    if brief is None:
        return None
    return lsp.Hover(
        contents=lsp.MarkupContent(
            kind=lsp.MarkupKind.Markdown,
            value=f"```pinescript\n{word}\n```\n\n{brief}\n",
        ),
        range=lsp.Range(
            start=lsp.Position(line=line, character=start),
            end=lsp.Position(line=line, character=end),
        ),
    )


def _build_enum_hover(
    info: dict[str, Any],
    member: str | None,
    line: int,
    start: int,
    end: int,
) -> lsp.Hover:
    name = info.get("name", "")
    export = "export " if info.get("export") else ""
    lines = [f"{export}enum {name}"]
    matched = None
    for item in info.get("members", []):
        mname = item.get("name", "")
        value = item.get("value")
        decl = f"    {mname}" if value is None else f"    {mname} = {value!r}"
        lines.append(decl)
        if member and mname == member:
            matched = item
    if member and matched is None:
        # Unknown member still shows the enum type.
        pass
    detail = "\n".join(lines)
    if member and matched is not None:
        value = matched.get("value")
        brief = f"Member of user enum `{name}`."
        if value is not None:
            brief += f" Value: `{value!r}`."
    else:
        brief = "User-defined enum."
    content = f"```pinescript\n{detail}\n```\n\n{brief}\n"
    return lsp.Hover(
        contents=lsp.MarkupContent(kind=lsp.MarkupKind.Markdown, value=content),
        range=lsp.Range(
            start=lsp.Position(line=line, character=start),
            end=lsp.Position(line=line, character=end),
        ),
    )


def _signature_from_info(info: dict) -> str:
    """Prefer a real signature line; fall back to ``detail`` / label."""
    label = (info.get("label") or "").strip()
    detail = (info.get("detail") or "").strip()
    snippet = (info.get("snippet") or "").strip()
    if detail and not detail.endswith("(...)"):
        return detail
    if snippet:
        cleaned = _SNIPPET_PLACEHOLDER.sub(
            lambda m: m.group(2) if m.group(2) else "",
            snippet,
        )
        if cleaned and "param" not in cleaned.lower() and cleaned not in {label, f"{label}(...)"}:
            return cleaned
    return detail or label


def _format_params(info: dict) -> str:
    """Render a Parameters section when metadata includes ``params``."""
    params = info.get("params")
    if params is None:
        params = info.get("parameters")
    if not params:
        return ""
    entries: list[tuple[str, str]] = []
    if isinstance(params, dict):
        entries = [(str(k), "" if v is None else str(v)) for k, v in params.items()]
    elif isinstance(params, list):
        for item in params:
            if isinstance(item, str):
                entries.append((item, ""))
            elif isinstance(item, dict):
                name = item.get("name") or item.get("label") or ""
                if not name:
                    continue
                typ = item.get("type") or ""
                desc = item.get("brief") or item.get("documentation") or item.get("detail") or ""
                extra = f" (`{typ}`)" if typ else ""
                tail = f" — {desc}" if desc else ""
                entries.append((str(name), f"{extra}{tail}"))
    if not entries:
        return ""
    lines = ["**Parameters:**"]
    for name, desc in entries:
        if desc and not desc.startswith(" ") and not desc.startswith(" —"):
            lines.append(f"- `{name}`: {desc}")
        elif desc:
            lines.append(f"- `{name}`{desc}")
        else:
            lines.append(f"- `{name}`")
    return "\n".join(lines) + "\n\n"


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
    brief = info.get("brief", "")
    documentation = info.get("documentation", "")
    signature = _signature_from_info(info)

    content = f"""```pinescript
{signature}
```

{brief}

"""

    params_block = _format_params(info)
    if params_block:
        content += params_block

    if documentation and documentation != brief:
        content += f"---\n{_format_documentation(documentation)}\n\n"

    content += _build_examples(info)
    content += _build_see_also(info)

    # Add reference Pine docs link
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
    """Build a link to reference Pine documentation.

    Note: reference Pine docs links require the full function reference.
    This is a placeholder that shows how to structure the link.
    """
    # Don't include external links in basic hover
    return ""
