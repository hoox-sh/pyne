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

"""Round 8 Agent 04 — compile engine packing / normalize / cache recovery goldens.

Imports only ``pynescript.compiler.engine`` (+ numpy). Does not touch visitor or
numba kernel modules under test ownership of other agents.
"""

from __future__ import annotations

import pickle

import numpy as np

from pynescript.compiler.engine import CompiledScript
from pynescript.compiler.engine import _call_execute_with_recovery
from pynescript.compiler.engine import _coerce_plot_array
from pynescript.compiler.engine import _is_legacy_execute_arity_error
from pynescript.compiler.engine import _is_numba_cache_corruption
from pynescript.compiler.engine import _is_plot_sequence
from pynescript.compiler.engine import _normalize_result
from pynescript.compiler.engine import _pack_plot_sequence
from pynescript.compiler.engine import _uniquify_series_key
from pynescript.compiler.engine import _uniquify_title_list
from pynescript.compiler.engine import clear_compile_cache
from pynescript.compiler.engine import compile_script


def _ohlcv(n: int = 16) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    c = np.arange(n, dtype=np.float64) + 1.0
    o = c - 0.25
    h = c + 0.5
    l = c - 0.5
    v = np.ones(n, dtype=np.float64)
    return o, h, l, c, v


class TestUniquifyAndPack:
    def test_uniquify_series_key_suffixes(self) -> None:
        used: set[str] = set()
        assert _uniquify_series_key("x", used) == "x"
        assert _uniquify_series_key("x", used) == "x_2"
        assert _uniquify_series_key("x", used) == "x_3"
        assert _uniquify_series_key("y", used) == "y"
        assert used == {"x", "x_2", "x_3", "y"}

    def test_uniquify_title_list_stable(self) -> None:
        assert _uniquify_title_list(["a", "a", "b", "a"]) == ["a", "a_2", "b", "a_3"]
        assert _uniquify_title_list(["", "plot_0"]) == ["plot_0", "plot_0_2"]

    def test_pack_duplicate_titles_keeps_all_series(self) -> None:
        raw = (np.full(3, 1.0), np.full(3, 2.0), np.full(3, 3.0))
        out = _pack_plot_sequence(raw, ["x", "x", "y"])
        assert set(out) == {"x", "x_2", "y"}
        assert np.allclose(out["x"], 1.0)
        assert np.allclose(out["x_2"], 2.0)
        assert np.allclose(out["y"], 3.0)

    def test_pack_extra_series_beyond_titles_not_dropped(self) -> None:
        raw = (np.ones(2), np.full(2, 9.0), np.full(2, 7.0))
        out = _pack_plot_sequence(raw, ["only"])
        assert set(out) == {"only", "plot_1", "plot_2"}
        assert np.allclose(out["plot_1"], 9.0)

    def test_pack_empty_title_falls_back_to_plot_i(self) -> None:
        raw = (np.ones(2), np.full(2, 2.0))
        out = _pack_plot_sequence(raw, ["", None])  # type: ignore[list-item]
        assert "plot_0" in out
        assert "plot_1" in out

    def test_compiled_script_pack_result_uniquifies(self) -> None:
        cs = CompiledScript(
            source="",
            generated_code="",
            execute=lambda *a: None,
            plot_titles=["x", "x"],
        )
        raw = (np.ones(2), np.full(2, 5.0))
        out = cs._pack_result(raw)
        assert list(out.keys()) == ["x", "x_2"]
        assert np.allclose(out["x_2"], 5.0)

    def test_pack_list_of_arrays_same_as_tuple(self) -> None:
        """List returns must not collapse into a single 2d ``plot`` key."""
        raw_list = [np.ones(3), np.full(3, 2.0)]
        assert _is_plot_sequence(raw_list)
        out = CompiledScript(
            source="",
            generated_code="",
            execute=lambda *a: None,
            plot_titles=["a", "b"],
        )._pack_result(raw_list)
        assert set(out) == {"a", "b"}
        assert out["a"].ndim == 1


