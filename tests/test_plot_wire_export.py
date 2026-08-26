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

"""AXIS contract parity: plot wire params, OHLC siblings, drawing export."""

from __future__ import annotations

import math

from backend.runtime import Runtime
from pynescript.ast.evaluator.builtins.drawing import Box
from pynescript.ast.evaluator.builtins.drawing import ChartPoint
from pynescript.ast.evaluator.builtins.drawing import DrawingRegistry
from pynescript.ast.evaluator.builtins.drawing import Label
from pynescript.ast.evaluator.builtins.drawing import Polyline
from pynescript.ast.evaluator.builtins.drawing import Table
from pynescript.ast.evaluator.builtins.drawing import TableCell
from pynescript.ast.evaluator.builtins.plot_params import PLOT_PARAM_SPECS
from pynescript.ast.evaluator.builtins.plot_params import extract_wire_meta
from pynescript.ast.evaluator.builtins.plot_params import param_index
from pynescript.ast.evaluator.builtins.plot_params import resolve_arg
from pynescript.compiler.engine import clear_compile_cache


class TestParamSpec:
    def test_canonical_plot_order(self) -> None:
        assert param_index("plot", "linewidth") == 3
        assert param_index("plot", "style") == 4
        assert param_index("plot", "trackprice") == 5
        assert param_index("plot", "histbase") == 6
        assert param_index("plot", "offset") == 7
        assert param_index("plot", "show_last") == 10

    def test_unknown_param_is_minus_one(self) -> None:
        assert param_index("plot", "nonsense") == -1
        assert param_index("nope", "series") == -1

    def test_resolve_kwarg_wins(self) -> None:
        args = ["c", "t", None, 2]
        kwargs = {"style": "histogram"}
        assert resolve_arg("plot", "style", args, kwargs) == "histogram"
        assert resolve_arg("plot", "linewidth", args, kwargs, 1) == 2

    def test_resolve_positional(self) -> None:
        args = ["c", "t", "#f00", 2, "histogram", False, -10.0]
        assert resolve_arg("plot", "linewidth", args, None, 1) == 2
        assert resolve_arg("plot", "style", args, None, "") == "histogram"
        assert resolve_arg("plot", "histbase", args, None, None) == -10.0


class TestExtractWireMeta:
    def test_static_values(self) -> None:
        args = ["c", None, None, 2, "histogram", True, -20.0, 3, False, True, 50]
        out = extract_wire_meta("plot", args, None)
        assert out == {
            "trackprice": True,
            "histbase": -20.0,
            "offset": 3,
            "join": False,
            "editable": True,
            "show_last": 50,
        }

    def test_kwargs_only(self) -> None:
        out = extract_wire_meta("plot", ["c"], {"offset": 2, "histbase": 5, "editable": False})
        assert out == {"offset": 2, "histbase": 5.0, "editable": False}

    def test_absent_and_default_offset_omitted(self) -> None:
        assert extract_wire_meta("plot", ["c"], None) == {}
        # offset=0 is Pine default → omitted
        assert extract_wire_meta("plot", ["c"], {"offset": 0}) == {}

    def test_bool_rejected_for_int_param(self) -> None:
        assert extract_wire_meta("plot", ["c"], {"offset": True}) == {}

    def test_uncoercible_values_skipped(self) -> None:
        assert extract_wire_meta("plot", ["c"], {"offset": "x"}) == {}
        assert extract_wire_meta("plot", ["c"], {"histbase": float("nan")}) == {}

    def test_hline_kind_and_unknown_kind(self) -> None:
        assert extract_wire_meta("hline", [1.0], {"editable": False}) == {"editable": False}
        assert extract_wire_meta("nope", ["c"], {"offset": 2}) == {}

    def test_spec_positions_match_order(self) -> None:
        for spec in PLOT_PARAM_SPECS.values():
            assert spec == tuple((n, i) for i, (n, _) in enumerate(spec))


