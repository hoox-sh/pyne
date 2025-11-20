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

"""Unit tests for Map collection."""

from __future__ import annotations

import pytest

from pynescript.ast.evaluator.builtins.map import Map


class TestMapBasics:
    """Test basic Map operations."""

    def test_new_empty_map(self) -> None:
        """Create new empty map."""
        m: Map[str, int] = Map()
        assert m.size() == 0
        assert m.keys() == []
        assert m.values() == []

    def test_put_single_item(self) -> None:
        """Put single key-value pair."""
        m: Map[str, int] = Map()
        m.put("key1", 42)
        assert m.size() == 1
        assert m.get("key1") == 42

    def test_put_multiple_items(self) -> None:
        """Put multiple key-value pairs."""
        m: Map[str, int] = Map()
        m.put("key1", 10)
        m.put("key2", 20)
        m.put("key3", 30)
        assert m.size() == 3
        assert m.get("key1") == 10
        assert m.get("key2") == 20
        assert m.get("key3") == 30

    def test_put_update_existing(self) -> None:
        """Update existing key."""
        m: Map[str, int] = Map()
        m.put("key", 100)
        assert m.get("key") == 100
        m.put("key", 200)
        assert m.get("key") == 200
        assert m.size() == 1

    def test_get_nonexistent_key(self) -> None:
        """Get nonexistent key returns None."""
        m: Map[str, int] = Map()
        assert m.get("missing") is None

    def test_remove_existing_key(self) -> None:
        """Remove existing key."""
        m: Map[str, int] = Map()
        m.put("key1", 10)
        m.put("key2", 20)
        m.remove("key1")
        assert m.size() == 1
        assert m.get("key1") is None
        assert m.get("key2") == 20

    def test_remove_nonexistent_key(self) -> None:
        """Remove nonexistent key (no error)."""
        m: Map[str, int] = Map()
        m.put("key1", 10)
        m.remove("missing")  # Should not raise
        assert m.size() == 1

    def test_contains_existing_key(self) -> None:
        """Check if key exists."""
        m: Map[str, int] = Map()
        m.put("key1", 10)
        assert m.contains("key1") is True

    def test_contains_nonexistent_key(self) -> None:
        """Check if key not exists."""
        m: Map[str, int] = Map()
        assert m.contains("missing") is False

    def test_clear_map(self) -> None:
        """Clear all entries."""
        m: Map[str, int] = Map()
        m.put("key1", 10)
        m.put("key2", 20)
        m.put("key3", 30)
        m.clear()
        assert m.size() == 0
        assert m.keys() == []
        assert m.values() == []

    def test_clear_empty_map(self) -> None:
        """Clear already empty map (no error)."""
        m: Map[str, int] = Map()
        m.clear()
        assert m.size() == 0


class TestMapQueryMethods:
    """Test Map query methods."""

    def test_keys(self) -> None:
        """Get all keys."""
        m: Map[str, int] = Map()
        m.put("a", 1)
        m.put("b", 2)
        m.put("c", 3)
        keys = m.keys()
        assert len(keys) == 3
        assert "a" in keys
        assert "b" in keys
        assert "c" in keys

    def test_keys_empty_map(self) -> None:
        """Get keys from empty map."""
        m: Map[str, int] = Map()
        assert m.keys() == []

    def test_values(self) -> None:
        """Get all values."""
        m: Map[str, int] = Map()
        m.put("a", 1)
        m.put("b", 2)
        m.put("c", 3)
        values = m.values()
        assert len(values) == 3
        assert 1 in values
        assert 2 in values
        assert 3 in values

    def test_values_empty_map(self) -> None:
        """Get values from empty map."""
        m: Map[str, int] = Map()
        assert m.values() == []

    def test_size(self) -> None:
        """Get map size."""
        m: Map[str, int] = Map()
        assert m.size() == 0
        m.put("a", 1)
        assert m.size() == 1
        m.put("b", 2)
        assert m.size() == 2
        m.remove("a")
        assert m.size() == 1


class TestMapCopy:
    """Test Map copy operation."""

    def test_copy_empty_map(self) -> None:
        """Copy empty map."""
        m1: Map[str, int] = Map()
        m2 = m1.copy()
        assert m2.size() == 0

    def test_copy_map_with_items(self) -> None:
        """Copy map with items."""
        m1: Map[str, int] = Map()
        m1.put("a", 1)
        m1.put("b", 2)
        m2 = m1.copy()
        assert m2.size() == 2
        assert m2.get("a") == 1
        assert m2.get("b") == 2

    def test_copy_independence(self) -> None:
        """Copy is independent from original."""
        m1: Map[str, int] = Map()
        m1.put("a", 1)
        m2 = m1.copy()
        m2.put("b", 2)
        assert m1.size() == 1
        assert m2.size() == 2
        assert m1.get("b") is None

    def test_copy_modification_doesnt_affect_original(self) -> None:
        """Modifying copy doesn't affect original."""
        m1: Map[str, int] = Map()
        m1.put("a", 1)
        m2 = m1.copy()
        m2.put("a", 999)
        assert m1.get("a") == 1
        assert m2.get("a") == 999


