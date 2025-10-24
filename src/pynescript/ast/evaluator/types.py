from __future__ import annotations

from typing import Any
from typing import NoReturn
from typing import Protocol

from pynescript.ast.node import AST


class EvaluatorProtocol(Protocol):
    context: dict[str, Any]

    def visit(self, node: AST) -> Any:  # pragma: no cover - typing helper
        ...

    def _error(self, msg: str) -> NoReturn:  # pragma: no cover - typing helper
        ...

    def _call_builtin(self, name: str, args: list[Any]) -> Any:  # pragma: no cover - typing helper
        ...

    def _invoke_method(
        self, obj: Any, method_name: str, args: list[Any], kwargs: dict[str, Any]
    ) -> Any:  # pragma: no cover - typing helper
        ...

    def _handle_udt_new(
        self, type_obj: Any, args: list[Any], kwargs: dict[str, Any]
    ) -> Any:  # pragma: no cover - typing helper
        ...