def _bars(n: int = 24) -> list[dict]:
    out = []
    for i in range(n):
        c = 100 + 5 * math.sin(i / 3.0)
        up = i % 2 == 0
        o = c - 0.5 if up else c + 0.5
        out.append(
            {
                "time": 1_700_000_000 + i * 86400,
                "open": o,
                "high": max(o, c) + 1,
                "low": min(o, c) - 1,
                "close": c,
                "volume": 10,
            }
        )
    return out


_WIRE_SCRIPT = """
//@version=6
indicator("wire", overlay=true)
plot(close, title="base", linewidth=2, offset=3, histbase=-10, trackprice=true, join=true, editable=false, show_last=20)
bgcolor(close > open ? color.green : na, title="bg", offset=1)
"""


class TestRuntimeWireMeta:
    def test_plot_wire_params_exported(self) -> None:
        r = Runtime().run(_WIRE_SCRIPT, _bars(), mode="interpret")
        meta = r["plot_meta"]["base"]
        assert meta["linewidth"] == 2
        assert meta["offset"] == 3
        assert meta["histbase"] == -10.0
        assert meta["trackprice"] is True
        assert meta["join"] is True
        assert meta["editable"] is False
        assert meta["show_last"] == 20

    def test_bgcolor_offset(self) -> None:
        r = Runtime().run(_WIRE_SCRIPT, _bars(), mode="interpret")
        assert r["plot_meta"]["bg"].get("offset") == 1

    def test_defaults_omitted(self) -> None:
        script = '//@version=6\nindicator("m", overlay=true)\nplot(close, title="plain")\n'
        r = Runtime().run(script, _bars(), mode="interpret")
        meta = r["plot_meta"]["plain"]
        for key in ("offset", "histbase", "trackprice", "join", "show_last"):
            assert key not in meta


class TestPositionalIndex:
    def test_positional_linewidth_style_runtime(self) -> None:
        # Pine v6 canonical order: plot(series, title, color, linewidth, style, ...)
        script = '//@version=6\nindicator("p")\nplot(close, "t", color.red, 3, plot.style_histogram)\n'
        r = Runtime().run(script, _bars(), mode="interpret")
        meta = r["plot_meta"]["t"]
        assert meta["linewidth"] == 3
        assert meta["style"] == "style_histogram"

    def test_positional_linewidth_interpret(self) -> None:
        from pynescript.ast.evaluator import NodeLiteralEvaluator
        from pynescript.ast.evaluator.builtins.plotting import PlotRegistry
        from pynescript.ast.helper import parse

        PlotRegistry.reset()
        ev = NodeLiteralEvaluator()
        ev.visit(parse('plot(close, "t", color.red, 4)', mode="eval").body)
        assert len(PlotRegistry.plots) == 1
        assert PlotRegistry.plots[0].linewidth == 4

    def test_kwargs_branch_positional_fallbacks(self) -> None:
        from pynescript.runtime.evaluator import CustomEvaluator

        ev = CustomEvaluator()
        ev._builtin_plot([1.0, "t", "#f00", 3], {"style": "style_histogram"})
        m = ev._plot_meta_list[0]
        assert m["linewidth"] == 3
        assert m["style"] == "style_histogram"


class TestCaptureLayer:
    def _run_evaluator(self, script: str):
        # Drive CustomEvaluator directly so we can inspect _plot_meta_list
        # before host packing (packing whitelist is a later task).
        from pynescript.ast.helper import parse
        from pynescript.runtime.evaluator import CustomEvaluator

        ev = CustomEvaluator()
        tree = parse(script)
        bars = _bars(4)
        for b in bars:
            ev.current_series = {
                "open": [b["open"]],
                "high": [b["high"]],
                "low": [b["low"]],
                "close": [b["close"]],
            }
            ev._plot_n_bars = len(bars)
            try:
                ev.visit(tree)
            except Exception:  # noqa: S110 — capture still ran for statements that evaluated
                pass
            ev.finish_bar_plots()
        return ev

    def test_first_sighting_registers_extras(self) -> None:
        script = '//@version=6\nindicator("w")\nplot(close, title="base", offset=3, histbase=-10, trackprice=true)\n'
        ev = self._run_evaluator(script)
        by_title = {m.get("title"): m for m in ev._plot_meta_list}
        m = by_title["base"]
        assert m["offset"] == 3
        assert m["histbase"] == -10
        assert m["trackprice"] is True
        assert "_wire_missing" not in m

    def test_na_dynamic_defers_via_pending(self) -> None:
        script = '//@version=6\nindicator("d")\nvar int off = na\nplot(close, title="dyn", offset=off)\n'
        ev = self._run_evaluator(script)
        pend_before = ev._plot_wire_pending
        assert pend_before == 1
        m = next(m for m in ev._plot_meta_list if m.get("title") == "dyn")
        assert m["_wire_missing"] == ("offset",)


