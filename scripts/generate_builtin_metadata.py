#!/usr/bin/env python3
"""Generate builtin metadata JSON for LSP completion and hover.

This script introspects the BuiltinEvaluator and generates a structured
JSON file with all builtin function metadata for LSP features.
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
    module, _, func = name.partition(".")
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


def _extract_signature(name: str, doc: str) -> str:
    """Extract signature from docstring or generate one."""
    # Try to extract from "Signature: func(args)" pattern
    if "Signature:" in doc:
        match = re.search(r"Signature:\s*(\w+\([^\)]*\))", doc)
        if match:
            return match.group(1)

    # Generate based on function type
    parts = name.split(".")
    func_name = parts[-1]

    if func_name in ("new", "from", "of"):
        return f"{name}(...)"

    return f"{name}(...)"


def _generate_snippet(name: str) -> str:
    """Generate a completion snippet with placeholders."""
    # Extract parameter names if possible from doc
    parts = name.split(".")
    func = parts[-1]

    # Common parameter patterns
    param_patterns = {
        "series": "${1:series}",
        "length": "${2:length}",
        "source": "${1:source}",
        "period": "${2:period}",
        "cond": "${1:condition}",
        "message": '"${1:message}"',
        "title": '"${1:title}"',
        "value": "${1:value}",
        "price": "${1:price}",
    }

    # Generate snippet with numbered placeholders
    if "." in name:
        snippet = name + "("
        parts_count = _count_params(name)
        for i in range(1, parts_count + 1):
            snippet += f"${{{i}:param{i}}}"
            if i < parts_count:
                snippet += ", "
        snippet += ")"
    else:
        snippet = f"{name}(${{1:arg}})"

    return snippet


def _count_params(name: str) -> int:
    """Estimate parameter count based on function name patterns."""
    # TA functions typically have 2 params
    if name.startswith("ta."):
        if name in ("ta.sma", "ta.ema", "ta.rma", "ta.wma", "ta.vwma", "ta.hma", "ta.rsi", "ta.stdev"):
            return 2
        if name in ("ta.bb", "ta.macd", "ta.supertrend", "ta.atr"):
            return 3
        return 2

    # Array operations
    if name.startswith("array."):
        if name.endswith("new"):
            return 1
        if name in ("array.push", "array.pop", "array.shift", "array.unshift"):
            return 2
        return 1

    # Strategy
    if name.startswith("strategy."):
        return 2

    # Others
    return 1


def generate_metadata() -> dict[str, Any]:
    """Generate builtin metadata from BuiltinEvaluator."""
    from pynescript.ast.evaluator.builtins import BuiltinEvaluator

    evaluator = BuiltinEvaluator()

    # Trigger dispatch map build
    try:
        evaluator._call_builtin("math.sqrt", [4])
    except Exception:
        pass

    dispatch = evaluator._builtin_dispatch
    metadata = {}

    for name, handler in sorted(dispatch.items()):
        doc = handler.__doc__ or ""

        # Extract brief description
        brief = ""
        if doc:
            # Take first sentence
            sentences = doc.split(".")
            brief = sentences[0].strip()
            if len(brief) > 100:
                brief = brief[:97] + "..."

        # Extract full documentation
        documentation = doc.strip()

        # Generate signature
        signature = _extract_signature(name, doc)

        # Generate snippet
        snippet = _generate_snippet(name)

        # Infer category
        category = _infer_category(name)

        # Determine kind
        if name.startswith("strategy.") or name.startswith("ta."):
            kind = "function"
        elif name.startswith("input."):
            kind = "function"
        else:
            kind = "function"

        metadata[name] = {
            "label": name,
            "kind": kind,
            "detail": signature,
            "brief": brief,
            "documentation": documentation,
            "snippet": snippet,
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
    for name, info in metadata.items():
        cat = info["category"]
        categories[cat] = categories.get(cat, 0) + 1

    print(f"Generated {len(metadata)} builtin entries")
    print(f"Output: {output_path}")
    print("\nBy category:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")


if __name__ == "__main__":
    main()
