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

"""Warm-path library compile key: digest memo hit vs miss.

``compile_script(..., libraries=)`` already returns a cached ``CompiledScript``
on the second call. Building that key used to re-hash the script and library
sources and rebuild a JSON blob on every hit. The digest is now memoized by
the canonical inputs (value equality, not object identity).
"""

from __future__ import annotations

import hashlib
import json

import numpy as np

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

_SRC_OTHER = """//@version=6
indicator("inline lib")
import ns/Lib/1 as lib
plot(lib.add(close, 2.0), "sum")
"""


def _libs(lib_source: str = _LIB_A, *, name: str = "Lib", version: object = 1) -> list[dict[str, object]]:
    return [{"namespace": "ns", "name": name, "version": version, "source": lib_source}]


def _manual_digest(source: str, libraries: list[dict[str, object]]) -> str:
    """Independent copy of the pre-memo key algorithm (sha256 of canonical JSON)."""
    libs: list[dict[str, object]] = []
    for item in libraries:
        if not isinstance(item, dict):
            digest = hashlib.sha256(repr(item).encode("utf-8")).hexdigest()
            libs.append({"n": "", "m": "", "v": 1, "s": digest})
            continue
        raw_version = item.get("version")
        version_in: object = raw_version if raw_version else 1
        try:
            version: object = int(version_in)  # type: ignore[arg-type]
        except Exception:
            version = str(version_in)
        lib_source = str(item.get("source") or "")
        libs.append(
            {
                "n": str(item.get("namespace") or ""),
                "m": str(item.get("name") or ""),
                "v": version,
                "s": hashlib.sha256(lib_source.encode("utf-8")).hexdigest(),
            }
        )
    blob = json.dumps(
        {
            "v": engine._DISK_META_VERSION,
            "src": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            "libs": libs,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def setup_function() -> None:
    engine.clear_compile_cache()


def teardown_function() -> None:
    engine.clear_compile_cache()


def _spy_transpile(monkeypatch):
    calls: list[tuple] = []
    real = engine._transpile_once

    def spy(*args, **kwargs):
        calls.append((args, kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr(engine, "_transpile_once", spy)
    return calls


def test_digest_matches_canonical_json_and_reuses_memo() -> None:
    libs = _libs()
    first = engine._library_cache_key(_SRC, libs)
    assert first == _manual_digest(_SRC, libs)
    assert len(first) == 64
    info_mid = engine._library_cache_key_digest.cache_info()
    second = engine._library_cache_key(_SRC, _libs())
    info = engine._library_cache_key_digest.cache_info()
    assert second == first
    assert info.hits == info_mid.hits + 1
    assert info.misses == info_mid.misses


def test_fresh_string_objects_hit_digest_memo() -> None:
    engine._library_cache_key(_SRC, _libs())
    src2 = _SRC.encode("utf-8").decode("utf-8")
    lib2 = _LIB_A.encode("utf-8").decode("utf-8")
    assert src2 is not _SRC
    assert lib2 is not _LIB_A
    before = engine._library_cache_key_digest.cache_info()
    again = engine._library_cache_key(src2, [{"namespace": "ns", "name": "Lib", "version": 1, "source": lib2}])
    after = engine._library_cache_key_digest.cache_info()
    assert again == engine._library_cache_key(_SRC, _libs())
    assert after.hits >= before.hits + 1
    assert after.misses == before.misses


def test_changed_inputs_miss_digest_memo() -> None:
    base = engine._library_cache_key(_SRC, _libs())
    assert engine._library_cache_key(_SRC, _libs(_LIB_A_V2)) != base
    assert engine._library_cache_key(_SRC_OTHER, _libs()) != base
    assert engine._library_cache_key(_SRC, _libs(version=2)) != base
    assert engine._library_cache_key(_SRC, _libs(name="Other")) != base
    # int and numeric string coerce to the same version, so this is a hit.
    assert engine._library_cache_key(_SRC, _libs(version="1")) == base
    # Ignored extra keys are not part of the digest.
    extra = [{"namespace": "ns", "name": "Lib", "version": 1, "source": _LIB_A, "note": "ignored"}]
    assert engine._library_cache_key(_SRC, extra) == base
    forward = engine._library_cache_key(
        _SRC,
        [
            {"namespace": "ns", "name": "Lib", "version": 1, "source": _LIB_A},
            {"namespace": "ns", "name": "OtherLib", "version": 1, "source": _LIB_B},
        ],
    )
    backward = engine._library_cache_key(
        _SRC,
        [
            {"namespace": "ns", "name": "OtherLib", "version": 1, "source": _LIB_B},
            {"namespace": "ns", "name": "Lib", "version": 1, "source": _LIB_A},
        ],
    )
    assert forward != backward


def test_in_place_library_mutation_misses_digest() -> None:
    libs = _libs()
    before = engine._library_cache_key(_SRC, libs)
    libs[0]["source"] = _LIB_A_V2
    after = engine._library_cache_key(_SRC, libs)
    assert after != before
    libs[0]["source"] = _LIB_A
    libs[0]["version"] = 9
    assert engine._library_cache_key(_SRC, libs) != before


def test_clear_compile_cache_drops_digest_memo() -> None:
    engine._library_cache_key(_SRC, _libs())
    assert engine._library_cache_key_digest.cache_info().currsize >= 1
    engine.clear_compile_cache()
    info = engine._library_cache_key_digest.cache_info()
    assert info.currsize == 0
    assert info.hits == 0
    assert info.misses == 0


def test_version_bump_misses_digest(monkeypatch) -> None:
    first = engine._library_cache_key(_SRC, _libs())
    monkeypatch.setattr(engine, "_DISK_META_VERSION", engine._DISK_META_VERSION + 1)
    second = engine._library_cache_key(_SRC, _libs())
    assert second != first
    assert second == _manual_digest(_SRC, _libs())


def test_warm_library_compile_hits_then_source_change_misses(monkeypatch) -> None:
    calls = _spy_transpile(monkeypatch)
    first = compile_script(_SRC, libraries=_libs())
    second = compile_script(_SRC, libraries=_libs())
    assert len(calls) == 1
    assert second is first
    changed = compile_script(_SRC, libraries=_libs(_LIB_A_V2))
    assert len(calls) == 2
    assert changed is not first
    o = np.arange(4, dtype=np.float64)
    out_hit = first.run(o, o, o, o, o)
    out_miss = changed.run(o, o, o, o, o)
    np.testing.assert_allclose(out_hit["sum"], o + 1.0)
    np.testing.assert_allclose(out_miss["sum"], o + 11.0)


def test_in_place_mutation_recompiles(monkeypatch) -> None:
    calls = _spy_transpile(monkeypatch)
    libs = _libs()
    first = compile_script(_SRC, libraries=libs)
    libs[0]["source"] = _LIB_A_V2
    second = compile_script(_SRC, libraries=libs)
    assert len(calls) == 2
    assert second is not first
    o = np.array([1.0, 2.0], dtype=np.float64)
    np.testing.assert_allclose(first.run(o, o, o, o, o)["sum"], o + 1.0)
    np.testing.assert_allclose(second.run(o, o, o, o, o)["sum"], o + 11.0)
