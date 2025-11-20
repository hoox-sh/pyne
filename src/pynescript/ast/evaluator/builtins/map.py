# Copyright 2024-2025 jango_blockchained
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

"""Map collection type and operations for Pine Script v6."""

from __future__ import annotations

from typing import Any
from typing import Generic
from typing import TypeVar


__all__ = ["Map"]

K = TypeVar("K")
V = TypeVar("V")


class Map(Generic[K, V]):
    """Represents a key-value map (dictionary) in Pine Script."""

    def __init__(self):
        """Initialize empty map."""
        self.data: dict[Any, Any] = {}

    # ========== CORE METHODS ==========

    def get(self, key: K) -> V | None:
        """Get value by key, returns None if not found."""
        return self.data.get(key)

    def put(self, key: K, value: V) -> None:
        """Insert or update key-value pair."""
        self.data[key] = value

    def put_all(self, other: Map[K, V]) -> None:
        """Insert all key-value pairs from another map."""
        if not isinstance(other, Map):
            msg = "put_all requires a Map argument"
            raise TypeError(msg)
        self.data.update(other.data)

    def remove(self, key: K) -> None:
        """Remove key from map. Safe operation (no error if key not found)."""
        if key in self.data:
            del self.data[key]

    def clear(self) -> None:
        """Remove all entries from map."""
        self.data.clear()

    def contains(self, key: K) -> bool:
        """Check if key exists in map."""
        return key in self.data

    def keys(self) -> list[K]:
        """Get all keys as list."""
        return list(self.data.keys())

    def values(self) -> list[V]:
        """Get all values as list."""
        return list(self.data.values())

    def size(self) -> int:
        """Get number of key-value pairs."""
        return len(self.data)

    def copy(self) -> Map[K, V]:
        """Create shallow copy of map."""
        new_map: Map[K, V] = Map()
        new_map.data = self.data.copy()
        return new_map

    def __repr__(self) -> str:
        """String representation."""
        return f"map({self.size()})"
