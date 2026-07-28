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

import re

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
        "request",
    }
)

# Pure constant namespaces (shape.triangleup, size.small, location.abovebar, …)
_ENUM_NS = frozenset(
    {
        "location",
        "shape",
        "size",
        "position",
        "display",
        "xloc",
        "yloc",
        "extend",
        "scale",
        "format",
        "order",
        "text",
        "session",
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
        self.user_funcs: set[str] = set()  # user-defined function names
        self.series_params: set[str] = set()  # UDF params used as series (history)
        self.series_locals: set[str] = set()  # UDF locals used with history (current fn)
        self.func_series_params: dict[str, set[str]] = {}
        self.func_series_locals: dict[str, list[str]] = {}  # func -> local names needing state arr
        self.func_st_params: dict[str, list[str]] = {}  # func -> transitive __st_* params
        self.func_param_names: dict[str, list[str]] = {}
        self.func_needs_bar: dict[str, bool] = {}
        self.string_series: set[str] = set()  # per-bar string/color series (object dtype)

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
        self._emit_series_local_state(lines, indent="    ")
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
            if arr[:-4] in self.udt_vars or arr[:-4] in self.string_series:
                lines.append(f"    {arr} = np.empty(n_bars, dtype=object)")
            else:
                lines.append(f"    {arr} = np.full(n_bars, np.nan)")
        self._emit_series_local_state(lines, indent="    ")
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

    def _emit_series_local_state(self, lines: list[str], *, indent: str = "    ") -> None:
        """Preallocate persistent arrays for UDF series locals (history across bars)."""
        for func_name, slocs in sorted(self.func_series_locals.items()):
            for s in slocs:
                lines.append(f"{indent}__st_{func_name}_{s} = np.full(n_bars, np.nan)")

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
            if name in self.series_locals:
                return f"{name}_arr[__bar_idx] = {val}"
            return f"{name} = {val}"


        # String / non-numeric const → scalar (object mode), not float series
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            self.object_mode = True
            self.scalar_vars.add(name)
            if is_var:
                return f"if __bar_idx == 0:\n    {name} = {val}"
            return f"{name} = {val}"

        # String/color RHS: bar-constant → scalar; per-bar (ternary colors, …) →
        # object-dtype series. Avoids float64 stores like m_arr[i] = 'EMA' or
        # color_arr[i] = '#22AB94' (TypingError setitem unicode / str→float).
        if self._is_stringy_value(node.value) or self._looks_like_string_expr(val):
            self.object_mode = True
            if self._is_bar_constant_stringy(node.value):
                self.scalar_vars.add(name)
                if is_var:
                    return f"if __bar_idx == 0:\n    {name} = {val}"
                return f"{name} = {val}"
            # Per-bar string/color series (e.g. close > open ? color.green : color.red)
            self.string_series.add(name)
            self.arrays.add(f"{name}_arr")
            if is_var:
                return (
                    f"if __bar_idx == 0:\n"
                    f"    {name}_arr[__bar_idx] = {val}\n"
                    f"else:\n"
                    f"    {name}_arr[__bar_idx] = {name}_arr[__bar_idx - 1]"
                )
            return f"{name}_arr[__bar_idx] = {val}"

        # Map / scalar object vars (var m = map.new...)
        if name in self.map_vars or name in self.scalar_vars:
            if is_var:
                return f"if __bar_idx == 0:\n    {name} = {val}"
            return f"{name} = {val}"

        # Existing string series re-assign / already tracked
        if name in self.string_series:
            self.object_mode = True
            self.arrays.add(f"{name}_arr")
            if is_var:
                return (
                    f"if __bar_idx == 0:\n"
                    f"    {name}_arr[__bar_idx] = {val}\n"
                    f"else:\n"
                    f"    {name}_arr[__bar_idx] = {name}_arr[__bar_idx - 1]"
                )
            return f"{name}_arr[__bar_idx] = {val}"

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

        # array.new*/from/copy/slice / matrix.new* → scalar handle (object mode)
        if self._is_array_or_matrix_handle(node.value):
            self.object_mode = True
            self.scalar_vars.add(name)
            if is_var:
                return f"if __bar_idx == 0:\n    {name} = {val}"
            return f"{name} = {val}"

        self.arrays.add(f"{name}_arr")
        if is_var:
            return f"{name}_arr[__bar_idx] = {val} if __bar_idx == 0 else {name}_arr[__bar_idx-1]"
        return f"{name}_arr[__bar_idx] = {val}"

    _STRINGY_INPUT_ATTRS = frozenset(
        {
            "string",
            "text_area",
            "color",
            "symbol",
            "timeframe",
            "session",
            "source",
        }
    )

    _COLOR_CALL_ATTRS = frozenset({"new", "rgb", "r", "g", "b", "t", "from_gradient"})
    def _is_stringy_value(self, node) -> bool:
        """True when RHS is a string/color value that must not become float64 series."""
        if node is None:
            return False
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return True
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "color":
                return True
            return False
        if isinstance(node, ast.Name):
            return node.id in self.scalar_vars or node.id in self.string_series
        if isinstance(node, ast.Conditional):
            # Ternary colors/strings: either branch stringy is enough
            return self._is_stringy_value(node.body) or self._is_stringy_value(node.orelse)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            # string concat
            return self._is_stringy_value(node.left) or self._is_stringy_value(node.right)
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Specialize):
                f = f.value
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
                ns, attr = f.value.id, f.attr
                if ns == "input" and attr in self._STRINGY_INPUT_ATTRS:
                    return True
                if ns == "color" and attr in self._COLOR_CALL_ATTRS:
                    return True
                if ns == "str" and attr in (
                    "tostring",
                    "format",
                    "replace",
                    "lower",
                    "upper",
                    "trim",
                    "tostring_all",
                ):
                    return True
            if isinstance(f, ast.Name) and f.id in ("str", "tostring"):
                return True
        return False

    def _is_bar_constant_stringy(self, node) -> bool:
        """True for string/color values that do not change per bar (safe as scalars)."""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return True
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "color":
                return True
            return False
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Specialize):
                f = f.value
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
                ns, attr = f.value.id, f.attr
                if ns == "input" and attr in self._STRINGY_INPUT_ATTRS:
                    return True
                # color.new/rgb with constant-ish args still treated as scalar rebind
                if ns == "color" and attr in self._COLOR_CALL_ATTRS:
                    return True
            return False
        if isinstance(node, ast.Name):
            return node.id in self.scalar_vars
        # Conditional / BinOp concat / series refs → per-bar
        return False

    @staticmethod
    def _is_quoted_string_expr(val: str) -> bool:
        """Belt-and-suspenders: visited Python expr is a string literal."""
        if not isinstance(val, str) or len(val) < 2:
            return False
        return (val[0] == val[-1] == "'") or (val[0] == val[-1] == '"')

    @staticmethod
    def _looks_like_string_expr(val: str) -> bool:
        """Heuristic on visited Python: string/color literals, ternaries of strings."""
        import re

        if not isinstance(val, str) or not val:
            return False
        if CompilerVisitor._is_quoted_string_expr(val):
            return True
        # ternary of colors: ('#x' if ... else '#y') or ('green' if ... else 'red')
        if ("'" in val or '"' in val) and ("#" in val or " if " in val):
            if any(tok in val for tok in ("_arr", "numba_", "np.")):
                if re.search(r"""['\"]#""", val) or re.search(
                    r"""['\"][A-Za-z#]""", val
                ):
                    return True
            else:
                return True
        return False

    def _is_array_or_matrix_handle(self, node) -> bool:
        """True when RHS yields an array/matrix object handle (not a float series)."""
        if not isinstance(node, ast.Call):
            return False
        f = node.func
        if isinstance(f, ast.Specialize):
            f = f.value
        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
            if f.value.id == "array" and f.attr in (
                "new",
                "from",
                "copy",
                "slice",
                "new_float",
                "new_int",
                "new_bool",
                "new_string",
                "new_color",
                "new_line",
                "new_label",
                "new_box",
            ):
                return True
            if f.value.id == "matrix" and f.attr.startswith("new"):
                return True
        return False

    # Back-compat alias
    _is_array_or_matrix_new = _is_array_or_matrix_handle

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
        # Series locals must write through their persistent array
        if (
            self.in_function
            and isinstance(node.target, ast.Name)
            and node.target.id in self.series_locals
        ):
            val = self.visit(node.value)
            return f"{node.target.id}_arr[__bar_idx] = {val}"
        target = self.visit(node.target)
        val = self.visit(node.value)
        return f"{target} = {val}"

    def visit_Name(self, node: ast.Name):
        if self.in_function and node.id in self.local_vars:
            # Series-style UDF params are full arrays indexed by current bar
            if node.id in self.series_params:
                return f"{node.id}[__bar_idx]"
            # Series locals: persistent state array passed as {name}_arr
            if node.id in self.series_locals:
                return f"{node.id}_arr[__bar_idx]"
            return node.id
        if node.id in self.map_vars or node.id in self.scalar_vars:
            return node.id
        # Built-in series / scalars (never allocate bare *_arr)
        if node.id == "na":
            return "np.nan"
        if node.id in ("open", "high", "low", "close"):
            return f"{node.id}_arr[__bar_idx]"
        if node.id == "volume":
            return "vol_arr[__bar_idx]"
        if node.id == "hl2":
            return "((high_arr[__bar_idx] + low_arr[__bar_idx]) * 0.5)"
        if node.id == "hlc3":
            return "((high_arr[__bar_idx] + low_arr[__bar_idx] + close_arr[__bar_idx]) / 3.0)"
        if node.id == "ohlc4":
            return (
                "((open_arr[__bar_idx] + high_arr[__bar_idx] + "
                "low_arr[__bar_idx] + close_arr[__bar_idx]) / 4.0)"
            )
        if node.id in ("bar_index",):
            return "__bar_idx"
        # Built-in time series / calendar scalars (no time_arr allocation)
        if node.id == "time":
            # ms timestamp stub: bar index * 60_000
            return "(float(__bar_idx) * 60000.0)"
        if node.id == "timenow":
            return "(float(n_bars) * 60000.0)"
        if node.id in (
            "year",
            "month",
            "dayofmonth",
            "dayofweek",
            "hour",
            "minute",
            "second",
        ):
            defaults = {
                "year": "2020",
                "month": "1",
                "dayofmonth": "1",
                "dayofweek": "1",
                "hour": "0",
                "minute": "0",
                "second": "0",
            }
            return defaults.get(node.id, "0")
        if node.id in ("true", "True"):
            return "True"
        if node.id in ("false", "False"):
            return "False"
        if node.id in self.udt_types:
            return node.id  # type name for .new
        if node.id in _NS:
            return node.id
        if node.id in self.udt_vars or node.id in self.string_series:
            return f"{node.id}_arr[__bar_idx]"
        return f"{node.id}_arr[__bar_idx]"
    def visit_Attribute(self, node: ast.Attribute):
        # color.red etc.
        if isinstance(node.value, ast.Name) and node.value.id == "color":
            return repr(self._color_const(node.attr))
        # math.pi / math.e
        if isinstance(node.value, ast.Name) and node.value.id == "math":
            if node.attr == "pi":
                return "np.pi"
            if node.attr == "e":
                return "np.e"
            # leave method attrs for Call (math.abs → math_abs)
            return f"math_{node.attr}"
        # dayofweek.monday … dayofweek.sunday — integer constants (TV: Sunday=1 … Saturday=7)
        # Must run before fallthrough (visit Name dayofweek → "1" then "1_monday").
        if isinstance(node.value, ast.Name) and node.value.id == "dayofweek":
            m = {
                "sunday": "1",
                "monday": "2",
                "tuesday": "3",
                "wednesday": "4",
                "thursday": "5",
                "friday": "6",
                "saturday": "7",
            }
            return m.get(node.attr.lower(), "1")
        # month.january … month.december — integer constants (1..12)
        if isinstance(node.value, ast.Name) and node.value.id == "month":
            m = {
                "january": "1",
                "february": "2",
                "march": "3",
                "april": "4",
                "may": "5",
                "june": "6",
                "july": "7",
                "august": "8",
                "september": "9",
                "october": "10",
                "november": "11",
                "december": "12",
            }
            return m.get(node.attr.lower(), "1")
        # syminfo.* compile-time stubs
        if isinstance(node.value, ast.Name) and node.value.id == "syminfo":
            stubs = {
                "mintick": "0.01",
                "pointvalue": "1.0",
                "ticker": repr("SYMBOL"),
                "tickerid": repr("SYMBOL"),
                "currency": repr("USD"),
                "basecurrency": repr("USD"),
                "type": repr("stock"),
                "root": repr("SYMBOL"),
                "prefix": repr(""),
                "description": repr("SYMBOL"),
                "timezone": repr("UTC"),
                "session": repr("0930-1600"),
                "period": repr("1D"),
                "mincontract": "1.0",
                "volumetype": repr("base"),
            }
            if node.attr in stubs:
                return stubs[node.attr]
            return "0.0"
        # timeframe.* compile-time stubs
        if isinstance(node.value, ast.Name) and node.value.id == "timeframe":
            if node.attr == "period":
                return repr("1D")
            if node.attr in (
                "isintraday",
                "isdaily",
                "isweekly",
                "ismonthly",
                "isseconds",
                "isminutes",
                "ishours",
            ):
                return "False" if node.attr != "isdaily" else "True"
            if node.attr == "multiplier":
                return "1"
            if node.attr == "in_seconds":
                return "timeframe_in_seconds"
            return repr(node.attr)
        if isinstance(node.value, ast.Name) and node.value.id == "chart":
            if node.attr in ("fg_color", "foreground_color"):
                return repr("#000000")
            if node.attr in ("bg_color", "background_color"):
                return repr("#FFFFFF")
            if node.attr == "is_heikinashi":
                return "False"
            if node.attr == "is_renko":
                return "False"
            if node.attr == "is_kagi":
                return "False"
            if node.attr == "is_linebreak":
                return "False"
            if node.attr == "is_pnf":
                return "False"
            if node.attr == "is_range":
                return "False"
            if node.attr == "left_visible_bar_time":
                return "0.0"
            if node.attr == "right_visible_bar_time":
                return "0.0"
            return repr(node.attr)
        # hline.style_solid / linestyle constants
        if isinstance(node.value, ast.Name) and node.value.id == "hline":
            styles = {
                "style_solid": "solid",
                "style_dashed": "dashed",
                "style_dotted": "dotted",
            }
            if node.attr in styles:
                return repr(styles[node.attr])
            return f"hline_{node.attr}"
        # location.abovebar / shape.triangleup / size.small / position.* / etc.
        if isinstance(node.value, ast.Name) and node.value.id in _ENUM_NS:
            return repr(node.attr)
        # barstate.islast / isfirst / …
        if isinstance(node.value, ast.Name) and node.value.id == "barstate":
            return self._emit_barstate(node.attr)
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
    def _emit_barstate(self, attr: str) -> str:
        """barstate.* flags for compile path."""
        if attr in ("isfirst", "isfirstconfirmedhistory"):
            return "(__bar_idx == 0)"
        if attr in ("islast", "islastconfirmedhistory"):
            return "(__bar_idx == n_bars - 1)"
        if attr == "ishistory":
            return "(__bar_idx < n_bars - 1)"
        if attr == "isrealtime":
            return "False"
        if attr == "isnew":
            return "True"
        if attr == "isconfirmed":
            return "True"
        return "False"

    def _emit_array_or_matrix(
        self, func_name: str, args: list[str], kwargs: dict[str, str]
    ) -> str:
        """Minimal array/matrix surface in object mode."""
        if func_name in (
            "array_new",
            "array_new_float",
            "array_new_int",
            "array_new_bool",
            "array_new_string",
            "array_new_color",
            "array_new_line",
            "array_new_label",
            "array_new_box",
        ):
            size = args[0] if args else "0"
            fill = args[1] if len(args) > 1 else "np.nan"
            return f"([{fill}] * int({size}) if int({size}) > 0 else [])"
        if func_name == "array_from":
            return f"[{', '.join(args)}]" if args else "[]"
        if func_name == "array_copy":
            return f"list({args[0]})" if args else "[]"
        if func_name == "array_slice":
            if len(args) >= 3:
                return f"({args[0]}[int({args[1]}):int({args[2]})])"
            if len(args) == 2:
                return f"({args[0]}[int({args[1]}):])"
            return f"list({args[0]})" if args else "[]"
        if func_name == "array_push":
            return f"{args[0]}.append({args[1]})" if len(args) > 1 else f"{args[0]}.append(np.nan)"
        if func_name == "array_pop":
            return f"({args[0]}.pop() if {args[0]} else np.nan)"
        if func_name == "array_shift":
            return f"({args[0]}.pop(0) if {args[0]} else np.nan)"
        if func_name == "array_unshift":
            if len(args) > 1:
                return f"{args[0]}.insert(0, {args[1]})"
            return f"{args[0]}.insert(0, np.nan)" if args else ""
        if func_name == "array_get":
            return f"({args[0]}[int({args[1]})] if 0 <= int({args[1]}) < len({args[0]}) else np.nan)"
        if func_name == "array_set":
            return (
                f"{args[0]}.__setitem__(int({args[1]}), {args[2]})"
                if len(args) > 2
                else ""
            )
        if func_name == "array_size":
            return f"len({args[0]})"
        if func_name == "array_clear":
            return f"{args[0]}.clear()"
        if func_name == "array_remove":
            if len(args) > 1:
                return (
                    f"({args[0]}.pop(int({args[1]})) "
                    f"if 0 <= int({args[1]}) < len({args[0]}) else np.nan)"
                )
            return f"({args[0]}.pop() if {args[0]} else np.nan)" if args else "np.nan"
        if func_name == "array_includes":
            if len(args) > 1:
                return f"({args[1]} in {args[0]})"
            return "False"
        if func_name == "array_join":
            if len(args) > 1:
                return f"(str({args[1]}).join(str(x) for x in {args[0]}))"
            return f"(''.join(str(x) for x in {args[0]}))" if args else "''"
        if func_name in ("matrix_new", "matrix_new_float", "matrix_new_int"):
            rows = args[0] if args else "0"
            cols = args[1] if len(args) > 1 else "0"
            fill = args[2] if len(args) > 2 else "np.nan"
            return f"[[{fill} for _c in range(int({cols}))] for _r in range(int({rows}))]"
        if func_name == "matrix_get":
            if len(args) >= 3:
                return (
                    f"({args[0]}[int({args[1]})][int({args[2]})] "
                    f"if 0 <= int({args[1]}) < len({args[0]}) "
                    f"and 0 <= int({args[2]}) < (len({args[0]}[0]) if {args[0]} else 0) "
                    f"else np.nan)"
                )
            return "np.nan"
        if func_name == "matrix_set":
            if len(args) >= 4:
                return f"{args[0]}[int({args[1]})][int({args[2]})] = {args[3]}"
            return ""
        if func_name == "matrix_rows":
            return f"len({args[0]})" if args else "0"
        if func_name == "matrix_columns":
            if args:
                return f"(len({args[0]}[0]) if {args[0]} else 0)"
            return "0"
        if func_name == "matrix_fill":
            if len(args) >= 2:
                return (
                    f"[__r.__setitem__(__c, {args[1]}) "
                    f"for __r in {args[0]} for __c in range(len(__r))]"
                )
            return ""
        return f"{func_name}({', '.join(args)})"

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
            if (
                isinstance(func.value, ast.Attribute)
                and isinstance(func.value.value, ast.Name)
                and func.value.value.id == "strategy"
                and func.value.attr in ("opentrades", "closedtrades")
            ):
                # Must not visit opentrades first (count expr) or we get
                # "0 if … else 1_entry_price(0)" which is invalid Python.
                func_name = f"strategy_{func.value.attr}_{func.attr}"
            elif isinstance(func.value, ast.Name) and func.value.id == "log":
                func_name = f"log_{func.attr}"
            elif (
                isinstance(func.value, ast.Name)
                and func.value.id in self.udt_types
                and func.attr == "new"
            ):
                return self._emit_udt_new(func.value.id, node)
            elif isinstance(func.value, ast.Name) and func.value.id in _NS:
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

        if func_name in ("indicator", "library", "study"):
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
            # Prefer explicit defval; else first positional (never title/group strings)
            if "defval" in kwargs:
                return kwargs["defval"]
            if args:
                return args[0]
            # string/bool inputs without defval
            if func_name in ("input_string", "input_text_area"):
                self.object_mode = True
                return "''"
            if func_name == "input_bool":
                return "False"
            return "0.0"

        # strategy.entry / close / order / cancel …
        if func_name.startswith("strategy_opentrades_") or func_name.startswith("strategy_closedtrades_"):
            return self._emit_strategy_trade_query(func_name[len("strategy_"):], args, kwargs)

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

        # array.* / matrix.* → object mode stubs
        if func_name.startswith("array_") or func_name.startswith("matrix_"):
            self.object_mode = True
            return self._emit_array_or_matrix(func_name, args, kwargs)

        if func_name in ("log_info", "log_warning", "log_error"):
            return ""

        if func_name in ("runtime_error", "runtime_error_code"):
            self.object_mode = True
            msg = args[0] if args else repr("runtime.error")
            return f"raise RuntimeError(str({msg}))"

        if func_name == "color_new":
            # color.new(base, transp) — keep base color string
            return args[0] if args else repr("#000000")

        if func_name == "timestamp":
            self.object_mode = True
            return "0"

        if func_name in ("alertcondition", "alert"):
            return ""

        # table.cell / table.cell_set / … (table_new already in drawing path)
        if func_name == "table_cell":
            self.object_mode = True
            return ""
        if func_name in (
            "table_cell_set",
            "table_merge_cells",
            "table_clear",
            "table_delete",
            "table_set_position",
            "table_set_bgcolor",
            "table_set_border_color",
            "table_set_border_width",
            "table_set_frame_color",
            "table_set_frame_width",
        ):
            self.object_mode = True
            return ""

        # str.* / tostring
        if func_name in ("str_tostring", "tostring"):
            self.object_mode = True
            return f"str({args[0]})" if args else "''"
        if func_name == "str_format":
            self.object_mode = True
            return f"str({args[0]})" if args else "''"
        if func_name == "str_length":
            self.object_mode = True
            return f"len(str({args[0]}))" if args else "0"
        if func_name == "str_contains":
            self.object_mode = True
            if len(args) >= 2:
                return f"(str({args[1]}) in str({args[0]}))"
            return "False"
        if func_name == "str_startswith":
            self.object_mode = True
            if len(args) >= 2:
                return f"str({args[0]}).startswith(str({args[1]}))"
            return "False"
        if func_name == "str_endswith":
            self.object_mode = True
            if len(args) >= 2:
                return f"str({args[0]}).endswith(str({args[1]}))"
            return "False"
        if func_name in ("str_replace_all", "str_replace"):
            self.object_mode = True
            if len(args) >= 3:
                return f"str({args[0]}).replace(str({args[1]}), str({args[2]}))"
            return f"str({args[0]})" if args else "''"
        if func_name == "str_lower":
            self.object_mode = True
            return f"str({args[0]}).lower()" if args else "''"
        if func_name == "str_upper":
            self.object_mode = True
            return f"str({args[0]}).upper()" if args else "''"
        if func_name == "str_trim":
            self.object_mode = True
            return f"str({args[0]}).strip()" if args else "''"

        # timeframe.in_seconds(...)
        if func_name == "timeframe_in_seconds":
            # stub: treat as daily-ish (86400s); enough for comparisons / ratios
            return "86400.0"

        # bare v3 security(...) same as request.security passthrough
        if func_name == "security":
            if len(args) >= 3:
                return args[2]
            return "close_arr[__bar_idx]"

        # request.security / security_lower_tf / seed — same-symbol passthrough stub
        if func_name in ("request_security", "request_security_lower_tf", "request_seed"):
            # signature: security(symbol, timeframe, expression, ...)
            if len(args) >= 3:
                return args[2]
            return "close_arr[__bar_idx]"

        # Other request.* APIs — numeric NaN stub
        if func_name.startswith("request_"):
            self.object_mode = True
            return "np.nan"

        # Calendar / time extractors
        if func_name == "dayofweek":
            return "2"
        if func_name in ("hour", "minute", "second"):
            return "0"
        if func_name == "month":
            return "1"
        if func_name == "year":
            return "2020"
        if func_name in ("dayofmonth", "dayofyear"):
            return "1"

        # Bare v3/v4 TA aliases (sma, ema, …) → ta_* so one handler path
        _BARE_TA = {
            "sma": "ta_sma",
            "ema": "ta_ema",
            "rsi": "ta_rsi",
            "rma": "ta_rma",
            "highest": "ta_highest",
            "lowest": "ta_lowest",
            "stdev": "ta_stdev",
            "change": "ta_change",
            "atr": "ta_atr",
            "crossover": "ta_crossover",
            "crossunder": "ta_crossunder",
            "cross": "ta_cross",
            "pivothigh": "ta_pivothigh",
            "pivotlow": "ta_pivotlow",
            "valuewhen": "ta_valuewhen",
            "stoch": "ta_stoch",
            "cci": "ta_cci",
            "vwap": "ta_vwap",
            "tr": "ta_tr",
            "sar": "ta_sar",
            "cum": "ta_cum",
            "percentile_nearest_rank": "ta_percentile_nearest_rank",
        }
        if func_name in _BARE_TA:
            func_name = _BARE_TA[func_name]

        def _arr(expr: str) -> str:
            return expr.replace("[__bar_idx]", "")

        def _is_series_arr(expr: str) -> bool:
            a = _arr(expr)
            return a.endswith("_arr") or a in (
                "open_arr",
                "high_arr",
                "low_arr",
                "close_arr",
                "vol_arr",
            )

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
        if func_name == "ta_crossover":
            a = _arr(args[0]) if args else "close_arr"
            b = _arr(args[1]) if len(args) > 1 else "0.0"
            # scalar series vs series: if b is not an array name, use constant path
            if b.endswith("_arr") or b in (
                "open_arr",
                "high_arr",
                "low_arr",
                "close_arr",
                "vol_arr",
            ):
                return f"numba_crossover({a}, {b}, __bar_idx)"
            return f"numba_crossover_scalar({a}, float({b}), __bar_idx)"
        if func_name == "ta_crossunder":
            a = _arr(args[0]) if args else "close_arr"
            b = _arr(args[1]) if len(args) > 1 else "0.0"
            if b.endswith("_arr") or b in (
                "open_arr",
                "high_arr",
                "low_arr",
                "close_arr",
                "vol_arr",
            ):
                return f"numba_crossunder({a}, {b}, __bar_idx)"
            return f"numba_crossunder_scalar({a}, float({b}), __bar_idx)"
        if func_name == "ta_cross":
            a = _arr(args[0]) if args else "close_arr"
            b = _arr(args[1]) if len(args) > 1 else "0.0"
            if b.endswith("_arr") or b in (
                "open_arr",
                "high_arr",
                "low_arr",
                "close_arr",
                "vol_arr",
            ):
                return (
                    f"(numba_crossover({a}, {b}, __bar_idx) or "
                    f"numba_crossunder({a}, {b}, __bar_idx))"
                )
            return (
                f"(numba_crossover_scalar({a}, float({b}), __bar_idx) or "
                f"numba_crossunder_scalar({a}, float({b}), __bar_idx))"
            )
        if func_name == "ta_tr":
            # ta.tr() / ta.tr(handle_na) — chart high/low/close; optional bool ignored
            if len(args) >= 3 and _is_series_arr(args[0]):
                return (
                    f"numba_tr({_arr(args[0])}, {_arr(args[1])}, {_arr(args[2])}, __bar_idx)"
                )
            return "numba_tr(high_arr, low_arr, close_arr, __bar_idx)"
        if func_name == "ta_cum":
            src = args[0] if args else "close_arr[__bar_idx]"
            return f"numba_cum({_arr(src)}, __bar_idx)"
        if func_name == "ta_valuewhen":
            # Prefer real history scan when cond is a series array; else current source
            if len(args) >= 2 and _is_series_arr(args[0]):
                occ = args[2] if len(args) > 2 else "0"
                return (
                    f"numba_valuewhen({_arr(args[0])}, {_arr(args[1])}, "
                    f"int({occ}), __bar_idx)"
                )
            return args[1] if len(args) > 1 else "np.nan"
        if func_name in ("ta_pivothigh", "ta_pivotlow"):
            # ta.pivothigh(left, right) → high; ta.pivothigh(src, left, right)
            nb = "numba_pivothigh" if func_name == "ta_pivothigh" else "numba_pivotlow"
            default_src = "high_arr" if func_name == "ta_pivothigh" else "low_arr"
            if len(args) >= 3:
                src, left, right = args[0], args[1], args[2]
                return f"{nb}({_arr(src)}, int({left}), int({right}), __bar_idx)"
            if len(args) >= 2:
                left, right = args[0], args[1]
                return f"{nb}({default_src}, int({left}), int({right}), __bar_idx)"
            return f"{nb}({default_src}, 5, 5, __bar_idx)"
        if func_name == "ta_stoch":
            # ta.stoch(source, high, low, length) or ta.stoch(length)
            if len(args) >= 4:
                return (
                    f"numba_stoch({_arr(args[0])}, {_arr(args[1])}, {_arr(args[2])}, "
                    f"int({args[3]}), __bar_idx)"
                )
            length = args[0] if args else "14"
            return f"numba_stoch(close_arr, high_arr, low_arr, int({length}), __bar_idx)"
        if func_name == "ta_cci":
            # ta.cci(source, length) or ta.cci(length) → hlc3 approx as close
            if len(args) >= 2:
                return f"numba_cci({_arr(args[0])}, int({args[1]}), __bar_idx)"
            length = args[0] if args else "20"
            # typical price via (h+l+c)/3 not available as array — use close MVP
            return f"numba_cci(close_arr, int({length}), __bar_idx)"
        if func_name == "ta_vwap":
            # ta.vwap / ta.vwap(source) — cumulative typical*vol / cum vol
            if args and _is_series_arr(args[0]):
                return f"numba_vwap({_arr(args[0])}, vol_arr, __bar_idx)"
            # default source = hlc3; approximate with (h+l+c)/3 via close as MVP if no src
            # Use close for bare form; better: build from chart (still correct enough)
            return "numba_vwap(close_arr, vol_arr, __bar_idx)"
        if func_name == "ta_sar":
            # ta.sar(start, inc, max) using chart high/low
            start = args[0] if args else "0.02"
            inc = args[1] if len(args) > 1 else "0.02"
            maximum = args[2] if len(args) > 2 else "0.2"
            if len(args) >= 5 and _is_series_arr(args[0]):
                return (
                    f"numba_sar({_arr(args[0])}, {_arr(args[1])}, float({args[2]}), "
                    f"float({args[3]}), float({args[4]}), __bar_idx)"
                )
            return (
                f"numba_sar(high_arr, low_arr, float({start}), float({inc}), "
                f"float({maximum}), __bar_idx)"
            )
        if func_name == "ta_percentile_nearest_rank":
            # ta.percentile_nearest_rank(source, length, percentage)
            if len(args) >= 3:
                return (
                    f"numba_percentile_nearest_rank({_arr(args[0])}, int({args[1]}), "
                    f"float({args[2]}), __bar_idx)"
                )
            src = args[0] if args else "close_arr[__bar_idx]"
            length = args[1] if len(args) > 1 else "14"
            return f"numba_percentile_nearest_rank({_arr(src)}, int({length}), 50.0, __bar_idx)"


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
        if func_name == "math_exp":
            return f"np.exp({args[0]})"
        if func_name == "math_log":
            return f"np.log({args[0]})"
        if func_name == "math_log10":
            return f"np.log10({args[0]})"
        if func_name == "math_pow":
            return f"({args[0]} ** {args[1]})" if len(args) > 1 else f"({args[0]} ** 2)"
        if func_name in ("math_round", "round"):
            return f"float(np.round({args[0]}))" if args else "0.0"
        if func_name in ("math_floor", "floor"):
            return f"float(np.floor({args[0]}))" if args else "0.0"
        if func_name in ("math_ceil", "ceil"):
            return f"float(np.ceil({args[0]}))" if args else "0.0"
        if func_name == "math_sign":
            return f"float(np.sign({args[0]}))" if args else "0.0"
        if func_name == "math_sum":
            period = args[1] if len(args) > 1 else "14"
            src_e = args[0] if args else "close_arr[__bar_idx]"
            return f"(numba_sma({_arr(src_e)}, {period}, __bar_idx) * float({period}))"
        if func_name == "math_avg":
            period = args[1] if len(args) > 1 else "14"
            src_e = args[0] if args else "close_arr[__bar_idx]"
            return f"numba_sma({_arr(src_e)}, {period}, __bar_idx)"
        if func_name == "math_random":
            self.object_mode = True
            return "0.5"
        if func_name == "color_rgb":
            self.object_mode = True
            return repr("#000000")
        if func_name in ("color_r", "color_g", "color_b", "color_t"):
            return "0.0"
        if func_name in ("math_cos", "cos"):
            return f"np.cos({args[0]})" if args else "np.nan"
        if func_name in ("math_sin", "sin"):
            return f"np.sin({args[0]})" if args else "np.nan"
        if func_name in ("math_tan", "tan"):
            return f"np.tan({args[0]})" if args else "np.nan"
        if func_name in ("math_asin", "asin"):
            return f"np.arcsin({args[0]})" if args else "np.nan"
        if func_name in ("math_acos", "acos"):
            return f"np.arccos({args[0]})" if args else "np.nan"
        if func_name in ("math_atan", "atan"):
            return f"np.arctan({args[0]})" if args else "np.nan"
        if func_name == "math_atan2":
            if len(args) >= 2:
                return f"np.arctan2({args[0]}, {args[1]})"
            return "np.nan"
        if func_name == "na":
            return "np.nan"
        if func_name in ("float", "int", "bool", "string"):
            return args[0] if args else "np.nan"

        # User-defined function: pass full series arrays for series-style params
        if func_name in self.user_funcs:
            param_names = self.func_param_names.get(func_name, [])
            series_set = self.func_series_params.get(func_name, set())
            series_locals = self.func_series_locals.get(func_name, [])
            st_params = self.func_st_params.get(func_name, [])
            call_args: list[str] = []
            for i, a in enumerate(args):
                pname = param_names[i] if i < len(param_names) else None
                if pname and pname in series_set and a.endswith("[__bar_idx]"):
                    call_args.append(a[: -len("[__bar_idx]")])
                else:
                    call_args.append(a)
            # Own series-local state arrays (allocated in execute_script_compiled)
            for s in series_locals:
                call_args.append(f"__st_{func_name}_{s}")
            # Transitive series-local state from nested UDF calls
            for st in st_params:
                call_args.append(st)
            # Chart series / bar index are free vars under njit — pass explicitly
            if self.func_needs_bar.get(func_name) or series_set or series_locals or st_params:
                for extra in (
                    "open_arr",
                    "high_arr",
                    "low_arr",
                    "close_arr",
                    "vol_arr",
                    "__bar_idx",
                ):
                    call_args.append(extra)
            return f"{func_name}({', '.join(call_args)})"

        # Unknown call: object mode so we don't hard-fail under nopython
        # (still may NameError — better than invalid njit)
        if func_name not in ("unknown_func",):
            self.object_mode = True
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
        # strategy.opentrades.entry_price(n) etc. (see visit_Call)
        if method.startswith("opentrades_") or method.startswith("closedtrades_"):
            return self._emit_strategy_trade_query(method, args, kwargs)

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

        # positional → named where possible (Pine names)
        names_by_method = {
            "entry": ("id", "direction", "qty", "limit", "stop", "comment"),
            "close": ("id", "qty", "comment"),
            "close_all": ("comment",),
            "order": ("id", "direction", "qty", "limit", "stop", "oca_name", "oca_type", "comment"),
            "cancel": ("id",),
            "cancel_all": (),
        }
        # Pine strategy.exit(id, from_entry, qty, qty_percent, profit, limit, loss, stop, …)
        # First positional is the *exit order* name, not the position id. from_entry → id.
        if method == "exit":
            param_names: tuple[str, ...] = (
                "_exit_id",
                "id",
                "qty",
                "qty_percent",
                "profit",
                "limit",
                "loss",
                "stop",
            )
        else:
            param_names = names_by_method.get(broker_method, ())

        # Collect into ordered dict so kwargs never emit duplicate keys
        seen: dict[str, str] = {}
        for i, a in enumerate(args):
            if i < len(param_names):
                seen[param_names[i]] = a
        for k, v in kwargs.items():
            key = k
            if key == "from_entry":
                key = "id"
            elif method == "exit" and key == "id":
                # keyword id= is the exit order name, not the position id
                key = "_exit_id"
            seen[key] = v  # later wins

        if method == "exit":
            exit_id = seen.pop("_exit_id", None)
            if exit_id is not None and "comment" not in seen:
                seen["comment"] = exit_id

        seen["price"] = "float(close_arr[__bar_idx])"
        parts = [f"{k}={v}" for k, v in seen.items()]
        return f"__strategy.{broker_method}({', '.join(parts)})"

    def _emit_strategy_trade_query(self, method: str, args: list[str], kwargs: dict[str, str]) -> str:
        """Stub strategy.opentrades.* / strategy.closedtrades.* method calls."""
        self.object_mode = True
        self.uses_strategy = True
        if method.startswith("opentrades_"):
            attr = method[len("opentrades_") :]
            if attr == "entry_price":
                return "(__strategy.position_avg_price if __strategy.position_size != 0 else np.nan)"
            if attr == "size":
                return "__strategy.position_size"
            if attr == "entry_id":
                return "(__strategy.position_entry_name if __strategy.position_size != 0 else '')"
            if attr in (
                "entry_bar_index",
                "profit",
                "commission",
                "max_runup",
                "max_drawdown",
                "comment",
            ):
                return "0.0"
            return "0.0"
        if method.startswith("closedtrades_"):
            attr = method[len("closedtrades_") :]
            if attr in ("exit_bar_index", "entry_bar_index"):
                return "0"
            if attr == "entry_id" or attr == "exit_id":
                return "''"
            return "0.0"
        return "0.0"
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
        # History on UDF params/locals: use array base, never index a scalar float
        if (
            self.in_function
            and isinstance(node.value, ast.Name)
            and node.value.id in self.local_vars
        ):
            name = node.value.id
            slice_val = self.visit(node.slice)
            if name in self.series_params:
                base = name
            elif name in self.series_locals:
                base = f"{name}_arr"
            else:
                # Late discovery (param history): keep param-as-array convention
                self.series_params.add(name)
                base = name
            return f"({base}[__bar_idx - {slice_val}] if __bar_idx >= {slice_val} else np.nan)"

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
        arg_set = set(args)
        self.user_funcs.add(func_name)
        prev_series = set(self.series_params)
        prev_series_locals = set(self.series_locals)
        self.in_function = True
        self.local_vars = set(args)

        # Pass 0: assigned locals + names used under history subscript
        assigned: set[str] = set()
        history_names: set[str] = set()
        for stmt in node.body:
            self._collect_assigned_names(stmt, assigned)
            self._collect_history_names(stmt, history_names)

        # Params used with history → series_params (full arrays from caller)
        self.series_params = set()
        for stmt in node.body:
            self._mark_series_params(stmt)
        # Only param names from this function count as series_params for body gen
        series_for_func = {a for a in args if a in self.series_params or a in history_names}
        # Body gen sees only this function's series params (avoid cross-fn name clash)
        self.series_params = set(series_for_func)

        # Assigned non-params used with history → series_locals (persistent state arrs)
        series_locals = sorted(n for n in history_names if n in assigned and n not in arg_set)
        self.series_locals = set(series_locals)
        self.local_vars |= assigned

        body_lines = []
        for stmt in node.body:
            val = self.visit(stmt)
            if val:
                body_lines.append(val)

        self.in_function = False
        self.local_vars = set()
        # Restore + accumulate series_params for call-site lowering of this fn's args
        self.series_params = prev_series | series_for_func
        self.series_locals = prev_series_locals
        self.func_series_params[func_name] = series_for_func
        self.func_series_locals[func_name] = list(series_locals)
        self.func_param_names[func_name] = list(args)

        # njit forbids free vars: if body indexes chart series or uses __bar_idx
        # (series history, close/high/…, bar_index, or nested UDF that needs ctx),
        # inject full chart context as trailing params.
        body_text = "\n".join(body_lines)
        _ctx_tokens = (
            "__bar_idx",
            "open_arr",
            "high_arr",
            "low_arr",
            "close_arr",
            "vol_arr",
        )
        # Nested callees may need __st_* state arrays passed through this frame
        st_refs = sorted(set(re.findall(r"__st_[A-Za-z_][A-Za-z0-9_]*", body_text)))
        self.func_st_params[func_name] = st_refs

        sl_params = [f"{s}_arr" for s in series_locals]
        needs_ctx = (
            any(tok in body_text for tok in _ctx_tokens)
            or bool(series_for_func)
            or bool(series_locals)
            or bool(st_refs)
        )
        param_list = list(args)
        for p in sl_params:
            if p not in param_list:
                param_list.append(p)
        for p in st_refs:
            if p not in param_list:
                param_list.append(p)
        if needs_ctx:
            extra = ["open_arr", "high_arr", "low_arr", "close_arr", "vol_arr", "__bar_idx"]
            param_list.extend(e for e in extra if e not in param_list)
            self.func_needs_bar[func_name] = True
        else:
            self.func_needs_bar[func_name] = False
        deco = "@numba.njit(cache=False)" if not self.object_mode else ""
        lines = []
        if deco:
            lines.append(deco)
        lines.append(f"def {func_name}({', '.join(param_list)}):")
        if not body_lines:
            lines.append("    pass")
        else:
            last_ast = node.body[-1] if node.body else None
            # Only wrap a pure expression result — never `if`/`for`/`while` as `return if …`
            returnable = isinstance(last_ast, ast.Expr) and not isinstance(
                getattr(last_ast, "value", None),
                (ast.If, ast.ForTo, ast.While, ast.ForIn),
            )
            for i, line in enumerate(body_lines):
                is_last = i == len(body_lines) - 1
                line = line.replace("\n", "\n    ")
                stripped = line.lstrip()
                if is_last and returnable and not stripped.startswith(
                    ("if ", "for ", "while ", "else:", "elif ", "try:", "with ")
                ):
                    lines.append(f"    return {line}")
                else:
                    lines.append(f"    {line}")
        self.functions.append("\n".join(lines))
        return ""

    def _mark_series_params(self, node) -> None:
        """Walk a subtree and mark local names used under Subscript as series params."""
        if node is None or not hasattr(node, "__dict__"):
            return
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            if node.value.id in self.local_vars:
                self.series_params.add(node.value.id)
        for child in node.__dict__.values():
            if isinstance(child, list):
                for c in child:
                    self._mark_series_params(c)
            else:
                self._mark_series_params(child)

    def _collect_assigned_names(self, node, out: set[str]) -> None:
        """Collect Name targets of Assign/ReAssign in a subtree."""
        if node is None or not hasattr(node, "__dict__"):
            return
        if isinstance(node, (ast.Assign, ast.ReAssign)):
            t = node.target
            if isinstance(t, ast.Name):
                out.add(t.id)
            elif isinstance(t, ast.Tuple):
                for el in getattr(t, "elts", []) or []:
                    if isinstance(el, ast.Name):
                        out.add(el.id)
        for child in node.__dict__.values():
            if isinstance(child, list):
                for c in child:
                    self._collect_assigned_names(c, out)
            else:
                self._collect_assigned_names(child, out)

    def _collect_history_names(self, node, out: set[str]) -> None:
        """Collect Name bases of history Subscripts (x[1], x[n])."""
        if node is None or not hasattr(node, "__dict__"):
            return
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            out.add(node.value.id)
        for child in node.__dict__.values():
            if isinstance(child, list):
                for c in child:
                    self._collect_history_names(c, out)
            else:
                self._collect_history_names(child, out)

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
