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

"""Pine ``map.*`` builtins dispatching onto :class:`~.map.Map`.

Creates maps, mutates entries, and exposes keys/values/size. Plain Python
``dict`` values from compile/host bridges are wrapped in-place so mutations
remain visible to the host.

Mixin composition
-----------------
:class:`MapBuiltinsMixin` contributes ``_map_builtin_map`` into
:class:`~pynescript.ast.evaluator.builtins.BuiltinEvaluator`.
"""

from __future__ import annotations

from typing import Any

from .base import BuiltinDispatchMixin
from .base import BuiltinHandler
from .map import Map


UNARY = 1
BINARY = 2
TERNARY = 3


class MapBuiltinsMixin(BuiltinDispatchMixin):
    """``map.new`` / ``get`` / ``put`` / ``remove`` / … builtin handlers.

    Validates operands as :class:`~.map.Map` (or wraps ``dict``) and forwards
    to instance methods on the collection type.
    """

    def _map_builtin_map(self) -> dict[str, BuiltinHandler]:
        """Build dispatch map for map operations."""
        return {
            # Core operations
            "map.new": self._builtin_map_new,
            "map.get": self._builtin_map_get,
            "map.put": self._builtin_map_put,
            "map.put_all": self._builtin_map_put_all,
            "map.remove": self._builtin_map_remove,
            "map.clear": self._builtin_map_clear,
            "map.contains": self._builtin_map_contains,
            "map.keys": self._builtin_map_keys,
            "map.values": self._builtin_map_values,
            "map.size": self._builtin_map_size,
            "map.copy": self._builtin_map_copy,
        }

    # ========== HELPER METHODS ==========

    def _expect_map(self, value: Any, message: str) -> Map[Any, Any]:
        """Validate that value is a Map instance (hard-fail on na / wrong type)."""
        if isinstance(value, Map):
            return value
        if value is None:
            self._error(f"{message} (got na)")
        # Plain dict (compile-path / host bridges) — wrap without copy so puts mutate.
        if isinstance(value, dict):
            wrapped: Map[Any, Any] = Map()
            wrapped.data = value
            return wrapped
        tname = type(value).__name__
        self._error(f"{message} (got {tname}, expected map)")

    def _coerce_optional_map(self, value: Any) -> Map[Any, Any] | None:
        """Like ``_expect_map`` but ``na`` / non-map → ``None`` (reference soft-na)."""
        if value is None:
            return None
        if isinstance(value, Map):
            return value
        if isinstance(value, dict):
            wrapped: Map[Any, Any] = Map()
            wrapped.data = value
            return wrapped
        return None

    # ========== CORE OPERATIONS ==========

    def _builtin_map_new(self, _args: list[Any]) -> Map[Any, Any]:
        """map.new() -> Map

        Creates new empty map.
        """
        return Map()

    def _builtin_map_get(self, args: list[Any]) -> Any:
        """map.get(map, key) -> value

        Returns value for key, or None if not found. ``na`` map → ``na``.
        """
        if len(args) < BINARY:
            self._error("map.get requires map and key")
        map_obj = self._coerce_optional_map(args[0])
        if map_obj is None:
            return None
        key = args[UNARY]
        return map_obj.get(key)

    def _builtin_map_put(self, args: list[Any]) -> None:
        """map.put(map, key, value) -> void

        Inserts or updates key-value pair. ``na`` map → no-op.
        """
        if len(args) < TERNARY:
            self._error("map.put requires map, key, and value")
        map_obj = self._coerce_optional_map(args[0])
        if map_obj is None:
            # Soft-na only for genuine na; wrong types still hard-fail
            if args[0] is None:
                return None
            self._expect_map(args[0], "map.put: first arg must be map")
            return None
        key = args[UNARY]
        value = args[BINARY]
        map_obj.put(key, value)
        return None

    def _builtin_map_put_all(self, args: list[Any]) -> None:
        """map.put_all(map, other_map) -> void

        Inserts all key-value pairs from another map. ``na`` either → no-op.
        """
        if len(args) < BINARY:
            self._error("map.put_all requires map and other map")
        map_obj = self._coerce_optional_map(args[0])
        other_map = self._coerce_optional_map(args[UNARY])
        if map_obj is None or other_map is None:
            if args[0] is not None and map_obj is None:
                self._expect_map(args[0], "map.put_all: first arg must be map")
            return None
        map_obj.put_all(other_map)
        return None

    def _builtin_map_remove(self, args: list[Any]) -> Any:
        """map.remove(map, key) -> previous value or na

        Removes key and returns the prior value (reference). Missing key / na map → na.
        """
        if len(args) < BINARY:
            self._error("map.remove requires map and key")
        map_obj = self._coerce_optional_map(args[0])
        if map_obj is None:
            return None
        key = args[UNARY]
        prev = map_obj.get(key)
        map_obj.remove(key)
        return prev

    def _builtin_map_clear(self, args: list[Any]) -> None:
        """map.clear(map) -> void

        Removes all entries from map. ``na`` map → no-op.
        """
        if len(args) < UNARY:
            self._error("map.clear requires map")
        map_obj = self._coerce_optional_map(args[0])
        if map_obj is None:
            return None
        map_obj.clear()
        return None

    def _builtin_map_contains(self, args: list[Any]) -> bool | None:
        """map.contains(map, key) -> bool; ``na`` map → ``na``."""
        if len(args) < BINARY:
            self._error("map.contains requires map and key")
        map_obj = self._coerce_optional_map(args[0])
        if map_obj is None:
            return None
        key = args[UNARY]
        return map_obj.contains(key)

    def _builtin_map_keys(self, args: list[Any]) -> list[Any] | None:
        """map.keys(map) -> array; ``na`` map → ``na``."""
        if len(args) < UNARY:
            self._error("map.keys requires map")
        map_obj = self._coerce_optional_map(args[0])
        if map_obj is None:
            return None
        return map_obj.keys()

    def _builtin_map_values(self, args: list[Any]) -> list[Any] | None:
        """map.values(map) -> array; ``na`` map → ``na``."""
        if len(args) < UNARY:
            self._error("map.values requires map")
        map_obj = self._coerce_optional_map(args[0])
        if map_obj is None:
            return None
        return map_obj.values()

    def _builtin_map_size(self, args: list[Any]) -> int | None:
        """map.size(map) -> int; ``na`` map → ``na`` (reference soft-na)."""
        if len(args) < UNARY:
            self._error("map.size requires map")
        map_obj = self._coerce_optional_map(args[0])
        if map_obj is None:
            return None
        return map_obj.size()

    def _builtin_map_copy(self, args: list[Any]) -> Map[Any, Any] | None:
        """map.copy(map) -> Map; ``na`` map → ``na``."""
        if len(args) < UNARY:
            self._error("map.copy requires map")
        map_obj = self._coerce_optional_map(args[0])
        if map_obj is None:
            return None
        return map_obj.copy()