class TestLazyWireResolution:
    def _seed(self):
        from pynescript.runtime.evaluator import CustomEvaluator

        ev = CustomEvaluator()
        ev._plot_value_cols.append([None])
        ev._plot_meta_list.append(
            {"type": "plot", "kind": "plot", "title": "t", "_wire_missing": ("offset", "histbase")}
        )
        ev._plot_wire_pending = 1
        return ev

    def test_full_resolution_decrements_pending(self) -> None:
        ev = self._seed()
        ev._lazy_plot_wire(0, "plot", ["c"], {"offset": 2, "histbase": -5})
        m = ev._plot_meta_list[0]
        assert m["offset"] == 2 and m["histbase"] == -5.0
        assert "_wire_missing" not in m
        assert ev._plot_wire_pending == 0

    def test_partial_fill_retains_remainder(self) -> None:
        ev = self._seed()
        ev._lazy_plot_wire(0, "plot", ["c"], {"offset": 2})
        m = ev._plot_meta_list[0]
        assert m["offset"] == 2
        assert m["_wire_missing"] == ("histbase",)
        assert ev._plot_wire_pending == 1


_CANDLE_SCRIPT = """
//@version=6
indicator("c", overlay=true)
plotcandle(open, high, low, close, title="px", color=color.blue,
           wickcolor=color.orange, bordercolor=color.red)
"""


class TestCandleOhlc:
    def test_sibling_columns_and_meta_refs(self) -> None:
        r = Runtime().run(_CANDLE_SCRIPT, _bars(), mode="interpret")
        s = r["series"]
        assert {"px", "px.open", "px.high", "px.low"} <= set(s)
        b = _bars()[5]
        assert s["px.open"][5] == b["open"]
        assert s["px.high"][5] == b["high"]
        assert s["px.low"][5] == b["low"]
        assert s["px"][5] == b["close"]
        meta = r["plot_meta"]["px"]
        assert meta["kind"] == "plotcandle"
        assert meta["open"] == "px.open"
        assert meta["high"] == "px.high"
        assert meta["low"] == "px.low"
        assert meta["close"] == "px"
        assert meta["style"] == "candles"

    def test_wick_border_colors(self) -> None:
        r = Runtime().run(_CANDLE_SCRIPT, _bars(), mode="interpret")
        meta = r["plot_meta"]["px"]
        # colors serialize via to_rgba/to_hex/hex-int paths; assert presence + string
        assert isinstance(meta.get("wickcolor"), str) and meta["wickcolor"]
        assert isinstance(meta.get("bordercolor"), str) and meta["bordercolor"]

    def test_positional_wick_border(self) -> None:
        # Pine v6 canonical order: open, high, low, close, title@4, color@5,
        # wickcolor@6 — previously kwargs-only.
        script = (
            '//@version=6\nindicator("pw", overlay=true)\n'
            'plotcandle(open, high, low, close, "pt", color.blue, color.orange)\n'
        )
        r = Runtime().run(script, _bars(), mode="interpret")
        meta = r["plot_meta"]["pt"]
        assert isinstance(meta.get("wickcolor"), str) and meta["wickcolor"]
        assert meta.get("color") == "#2962FF"

    def test_positional_plotbar_bordercolor(self) -> None:
        # bordercolor@8 (after editable@6, show_last@7)
        script = (
            '//@version=6\nindicator("pb", overlay=true)\n'
            'plotbar(open, high, low, close, "pb", color.green, true, 10, color.red)\n'
        )
        r = Runtime().run(script, _bars(), mode="interpret")
        meta = r["plot_meta"]["pb"]
        assert isinstance(meta.get("bordercolor"), str) and meta["bordercolor"]
        assert meta["style"] == "bars"

    def test_plotbar_ohlc(self) -> None:
        script = '//@version=6\nindicator("b")\nplotbar(open, high, low, close, title="brs")\n'
        r = Runtime().run(script, _bars(), mode="interpret")
        assert {"brs", "brs.open", "brs.high", "brs.low"} <= set(r["series"])

    def test_candle_display_exported(self) -> None:
        script = (
            '//@version=6\nindicator("cd", overlay=true)\n'
            'plotcandle(open, high, low, close, title="pd", display=display.all)\n'
        )
        r = Runtime().run(script, _bars(), mode="interpret")
        assert r["plot_meta"]["pd"].get("display") is not None

    def test_mid_run_first_fire_no_crash(self) -> None:
        script = (
            '//@version=6\nindicator("mr", overlay=true)\n'
            'if close > 100\n    plotcandle(open, high, low, close, title="mx")\n'
            'plot(close, title="after")\n'
        )
        r = Runtime().run(script, _bars(), mode="interpret")  # must not raise
        assert "after" in r["series"]
        assert "mx" in r["series"]

    def test_dynamic_color_resolves_late(self) -> None:
        script = (
            '//@version=6\nindicator("dyn", overlay=true)\n'
            "var color wc = na\n"
            "if bar_index == 3\n    wc := color.orange\n"
            'plotcandle(open, high, low, close, title="dx", wickcolor=wc)\n'
        )
        r = Runtime().run(script, _bars(8), mode="interpret")
        meta = r["plot_meta"]["dx"]
        assert meta.get("wickcolor") == "#FF6D00"

    def test_two_same_titled_candles_register_both(self) -> None:
        script = (
            '//@version=6\nindicator("dup", overlay=true)\n'
            "plotcandle(open, high, low, close)\n"
            "plotcandle(open, high, low, close)\n"
        )
        r = Runtime().run(script, _bars(), mode="interpret")
        s = r["series"]
        assert {"candles", "candles.open", "candles.high", "candles.low"} <= set(s)
        assert {"candles_2", "candles_2.open", "candles_2.high", "candles_2.low"} <= set(s)


