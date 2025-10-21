from __future__ import annotations

from typing import Any, Protocol, NoReturn

from pynescript.ast.node import AST


class EvaluatorProtocol(Protocol):
    context: dict[str, Any]

    def visit(self, node: AST) -> Any:  # pragma: no cover - typing helper
        ...

    def _error(self, msg: str) -> NoReturn:  # pragma: no cover - typing helper
        ...

    def _call_builtin(self, name: str, args: list[Any]) -> Any:  # pragma: no cover - typing helper
        ...
