#!/usr/bin/env python3
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

"""Generate builtin metadata JSON for LSP completion and hover.

This script introspects the BuiltinEvaluator and generates a structured
JSON file with all builtin function metadata for LSP features.

CLI (from repo root, with package importable)::

    python scripts/generate_builtin_metadata.py

Writes ``src/pynescript/langserver/providers/builtin_metadata.json``.
"""

from __future__ import annotations

import json
import re

from pathlib import Path
from typing import Any


def _infer_category(name: str) -> str:
    """Infer the completion category from the function name."""
    if "." not in name:
        return "builtin"
    module, _, _ = name.partition(".")
    categories = {
        "ta": "ta.technical_analysis",
        "strategy": "strategy",
        "request": "request",
        "input": "input",
        "array": "array",
        "matrix": "matrix",
        "map": "map",
        "math": "math",
        "str": "str",
        "color": "color",
        "plot": "plot",
        "plotshape": "plotshape",
        "plotbar": "plotbar",
        "plotcandle": "plotcandle",
        "line": "line",
        "label": "label",
        "box": "box",
        "table": "table",
        "polyline": "polyline",
        "alert": "alert",
        "alertcondition": "alert",
        "log": "log",
        "ticker": "ticker",
        "timeframe": "timeframe",
        "chart": "chart",
    }
    return categories.get(module, module)


def _extract_signature(name: str, doc: str) -> tuple[str, list[str]]:
    """Extract a Pine signature and parameter names from a docstring.

    Returns ``(signature, params)``. Falls back to ``name(...)`` / ``[]``.
    """
    # 1. Explicit "Signature: func(args)" / "Pine signature:" blocks.
    for marker in ("Signature:", "Pine signature:"):
        if marker in doc:
            match = re.search(
                rf"{marker}\s*`*([A-Za-z_][\w.]*\s*\([^)]*\))",
                doc,
                re.DOTALL,
            )
            if match:
                signature = " ".join(match.group(1).split())
                return signature, _params_from_signature(signature)

    # 2. First function-shaped line in the docstring. Many handlers start with
    #    ``strategy.entry(id, direction, qty, ...)`` or ``array.get(id, index)``.
    parts = name.split(".")
    leaf = parts[-1]
    patterns = [re.escape(name), re.escape(leaf)]
    for pattern in patterns:
        match = re.search(
            rf"(?<![\w.])`?{pattern}\s*\(([^)]*)\)",
            doc,
            re.DOTALL,
        )
        if match:
            inner = " ".join(match.group(1).split())
            signature = f"{name}({inner})"
            return signature, _params_from_signature(signature)

    # 3. Generated fallback.
    return f"{name}(...)", []


def _params_from_signature(signature: str) -> list[str]:
    """Extract clean parameter names from a signature string."""
    start = signature.find("(")
    end = signature.rfind(")")
    if start < 0 or end <= start:
        return []
    inner = signature[start + 1 : end].strip()
    if not inner or inner == "...":
        return []
    names: list[str] = []
    depth = 0
    current: list[str] = []
    for char in inner:
        if char in "([{<":
            depth += 1
        elif char in ")]}>":
            depth = max(0, depth - 1)
        if char == "," and depth == 0:
            names.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    if current:
        names.append("".join(current).strip())
    cleaned: list[str] = []
    for chunk in names:
        if not chunk or chunk in {"...", "*", "**"}:
            continue
        if chunk.startswith(("*", "**")):
            continue
        name = chunk.split("=", 1)[0].strip().lstrip("*").strip()
        token = name.split()[-1] if name else ""
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token):
            cleaned.append(token)
    return cleaned


