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