def _clean_registry() -> None:
    DrawingRegistry.lines.clear()
    DrawingRegistry.boxes.clear()
    DrawingRegistry.labels.clear()
    DrawingRegistry.tables.clear()
    DrawingRegistry.polylines.clear()
    DrawingRegistry.linefills.clear()


def _make_table_host():
    """Evaluator instance exposing drawing table handlers."""
    from pynescript.ast.evaluator import NodeLiteralEvaluator

    return NodeLiteralEvaluator()


class TestDrawingExportParity:
    def test_box_full_styling(self) -> None:
        _clean_registry()
        DrawingRegistry.boxes.append(
            Box(
                left=1,
                top=110.0,
                right=10,
                bottom=100.0,
                border_style="dashed",
                extend="right",
                text="zone",
                text_color="#00ff00",
                text_halign="left",
                text_valign="top",
                text_size=14,
                text_wrap="auto",
            )
        )
        out = {d["type"]: d for d in DrawingRegistry.export_for_api([])}["box"]
        assert out["extend"] == "right"
        assert out["border_style"] == "dashed"
        assert out["text_color"] == "#00ff00"
        assert out["text_halign"] == "left"
        assert out["text_valign"] == "top"
        assert out["text_size"] == 14
        assert out["text_wrap"] == "auto"

    def test_label_tooltip_and_alignment(self) -> None:
        _clean_registry()
        DrawingRegistry.labels.append(
            Label(
                x=2,
                y=101.0,
                text="hi",
                tooltip="tt",
                text_halign="right",
                text_valign="bottom",
                text_formatting="bold",
            )
        )
        out = DrawingRegistry.export_for_api([0, 1])[0]
        assert out["type"] == "label"
        assert out["tooltip"] == "tt"
        assert out["text_halign"] == "right"
        assert out["text_valign"] == "bottom"
        assert out["text_formatting"] == "bold"

    def test_polyline_curved_fill_overlay(self) -> None:
        _clean_registry()
        DrawingRegistry.polylines.append(
            Polyline(
                points=[ChartPoint(index=0, price=100.0), ChartPoint(index=3, price=105.0)],
                curved=True,
                fill_color="rgba(255,0,0,0.2)",
                force_overlay=True,
            )
        )
        out = DrawingRegistry.export_for_api([0, 1, 2, 3])[0]
        assert out["type"] == "polyline"
        assert out["curved"] is True
        assert out["fill_color"] == "rgba(255,0,0,0.2)"
        assert out["force_overlay"] is True

    def test_polyline_fill_color_omitted_when_none(self) -> None:
        _clean_registry()
        DrawingRegistry.polylines.append(
            Polyline(points=[ChartPoint(index=0, price=100.0), ChartPoint(index=3, price=105.0)])
        )
        out = DrawingRegistry.export_for_api([0, 1, 2, 3])[0]
        assert "fill_color" not in out


