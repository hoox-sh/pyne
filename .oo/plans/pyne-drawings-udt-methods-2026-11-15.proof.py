# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Assertion proof for UDT-returning UDF method dispatch."""

# ruff: noqa: S101, T201

from __future__ import annotations

import numpy as np

from pynescript.compiler.engine import compile_script
from pynescript.compiler.engine import transpile


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


def main() -> None:
    code = transpile(_SRC)
    assert "tag(makeB())" in code, code
    assert "tag__1_A(makeB())" not in code, code

    compiled = compile_script(_SRC, use_cache=False)
    assert compiled.object_mode is True
    n = 8
    close = np.arange(100.0, 100.0 + n, dtype=np.float64)
    out = compiled.run(close, close + 1, close - 1, close, np.ones(n))
    value = float(out["tag"][-1])
    assert value == 200.0, value

    mixed_code = transpile(_MIXED_SRC)
    assert "tag__1_A(pick(1.0))" in mixed_code, mixed_code
    assert "tag(pick(1.0))" not in mixed_code, mixed_code
    mixed = compile_script(_MIXED_SRC, use_cache=False)
    mixed_out = mixed.run(close, close + 1, close - 1, close, np.ones(n))
    mixed_value = float(mixed_out["tag"][-1])
    assert mixed_value == 100.0, mixed_value

    print("UDT_RETURN_DISPATCH_OK tag=200.0 wrong=0 mixed=100.0")


if __name__ == "__main__":
    main()
