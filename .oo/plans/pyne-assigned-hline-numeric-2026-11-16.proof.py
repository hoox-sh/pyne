# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Proof: dead assigned hline stays numeric; handle use stays object."""

from __future__ import annotations

# ruff: noqa: S101, T201
import sys

from pynescript.compiler.engine import compile_script
from pynescript.compiler.engine import transpile
from pynescript.runtime import Runtime

sys.path.insert(0, "tests")
import test_compiler_numba as t  # noqa: E402

DEAD = """//@version=5
indicator("x")
h = hline(50, "mid", color=color.red, linestyle=hline.style_dashed)
plot(close, "c")
"""

TWO = """//@version=5
indicator("x")
h1 = hline(50, "a")
h2 = hline(60, "b")
plot(close, "c")
"""

DELETE = """//@version=5
indicator("x")
h = hline(50)
hline.delete(h)
plot(close, "c")
"""

FILL = """//@version=5
indicator("x")
h = hline(50)
fill(h, h, color=color.red)
plot(close, "c")
"""


def main() -> None:
    compiled = compile_script(DEAD, use_cache=False)
    assert compiled.object_mode is False
    code = transpile(DEAD)
    assert "@numba.njit" in code and "__drawings" not in code
    assert compiled.plot_attrs[0]["linestyle"] == "style_dashed"
    bars = t._bars_list(6)
    interp = Runtime(symbol="TEST").run(DEAD, bars, mode="interpret")
    out = Runtime(symbol="TEST").run(DEAD, bars, mode="compile")
    assert "error" not in interp, interp.get("error")
    assert "error" not in out, out.get("error")
    for key in ("mid", "c"):
        assert list(out["series"][key]) == list(interp["series"][key]), key
    assert all(float(x) == 50.0 for x in out["series"]["mid"])

    two = compile_script(TWO, use_cache=False)
    assert two.object_mode is False
    two_out = Runtime(symbol="TEST").run(TWO, bars, mode="compile")
    assert "error" not in two_out, two_out.get("error")
    assert all(float(x) == 50.0 for x in two_out["series"]["a"])
    assert all(float(x) == 60.0 for x in two_out["series"]["b"])

    assert compile_script(DELETE, use_cache=False).object_mode is True
    assert compile_script(FILL, use_cache=False).object_mode is True

    print("ASSIGNED_HLINE_OK dead=1 two=1 handle_use=object")


if __name__ == "__main__":
    main()