class TestTableParity:
    def test_frame_border_export(self) -> None:
        _clean_registry()
        DrawingRegistry.tables.append(
            Table(
                position="top_right",
                rows=2,
                columns=2,
                frame_color="#111111",
                frame_width=2,
                border_color="#222222",
                border_width=3,
            )
        )
        out = DrawingRegistry.export_for_api([])[0]
        assert out["type"] == "table"
        assert out["frame_width"] == 2
        assert out["border_color"] == "#222222"
        assert out["border_width"] == 3

    def test_merge_cells_registry_and_export(self) -> None:
        _clean_registry()
        tb = Table(rows=4, columns=4)
        DrawingRegistry.tables.append(tb)
        ev = _make_table_host()
        ev._handle_table_merge_cells([tb, 0, 0, 1, 1])
        assert tb.merged == [(0, 0, 1, 1)]
        out = DrawingRegistry.export_for_api([])[0]
        assert out["merged_cells"] == [[0, 0, 1, 1]]

    def test_merge_overlap_soft_ignored(self) -> None:
        tb = Table(rows=4, columns=4)
        ev = _make_table_host()
        ev._handle_table_merge_cells([tb, 0, 0, 1, 1])
        ev._handle_table_merge_cells([tb, 1, 1, 2, 2])  # overlaps → ignored
        ev._handle_table_merge_cells([tb, 2, 0, 3, 1])  # disjoint → kept
        assert tb.merged == [(0, 0, 1, 1), (2, 0, 3, 1)]

    def test_clear_full_vs_range(self) -> None:
        tb = Table(rows=3, columns=3)
        for r in range(3):
            for c in range(3):
                tb.cells[(r, c)] = TableCell(text=f"{r}{c}")
        ev = _make_table_host()
        ev._handle_table_clear([tb])
        assert tb.cells == {}
        for r in range(3):
            for c in range(3):
                tb.cells[(r, c)] = TableCell(text=f"{r}{c}")
        ev._handle_table_clear([tb, 1, 1, 2, 2])
        assert set(tb.cells) == {(0, 0), (0, 1), (0, 2), (1, 0), (2, 0)}


