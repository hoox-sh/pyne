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

"""Engine helper / recovery / packing edges not covered by emit Runtime scripts."""

from __future__ import annotations

import os
import pickle
import tempfile

from pathlib import Path

import numpy as np
import pytest

from pynescript.compiler.engine import CompiledScript
from pynescript.compiler.engine import _coerce_plot_array
from pynescript.compiler.engine import _env_truthy
from pynescript.compiler.engine import _format_fallback_reason
from pynescript.compiler.engine import _is_legacy_execute_arity_error
from pynescript.compiler.engine import _is_numba_cache_corruption
from pynescript.compiler.engine import _is_numba_nopython_failure
from pynescript.compiler.engine import _is_plot_sequence
from pynescript.compiler.engine import _normalize_result
from pynescript.compiler.engine import _pack_plot_sequence
from pynescript.compiler.engine import _sha256_text
from pynescript.compiler.engine import _uniquify_series_key
from pynescript.compiler.engine import _uniquify_title_list
from pynescript.compiler.engine import clear_compile_cache
from pynescript.compiler.engine import clear_disk_compile_cache
from pynescript.compiler.engine import compile_cache_stats
from pynescript.compiler.engine import compile_script
from pynescript.runtime import Runtime


def _bars(n: int = 20) -> list[dict[str, float | int]]:
    return [
        {
            "time": 1_700_000_000_000 + i * 60_000,
            "open": 100.0 + i * 0.1,
            "high": 101.0 + i * 0.1,
            "low": 99.0 + i * 0.1,
            "close": 100.5 + i * 0.1,
            "volume": 10.0 + i,
        }
        for i in range(n)
    ]


def _ohlcv(n: int = 16):
    c = np.arange(n, dtype=np.float64) + 1.0
    return c - 0.25, c + 0.5, c - 0.5, c, np.ones(n, dtype=np.float64)


class TestNumbaCacheAndArityHelpers:
    def test_is_numba_cache_corruption_variants(self) -> None:
        assert _is_numba_cache_corruption(EOFError())
        assert _is_numba_cache_corruption(pickle.UnpicklingError("bad"))
        assert _is_numba_cache_corruption(RuntimeError("Ran out of input"))
        assert _is_numba_cache_corruption(RuntimeError("pickle data was truncated"))
        assert _is_numba_cache_corruption(RuntimeError("UnpicklingError: pickle broken"))

        class UnpicklingError(Exception):
            pass

        assert _is_numba_cache_corruption(UnpicklingError("x"))
        assert not _is_numba_cache_corruption(ValueError("unrelated"))

    def test_legacy_execute_arity_messages(self) -> None:
        assert _is_legacy_execute_arity_error(
            TypeError("execute_script_compiled() takes 5 positional arguments but 6 were given")
        )
        assert _is_legacy_execute_arity_error(TypeError("takes 5 positional arguments but 6 were given"))
        assert _is_legacy_execute_arity_error(TypeError("expected 5 arguments, got 6"))
        assert not _is_legacy_execute_arity_error(TypeError("takes 3 positional arguments but 4 were given"))
        assert not _is_legacy_execute_arity_error(ValueError("takes 5"))

    def test_is_numba_nopython_failure_markers(self) -> None:
        assert _is_numba_nopython_failure(TypeError("Failed in nopython mode"))
        assert _is_numba_nopython_failure(RuntimeError("cannot determine Numba type of …"))
        assert _is_numba_nopython_failure(RuntimeError("No implementation of function Foo"))
        assert not _is_numba_nopython_failure(ValueError("plain"))

    def test_format_fallback_reason_truncates(self) -> None:
        short = _format_fallback_reason(RuntimeError("boom"))
        assert "boom" in short
        long = _format_fallback_reason(RuntimeError("x" * 400))
        assert len(long) < 400
        assert long.endswith("...")


