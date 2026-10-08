# Copyright (C) 2024-2026 jango_blockchained
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Table cell style storage + export parity (AXIS bottom-panel tables)."""

from __future__ import annotations

from pynescript.ast.evaluator.builtins.drawing import (
    DrawingRegistry,
    Table,
    TableCell,
)


class TestTableCellStorage:
    def setup_method(self) -> None:
        DrawingRegistry.reset()

    def test_cell_stores_v6_kwargs(self) -> None:
        from pynescript.ast.evaluator.builtins.drawing import DrawingBuiltinsMixin

        mixin = DrawingBuiltinsMixin()
        tb = Table(position="top_right", rows=2, columns=2)
        DrawingRegistry.tables.append(tb)
        mixin._handle_table_cell(
            [tb, 1, 0, "hi"],
            {
                "width": 30,
                "height": 12,
                "text_halign": "text.right",
                "text_valign": "text.top",
                "text_size": "small",
                "text_font_family": "monospace",
                "text_formatting": "bold",
                "tooltip": "tip",
            },
        )
        cell = tb.cells[(0, 1)]
        assert cell.width == 30
        assert cell.height == 12
        assert cell.text_halign == "text.right"
        assert cell.text_valign == "text.top"
        assert cell.text_size == "small"
        assert cell.text_font_family == "monospace"
        assert cell.text_formatting == "bold"
        assert cell.tooltip == "tip"

    def test_cell_v6_positional_order(self) -> None:
        from pynescript.ast.evaluator.builtins.drawing import DrawingBuiltinsMixin

        mixin = DrawingBuiltinsMixin()
        tb = Table(position="top_right", rows=2, columns=2)
        DrawingRegistry.tables.append(tb)
        mixin._handle_table_cell(
            [tb, 0, 1, "p", 10, 20, "#ff0000", "right", "top", "small", "monospace", "bold", "#00ff00", "tt"],
            {},
        )
        cell = tb.cells[(1, 0)]
        assert cell.width == 10
        assert cell.height == 20
        assert cell.text_color == "#ff0000"
        assert cell.text_halign == "right"
        assert cell.text_size == "small"
        assert cell.bgcolor == "#00ff00"
        assert cell.tooltip == "tt"

    def test_cell_v5_positional_compat(self) -> None:
        from pynescript.ast.evaluator.builtins.drawing import DrawingBuiltinsMixin

        mixin = DrawingBuiltinsMixin()
        tb = Table(position="top_right", rows=1, columns=1)
        DrawingRegistry.tables.append(tb)
        mixin._handle_table_cell([tb, 0, 0, "v5", 0, 0, "#111111", "c", "c", "auto", "#222222", "vtip"], {})
        cell = tb.cells[(0, 0)]
        assert cell.bgcolor == "#222222"
        assert cell.tooltip == "vtip"


class TestInterpretTableExport:
    def setup_method(self) -> None:
        DrawingRegistry.reset()

    def test_export_carries_style_and_overlay(self) -> None:
        tb = Table(
            position="top_right",
            rows=1,
            columns=2,
            frame_color="#111111",
            frame_width=2,
            border_color="#222222",
            border_width=1,
            bgcolor="#333333",
            force_overlay=True,
        )
        tb.cells[(0, 0)] = TableCell(
            text="a", width=10, height=20, text_halign="right",
            text_valign="top", text_size="small", tooltip="tip",
        )
        tb.cells[(0, 1)] = TableCell(text="b")
        tb.merged.append((0, 0, 0, 1))
        DrawingRegistry.tables.append(tb)
        out = DrawingRegistry.export_for_api([1_700_000_000])
        assert len(out) == 1
        d = out[0]
        assert d["type"] == "table"
        assert d["force_overlay"] is True
        assert d["merged_cells"] == [[0, 0, 0, 1]]
        cells = {c["col"]: c for c in d["cells"]}
        assert cells[0]["width"] == 10
        assert cells[0]["height"] == 20
        assert cells[0]["text_halign"] == "right"
        assert cells[0]["text_valign"] == "top"
        assert cells[0]["text_size"] == "small"
        assert cells[0]["tooltip"] == "tip"
        assert cells[1]["text"] == "b"


class TestCompileTableExport:
    def test_compile_events_carry_style(self) -> None:
        events = [
            {
                "kind": "table",
                "position": "top_right",
                "rows": 1,
                "columns": 2,
                "bgcolor": "#333333",
                "frame_color": "#111111",
                "frame_width": 2,
                "border_color": "#222222",
                "border_width": 1,
                "force_overlay": True,
                "merged_cells": [[0, 0, 0, 1]],
                "cells": [
                    {
                        "row": 0, "col": 0, "text": "a", "width": 10,
                        "height": 20, "text_halign": "right",
                        "text_valign": "top", "text_size": "small",
                        "tooltip": "tip",
                    },
                    {"row": 0, "col": 1, "text": "b"},
                ],
            }
        ]
        out = DrawingRegistry.export_compile_events_for_api(events, [1_700_000_000])
        assert len(out) == 1
        d = out[0]
        assert d["type"] == "table"
        assert d["force_overlay"] is True
        assert d["frame_width"] == 2
        assert d["border_width"] == 1
        assert d["merged_cells"] == [[0, 0, 0, 1]]
        cells = {c["col"]: c for c in d["cells"]}
        assert cells[0]["width"] == 10
        assert cells[0]["tooltip"] == "tip"
        assert cells[0]["text_halign"] == "right"