class TestCompileAttrs:
    def test_static_attrs_propagate(self) -> None:
        clear_compile_cache()
        script = '//@version=6\nindicator("cm", overlay=true)\nplot(close, title="cm_line", linewidth=3, offset=2)\n'
        r = Runtime().run(script, _bars(), mode="compile")
        meta = r["plot_meta"]["cm_line"]
        assert meta["linewidth"] == 3
        assert meta.get("offset") == 2

    def test_dynamic_attr_omitted(self) -> None:
        clear_compile_cache()
        script = '//@version=6\nindicator("cd")\nplot(sma(close, 3), title="d", linewidth=nz(close[0]))\n'
        r = Runtime().run(script, _bars(), mode="compile")
        m = r["plot_meta"]["d"]
        assert not isinstance(m.get("linewidth"), str)

    def test_bgcolor_offset_parity_both_modes(self) -> None:
        # bgcolor meta comes from __drawings events in compile mode; the
        # constant offset must fold into plot_meta like interpret.
        script = (
            '//@version=6\nindicator("bgp", overlay=true)\n'
            'bgcolor(close > open ? color.green : na, title="bgp_bg", offset=1)\n'
        )
        ri = Runtime().run(script, _bars(), mode="interpret")
        clear_compile_cache()
        rc = Runtime().run(script, _bars(), mode="compile")
        assert ri["plot_meta"]["bgp_bg"].get("offset") == 1
        assert rc["plot_meta"]["bgp_bg"].get("offset") == 1

    def test_ir_share_does_not_leak_titles_or_attrs(self) -> None:
        # Metadata-only siblings share numeric IR; each payload keeps its own
        # titles/attrs (IR-cache share is gated on metadata equality).
        clear_compile_cache()
        bars = _bars(12)
        src_a = '//@version=6\nindicator("a")\nplot(close, title="alpha")\n'
        src_b = '//@version=6\nindicator("b")\nplot(close, title="beta", linewidth=4)\n'
        ra = Runtime().run(src_a, bars, mode="compile")
        rb = Runtime().run(src_b, bars, mode="compile")
        ma, mb = ra["plot_meta"]["alpha"], rb["plot_meta"]["beta"]
        assert ma["title"] == "alpha"
        assert mb["title"] == "beta"
        assert mb.get("linewidth") == 4
        assert ma.get("linewidth") in (1, None)


# ---------------------------------------------------------------------------
# Arnjesix regression matrix: offset contract validation (issue #6)
# ---------------------------------------------------------------------------


_OFFSET_SCRIPT = """
//@version=6
indicator("off", overlay=true)
plot(close, title="p_n2", offset=-2)
plot(close, title="p_0")
plot(close, title="p_2", offset=2)
bgcolor(color.red, title="bg_n2", offset=-2)
bgcolor(color.blue, title="bg_2", offset=2)
barcolor(color.green, title="bc_n2", offset=-2)
barcolor(color.orange, title="bc_2", offset=2)
plotshape(close > open, title="ps_n2", offset=-2)
plotshape(close > open, title="ps_2", offset=2)
plotchar(close > open, title="pc_n2", offset=-2)
plotchar(close > open, title="pc_2", offset=2)
"""