class TestPlotPackNormalizeCoerce:
    def test_is_plot_sequence_shapes(self) -> None:
        assert _is_plot_sequence(())
        assert _is_plot_sequence([])
        assert _is_plot_sequence((np.ones(2), np.ones(2)))
        assert _is_plot_sequence([np.ones(2), np.ones(2)])
        assert _is_plot_sequence([[1, 2], [3, 4]])
        assert not _is_plot_sequence([1, 2, 3])
        assert not _is_plot_sequence({"a": 1})
        assert not _is_plot_sequence(np.ones(3))

    def test_pack_and_uniquify(self) -> None:
        used: set[str] = set()
        assert _uniquify_series_key("a", used) == "a"
        assert _uniquify_series_key("a", used) == "a_2"
        assert _uniquify_title_list(["x", "x", ""]) == ["x", "x_2", "plot_2"]
        packed = _pack_plot_sequence((np.ones(2), np.full(2, 2.0), np.full(2, 3.0)), ["a", "a"])
        assert set(packed) == {"a", "a_2", "plot_2"}

    def test_coerce_none_and_object_cells(self) -> None:
        arr = _coerce_plot_array([1.0, None, 3.0])
        assert arr.dtype == np.float64
        assert np.isnan(arr[1])
        empty = _coerce_plot_array(None)
        assert isinstance(empty, np.ndarray)
        assert empty.size == 0
        obj = _coerce_plot_array(np.array(["#fff", None], dtype=object))
        assert isinstance(obj, np.ndarray)

    def test_normalize_scalar_and_drawings(self) -> None:
        out = _normalize_result(np.array([1.0, 2.0]))
        assert "plot" in out
        mapped = _normalize_result(
            {
                "a": [1.0, None, 3.0],
                "__drawings": None,
                "__events": None,
            }
        )
        assert mapped["__drawings"] == []
        assert mapped["__events"] == []
        assert np.isnan(mapped["a"][1])


class TestEnvDiskCacheAndCompile:
    def test_env_truthy_defaults(self) -> None:
        key = "PYNESCRIPT_TEST_ENV_TRUTHY_TMP"
        try:
            os.environ.pop(key, None)
            assert _env_truthy(key, default="1") is True
            assert _env_truthy(key, default="0") is False
            os.environ[key] = "false"
            assert _env_truthy(key) is False
            os.environ[key] = "yes"
            assert _env_truthy(key) is True
        finally:
            os.environ.pop(key, None)

    def test_clear_disk_compile_cache_removes_files(self) -> None:
        old = os.environ.get("PYNE_COMPILE_CACHE_DIR")
        td = tempfile.mkdtemp()
        try:
            os.environ["PYNE_COMPILE_CACHE_DIR"] = td
            Path(td, "x.py").write_text("a=1\n", encoding="utf-8")
            Path(td, "y.json").write_text("{}", encoding="utf-8")
            pyc = Path(td) / "__pycache__"
            pyc.mkdir(exist_ok=True)
            (pyc / "z.pyc").write_bytes(b"abc")
            clear_disk_compile_cache()
            remaining = [p.name for p in Path(td).iterdir()]
            assert "x.py" not in remaining
            assert "y.json" not in remaining
        finally:
            if old is None:
                os.environ.pop("PYNE_COMPILE_CACHE_DIR", None)
            else:
                os.environ["PYNE_COMPILE_CACHE_DIR"] = old

    def test_compile_cache_stats_and_sha(self) -> None:
        stats = compile_cache_stats()
        assert "source_entries" in stats
        assert isinstance(_sha256_text("hello"), str)
        assert len(_sha256_text("hello")) == 64

    def test_compiled_script_run_volume_default_and_mismatch(self) -> None:
        src = """//@version=6
indicator("e")
plot(close, "c")
"""
        clear_compile_cache()
        cs = compile_script(src, use_cache=False)
        o, h, l, c, _v = _ohlcv(10)
        out = cs.run(o, h, l, c, None)
        assert "c" in out
        with pytest.raises(ValueError, match="same length"):
            cs.run(o, h, l, c[:5], _v[:5])

    def test_compiled_script_time_length_mismatch(self) -> None:
        src = """//@version=6
indicator("t")
plot(close, "c")
"""
        cs = compile_script(src, use_cache=False)
        o, h, l, c, v = _ohlcv(8)
        t = np.arange(3, dtype=np.int64)
        with pytest.raises(ValueError, match="time array"):
            cs.run(o, h, l, c, v, time=t)

    def test_runtime_compile_then_auto_reuse(self) -> None:
        src = """//@version=6
indicator("r")
plot(ta.sma(close, 3), "s")
"""
        bars = _bars(24)
        a = Runtime(symbol="E").run(src, bars, mode="compile")
        b = Runtime(symbol="E").run(src, bars, mode="auto")
        assert "error" not in a, a.get("error")
        assert "error" not in b, b.get("error")
        assert "s" in (a.get("series") or {})
        assert "s" in (b.get("series") or {})

    def test_pack_result_uniquifies_on_compiled_script(self) -> None:
        cs = CompiledScript(
            source="",
            generated_code="",
            execute=lambda *a, **k: None,
            plot_titles=["dup", "dup"],
        )
        raw = (np.ones(3), np.full(3, 2.0))
        out = cs._pack_result(raw)
        assert list(out.keys()) == ["dup", "dup_2"]
