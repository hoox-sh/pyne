# Copyright 2024-2025 Yunseong Hwang, jango_blockchained
#
# Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.gnu.org/licenses/lgpl-3.0.en.html
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: LGPL-3.0-or-later

"""Map collection evaluator for Pine Script v6."""

from __future__ import annotations

from typing import Any

from .base import BuiltinDispatchMixin
from .base import BuiltinHandler
from .map import Map


UNARY = 1
BINARY = 2
TERNARY = 3


class MapBuiltinsMixin(BuiltinDispatchMixin):
    """Map collection built-in functions and methods."""

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
        """Validate that value is a Map instance."""
        if not isinstance(value, Map):
            self._error(message)
        return value

    # ========== CORE OPERATIONS ==========

    def _builtin_map_new(self, _args: list[Any]) -> Map[Any, Any]:
        """map.new() -> Map

        Creates new empty map.
        """
        return Map()

    def _builtin_map_get(self, args: list[Any]) -> Any:
        """map.get(map, key) -> value

        Returns value for key, or None if not found.
        """
        if len(args) < BINARY:
            self._error("map.get requires map and key")
        map_obj = self._expect_map(args[0], "map.get: first arg must be map")
        key = args[UNARY]
        return map_obj.get(key)

    def _builtin_map_put(self, args: list[Any]) -> None:
        """map.put(map, key, value) -> void

        Inserts or updates key-value pair.
        """
        if len(args) < TERNARY:
            self._error("map.put requires map, key, and value")
        map_obj = self._expect_map(args[0], "map.put: first arg must be map")
        key = args[UNARY]
        value = args[BINARY]
        map_obj.put(key, value)

    def _builtin_map_put_all(self, args: list[Any]) -> None:
        """map.put_all(map, other_map) -> void

        Inserts all key-value pairs from another map.
        """
        if len(args) < BINARY:
            self._error("map.put_all requires map and other map")
        map_obj = self._expect_map(args[0], "map.put_all: first arg must be map")
        other_map = self._expect_map(args[UNARY], "map.put_all: second arg must be map")
        map_obj.put_all(other_map)

    def _builtin_map_remove(self, args: list[Any]) -> None:
        """map.remove(map, key) -> void

        Removes key from map (no error if not found).
        """
        if len(args) < BINARY:
            self._error("map.remove requires map and key")
        map_obj = self._expect_map(args[0], "map.remove: first arg must be map")
        key = args[UNARY]
        map_obj.remove(key)

    def _builtin_map_clear(self, args: list[Any]) -> None:
        """map.clear(map) -> void

        Removes all entries from map.
        """
        if len(args) < UNARY:
            self._error("map.clear requires map")
        map_obj = self._expect_map(args[0], "map.clear: arg must be map")
        map_obj.clear()

    def _builtin_map_contains(self, args: list[Any]) -> bool:
        """map.contains(map, key) -> bool

        Returns true if key exists in map.
        """
        if len(args) < BINARY:
            self._error("map.contains requires map and key")
        map_obj = self._expect_map(args[0], "map.contains: first arg must be map")
        key = args[UNARY]
        return map_obj.contains(key)

    def _builtin_map_keys(self, args: list[Any]) -> list[Any]:
        """map.keys(map) -> array

        Returns array of all keys in map.
        """
        if len(args) < UNARY:
            self._error("map.keys requires map")
        map_obj = self._expect_map(args[0], "map.keys: arg must be map")
        return map_obj.keys()

    def _builtin_map_values(self, args: list[Any]) -> list[Any]:
        """map.values(map) -> array

        Returns array of all values in map.
        """
        if len(args) < UNARY:
            self._error("map.values requires map")
        map_obj = self._expect_map(args[0], "map.values: arg must be map")
        return map_obj.values()

    def _builtin_map_size(self, args: list[Any]) -> int:
        """map.size(map) -> int

        Returns number of key-value pairs in map.
        """
        if len(args) < UNARY:
            self._error("map.size requires map")
        map_obj = self._expect_map(args[0], "map.size: arg must be map")
        return map_obj.size()

    def _builtin_map_copy(self, args: list[Any]) -> Map[Any, Any]:
        """map.copy(map) -> Map

        Creates shallow copy of map.
        """
        if len(args) < UNARY:
            self._error("map.copy requires map")
        map_obj = self._expect_map(args[0], "map.copy: arg must be map")
        return map_obj.copy()