class TestMapPutAll:
    """Test Map put_all operation."""

    def test_put_all_into_empty(self) -> None:
        """Put all from source into empty map."""
        m1: Map[str, int] = Map()
        m1.put("a", 1)
        m1.put("b", 2)

        m2: Map[str, int] = Map()
        m2.put_all(m1)
        assert m2.size() == 2
        assert m2.get("a") == 1
        assert m2.get("b") == 2

    def test_put_all_merge(self) -> None:
        """Merge two maps."""
        m1: Map[str, int] = Map()
        m1.put("a", 1)
        m1.put("b", 2)

        m2: Map[str, int] = Map()
        m2.put("c", 3)
        m2.put("d", 4)

        m2.put_all(m1)
        assert m2.size() == 4
        assert m2.get("a") == 1
        assert m2.get("b") == 2
        assert m2.get("c") == 3
        assert m2.get("d") == 4

    def test_put_all_overwrite(self) -> None:
        """Put all overwrites existing keys."""
        m1: Map[str, int] = Map()
        m1.put("a", 1)
        m1.put("b", 2)

        m2: Map[str, int] = Map()
        m2.put("a", 999)
        m2.put("c", 3)

        m2.put_all(m1)
        assert m2.size() == 3
        assert m2.get("a") == 1  # Updated
        assert m2.get("b") == 2
        assert m2.get("c") == 3

    def test_put_all_empty_source(self) -> None:
        """Put all from empty map."""
        m1: Map[str, int] = Map()
        m2: Map[str, int] = Map()
        m2.put("a", 1)
        m2.put_all(m1)
        assert m2.size() == 1
        assert m2.get("a") == 1

    def test_put_all_type_error(self) -> None:
        """Put all with non-map raises error."""
        m: Map[str, int] = Map()
        with pytest.raises(TypeError):
            m.put_all("not a map")  # type: ignore


class TestMapDifferentKeyTypes:
    """Test Map with different key types."""

    def test_string_keys(self) -> None:
        """Map with string keys."""
        m: Map[str, int] = Map()
        m.put("key1", 100)
        m.put("key2", 200)
        assert m.get("key1") == 100
        assert m.get("key2") == 200

    def test_int_keys(self) -> None:
        """Map with integer keys."""
        m: Map[int, str] = Map()
        m.put(1, "one")
        m.put(2, "two")
        assert m.get(1) == "one"
        assert m.get(2) == "two"

    def test_mixed_type_keys(self) -> None:
        """Map with mixed type keys."""
        m: Map[int | str, int] = Map()
        m.put(1, 100)
        m.put("key", 200)
        assert m.get(1) == 100
        assert m.get("key") == 200

    def test_tuple_keys(self) -> None:
        """Map with tuple keys."""
        m: Map[tuple[int, int], str] = Map()
        m.put((1, 2), "pair")
        assert m.get((1, 2)) == "pair"


class TestMapDifferentValueTypes:
    """Test Map with different value types."""

    def test_string_values(self) -> None:
        """Map with string values."""
        m: Map[str, str] = Map()
        m.put("a", "hello")
        m.put("b", "world")
        assert m.get("a") == "hello"
        assert m.get("b") == "world"

    def test_float_values(self) -> None:
        """Map with float values."""
        m: Map[str, float] = Map()
        m.put("pi", 3.14159)
        m.put("e", 2.71828)
        assert m.get("pi") == 3.14159
        assert m.get("e") == 2.71828

    def test_list_values(self) -> None:
        """Map with list values."""
        m: Map[str, list[int]] = Map()
        m.put("nums", [1, 2, 3])
        assert m.get("nums") == [1, 2, 3]

    def test_none_values(self) -> None:
        """Map can store None as value."""
        m: Map[str, int | None] = Map()
        m.put("null", None)
        assert m.get("null") is None
        assert m.contains("null") is True

    def test_nested_map_values(self) -> None:
        """Map can store other maps as values."""
        inner: Map[str, int] = Map()
        inner.put("x", 10)

        outer: Map[str, Map[str, int]] = Map()
        outer.put("inner", inner)
        assert outer.get("inner").get("x") == 10


class TestMapEdgeCases:
    """Test Map edge cases."""

    def test_empty_string_key(self) -> None:
        """Empty string as key."""
        m: Map[str, int] = Map()
        m.put("", 42)
        assert m.get("") == 42
        assert m.contains("") is True

    def test_zero_key(self) -> None:
        """Zero as key."""
        m: Map[int, str] = Map()
        m.put(0, "zero")
        assert m.get(0) == "zero"

    def test_negative_key(self) -> None:
        """Negative number as key."""
        m: Map[int, str] = Map()
        m.put(-5, "negative")
        assert m.get(-5) == "negative"

    def test_repr_empty(self) -> None:
        """String representation of empty map."""
        m: Map[str, int] = Map()
        assert repr(m) == "map(0)"

    def test_repr_with_items(self) -> None:
        """String representation of non-empty map."""
        m: Map[str, int] = Map()
        m.put("a", 1)
        m.put("b", 2)
        assert repr(m) == "map(2)"

    def test_large_map(self) -> None:
        """Map with many entries."""
        m: Map[int, int] = Map()
        for i in range(1000):
            m.put(i, i * 2)
        assert m.size() == 1000
        assert m.get(500) == 1000
        assert m.get(999) == 1998

    def test_sequential_operations(self) -> None:
        """Complex sequence of operations."""
        m: Map[str, int] = Map()
        m.put("a", 1)
        m.put("b", 2)
        m.put("c", 3)
        assert m.size() == 3

        m.remove("b")
        assert m.size() == 2

        m.put("d", 4)
        m.put("e", 5)
        assert m.size() == 4

        m.clear()
        assert m.size() == 0

        m.put("f", 6)
        assert m.size() == 1
        assert m.get("f") == 6
