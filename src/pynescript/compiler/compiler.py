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

"""Pine AST → Python/Numba source.

Two backends:
- **numeric** (default): ``@numba.njit`` bar loop for series/math/ta/plot.
- **object**: pure-Python bar loop when UDT, map, or drawing APIs appear.
"""

from __future__ import annotations

from pynescript.ast import node as ast
from pynescript.ast.visitor import NodeVisitor

_NS = frozenset(
    {
        "ta",
        "math",
        "str",
        "array",
        "matrix",
        "map",
        "syminfo",
        "timeframe",
        "color",
        "plot",
        "strategy",
        "input",
        "label",
        "line",
        "box",
        "table",
        "polyline",
        "linefill",
        "chart",
        "hline",
        "bgcolor",
        "barcolor",
        "fill",
    }
)

_DRAWING_FUNCS = frozenset(
    {
        "hline",
        "bgcolor",
        "barcolor",
        "fill",
        "plotshape",
        "plotchar",
        "plotarrow",
        "plotbar",
        "plotcandle",
        "label_new",
        "line_new",
        "box_new",
        "table_new",
        "polyline_new",
        "label_delete",
        "line_delete",
        "box_delete",
        "table_delete",
        "polyline_delete",
    }
)


class CompilerVisitor(NodeVisitor):
    def __init__(self):
        super().__init__()
        self.arrays: set[str] = set()
        self.plots: list[dict] = []
        self.functions: list[str] = []
        self.in_function = False
        self.local_vars: set[str] = set()
        # Object-mode state
        self.object_mode = False
        self.uses_strategy = False
        self.strategy_kwargs: dict[str, str] = {}
        self.udt_types: dict[str, list[str]] = {}  # type name -> field names
        self.udt_vars: set[str] = set()  # series names holding UDT instances
        self.map_vars: set[str] = set()  # var map names (single object, not series)
        self.scalar_vars: set[str] = set()  # non-series locals (map handles, etc.)

    # ------------------------------------------------------------------ script
    def visit_Script(self, node: ast.Script):
        body_lines: list[str] = []
        for stmt in node.body:
            val = self.visit(stmt)
            if val:
                body_lines.append(val)

        if self.object_mode:
            return self._emit_object_mode(body_lines)
        return self._emit_numeric_mode(body_lines)

    def _emit_numeric_mode(self, body_lines: list[str]) -> str:
        lines = [
            "import numpy as np",
            "import numba",
            "from pynescript.compiler.numba_builtins import *",
            "",
        ]
        for func in self.functions:
            lines.append(func)
            lines.append("")

        lines.extend(
            [
                # cache=False: function is exec'd from <string> (no disk locator)
                "@numba.njit(cache=False)",
                "def execute_script_compiled(open_arr, high_arr, low_arr, close_arr, vol_arr):",
                "    n_bars = len(close_arr)",
            ]
        )
        for arr in sorted(self.arrays):
            lines.append(f"    {arr} = np.full(n_bars, np.nan)")
        for idx in range(len(self.plots)):
            lines.append(f"    plot_{idx} = np.full(n_bars, np.nan)")
        lines.append("    for __bar_idx in range(n_bars):")
        if not body_lines:
            lines.append("        pass")
        for line in body_lines:
            line = line.replace("\n", "\n        ")
            lines.append(f"        {line}")

        dict_items = [f"'{p['title']}': plot_{i}" for i, p in enumerate(self.plots)]
        lines.append("    return {" + ", ".join(dict_items) + "}")
        return "\n".join(lines)

    def _emit_object_mode(self, body_lines: list[str]) -> str:
        """Python bar loop with UDT dicts, maps, drawing, and strategy events."""
        lines = [
            "import numpy as np",
            "from pynescript.compiler.numba_builtins import *",
            "",
        ]
        if self.uses_strategy:
            lines.append("from pynescript.compiler.strategy_broker import CompileStrategyBroker")
            lines.append("")
        for func in self.functions:
            # strip @numba.njit for object-mode user functions
            cleaned = "\n".join(l for l in func.splitlines() if not l.startswith("@numba"))
            lines.append(cleaned)
            lines.append("")

        lines.extend(
            [
                "def execute_script_compiled(open_arr, high_arr, low_arr, close_arr, vol_arr):",
                "    n_bars = len(close_arr)",
                "    open_arr = np.asarray(open_arr, dtype=np.float64)",
                "    high_arr = np.asarray(high_arr, dtype=np.float64)",
                "    low_arr = np.asarray(low_arr, dtype=np.float64)",
                "    close_arr = np.asarray(close_arr, dtype=np.float64)",
                "    vol_arr = np.asarray(vol_arr, dtype=np.float64)",
                "    __drawings = []",
            ]
        )
        if self.uses_strategy:
            # Broker ctor kwargs from strategy() declaration when present
            sk = self.strategy_kwargs
            ctor_args = []
            for key in ("initial_capital", "commission_value", "commission_type", "slippage", "mintick"):
                if key in sk:
                    py_key = "slippage_ticks" if key == "slippage" else key
                    ctor_args.append(f"{py_key}={sk[key]}")
            ctor = ", ".join(ctor_args)
            lines.append(f"    __strategy = CompileStrategyBroker({ctor})")
        for arr in sorted(self.arrays):
            # object series use object dtype
            if arr[:-4] in self.udt_vars:  # name_arr -> name
                lines.append(f"    {arr} = np.empty(n_bars, dtype=object)")
            else:
                lines.append(f"    {arr} = np.full(n_bars, np.nan)")
        for name in sorted(self.map_vars | self.scalar_vars):
            lines.append(f"    {name} = None")
        for idx in range(len(self.plots)):
            lines.append(f"    plot_{idx} = np.full(n_bars, np.nan)")

        lines.append("    for __bar_idx in range(n_bars):")
        if self.uses_strategy:
            # Update OHLC then fill pending orders before script body
            # (same order as interpreter Runtime: process → evaluate).
            lines.append(
                "        __strategy.set_bar("
                "__bar_idx, 0, float(close_arr[__bar_idx]), "
                "open_=float(open_arr[__bar_idx]), "
                "high=float(high_arr[__bar_idx]), "
                "low=float(low_arr[__bar_idx]), "
                "close=float(close_arr[__bar_idx]))"
            )
            lines.append(
                "        __strategy.process_pending_orders("
                "open_=float(open_arr[__bar_idx]), "
                "high=float(high_arr[__bar_idx]), "
                "low=float(low_arr[__bar_idx]), "
                "close=float(close_arr[__bar_idx]))"
            )
        if not body_lines and not self.uses_strategy:
            lines.append("        pass")
        for line in body_lines:
            line = line.replace("\n", "\n        ")
            lines.append(f"        {line}")
        if not body_lines and self.uses_strategy:
            lines.append("        pass")

        dict_items = [f"'{p['title']}': plot_{i}" for i, p in enumerate(self.plots)]
        extras = ["'__drawings': __drawings"]
        if self.uses_strategy:
            extras.append("'__events': __strategy.to_events()")
            extras.append("'__position_size': __strategy.position_size")
            extras.append("'__netprofit': __strategy.netprofit")
            extras.append("'__equity': __strategy.equity")
        ret_parts = dict_items + extras
        lines.append("    return {" + ", ".join(ret_parts) + "}")
        return "\n".join(lines)

    # ---------------------------------------------------------------- statements
    def visit_TypeDef(self, node: ast.TypeDef):
        self.object_mode = True
        fields: list[str] = []
        for stmt in node.body:
            if isinstance(stmt, ast.Assign) and isinstance(stmt.target, ast.Name):
                fields.append(stmt.target.id)
        self.udt_types[node.name] = fields
        return ""  # type definitions are compile-time only

    def visit_EnumDef(self, node: ast.EnumDef):
        # Enums as string constants in object mode
        self.object_mode = True
        return ""

    def visit_Assign(self, node: ast.Assign):
        # Tuple unpack: [a, b, c] = ta.macd(...) / ta.bb(...)
        if isinstance(node.target, ast.Tuple):
            return self._visit_tuple_assign(node)

        if not isinstance(node.target, ast.Name):
            # field assign obj.field := handled via ReAssign/Attribute
            if isinstance(node.target, ast.Attribute):
                self.object_mode = True
                obj = self.visit(node.target.value)
                val = self.visit(node.value)
                return f"{obj}[{node.target.attr!r}] = {val}"
            return ""

        name = node.target.id
        val = self.visit(node.value)
        is_var = hasattr(node, "mode") and isinstance(node.mode, (ast.Var, ast.VarIp))

        if self.in_function:
            self.local_vars.add(name)
            return f"{name} = {val}"

        # Map / scalar object vars (var m = map.new...)
        if name in self.map_vars or name in self.scalar_vars:
            if is_var:
                return f"if __bar_idx == 0:\n    {name} = {val}"
            return f"{name} = {val}"

        # UDT series
        if name in self.udt_vars or self._looks_like_udt_ctor(node.value):
            self.object_mode = True
            self.udt_vars.add(name)
            self.arrays.add(f"{name}_arr")
            if is_var:
                return (
                    f"if __bar_idx == 0:\n"
                    f"    {name}_arr[__bar_idx] = {val}\n"
                    f"else:\n"
                    f"    {name}_arr[__bar_idx] = {name}_arr[__bar_idx - 1]"
                )
            return f"{name}_arr[__bar_idx] = {val}"

        # Detect map.new assignment
        if self._is_map_new(node.value):
            self.object_mode = True
            self.map_vars.add(name)
            if is_var:
                return f"if __bar_idx == 0:\n    {name} = {{}}"
            return f"{name} = {{}}"

        self.arrays.add(f"{name}_arr")
        if is_var:
            return f"{name}_arr[__bar_idx] = {val} if __bar_idx == 0 else {name}_arr[__bar_idx-1]"
        return f"{name}_arr[__bar_idx] = {val}"

    def _visit_tuple_assign(self, node: ast.Assign) -> str:
        """Lower ``[a,b,c] = ta.bb(...)`` / ``ta.macd(...)`` to per-series stores."""
        elts = list(node.target.elts)
        names: list[str] = []
        for el in elts:
            if not isinstance(el, ast.Name):
                return ""
            names.append(el.id)
            self.arrays.add(f"{el.id}_arr")

        # Prefer structured multi-return for known multi-value TA
        if isinstance(node.value, ast.Call):
            call_code = self.visit(node.value)
            # Multi-return forms emit a temp unpack
            if call_code.startswith("numba_bb(") or call_code.startswith("numba_macd("):
                lines = [f"__tup = {call_code}"]
                for i, name in enumerate(names):
                    lines.append(f"{name}_arr[__bar_idx] = __tup[{i}]")
                return "\n".join(lines)

        # Fallback: visit RHS once if it is a simple tuple literal
        if isinstance(node.value, ast.Tuple):
            lines = []
            for name, el in zip(names, node.value.elts, strict=False):
                lines.append(f"{name}_arr[__bar_idx] = {self.visit(el)}")
            return "\n".join(lines)

        # Unknown multi-assign — leave empty (numeric path may break; prefer object later)
        return ""

    def _looks_like_udt_ctor(self, node) -> bool:
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "new" and isinstance(node.func.value, ast.Name):
                return node.func.value.id in self.udt_types
        return False

    def _is_map_new(self, node) -> bool:
        # map.new<...>() or Specialize(map.new, ...)
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Specialize):
                f = f.value
            if isinstance(f, ast.Attribute) and f.attr == "new":
                if isinstance(f.value, ast.Name) and f.value.id == "map":
                    return True
        return False

    def visit_ReAssign(self, node: ast.ReAssign):
        if isinstance(node.target, ast.Attribute):
            self.object_mode = True
            obj = self.visit(node.target.value)
            val = self.visit(node.value)
            # UDT field write: p.x := 1
            return f"{obj}[{node.target.attr!r}] = {val}"
        target = self.visit(node.target)
        val = self.visit(node.value)
        return f"{target} = {val}"

    def visit_Name(self, node: ast.Name):
        if self.in_function and node.id in self.local_vars:
            return node.id
        if node.id in self.map_vars or node.id in self.scalar_vars:
            return node.id
        if node.id in ["open", "high", "low", "close", "volume"]:
            return f"{node.id}_arr[__bar_idx]"
        if node.id in ("bar_index",):
            return "__bar_idx"
        if node.id in self.udt_types:
            return node.id  # type name for .new
        if node.id in _NS:
            return node.id
        if node.id in self.udt_vars:
            return f"{node.id}_arr[__bar_idx]"
        return f"{node.id}_arr[__bar_idx]"

    def visit_Attribute(self, node: ast.Attribute):
        # color.red etc.
        if isinstance(node.value, ast.Name) and node.value.id == "color":
            return repr(self._color_const(node.attr))
        if isinstance(node.value, ast.Name) and node.value.id in self.udt_types:
            # Point.new handled in Call
            return f"{node.value.id}_{node.attr}"
        # strategy.* series/constants
        if isinstance(node.value, ast.Name) and node.value.id == "strategy":
            return self._emit_strategy_attr(node.attr)
        # strategy.oca.reduce / strategy.commission.percent
        if (
            isinstance(node.value, ast.Attribute)
            and isinstance(node.value.value, ast.Name)
            and node.value.value.id == "strategy"
        ):
            parent = node.value.attr
            if parent == "oca" and node.attr in ("none", "cancel", "reduce"):
                return repr(node.attr)
            if parent == "commission" and node.attr in (
                "percent",
                "cash_per_order",
                "cash_per_contract",
            ):
                return repr(node.attr)
            if parent == "direction" and node.attr in ("long", "short", "all"):
                return repr(node.attr)

        val = self.visit(node.value)
        # UDT field read: p.x → p['x'] in object mode
        if self.object_mode:
            # strip series indexing for type-ish access
            if val.endswith("[__bar_idx]"):
                # could be series field or udt series
                base = val
                # If base is a UDT instance expression ending with [__bar_idx]
                return f"{base}[{node.attr!r}]"
            if val in self.map_vars or val in self.scalar_vars:
                return f"{val}[{node.attr!r}]"
        if val.endswith("[__bar_idx]"):
            val = val[:-11]
        return f"{val}_{node.attr}"

    def _emit_strategy_attr(self, attr: str) -> str:
        """Map strategy.long/position_size/… for compile path."""
        if attr in ("long", "short"):
            return repr(attr)
        # Nested constants strategy.oca.reduce etc. come as strategy_oca via Call
        series_map = {
            "position_size": "__strategy.position_size",
            "position_avg_price": "__strategy.position_avg_price",
            "position_entry_name": "__strategy.position_entry_name",
            "netprofit": "__strategy.netprofit",
            "equity": "__strategy.equity",
            "closedtrades": "__strategy.closed_trades",
            "opentrades": "0 if __strategy.position_size == 0 else 1",
            "initial_capital": "__strategy.initial_capital",
        }
        if attr in series_map:
            self.object_mode = True
            self.uses_strategy = True
            return series_map[attr]
        # oca / commission nested attrs: strategy.oca → leave for outer attr
        if attr in ("oca", "commission", "direction", "risk"):
            return f"strategy_{attr}"
        self.object_mode = True
        self.uses_strategy = True
        return f"__strategy.{attr}"

    def _color_const(self, name: str) -> str:
        colors = {
            "red": "#F23645",
            "green": "#22AB94",
            "blue": "#2962FF",
            "white": "#FFFFFF",
            "black": "#000000",
            "gray": "#787B86",
            "yellow": "#FDD835",
            "orange": "#FF6D00",
            "purple": "#7B1FA2",
            "teal": "#089981",
            "aqua": "#00BCD4",
            "lime": "#00E676",
            "maroon": "#880E4F",
            "navy": "#311B92",
            "olive": "#808000",
            "silver": "#B2B5BE",
            "fuchsia": "#E040FB",
        }
        return colors.get(name, "#000000")

    def visit_Specialize(self, node: ast.Specialize):
        # map.new<string,float> → treat as map.new
        return self.visit(node.value)

    def visit_Call(self, node: ast.Call):
        # Resolve function name (unwrap Specialize for map.new<K,V>())
        func = node.func
        if isinstance(func, ast.Specialize):
            func = func.value

        if isinstance(func, ast.Name):
            func_name = func.id
        elif isinstance(func, ast.Attribute):
            if isinstance(func.value, ast.Name) and func.value.id == "log":
                func_name = f"log_{func.attr}"
            elif (
                isinstance(func.value, ast.Name)
                and func.value.id in self.udt_types
                and func.attr == "new"
            ):
                return self._emit_udt_new(func.value.id, node)
            else:
                if isinstance(func.value, ast.Name) and func.value.id in _NS:
                    func_name = f"{func.value.id}_{func.attr}"
                else:
                    val = self.visit(func.value)
                    if val.endswith("[__bar_idx]"):
                        val = val[:-11]
                    func_name = f"{val}_{func.attr}"
        else:
            func_name = "unknown_func"

        args: list[str] = []
        kwargs: dict[str, str] = {}
        for arg in node.args:
            if hasattr(arg, "value"):
                expr = self.visit(arg.value)
                if getattr(arg, "name", None):
                    kwargs[str(arg.name)] = expr
                else:
                    args.append(expr)
            else:
                args.append(self.visit(arg))

        if func_name in ("indicator", "library"):
            return ""
        if func_name == "strategy":
            # Capture declaration kwargs for CompileStrategyBroker
            self.uses_strategy = True
            self.object_mode = True
            for k, v in kwargs.items():
                self.strategy_kwargs[k] = v
            # also positional title is fine to ignore
            return ""

        if func_name == "input" or func_name.startswith("input_"):
            if args:
                return args[0]
            return kwargs.get("defval", "0.0")

        # strategy.entry / close / order / cancel …
        if func_name.startswith("strategy_"):
            return self._emit_strategy_call(func_name, args, kwargs)

        if func_name == "plot":
            title = f"Plot {len(self.plots)}"
            if "title" in kwargs:
                title = kwargs["title"].strip("\"'")
            elif len(args) > 1 and args[1]:
                title = args[1].strip("\"'")
            series_expr = args[0] if args else "np.nan"
            # UDT field already expanded
            self.plots.append({"expr": series_expr, "title": title})
            idx = len(self.plots) - 1
            return f"plot_{idx}[__bar_idx] = {series_expr}"

        # Drawing surface → event list (object mode)
        if func_name in _DRAWING_FUNCS or func_name.endswith("_new") and any(
            func_name.startswith(p) for p in ("label", "line", "box", "table", "polyline")
        ):
            self.object_mode = True
            return self._emit_drawing(func_name, args, kwargs)

        if func_name.startswith("map_"):
            self.object_mode = True
            return self._emit_map(func_name, args, kwargs)

        if func_name in ("log_info", "log_warning", "log_error"):
            return ""

        def _arr(expr: str) -> str:
            return expr.replace("[__bar_idx]", "")

        if func_name == "ta_sma":
            period = kwargs.get("length", args[1] if len(args) > 1 else "14")
            return f"numba_sma({_arr(args[0])}, {period}, __bar_idx)"
        if func_name == "ta_ema":
            period = kwargs.get("length", args[1] if len(args) > 1 else "14")
            return f"numba_ema({_arr(args[0])}, {period}, __bar_idx)"
        if func_name == "ta_rma":
            period = kwargs.get("length", args[1] if len(args) > 1 else "14")
            return f"numba_rma({_arr(args[0])}, {period}, __bar_idx)"
        if func_name == "ta_rsi":
            period = kwargs.get("length", args[1] if len(args) > 1 else "14")
            return f"numba_rsi({_arr(args[0])}, {period}, __bar_idx)"
        if func_name == "ta_highest":
            period = kwargs.get("length", args[1] if len(args) > 1 else "14")
            return f"numba_highest({_arr(args[0])}, {period}, __bar_idx)"
        if func_name == "ta_lowest":
            period = kwargs.get("length", args[1] if len(args) > 1 else "14")
            return f"numba_lowest({_arr(args[0])}, {period}, __bar_idx)"
        if func_name == "ta_stdev":
            period = kwargs.get("length", args[1] if len(args) > 1 else "14")
            return f"numba_stdev({_arr(args[0])}, {period}, __bar_idx)"
        if func_name == "ta_change":
            length = kwargs.get("length", args[1] if len(args) > 1 else "1")
            return f"numba_change({_arr(args[0])}, {length}, __bar_idx)"
        if func_name == "ta_atr":
            # ta.atr(length) uses high/low/close from chart arrays
            length = kwargs.get("length", args[0] if args else "14")
            if len(args) >= 4:
                # legacy ta.atr(high, low, close, length)
                return (
                    f"numba_atr({_arr(args[0])}, {_arr(args[1])}, {_arr(args[2])}, "
                    f"{args[3]}, __bar_idx)"
                )
            return f"numba_atr(high_arr, low_arr, close_arr, {length}, __bar_idx)"
        if func_name == "ta_bb":
            # ta.bb(source, length, mult) or ta.bb(length, mult)
            if len(args) >= 3:
                src, length, mult = args[0], args[1], args[2]
            elif len(args) == 2:
                src, length, mult = "close_arr[__bar_idx]", args[0], args[1]
            else:
                src, length, mult = "close_arr[__bar_idx]", "20", "2.0"
            return f"numba_bb({_arr(src)}, {length}, float({mult}), __bar_idx)"
        if func_name == "ta_macd":
            # ta.macd(source, fast, slow, signal)
            src = args[0] if args else "close_arr[__bar_idx]"
            fast = args[1] if len(args) > 1 else "12"
            slow = args[2] if len(args) > 2 else "26"
            signal = args[3] if len(args) > 3 else "9"
            return f"numba_macd({_arr(src)}, {fast}, {slow}, {signal}, __bar_idx)"

        if func_name in ("nz",):
            repl = args[1] if len(args) > 1 else "0.0"
            return f"numba_nz({args[0]}, {repl})"
        if func_name in ("math_abs", "abs"):
            return f"numba_abs({args[0]})"
        if func_name in ("math_max", "max"):
            return f"numba_max({args[0]}, {args[1]})"
        if func_name in ("math_min", "min"):
            return f"numba_min({args[0]}, {args[1]})"
        if func_name == "math_sqrt":
            return f"np.sqrt({args[0]})"
        if func_name == "na":
            return "np.nan"
        if func_name in ("float", "int", "bool", "string"):
            return args[0] if args else "np.nan"

        return f"{func_name}({', '.join(args)})"

    def _emit_strategy_call(self, func_name: str, args: list[str], kwargs: dict[str, str]) -> str:
        """Emit CompileStrategyBroker method call; force object mode."""
        self.object_mode = True
        self.uses_strategy = True
        method = func_name[len("strategy_") :]  # entry, close, order, …
        # Nested: strategy_oca_reduce is not a call on broker
        if method.startswith("oca_") or method.startswith("commission_"):
            # Constants used as bare names rarely appear as calls
            const = method.split("_")[-1]
            return repr(const)
        if method.startswith("risk_"):
            return ""  # risk.* declaration no-op in compile path for now
        if method in {"long", "short"}:
            return repr(method)

        # Map method names
        broker_method = {
            "entry": "entry",
            "close": "close",
            "close_all": "close_all",
            "order": "order",
            "cancel": "cancel",
            "cancel_all": "cancel_all",
            "exit": "close",  # simplify exit → close
        }.get(method, None)
        if broker_method is None:
            return ""

        # Build kwargs for broker: inject mark price
        parts: list[str] = []
        # positional → named where possible
        names_by_method = {
            "entry": ("id", "direction", "qty", "limit", "stop", "comment"),
            "close": ("id", "qty", "comment"),
            "close_all": ("comment",),
            "order": ("id", "direction", "qty", "limit", "stop", "oca_name", "oca_type", "comment"),
            "cancel": ("id",),
            "cancel_all": (),
        }
        param_names = names_by_method.get(broker_method, ())
        for i, a in enumerate(args):
            if i < len(param_names):
                parts.append(f"{param_names[i]}={a}")
            else:
                parts.append(a)
        for k, v in kwargs.items():
            # map Pine names
            key = k
            if key == "from_entry":
                key = "id"
            parts.append(f"{key}={v}")
        parts.append("price=float(close_arr[__bar_idx])")
        return f"__strategy.{broker_method}({', '.join(parts)})"

    def _emit_udt_new(self, type_name: str, node: ast.Call) -> str:
        self.object_mode = True
        fields = self.udt_types.get(type_name, [])
        args: list[str] = []
        for arg in node.args:
            if hasattr(arg, "value"):
                args.append(self.visit(arg.value))
            else:
                args.append(self.visit(arg))
        items = [f"'__type__': {type_name!r}"]
        for i, f in enumerate(fields):
            v = args[i] if i < len(args) else "np.nan"
            items.append(f"{f!r}: {v}")
        return "{" + ", ".join(items) + "}"

    def _emit_map(self, func_name: str, args: list[str], kwargs: dict[str, str]) -> str:
        if func_name == "map_new":
            return "{}"
        if func_name == "map_put":
            # map.put(id, key, value)
            m, key, val = args[0], args[1], args[2]
            return f"{m}.__setitem__({key}, {val})"
        if func_name == "map_get":
            m, key = args[0], args[1]
            return f"{m}.get({key}, np.nan)"
        if func_name == "map_contains":
            m, key = args[0], args[1]
            return f"({key} in {m})"
        if func_name == "map_remove":
            m, key = args[0], args[1]
            return f"{m}.pop({key}, None)"
        if func_name == "map_clear":
            return f"{args[0]}.clear()"
        if func_name == "map_size":
            return f"len({args[0]})"
        if func_name == "map_keys":
            return f"list({args[0]}.keys())"
        if func_name == "map_values":
            return f"list({args[0]}.values())"
        if func_name == "map_copy":
            return f"dict({args[0]})"
        return f"{func_name}({', '.join(args)})"

    def _emit_drawing(self, func_name: str, args: list[str], kwargs: dict[str, str]) -> str:
        kind = func_name.replace("_new", "").replace("_delete", "")
        if func_name.endswith("_delete"):
            return ""  # MVP: no-op deletes in compile path
        # Build event dict
        parts = [f"'kind': {kind!r}", "'bar': __bar_idx"]
        # positional common patterns
        if kind == "hline":
            parts.append(f"'price': {args[0] if args else 'np.nan'}")
            if "title" in kwargs:
                parts.append(f"'title': {kwargs['title']}")
            elif len(args) > 1:
                parts.append(f"'title': {args[1]}")
            if "color" in kwargs:
                parts.append(f"'color': {kwargs['color']}")
            elif len(args) > 2:
                parts.append(f"'color': {args[2]}")
        elif kind == "bgcolor":
            parts.append(f"'color': {args[0] if args else 'None'}")
        elif kind == "barcolor":
            parts.append(f"'color': {args[0] if args else 'None'}")
        elif kind == "label":
            parts.append(f"'x': {args[0] if args else '__bar_idx'}")
            parts.append(f"'y': {args[1] if len(args) > 1 else 'np.nan'}")
            parts.append(f"'text': {args[2] if len(args) > 2 else repr('')}")
            if "color" in kwargs:
                parts.append(f"'color': {kwargs['color']}")
        elif kind == "line":
            for i, key in enumerate(("x1", "y1", "x2", "y2")):
                parts.append(f"'{key}': {args[i] if i < len(args) else 'np.nan'}")
        elif kind == "box":
            for i, key in enumerate(("left", "top", "right", "bottom")):
                parts.append(f"'{key}': {args[i] if i < len(args) else 'np.nan'}")
        elif kind in ("plotshape", "plotchar", "plotarrow"):
            parts.append(f"'series': {args[0] if args else 'np.nan'}")
            if "title" in kwargs:
                parts.append(f"'title': {kwargs['title']}")
            elif len(args) > 1:
                parts.append(f"'title': {args[1]}")
        elif kind == "fill":
            parts.append(f"'plot1': {args[0] if args else 'None'}")
            parts.append(f"'plot2': {args[1] if len(args) > 1 else 'None'}")
        else:
            for i, a in enumerate(args[:6]):
                parts.append(f"'arg{i}': {a}")
        for k, v in kwargs.items():
            if k not in ("title", "color"):
                parts.append(f"{k!r}: {v}")
        return f"__drawings.append({{{', '.join(parts)}}})"

    # ---------------------------------------------------------------- exprs
    def visit_BinOp(self, node: ast.BinOp):
        left = self.visit(node.left)
        right = self.visit(node.right)
        op = {
            ast.Add: "+",
            ast.Sub: "-",
            ast.Mult: "*",
            ast.Div: "/",
            ast.Mod: "%",
        }.get(type(node.op), "+")
        return f"({left} {op} {right})"

    def visit_Compare(self, node: ast.Compare):
        left = self.visit(node.left)
        ops = []
        for op, comp in zip(node.ops, node.comparators):
            op_str = {
                ast.Gt: ">",
                ast.Lt: "<",
                ast.GtE: ">=",
                ast.LtE: "<=",
                ast.Eq: "==",
                ast.NotEq: "!=",
            }.get(type(op), "==")
            ops.append(f" {op_str} {self.visit(comp)}")
        return f"({left}{''.join(ops)})"

    def visit_Constant(self, node: ast.Constant):
        if isinstance(node.value, str):
            return repr(node.value)
        if node.value is None:
            return "None"
        if isinstance(node.value, bool):
            return "True" if node.value else "False"
        return str(node.value)

    def visit_Expr(self, node: ast.Expr):
        return self.visit(node.value)

    def visit_Subscript(self, node: ast.Subscript):
        arr = self.visit(node.value)
        slice_val = self.visit(node.slice)
        if arr.endswith("[__bar_idx]"):
            base_arr = arr[:-11]
            return f"({base_arr}[__bar_idx - {slice_val}] if __bar_idx >= {slice_val} else np.nan)"
        return f"{arr}[{slice_val}]"

    def visit_If(self, node: ast.If):
        test = self.visit(node.test)
        lines = [f"if {test}:"]
        for stmt in node.body:
            val = self.visit(stmt)
            if val:
                val = val.replace("\n", "\n    ")
                lines.append(f"    {val}")
        if len(lines) == 1:
            lines.append("    pass")
        if node.orelse:
            lines.append("else:")
            n = 0
            for stmt in node.orelse:
                val = self.visit(stmt)
                if val:
                    val = val.replace("\n", "\n    ")
                    lines.append(f"    {val}")
                    n += 1
            if n == 0:
                lines.append("    pass")
        return "\n".join(lines)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        func_name = node.name
        args = [arg.name for arg in node.args if hasattr(arg, "name")]
        self.in_function = True
        self.local_vars = set(args)
        body_lines = []
        for stmt in node.body:
            val = self.visit(stmt)
            if val:
                body_lines.append(val)
        self.in_function = False
        self.local_vars = set()
        deco = "@numba.njit(cache=False)" if not self.object_mode else ""
        lines = []
        if deco:
            lines.append(deco)
        lines.append(f"def {func_name}({', '.join(args)}):")
        if not body_lines:
            lines.append("    pass")
        else:
            for i, line in enumerate(body_lines):
                is_last = i == len(body_lines) - 1
                is_expr = isinstance(node.body[-1], ast.Expr)
                line = line.replace("\n", "\n    ")
                if is_last and is_expr:
                    lines.append(f"    return {line}")
                else:
                    lines.append(f"    {line}")
        self.functions.append("\n".join(lines))
        return ""

    def visit_ForTo(self, node: ast.ForTo):
        target = node.target.id if isinstance(node.target, ast.Name) else self.visit(node.target)
        start = self.visit(node.start)
        end = self.visit(node.end)
        step = self.visit(node.step) if getattr(node, "step", None) else "1"
        was = self.in_function
        self.in_function = True
        self.local_vars.add(target)
        lines = [
            f"{target} = {start}",
            f"__step_{target} = {step}",
            f"while ({target} <= {end}) if __step_{target} > 0 else ({target} >= {end}):",
        ]
        for stmt in node.body:
            val = self.visit(stmt)
            if val:
                val = val.replace("\n", "\n    ")
                lines.append(f"    {val}")
        lines.append(f"    {target} += __step_{target}")
        self.in_function = was
        if not was and target in self.local_vars:
            self.local_vars.discard(target)
        return "\n".join(lines)

    def visit_While(self, node: ast.While):
        test = self.visit(node.test)
        was = self.in_function
        self.in_function = True
        lines = [f"while {test}:"]
        n = 0
        for stmt in node.body:
            val = self.visit(stmt)
            if val:
                val = val.replace("\n", "\n    ")
                lines.append(f"    {val}")
                n += 1
        if n == 0:
            lines.append("    pass")
        self.in_function = was
        return "\n".join(lines)

    def visit_Break(self, node: ast.Break):
        return "break"

    def visit_Continue(self, node: ast.Continue):
        return "continue"

    def visit_BoolOp(self, node: ast.BoolOp):
        op = " and " if isinstance(node.op, ast.And) else " or "
        return f"({op.join(self.visit(v) for v in node.values)})"

    def visit_UnaryOp(self, node: ast.UnaryOp):
        operand = self.visit(node.operand)
        if isinstance(node.op, ast.Not):
            return f"(not {operand})"
        if isinstance(node.op, ast.UAdd):
            return f"(+{operand})"
        if isinstance(node.op, ast.USub):
            return f"(-{operand})"
        return operand

    def visit_Conditional(self, node: ast.Conditional):
        return f"({self.visit(node.body)} if {self.visit(node.test)} else {self.visit(node.orelse)})"

    def visit_Tuple(self, node: ast.Tuple):
        return "(" + ", ".join(self.visit(e) for e in node.elts) + ")"
