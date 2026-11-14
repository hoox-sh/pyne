# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Assertion proof for the PYNE literal-color numeric-mode slice.

Run from the pynescript repo root:

    PYTHONPATH=src .venv/bin/python \
        .openorchestrate/plans/pyne-numeric-coverage-2026-11-14.proof.py

The final COLOR_FOLD_PROOF_OK line is what `oo proof attach --expect` matches.
"""

# ruff: noqa: S101, T201

from __future__ import annotations

import re

from pathlib import Path

import numpy as np

from pynescript.compiler.engine import _transpile_once
from pynescript.compiler.engine import compile_script
from pynescript.runtime import Runtime
from pynescript.util.corpus_runtime import _make_bars


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "tests" / "data"

# Strict target set: color.new present, no other obvious object-only construct.
PATS = {
    "color_new": re.compile(r"\bcolor\s*\.\s*new\s*\("),
    "input_type": re.compile(r"type\s*=\s*input\s*\."),
    "hard": re.compile(
        r"\b(plotshape|plotchar|bgcolor|barcolor|alertcondition|input\s*\.\s*string|"
        r"str\s*\.\s*tostring|array\s*\.|map\s*\.|matrix\s*\.|label\s*\.|line\s*\.|"
        r"box\s*\.|table\s*\.|strategy\s*\(|library\s*\()"
    ),
    "hline": re.compile(r"=\s*hline\s*\("),
    "cseries": re.compile(r"\?\s*color\s*\.|color\s*\.\w+\s*:\s*color\s*\."),
    "request": re.compile(r"\brequest\s*\."),
    "import": re.compile(r"(?m)^\s*import\s+\S+"),
    "udt": re.compile(r"(?m)^\s*type\s+\w+"),
}

EXPECTED_NUMERIC = {
    "set01/indicators/205_ind_supertrend_from_scratch.pine",
    "set03/indicators/0449_ind_ttm_wave_ttm_wave.pine",
    "set04/indicators/0740_ind_plot_fill_demo.pine",
    "set04/indicators/0258_ind_accumulation_swing_index_asi_2.pine",
    "set04/indicators/0699_ind_example_2.pine",
    "set04/indicators/0909_ind_plot_2.pine",
    "set04/indicators/0257_ind_accumulation_swing_index_asi.pine",
}

# Numeric compile must preserve the same hline visual metadata object compile
# carries in __drawings. Interpret normalizes style_* to dotted/dashed; compile
# object/numeric keep style_dotted/style_dashed (pre-existing difference).
EXPECTED_HLINE = {
    "set03/indicators/0449_ind_ttm_wave_ttm_wave.pine": ("Zero", "#787B86", "style_dotted"),
    "set04/indicators/0258_ind_accumulation_swing_index_asi_2.pine": (
        "Zero Line",
        "rgba(120, 123, 134, 0.4)",
        "style_dashed",
    ),
    "set04/indicators/0257_ind_accumulation_swing_index_asi.pine": (
        "Zero Line",
        "rgba(120, 123, 134, 0.4)",
        "style_dashed",
    ),
}


def _candidates() -> list[str]:
    out: list[str] = []
    for set_name in ("set01", "set02", "set03", "set04"):
        for path in (DATA / set_name).rglob("*.pine"):
            src = path.read_text(errors="ignore")
            flags = {k: bool(rx.search(src)) for k, rx in PATS.items()}
            other = any(flags[k] for k in ("hard", "hline", "cseries", "request", "import", "udt"))
            if flags["color_new"] and not other and not flags["input_type"]:
                out.append(str(path.relative_to(DATA)))
    return out


def _ohlcv(n: int = 40, start: float = 100.0):
    close = np.arange(start, start + n, dtype=np.float64)
    return close, close + 1, close - 1, close, np.ones(n)


def main() -> None:
    numeric: list[str] = []
    object_mode: list[str] = []
    errors: list[str] = []
    for rel in _candidates():
        try:
            _code, _titles, _kinds, om, _attrs = _transpile_once((DATA / rel).read_text(errors="ignore"))
            (object_mode if om else numeric).append(rel)
        except Exception as exc:
            errors.append(f"{rel}: {type(exc).__name__}")

    assert set(numeric) == EXPECTED_NUMERIC, (sorted(numeric), sorted(EXPECTED_NUMERIC))
    assert len(object_mode) == 68, len(object_mode)
    assert len(errors) == 2, errors

    # Literal plot color: numeric emit, no runtime color helper.
    src_plot = '//@version=6\nindicator("x")\nplot(close, title="p", color=color.new(color.red, 50))\n'
    code, _t, _k, om, _a = _transpile_once(src_plot)
    assert om is False
    assert "pine_color_new(" not in code
    compiled = compile_script(src_plot, use_cache=False)
    assert compiled.object_mode is False
    o, h, l, c, v = _ohlcv()
    out = compiled.run(o, h, l, c, v)
    assert np.allclose(out["p"], c)

    # Literal fill color: numeric emit + folded rgba metadata.
    src_fill = (
        '//@version=6\nindicator("x")\n'
        'upper = plot(high, title="upper")\n'
        'lower = plot(low, title="lower")\n'
        "fill(upper, lower, color=color.new(color.green, 50))\n"
    )
    code, _t, _k, om, attrs = _transpile_once(src_fill)
    assert om is False
    assert attrs[2]["color"] == "rgba(34, 171, 148, 0.4980392156862745)"
    compiled = compile_script(src_fill, use_cache=False)
    assert compiled.object_mode is False
    out = compiled.run(o, h, l, c, v)
    assert np.allclose(out["upper"], h)
    assert np.allclose(out["lower"], l)

    # Controls must stay object mode.
    controls = {
        "dynamic_transp": '//@version=6\nindicator("x")\nt = close > open ? 50 : 25\nplot(close, color=color.new(color.red, t))\n',
        "color_series": '//@version=6\nindicator("x")\ncol = close > open ? color.green : color.red\nplot(close, color=col)\n',
        "bgcolor": '//@version=6\nindicator("x")\nbgcolor(color.new(color.red, 50))\nplot(close)\n',
        "udt": '//@version=6\nindicator("x")\ntype P\n    float x\np = P.new(close)\nplot(p.x)\n',
        "array": '//@version=6\nindicator("x")\na = array.new_float(2)\narray.set(a, 0, close)\nplot(array.get(a, 0))\n',
        "drawing": '//@version=6\nindicator("x")\nl = label.new(bar_index, close, "x")\nplot(close)\n',
    }
    for name, src in controls.items():
        _code, _t, _k, om, _a = _transpile_once(src)
        assert om is True, name

    # Legacy one-arg rgba string keeps its original text (no alpha renormalize).
    src_legacy = (
        '//@version=6\nindicator("x")\n'
        'upper = plot(high, title="upper")\n'
        'lower = plot(low, title="lower")\n'
        'fill(upper, lower, color=color.new("#FF000080"))\n'
    )
    _code, _t, _k, om, legacy_attrs = _transpile_once(src_legacy)
    assert om is False
    assert legacy_attrs[2]["color"] == "#FF000080"

    # Numeric hline synthesis must keep color/linestyle that object mode puts
    # in __drawings. This covers the 3 newly-numeric scripts the checker flagged.
    bars = _make_bars(60)
    ref_arrays = (
        [b["open"] for b in bars],
        [b["high"] for b in bars],
        [b["low"] for b in bars],
        [b["close"] for b in bars],
        [b["volume"] for b in bars],
        [b["time"] for b in bars],
    )
    hline_meta = 0
    hline_scanned = 0
    for rel in sorted(EXPECTED_NUMERIC):
        hline_scanned += 1
        src = (DATA / rel).read_text(errors="ignore")
        out = Runtime(symbol="TEST").run(src, bars, mode="compile")
        assert out.get("error") is None, (rel, out.get("error"))
        assert out.get("object_mode") is False, rel

        # Object-mode reference: every hline event carries the visual metadata.
        ref = compile_script(src, force_object_mode=True, use_cache=False)
        raw = ref.run(*ref_arrays)
        obj_hlines: dict[str, dict] = {}
        for ev in raw.get("__drawings", []):
            if ev.get("kind") == "hline" and ev.get("title"):
                obj_hlines.setdefault(str(ev["title"]), ev)
        if not obj_hlines:
            continue

        for title, ev in obj_hlines.items():
            meta = out["plot_meta"][title]
            for key in ("color", "linestyle", "linewidth"):
                if ev.get(key) is not None:
                    assert meta.get(key) == ev[key], (rel, title, key, meta, ev)
            expected = EXPECTED_HLINE.get(rel)
            if expected is not None:
                exp_title, exp_color, exp_style = expected
                assert title == exp_title, (rel, title)
                assert meta["color"] == exp_color, (rel, meta)
                assert meta["linestyle"] == exp_style, (rel, meta)
            hline_meta += 1

    assert hline_scanned == len(EXPECTED_NUMERIC) == 7
    assert hline_meta == len(EXPECTED_HLINE) == 3

    print(
        "COLOR_FOLD_PROOF_OK "
        f"numeric={len(numeric)} object={len(object_mode)} errors={len(errors)} "
        f"controls={len(controls)} hline_scanned={hline_scanned} "
        f"hline_meta={hline_meta} fill_color={attrs[2]['color']}"
    )


if __name__ == "__main__":
    main()