class TestNormalizeAndCoerce:
    def test_normalize_none_and_empty(self) -> None:
        assert _normalize_result(None) == {}
        assert _normalize_result(()) == {}
        assert _normalize_result([]) == {}

    def test_normalize_drawings_events_none_to_list(self) -> None:
        out = _normalize_result(
            {
                "plot_0": np.array([1.0, np.nan]),
                "__drawings": None,
                "__events": None,
                "__position_size": 1.5,
                "__equity": np.array([1.0, 2.0]),
            }
        )
        assert out["__drawings"] == []
        assert out["__events"] == []
        assert out["__position_size"] == 1.5
        assert isinstance(out["__equity"], np.ndarray)
        assert out["plot_0"].dtype == np.float64

    def test_coerce_none_cells_to_nan(self) -> None:
        arr = _coerce_plot_array([1.0, None, 3.0])
        assert arr.dtype == np.float64
        assert arr[0] == 1.0
        assert np.isnan(arr[1])
        assert arr[2] == 3.0

    def test_coerce_does_not_zero_fill_object_strings(self) -> None:
        obj = np.array(["#fff", None], dtype=object)
        # May stay object if cast fails mid-path; must not become zeros
        out = _coerce_plot_array(obj)
        if isinstance(out, np.ndarray) and out.dtype == object:
            assert out[0] == "#fff"
        # float cast of pure-None object works → nan, never 0
        nones = _coerce_plot_array(np.array([None, None], dtype=object))
        assert np.all(np.isnan(nones))

    def test_normalize_bare_tuple_index_keys(self) -> None:
        out = _normalize_result((np.ones(2), np.full(2, 2.0)))
        assert set(out) == {"plot_0", "plot_1"}


class TestEndToEndDuplicateTitles:
    def test_compile_run_duplicate_plot_titles(self) -> None:
        """Interpret-style key set: x, x_2, y — engine must not drop the first x."""
        clear_compile_cache()
        src = """//@version=5
indicator("dup")
plot(close, title="x")
plot(open, title="x")
plot(high, title="y")
"""
        compiled = compile_script(src, use_cache=False)
        # Transpile-time titles already uniquified on CompiledScript
        assert compiled.plot_titles == ["x", "x_2", "y"]
        o, h, l, c, v = _ohlcv(8)
        out = compiled.run(o, h, l, c, v)
        assert set(out.keys()) == {"x", "x_2", "y"}
        # close series vs open series
        assert np.allclose(out["x"], c)
        assert np.allclose(out["x_2"], o)
        assert np.allclose(out["y"], h)

    def test_object_mode_drawings_envelope_intact(self) -> None:
        clear_compile_cache()
        src = """//@version=5
indicator("hl")
h = hline(50, title="mid")
plot(close, title="c")
"""
        compiled = compile_script(src, use_cache=False)
        assert compiled.object_mode is True
        o, h, l, c, v = _ohlcv(10)
        out = compiled.run(o, h, l, c, v)
        assert "c" in out
        assert "__drawings" in out
        assert isinstance(out["__drawings"], list)
        assert any(
            isinstance(d, dict) and d.get("kind") == "hline" for d in out["__drawings"]
        )


class TestLegacyArityAndCache:
    def test_legacy_arity_error_detector(self) -> None:
        assert _is_legacy_execute_arity_error(
            TypeError("old_exec() takes 5 positional arguments but 6 were given")
        )
        assert not _is_legacy_execute_arity_error(TypeError("something else"))
        assert not _is_legacy_execute_arity_error(ValueError("nope"))

    def test_call_execute_retries_without_time(self) -> None:
        seen: list[int] = []

        def five_arg(o, h, l, c, v):  # noqa: ANN001
            seen.append(len((o, h, l, c, v)))
            return (c,)

        o, h, l, c, v = _ohlcv(4)
        t = np.arange(4, dtype=np.float64) * 60000.0
        raw = _call_execute_with_recovery(five_arg, o, h, l, c, v, t)
        assert seen == [5]
        assert isinstance(raw, tuple)

    def test_compiled_run_legacy_five_arg_execute(self) -> None:
        def five_arg(o, h, l, c, v):  # noqa: ANN001
            return (c, o)

        cs = CompiledScript(
            source="",
            generated_code="",
            execute=five_arg,
            plot_titles=["close", "open"],
        )
        o, h, l, c, v = _ohlcv(5)
        out = cs.run(o, h, l, c, v)
        assert np.allclose(out["close"], c)
        assert np.allclose(out["open"], o)

    def test_numba_cache_corruption_helpers(self) -> None:
        assert _is_numba_cache_corruption(EOFError("Ran out of input"))
        assert _is_numba_cache_corruption(pickle.UnpicklingError("pickle data was truncated"))
        assert not _is_numba_cache_corruption(RuntimeError("unrelated"))


class TestTranspileTitlesMatchRun:
    def test_plot_titles_match_run_keys_after_uniquify(self) -> None:
        clear_compile_cache()
        src = """//@version=5
indicator("t")
plot(close, title="same")
plot(open, title="same")
"""
        compiled = compile_script(src, use_cache=False)
        o, h, l, c, v = _ohlcv(6)
        keys = set(compiled.run(o, h, l, c, v).keys())
        assert set(compiled.plot_titles) == keys
        assert keys == {"same", "same_2"}
