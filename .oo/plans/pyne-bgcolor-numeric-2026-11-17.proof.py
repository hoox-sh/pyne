# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Proof: constant-color bgcolor stays numeric; dynamic colors stay object.

Every numeric case asserts compile-vs-interpret parity on the bgcolor series,
so "stays numeric" cannot pass by silently emitting the wrong colors.
"""

from __future__ import annotations

# ruff: noqa: S101, T201
import sys

from pynescript.compiler.engine import _transpile_once
from pynescript.compiler.engine import compile_script
from pynescript.compiler.engine import transpile
from pynescript.runtime import Runtime

sys.path.insert(0, "tests")
import test_compiler_numba as t  # noqa: E402

BARS = t._bars_list(6)

NUMERIC = {
    "ternary_hex_branch": (
        'bgcolor(close > 100.5 ? color.green : na, title="bg")',
        ["#22AB94"],
    ),
    "constant_hex": (
        'bgcolor(color.red, title="bg")',
        ["#F23645"],
    ),
    "constant_color_new": (
        'bgcolor(color.new(color.red, 90), title="bg")',
        ["rgba(242, 54, 69, 0.09803921568627451)"],
    ),
    "ternary_color_new": (
        'bgcolor(close > 100.5 ? color.new(color.orange, 70) : na, title="bg")',
        ["rgba(255, 109, 0, 0.2980392156862745)"],
    ),
    "hex_literal": (
        'bgcolor(#ff0000, title="bg")',
        ["#ff0000"],
    ),
    "barstate_isrealtime": (
        'bgcolor(barstate.isrealtime ? color.new(color.orange, 70) : na, title="bg")',
        [],
    ),
}

OBJECT = {
    "gradient": 'bgcolor(color.from_gradient(close, 100.0, 105.0, color.red, color.green), title="bg")',
    "dynamic_color_new_base": 'bgcolor(color.new(close > open ? color.red : color.green, 90), title="bg")',
    "dynamic_color_new_transp": 'bgcolor(color.new(color.red, close > open ? 90 : 50), title="bg")',
}


def main() -> None:
    for name, (body, expected_present) in NUMERIC.items():
        src = f'//@version=5\nindicator("x")\n{body}\nplot(close, "c")\n'
        code, _titles, _kinds, object_mode, _attrs = _transpile_once(src, force_object_mode=False)
        assert object_mode is False, f"{name}: must stay numeric"
        assert "@numba.njit" in code, f"{name}: must keep the njit entry point"
        assert "__drawings" not in code, f"{name}: must not emit drawing events"

        interp = Runtime(symbol="TEST").run(src, BARS, mode="interpret")
        out = Runtime(symbol="TEST").run(src, BARS, mode="compile")
        assert "error" not in interp, f"{name}: interpret error {interp.get('error')}"
        assert "error" not in out, f"{name}: compile error {out.get('error')}"
        assert list(out["series"]["bg"]) == list(interp["series"]["bg"]), f"{name}: parity mismatch"

        for color in expected_present:
            assert color in out["series"]["bg"], f"{name}: expected {color} in {out['series']['bg']}"

    # Direct constant color: every bar carries the color.
    assert compile_script(
        '//@version=5\nindicator("x")\nbgcolor(color.red, title="bg")\nplot(close, "c")\n',
        use_cache=False,
    ).object_mode is False

    for name, body in OBJECT.items():
        src = f'//@version=5\nindicator("x")\n{body}\nplot(close, "c")\n'
        assert compile_script(src, use_cache=False).object_mode is True, f"{name}: must stay object"

    print("BGCOLOR_OK numeric=6 object=3 parity=6/6")


if __name__ == "__main__":
    main()
