# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Library-path compile cache for ``compile_script`` (engine plan slice 2).

The library branch of :func:`pynescript.compiler.engine.compile_script` used to
re-transpile on every call. It now shares ``_COMPILE_CACHE`` / ``_IR_CACHE``
under a library-aware key (:func:`engine._library_cache_key`):

* key material = ``_DISK_META_VERSION`` + sha256 of the (sanitized) script
  source + ordered per-library ``(namespace, name, version, sha256(source))``;
* declared library order is significant (library identity resolves by
  namespace/name/version with first match winning, so list position is part of
  the input contract) — permuting the list is a cache miss, never a wrong hit.

Disk artifacts are intentionally not wired for this path yet.
"""

from __future__ import annotations

import numpy as np
import pytest

from pynescript.compiler import engine
from pynescript.compiler.engine import compile_script


_LIB_A = """//@version=6
library("Lib")
export add(float a, float b) =>
    a + b
"""

_LIB_A_V2 = """//@version=6
library("Lib")
export add(float a, float b) =>
    a + b + 10.0
"""

_LIB_B = """//@version=6
library("OtherLib")
export mul(float a, float b) =>
    a * b
"""

_SRC = """//@version=6
indicator("inline lib")
import ns/Lib/1 as lib
plot(lib.add(close, 1.0), "sum")
"""

_SRC_OTHER_PLOT = """//@version=6
indicator("inline lib")
import ns/Lib/1 as lib
plot(lib.add(close, 2.0), "sum")
"""

_SRC_TWO_LIBS = """//@version=6
indicator("two libs")
import ns/Lib/1 as a
import ns/OtherLib/1 as b
plot(a.add(close, 1.0) + b.mul(close, 2.0), "combo")
"""


def _libs(lib_source: str = _LIB_A, *, name: str = "Lib", version: object = 1) -> list[dict[str, object]]:
    return [{"namespace": "ns", "name": name, "version": version, "source": lib_source}]


def _two_libs() -> list[dict[str, object]]:
    return [
        {"namespace": "ns", "name": "Lib", "version": 1, "source": _LIB_A},
        {"namespace": "ns", "name": "OtherLib", "version": 1, "source": _LIB_B},
    ]


def _ohlcv(n: int = 4):
    close = 100.5 + np.arange(n, dtype=np.float64)
    open_ = close - 0.5
    high = close + 0.5
    low = close - 1.0
    volume = np.full(n, 1000.0)
    return open_, high, low, close, volume


@pytest.fixture(autouse=True)
def _clean_caches():
    engine.clear_compile_cache()
    yield
    engine.clear_compile_cache()


@pytest.fixture
def transpile_spy(monkeypatch):
    calls: list[tuple] = []
    original = engine._transpile_once

    def spy(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(engine, "_transpile_once", spy)
    return calls


def _assert_series_close(left: dict, right: dict) -> None:
    assert set(left) == set(right)
    for key, value in left.items():
        other = right[key]
        if isinstance(value, np.ndarray) or (
            isinstance(value, list) and all(isinstance(x, (int, float)) for x in value)
        ):
            np.testing.assert_allclose(np.asarray(value, dtype=np.float64), np.asarray(other, dtype=np.float64))
        else:
            assert value == other


def test_repeat_compile_transpiles_once(transpile_spy) -> None:
    first = compile_script(_SRC, libraries=_libs())
    second = compile_script(_SRC, libraries=_libs())
    assert len(transpile_spy) == 1
    assert second is first


def test_identical_libraries_hit_with_fresh_dicts(transpile_spy) -> None:
    compile_script(_SRC, libraries=_libs())
    compile_script(_SRC, libraries=_libs())  # fresh dict objects, same content
    assert len(transpile_spy) == 1


def test_version_string_matches_int(transpile_spy) -> None:
    # The compiler's own import matcher coerces with int(); the key mirrors it.
    compile_script(_SRC, libraries=_libs(version=1))
    compile_script(_SRC, libraries=_libs(version="1"))
    assert len(transpile_spy) == 1


def test_changed_library_source_retranspiles(transpile_spy) -> None:
    first = compile_script(_SRC, libraries=_libs(_LIB_A))
    second = compile_script(_SRC, libraries=_libs(_LIB_A_V2))
    assert len(transpile_spy) == 2
    assert second is not first
    o, h, lo, c, v = _ohlcv()
    out_first = first.run(o, h, lo, c, v)
    out_second = second.run(o, h, lo, c, v)
    assert not np.allclose(out_first["sum"], out_second["sum"])


def test_distinct_scripts_same_libraries_do_not_share(transpile_spy) -> None:
    first = compile_script(_SRC, libraries=_libs())
    second = compile_script(_SRC_OTHER_PLOT, libraries=_libs())
    assert len(transpile_spy) == 2
    assert first is not second
    o, h, lo, c, v = _ohlcv()
    out_first = first.run(o, h, lo, c, v)
    out_second = second.run(o, h, lo, c, v)
    np.testing.assert_allclose(out_first["sum"], c + 1.0)
    np.testing.assert_allclose(out_second["sum"], c + 2.0)


def test_cached_result_matches_fresh_compile(transpile_spy) -> None:
    cached = compile_script(_SRC, libraries=_libs())
    o, h, lo, c, v = _ohlcv()
    cached_out = cached.run(o, h, lo, c, v)
    engine.clear_compile_cache()
    fresh = compile_script(_SRC, libraries=_libs())
    fresh_out = fresh.run(o, h, lo, c, v)
    assert len(transpile_spy) == 2
    assert fresh.generated_code == cached.generated_code
    _assert_series_close(cached_out, fresh_out)


def test_permuted_library_order_misses_but_stays_correct(transpile_spy) -> None:
    forward = compile_script(_SRC_TWO_LIBS, libraries=_two_libs())
    reversed_libs = list(reversed(_two_libs()))
    swapped = compile_script(_SRC_TWO_LIBS, libraries=reversed_libs)
    # Declared order is part of the key: permuted order must miss, never hit.
    assert len(transpile_spy) == 2
    o, h, lo, c, v = _ohlcv()
    out_forward = forward.run(o, h, lo, c, v)
    out_swapped = swapped.run(o, h, lo, c, v)
    _assert_series_close(out_forward, out_swapped)
    np.testing.assert_allclose(out_forward["combo"], (c + 1.0) + c * 2.0)


def test_clear_compile_cache_drops_library_entries(transpile_spy) -> None:
    compile_script(_SRC, libraries=_libs())
    engine.clear_compile_cache()
    compile_script(_SRC, libraries=_libs())
    assert len(transpile_spy) == 2


def test_disk_meta_version_bump_invalidates_library_cache(transpile_spy, monkeypatch) -> None:
    compile_script(_SRC, libraries=_libs())
    monkeypatch.setattr(engine, "_DISK_META_VERSION", engine._DISK_META_VERSION + 1)
    compile_script(_SRC, libraries=_libs())
    assert len(transpile_spy) == 2


def test_use_cache_false_bypasses_library_cache(transpile_spy) -> None:
    compile_script(_SRC, libraries=_libs(), use_cache=False)
    compile_script(_SRC, libraries=_libs(), use_cache=False)
    assert len(transpile_spy) == 2
