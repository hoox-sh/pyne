# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Proof: literal runtime.error stays numeric; dynamic stays object."""

from __future__ import annotations

# ruff: noqa: S101, T201
import sys

from pynescript.compiler.engine import compile_script
from pynescript.runtime import Runtime

sys.path.insert(0, "tests")
import test_compiler_numba as t  # noqa: E402

UNREACHABLE = """//@version=5
indicator("err")
if close < 0
    runtime.error("unreachable")
plot(close, title="c")
"""

REACHABLE = """//@version=5
indicator("err")
if close > 0
    runtime.error("halted by design")
plot(close, title="c")
"""

NOARG = """//@version=5
indicator("err")
if close > 0
    runtime.error()
plot(close, title="c")
"""

DYNAMIC = """//@version=5
indicator("err")
msg = "value=" + str.tostring(close)
runtime.error(msg)
plot(close, title="c")
"""


def main() -> None:
    compiled = compile_script(UNREACHABLE, use_cache=False)
    assert compiled.object_mode is False
    o, h, l, c, v = t._ohlcv(10)
    out = compiled.run(o, h, l, c, v)
    assert "c" in out and len(out["c"]) == 10

    bars = t._bars_list(5)
    interp = Runtime(symbol="TEST").run(REACHABLE, bars, mode="interpret")
    comp = Runtime(symbol="TEST").run(REACHABLE, bars, mode="compile")
    assert interp.get("error_kind") == "runtime", interp
    assert comp.get("error_kind") == "runtime", comp
    assert "halted by design" in str(interp.get("error")), interp
    assert "halted by design" in str(comp.get("error")), comp
    assert compile_script(REACHABLE, use_cache=False).object_mode is False

    noarg_i = Runtime(symbol="TEST").run(NOARG, bars, mode="interpret")
    noarg_c = Runtime(symbol="TEST").run(NOARG, bars, mode="compile")
    assert noarg_i.get("error_kind") == "runtime", noarg_i
    assert noarg_c.get("error_kind") == "runtime", noarg_c
    assert str(noarg_i.get("error")).endswith("RuntimeError"), noarg_i
    assert str(noarg_c.get("error")).endswith("RuntimeError"), noarg_c
    assert "runtime.error" not in str(noarg_c.get("error")).lower(), noarg_c
    assert compile_script(NOARG, use_cache=False).object_mode is False

    assert compile_script(DYNAMIC, use_cache=False).object_mode is True

    print(
        "RUNTIME_ERROR_OK literal_numeric=1 reachable=runtime "
        "noarg=runtime dynamic=object"
    )


if __name__ == "__main__":
    main()
