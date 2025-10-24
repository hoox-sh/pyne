"""Script declaration functions for PineScript v6 evaluator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ScriptDeclaration:
    """Metadata for a PineScript script (indicator, strategy, or library)."""

    script_type: str  # "indicator", "strategy", or "library"
    title: str = ""
    description: str = ""


def indicator(title: str = "", description: str = "", **_kwargs: Any) -> ScriptDeclaration:
    """Declare an indicator script.

    Args:
        title: Full title of the indicator
        description: Description of the indicator
        **_kwargs: Additional parameters accepted by PineScript

    Returns:
        ScriptDeclaration object with script metadata
    """
    return ScriptDeclaration(
        script_type="indicator",
        title=str(title),
        description=str(description),
    )


def strategy(title: str = "", description: str = "", **_kwargs: Any) -> ScriptDeclaration:
    """Declare a strategy script.

    Args:
        title: Full title of the strategy
        description: Description of the strategy
        **_kwargs: Additional strategy parameters (pyramiding, default_qty_type, etc.)

    Returns:
        ScriptDeclaration object with script metadata
    """
    return ScriptDeclaration(
        script_type="strategy",
        title=str(title),
        description=str(description),
    )


def library(title: str = "", description: str = "", **_kwargs: Any) -> ScriptDeclaration:
    """Declare a library script.

    Args:
        title: Full title of the library
        description: Description of the library
        **_kwargs: Additional parameters accepted by PineScript

    Returns:
        ScriptDeclaration object with script metadata
    """
    return ScriptDeclaration(
        script_type="library",
        title=str(title),
        description=str(description),
    )


def register_script_declaration_functions(namespace: dict) -> None:
    """Register script declaration functions in the given namespace.

    Args:
        namespace: Dictionary to register functions in (typically evaluator's builtins)
    """
    namespace["indicator"] = indicator
    namespace["strategy"] = strategy
    namespace["library"] = library
