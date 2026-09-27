# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later

"""User methods that wrap drawing builtins must not call themselves."""

from __future__ import annotations

import re

import numpy as np

from pynescript.compiler.engine import compile_script
from pynescript.compiler.engine import transpile


def _ohlcv(n: int = 4):
    close = np.arange(100.0, 100.0 + n, dtype=np.float64)
    return close, close + 1, close - 1, close, np.ones(n)


def test_array_field_push_is_not_the_user_method() -> None:
    src = """//@version=5
indicator("t", overlay=true)
type boxish
    array<label> labels
method push(label lb, boxish host) =>
    host.labels.push(lb)
    host
var b = boxish.new()
var lb = label.new(bar_index, close, "x")
b.push(lb)
plot(close)
"""
    code = transpile(src)
    body = re.search(r"def push\(.*?\n(.*?)(?=\ndef )", code, re.S)
    assert body is not None
    assert re.search(r"(?<![\w.])push\(", body.group(1)) is None
    assert "safe_list_append" in body.group(1)
    compile_script(src, use_cache=False).run(*_ohlcv())


def test_font_family_constants_are_strings() -> None:
    src = """//@version=5
indicator("t")
plot(close)
l = label.new(bar_index, close, "x", text_font_family=font.family_monospace)
"""
    code = transpile(src)
    assert "udt_get_field(font" not in code
    assert "'family_monospace'" in code
    compile_script(src, use_cache=False).run(*_ohlcv())


def test_label_set_xy_wrapper_calls_builtin() -> None:
    src = """//@version=5
indicator("t", overlay=true)
method set_xy(label id, int x, float y) =>
    id.set_xy(x, y)
    id
var lb = label.new(bar_index, close, "x")
lb.set_xy(bar_index, close)
plot(close)
"""
    code = transpile(src)
    body = re.search(r"def set_xy\(.*?\n(.*?)(?=\ndef )", code, re.S)
    assert body is not None
    assert "set_xy(" not in body.group(1)
    assert "label_set_xy" in body.group(1) or "'method': 'label_set_xy'" in body.group(1)
    out = compile_script(src, use_cache=False).run(*_ohlcv())
    drawings = out.get("__drawings") or []
    assert any(isinstance(d, dict) and d.get("method") == "label_set_xy" for d in drawings)


def test_line_and_label_set_color_overloads_do_not_recurse() -> None:
    src = """//@version=5
indicator("t", overlay=true)
method set_color(label id, color c) =>
    id.set_color(c)
    id
method set_color(line id, color c) =>
    id.set_color(c)
    id
var lb = label.new(bar_index, close, "x")
var ln = line.new(bar_index, close, bar_index + 1, close)
lb.set_color(color.red)
ln.set_color(color.green)
plot(close)
"""
    code = transpile(src)
    assert "'method': 'label_set_color'" in code
    assert "'method': 'line_set_color'" in code
    out = compile_script(src, use_cache=False).run(*_ohlcv())
    assert "plot_0" in out