class TestOffsetContractMatrix:
    """Validate arnjesix's 5 pass conditions for the offset wire contract."""

    def test_raw_samples_identical_regardless_of_offset(self) -> None:
        """Pass condition 1: raw sample sequence identical between offset 0 and 2."""
        bars = _bars(10)
        r = Runtime().run(_OFFSET_SCRIPT, bars, mode="interpret")
        series = r["series"]
        # All plot variants capture the same close values — offset is metadata-only
        for title in ("p_n2", "p_0", "p_2"):
            assert series[title] == series["p_0"], f"raw samples differ for {title}"

    def test_only_metadata_differs(self) -> None:
        """Pass condition 2: only plot_meta.offset differs."""
        r = Runtime().run(_OFFSET_SCRIPT, _bars(10), mode="interpret")
        meta = r["plot_meta"]
        assert meta["p_n2"]["offset"] == -2
        assert "offset" not in meta["p_0"]  # 0 is default → omitted
        assert meta["p_2"]["offset"] == 2

    def test_json_round_trip_preserves_signed_offset(self) -> None:
        """Pass condition 3: JSON round-trip preserves signed value."""
        import json

        r = Runtime().run(_OFFSET_SCRIPT, _bars(10), mode="interpret")
        payload = json.dumps(r["plot_meta"])
        restored = json.loads(payload)
        assert restored["p_n2"]["offset"] == -2
        assert restored["p_2"]["offset"] == 2
        assert restored["bg_n2"]["offset"] == -2
        assert restored["bc_2"]["offset"] == 2

    def test_offset_per_kind_all_variants(self) -> None:
        """Each plot-like output owns its own offset."""
        r = Runtime().run(_OFFSET_SCRIPT, _bars(10), mode="interpret")
        meta = r["plot_meta"]
        assert meta["bg_n2"]["offset"] == -2
        assert meta["bg_2"]["offset"] == 2
        assert meta["bc_n2"]["offset"] == -2
        assert meta["bc_2"]["offset"] == 2
        assert meta["ps_n2"]["offset"] == -2
        assert meta["ps_2"]["offset"] == 2
        assert meta["pc_n2"]["offset"] == -2
        assert meta["pc_2"]["offset"] == 2

    def test_no_shared_or_last_write_wins(self) -> None:
        """Two plots with different offsets do not clobber each other."""
        r = Runtime().run(_OFFSET_SCRIPT, _bars(10), mode="interpret")
        meta = r["plot_meta"]
        assert meta["p_n2"]["offset"] == -2
        assert meta["p_2"]["offset"] == 2
        # Cross-check: changing one didn't affect the other
        assert meta["p_n2"]["offset"] != meta["p_2"]["offset"]

    def test_offset_with_na_gaps(self) -> None:
        """Offset works when the value series contains na gaps."""
        script = (
            '//@version=6\nindicator("off_na", overlay=true)\n'
            'plot(close > 100 ? close : na, title="na_plot", offset=2)\n'
            'bgcolor(close > 100 ? color.green : na, title="na_bg", offset=-1)\n'
        )
        r = Runtime().run(script, _bars(20), mode="interpret")
        meta = r["plot_meta"]
        assert meta["na_plot"]["offset"] == 2
        assert meta["na_bg"]["offset"] == -1

    def test_existing_scripts_without_offset_unchanged(self) -> None:
        """Pass condition 5: scripts omitting offset retain output and get default 0."""
        script = '//@version=6\nindicator("def")\nplot(close, title="plain")\n'
        r = Runtime().run(script, _bars(10), mode="interpret")
        meta = r["plot_meta"]["plain"]
        assert "offset" not in meta  # default 0 → omitted

    def test_offset_parity_interpret_vs_compile(self) -> None:
        """Offset folds identically in both modes."""
        script = (
            '//@version=6\nindicator("off_cm", overlay=true)\n'
            'plot(close, title="cm_off", offset=3)\n'
            'bgcolor(color.red, title="cm_bg_off", offset=-2)\n'
        )
        ri = Runtime().run(script, _bars(10), mode="interpret")
        clear_compile_cache()
        rc = Runtime().run(script, _bars(10), mode="compile")
        assert ri["plot_meta"]["cm_off"]["offset"] == 3
        assert rc["plot_meta"]["cm_off"]["offset"] == 3
        assert ri["plot_meta"]["cm_bg_off"]["offset"] == -2
        assert rc["plot_meta"]["cm_bg_off"]["offset"] == -2


# ---------------------------------------------------------------------------
# Compile-mode wire params for trackprice/show_last/editable/join (issue #7)
# ---------------------------------------------------------------------------


class TestCompileWireParams:
    """Verify trackprice/show_last/editable/join round-trip in compile mode."""

    def test_plot_wire_params_compile_parity(self) -> None:
        script = (
            '//@version=6\nindicator("cw", overlay=true)\n'
            'plot(close, title="cw_line", trackprice=true, show_last=50, '
            "editable=false, join=true, offset=2)\n"
        )
        ri = Runtime().run(script, _bars(10), mode="interpret")
        clear_compile_cache()
        rc = Runtime().run(script, _bars(10), mode="compile")
        for mode_name, r in (("interpret", ri), ("compile", rc)):
            meta = r["plot_meta"]["cw_line"]
            assert meta.get("trackprice") is True, f"{mode_name}: trackprice"
            assert meta.get("show_last") == 50, f"{mode_name}: show_last"
            assert meta.get("editable") is False, f"{mode_name}: editable"
            assert meta.get("join") is True, f"{mode_name}: join"
            assert meta.get("offset") == 2, f"{mode_name}: offset"

    def test_hline_editable_compile_parity(self) -> None:
        script = '//@version=6\nindicator("ch", overlay=true)\nhline(100, "level", editable=false)\n'
        ri = Runtime().run(script, _bars(5), mode="interpret")
        clear_compile_cache()
        rc = Runtime().run(script, _bars(5), mode="compile")
        assert ri["plot_meta"]["level"].get("editable") is False
        assert rc["plot_meta"]["level"].get("editable") is False
