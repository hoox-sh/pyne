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

"""Pine ``map`` collection type (key-value store).

Defines the runtime :class:`Map` value used by ``map.*`` builtins. Dispatch
handlers live in :mod:`map_evaluator` (:class:`MapBuiltinsMixin`); this module
is the pure data structure only.
"""

from __future__ import annotations

from typing import Any
from typing import Generic
from typing import TypeVar


__all__ = ["Map"]

K = TypeVar("K")
V = TypeVar("V")


class RealtimeSnapshotError(RuntimeError):
    """Cyclic container encountered while snapshotting realtime state."""


def _snapshot_value(value: Any, seen: set[int] | None = None) -> tuple[Any, ...]:
    """Recursive rollback snapshot node for a map value.

    Nested lists/dicts, Map/Matrix containers and UDT fields are snapshotted
    recursively. Cycles raise :class:`RealtimeSnapshotError` instead of
    recursing forever; the host re-raises it so an unconfirmed tick cannot
    silently commit. List, typed, and UDT nodes carry the original object so a
    removed or replaced value is restored into that object, not a new one.
    """
    if seen is None:
        seen = set()
    oid = id(value)
    if oid in seen:
        raise RealtimeSnapshotError("cyclic container in realtime rollback snapshot")
    if isinstance(value, list):
        seen.add(oid)
        try:
            return ("list", [_snapshot_value(item, seen) for item in value], value)
        finally:
            seen.discard(oid)
    if isinstance(value, dict):
        seen.add(oid)
        try:
            return ("dict", {key: _snapshot_value(item, seen) for key, item in value.items()})
        finally:
            seen.discard(oid)
    if isinstance(value, Map):
        seen.add(oid)
        try:
            return ("typed", _snapshot_value(value.data, seen), value)
        finally:
            seen.discard(oid)
    copy_fn = getattr(value, "copy_contents", None)
    if callable(copy_fn):
        return ("typed", copy_fn(), value)
    fields = getattr(value, "fields", None)
    if isinstance(fields, dict) and getattr(value, "udt", None) is not None:
        seen.add(oid)
        try:
            return ("udt", {key: _snapshot_value(item, seen) for key, item in fields.items()}, value)
        finally:
            seen.discard(oid)
    return ("value", value)


def _restore_value(current: Any, snap: tuple[Any, ...]) -> Any:
    """Write a snapshot node back, restoring removed/replaced typed values."""
    if not isinstance(snap, tuple) or len(snap) not in (2, 3):
        return current
    kind, payload = snap[0], snap[1]
    original = snap[2] if len(snap) == 3 else None
    if kind == "list":
        # Same as typed/UDT: a removed or replaced list comes back as the
        # object the caller still holds, with snapshotted contents.
        target = original if isinstance(original, list) else current
        if isinstance(target, list):
            restored = [_restore_value(target[i] if i < len(target) else None, node) for i, node in enumerate(payload)]
            target[:] = restored
            return target
        return [_restore_value(None, node) for node in payload]
    if kind == "dict":
        if isinstance(current, dict):
            restored = {key: _restore_value(current.get(key), node) for key, node in payload.items()}
            current.clear()
            current.update(restored)
            return current
        return {key: _restore_value(None, node) for key, node in payload.items()}
    if kind == "typed":
        target = original if original is not None else current
        restore_fn = getattr(target, "restore_contents", None)
        if callable(restore_fn):
            restore_fn(payload)
            return target
        return current
    if kind == "udt":
        target = original if original is not None else current
        fields = getattr(target, "fields", None)
        if isinstance(fields, dict):
            restored = {key: _restore_value(fields.get(key), node) for key, node in payload.items()}
            fields.clear()
            fields.update(restored)
            return target
        return current
    return payload


class Map(Generic[K, V]):
    """Mutable ordered-preserving key-value map for Pine ``map.*`` operations.

    Backed by a Python ``dict``. Methods mirror reference Pine map semantics
    (``get``/``put``/``remove``/``keys``/``values``/…). Evaluator dispatch is
    in :class:`~pynescript.ast.evaluator.builtins.map_evaluator.MapBuiltinsMixin`.
    """

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

    def remove(self, key: K) -> V | None:
        """Remove key from map; return prior value or None if missing."""
        if key in self.data:
            return self.data.pop(key)
        return None

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

    def copy_contents(self) -> tuple[str, Any]:
        """Recursive snapshot of map items (nested containers included)."""
        return _snapshot_value(self.data)

    def restore_contents(self, snap: tuple[str, Any]) -> None:
        """Restore from :meth:`copy_contents`, preserving nested identities."""
        restored = _restore_value(self.data, snap)
        if restored is not self.data and isinstance(restored, dict):
            self.data.clear()
            self.data.update(restored)

    def __repr__(self) -> str:
        """String representation."""
        return f"map({self.size()})"
