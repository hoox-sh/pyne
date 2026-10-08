# Copyright (C) 2024-2026 jango_blockchained
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Compile-path box/label/polyline extras parity with the interpret host."""

from __future__ import annotations

from pynescript.ast.evaluator.builtins.drawing import DrawingRegistry


class TestCompileBoxExtras:
    def test_box_carries_text_and_border_extras(self) -> None:
        events = [
            {
                "kind": "box",
                "left": 0,
                "top": 110.0,
                "right": 2,
                "bottom": 100.0,
                "bgcolor": "#00ff00",
                "border_color": "#ff0000",
                "border_width": 2,
                "border_style": "dashed",
                "extend": "right",
                "text": "zone",
                "text_color": "#ffffff",
                "text_halign": "right",
                "text_valign": "top",
                "text_size": "small",
                "text_wrap": "auto",
                "text_font_family": "monospace",
                "force_overlay": True,
            }
        ]
        out = DrawingRegistry.export_compile_events_for_api(events, [1_700_000_000, 1_700_086_400, 1_700_172_800])
        assert len(out) == 1
        d = out[0]
        assert d["type"] == "box"
        assert d["extend"] == "right"
        assert d["border_style"] == "dashed"
        assert d["text_color"] == "#ffffff"
        assert d["text_halign"] == "right"
        assert d["text_valign"] == "top"
        assert d["text_size"] == "small"
        assert d["text_wrap"] == "auto"
        assert d["text_font_family"] == "monospace"
        assert d["force_overlay"] is True


class TestCompileLabelExtras:
    def test_label_carries_tooltip_and_text_extras(self) -> None:
        events = [
            {
                "kind": "label",
                "x": 1, "y": 105.0,
                "text": "hi",
                "color": "#123456",
                "textcolor": "#ffffff",
                "style": "label_down",
                "yloc": "abovebar",
                "size": 14,
                "tooltip": "tip",
                "text_halign": "left",
                "text_valign": "bottom",
                "text_font_family": "monospace",
                "text_formatting": "bold",
                "force_overlay": False,
            }
        ]
        out = DrawingRegistry.export_compile_events_for_api(events, [1_700_000_000, 1_700_086_400])
        assert len(out) == 1
        d = out[0]
        assert d["type"] == "label"
        assert d["tooltip"] == "tip"
        assert d["text_halign"] == "left"
        assert d["text_valign"] == "bottom"
        assert d["text_font_family"] == "monospace"
        assert d["text_formatting"] == "bold"
        assert d["size"] == 14


class TestCompilePolylineExtras:
    def test_polyline_carries_curve_and_fill(self) -> None:
        events = [
            {
                "kind": "polyline",
                "points": [{"x": 0, "y": 100.0}, {"x": 1, "y": 110.0}],
                "closed": True,
                "color": "#0000ff",
                "width": 2,
                "style": "dashed",
                "curved": True,
                "force_overlay": True,
                "fill_color": "#00ff00",
            }
        ]
        out = DrawingRegistry.export_compile_events_for_api(events, [1_700_000_000, 1_700_086_400])
        assert len(out) == 1
        d = out[0]
        assert d["type"] == "polyline"
        assert d["curved"] is True
        assert d["force_overlay"] is True
        assert d["fill_color"] == "#00ff00"
