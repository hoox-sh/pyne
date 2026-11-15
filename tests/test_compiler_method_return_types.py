# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""UDT-returning UDF call sites must dispatch methods by the returned type."""

from __future__ import annotations

import numpy as np

from pynescript.compiler.engine import compile_script
from pynescript.compiler.engine import transpile


def _ohlcv(n: int = 8):
    close = np.arange(100.0, 100.0 + n, dtype=np.float64)
    return close, close + 1, close - 1, close, np.ones(n)


_SRC = """//@version=6
indicator("ret type")
type A
    float v
type B
    float v
method tag(B this) =>
    200.0
method tag(A this) =>
    100.0
makeB() =>
    B.new(0.0)
plot(makeB().tag(), "tag")
"""


def test_udf_return_udt_dispatches_correct_overload() -> None:
    """``makeB()`` returns B; ``tag`` must resolve B, not the last A overload."""
    code = transpile(_SRC)
    assert "tag(makeB())" in code, code
    assert "tag__1_A(makeB())" not in code, code

    compiled = compile_script(_SRC, use_cache=False)
    assert compiled.object_mode is True
    out = compiled.run(*_ohlcv())
    assert float(out["tag"][-1]) == 200.0


_MIXED_SRC = """//@version=6
indicator("mixed")
type A
    float v
type B
    float v
method tag(B this) =>
    200.0
method tag(A this) =>
    100.0
pick(float x) =>
    1.0
pick(int x) =>
    B.new(0.0)
plot(pick(1.0).tag(), "tag")
"""


def test_non_udt_overload_does_not_poison_receiver_inference() -> None:
    """``pick(float)`` returns a float; ``pick(int)`` returning B must not leak."""
    code = transpile(_MIXED_SRC)
    assert "tag__1_A(pick(1.0))" in code, code
    assert "tag(pick(1.0))" not in code, code

    compiled = compile_script(_MIXED_SRC, use_cache=False)
    out = compiled.run(*_ohlcv())
    assert float(out["tag"][-1]) == 100.0