def _generate_snippet(name: str, params: list[str] | None = None) -> str:
    """Generate a completion snippet with placeholders from real parameters."""
    if name in ("line.fill", "linefill.new"):
        return f"{name}(${{1:line1}}, ${{2:line2}}, ${{3:color}})"
    usable = [param for param in (params or []) if param not in {"args", "kwargs", "extra", "_args"}]
    if usable:
        placeholders = ", ".join(f"${{{index}:{param}}}" for index, param in enumerate(usable, 1))
        return f"{name}({placeholders})"
    # Unknown arity: insert the bare name rather than a bogus ``name(arg)``.
    # Many zero-parameter dispatch entries are constants/properties.
    return name


def _handler_params(name: str, handler: Any) -> list[str]:
    """Best-effort Pine parameter names for one dispatch handler."""
    order = getattr(handler, "_KWARG_ORDER", None)
    if order is None:
        order = getattr(getattr(handler, "__func__", None), "_KWARG_ORDER", None)
    if order is None and name.startswith("ta."):
        from pynescript.ast.evaluator.builtins.base import _TA_KWARG_ORDERS

        order = _TA_KWARG_ORDERS.get(name.split(".", 1)[1])
    if order:
        return [str(item) for item in order if str(item) not in {"args", "kwargs"}]
    try:
        from pynescript.ast.evaluator.builtins.base import _handler_param_names

        names = _handler_param_names(handler)
    except Exception:
        names = None
    if names:
        return [item for item in names if item not in {"args", "kwargs", "self", "extra", "_args"} and not item.startswith("_")]
    return []


def _brief_from_doc(name: str, doc: str) -> str:
    """Pick a short human description, skipping signature/parameter lines."""
    leaf = name.rsplit(".", 1)[-1]
    for raw in doc.splitlines():
        line = raw.strip().lstrip("`").rstrip("`")
        if not line:
            continue
        if line.startswith(("Signature:", "Pine signature:")):
            continue
        if re.match(rf"^`?{re.escape(name)}\s*\(", line) or re.match(rf"^`?{re.escape(leaf)}\s*\(", line):
            # Keep a trailing one-line description after the signature:
            # ``plot(series, …) → plot id`` / ``array.push(id, value) — append``.
            tail = line.split(")", 1)[1].strip(" .`") if ")" in line else ""
            tail = tail.lstrip("→-— ").strip()
            if tail:
                return tail[:117] + "..." if len(tail) > 120 else tail
            continue
        # Wrapped signature continuation lines (plot's parameter list).
        if re.match(r"^[a-z_][A-Za-z0-9_]*\s*(,|\))", line) and "," in line:
            continue
        return line[:117] + "..." if len(line) > 120 else line
    return ""


def generate_metadata() -> dict[str, Any]:
    """Generate builtin metadata from BuiltinEvaluator."""
    from pynescript.ast.evaluator.builtins import BuiltinEvaluator

    evaluator = BuiltinEvaluator()
    dispatch = evaluator._build_builtin_map()
    metadata = {}

    for name, handler in sorted(dispatch.items()):
        doc = handler.__doc__ or ""

        brief = _brief_from_doc(name, doc)
        documentation = doc.strip()

        signature, params = _extract_signature(name, doc)
        if not params:
            params = _handler_params(name, handler)
            if params:
                signature = f"{name}({', '.join(params)})"
        snippet = _generate_snippet(name, params)

        category = _infer_category(name)
        kind = "function"

        metadata[name] = {
            "label": name,
            "kind": kind,
            "detail": signature,
            "brief": brief,
            "documentation": documentation,
            "snippet": snippet,
            "params": params,
            "category": category,
        }

    return metadata


def main():
    """Generate and save builtin metadata JSON."""
    metadata = generate_metadata()

    output_path = Path(__file__).parent.parent / "src/pynescript/langserver/providers/builtin_metadata.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    # Print summary
    categories: dict[str, int] = {}
    for info in metadata.values():
        cat = info["category"]
        categories[cat] = categories.get(cat, 0) + 1

    print(f"Generated {len(metadata)} builtin entries")
    print(f"Output: {output_path}")
    print("\nBy category:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")


if __name__ == "__main__":
    main()
