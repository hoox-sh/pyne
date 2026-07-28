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

import keyword
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
        "console",
        "runtime",
        "barmerge",
        "barstate",
    }
)

# Pine identifiers that collide with Python builtins used in emitted code
# (e.g. param `len` shadows `len(buffer)` inside array.get emission).
_PY_RESERVED = frozenset(
    {
        "len",
        "max",
        "min",
        "sum",
        "abs",
        "round",
        "int",
        "float",
        "bool",
        "str",
        "list",
        "dict",
        "set",
        "type",
        "id",
        "open",
        "input",
        "map",
        "filter",
        "range",
        "all",
        "any",
        "zip",
        "sorted",
        "reversed",
        "enumerate",
        "print",
        "format",
        "pow",
        "hash",
        "vars",
        "dir",
        "next",
        "iter",
        "slice",
        "callable",
        "super",
        "object",
        "property",
        "bytes",
        "bytearray",
        "complex",
        "divmod",
        "bin",
        "hex",
        "oct",
        "ord",
        "chr",
        "ascii",
        "repr",
        "eval",
        "exec",
        "compile",
        "globals",
        "locals",
        "memoryview",
        "frozenset",
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

_STYLE_NS = frozenset(
    {
        "label",
        "plot",
        "line",
        "box",
        "table",
        "hline",
        "polyline",
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
        self.func_needs_strategy: dict[str, bool] = {}
        self.string_series: set[str] = set()  # per-bar string/color series (object dtype)
        self._expr_cum_i: int = 0  # synthetic state arrays for cum(expr)
        # Pine name → safe Python identifier within current UDF scope
        self.ident_map: dict[str, str] = {}
        # When True, visit_If emits `return` on tail expressions (UDF result if-expr)
        self.if_return_mode: bool = False

    @staticmethod
    def _safe_ident(name: str) -> str:
        """Avoid shadowing Python builtins/keywords used in generated code."""
        if not name:
            return name
        if name in _PY_RESERVED or keyword.iskeyword(name):
            return f"{name}_"
        return name

    def _py_ident(self, name: str) -> str:
        """Resolve a Pine local/param name to the emitted Python identifier."""
        if name in self.ident_map:
            return self.ident_map[name]
        safe = self._safe_ident(name)
        if safe != name:
            self.ident_map[name] = safe
        return safe

    @staticmethod
    def _resolve_args(
        args: list[str],
        kwargs: dict[str, str],
        names: tuple[str, ...],
        *,
        aliases: dict[str, str] | None = None,
    ) -> list[str]:
        """Merge positional + keyword args into Pine parameter order.

        Keyword-only calls like ``array.get(id=x, index=0)`` otherwise leave
        ``args`` empty and crash on ``args[0]``.
        """
        aliases = aliases or {}
        out: list[str] = []
        for i, name in enumerate(names):
            if i < len(args):
                out.append(args[i])
                continue
            if name in kwargs:
                out.append(kwargs[name])
                continue
            # common aliases (initial_value → fill, etc.)
            found = False
            for alt, canon in aliases.items():
                if canon == name and alt in kwargs:
                    out.append(kwargs[alt])
                    found = True
                    break
            if not found:
                break
        return out

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
            py = self._py_ident(name)
            if name in self.series_locals:
                return f"{py}_arr[__bar_idx] = {val}"
            return f"{py} = {val}"


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
        if self._is_drawing_new(node.value):
            self.object_mode = True
            self.scalar_vars.add(name)
            if is_var:
                return f"if __bar_idx == 0:\n    {name} = {val}"
            return f"{name} = {val}"



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

    def _is_drawing_new(self, node) -> bool:
        """True when RHS is label/line/box/table/polyline/linefill.new(...)."""
        if not isinstance(node, ast.Call):
            return False
        f = node.func
        if isinstance(f, ast.Specialize):
            f = f.value
        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
            if f.value.id in ("label", "line", "box", "table", "polyline", "linefill") and f.attr == "new":
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
            py = self._py_ident(node.target.id)
            return f"{py}_arr[__bar_idx] = {val}"
        if self.in_function and isinstance(node.target, ast.Name):
            self.local_vars.add(node.target.id)
            py = self._py_ident(node.target.id)
            val = self.visit(node.value)
            return f"{py} = {val}"
        target = self.visit(node.target)
        val = self.visit(node.value)
        return f"{target} = {val}"

    def visit_Name(self, node: ast.Name):
        if self.in_function and node.id in self.local_vars:
            py = self._py_ident(node.id)
            # Series-style UDF params are full arrays indexed by current bar
            if node.id in self.series_params:
                return f"{py}[__bar_idx]"
            # Series locals: persistent state array passed as {name}_arr
            if node.id in self.series_locals:
                return f"{py}_arr[__bar_idx]"
            return py
        if node.id in self.map_vars or node.id in self.scalar_vars:
            return self._py_ident(node.id) if node.id in self.ident_map else node.id
        # Built-in series / scalars (never allocate bare *_arr)
        if node.id == "tr":
            return "numba_tr(high_arr, low_arr, close_arr, __bar_idx)"
        if node.id == "obv":
            return "numba_obv(close_arr, vol_arr, __bar_idx)"
        if node.id == "na":
            return "np.nan"
        if node.id == "color":
            self.object_mode = True
            return repr("#000000")
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
        if node.id == "last_bar_index":
            return "(n_bars - 1)"
        if node.id == "last_bar_time":
            return "(float(n_bars - 1) * 60000.0)"
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
        # UDF names used as values (rare) — not series
        if node.id in self.user_funcs:
            return node.id
        if node.id in self.udt_vars or node.id in self.string_series:
            return f"{node.id}_arr[__bar_idx]"
        return f"{node.id}_arr[__bar_idx]"
    def visit_Attribute(self, node: ast.Attribute):
        # color.red etc.
        if isinstance(node.value, ast.Name) and node.value.id == "ta":
            if node.attr == "tr":
                return "numba_tr(high_arr, low_arr, close_arr, __bar_idx)"
            if node.attr == "obv":
                return "numba_obv(close_arr, vol_arr, __bar_idx)"
        if isinstance(node.value, ast.Name) and node.value.id == "color":
            return repr(self._color_const(node.attr))
        # Must run before fallthrough (visit Name label → "label" then "label_style_x").
        if isinstance(node.value, ast.Name) and node.value.id in _STYLE_NS:
            if node.attr.startswith("style_"):
                return repr(node.attr)
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
        """Minimal array/matrix surface in object mode.

        Resolves keyword-only calls (``array.get(id=…, index=…)``) and guards
        short arg lists so transpile never raises IndexError.
        """
        ra = self._resolve_args

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
            a = ra(
                args,
                kwargs,
                ("size", "initial_value"),
                aliases={"initial": "initial_value", "value": "initial_value"},
            )
            size = a[0] if a else (kwargs.get("size") or "0")
            fill = a[1] if len(a) > 1 else "np.nan"
            return f"([{fill}] * int({size}) if int({size}) > 0 else [])"
        if func_name == "array_sort":
            # Mutates in place; return id (Pine void / chain-friendly)
            a = ra(args, kwargs, ("id", "order"))
            if not a:
                return "[]"
            if len(a) > 1:
                # order.ascending / order.descending → 'ascending' / 'descending'
                return (
                    f"({a[0]}.sort(reverse=({a[1]} in "
                    f"('descending', 'desc', -1, True))), {a[0]})[1]"
                )
            return f"({a[0]}.sort(), {a[0]})[1]"
        if func_name == "array_reverse":
            a = ra(args, kwargs, ("id",))
            return f"({a[0]}.reverse(), {a[0]})[1]" if a else "[]"
        if func_name == "array_from":
            return f"[{', '.join(args)}]" if args else "[]"
        if func_name == "array_copy":
            a = ra(args, kwargs, ("id",))
            return f"list({a[0]})" if a else "[]"
        if func_name == "array_slice":
            a = ra(args, kwargs, ("id", "index_from", "index_to"))
            if len(a) >= 3:
                return f"({a[0]}[int({a[1]}):int({a[2]})])"
            if len(a) == 2:
                return f"({a[0]}[int({a[1]}):])"
            return f"list({a[0]})" if a else "[]"
        if func_name == "array_push":
            a = ra(args, kwargs, ("id", "value"))
            if len(a) > 1:
                return f"{a[0]}.append({a[1]})"
            if a:
                return f"{a[0]}.append(np.nan)"
            return ""
        if func_name == "array_pop":
            a = ra(args, kwargs, ("id",))
            return f"({a[0]}.pop() if {a[0]} else np.nan)" if a else "np.nan"
        if func_name == "array_shift":
            a = ra(args, kwargs, ("id",))
            return f"({a[0]}.pop(0) if {a[0]} else np.nan)" if a else "np.nan"
        if func_name == "array_unshift":
            a = ra(args, kwargs, ("id", "value"))
            if len(a) > 1:
                return f"{a[0]}.insert(0, {a[1]})"
            if a:
                return f"{a[0]}.insert(0, np.nan)"
            return ""
        if func_name == "array_get":
            a = ra(args, kwargs, ("id", "index"))
            if len(a) >= 2:
                return (
                    f"({a[0]}[int({a[1]})] if 0 <= int({a[1]}) < len({a[0]}) else np.nan)"
                )
            return "np.nan"
        if func_name == "array_set":
            a = ra(args, kwargs, ("id", "index", "value"))
            if len(a) > 2:
                return f"{a[0]}.__setitem__(int({a[1]}), {a[2]})"
            return ""
        if func_name == "array_size":
            a = ra(args, kwargs, ("id",))
            return f"len({a[0]})" if a else "0"
        if func_name == "array_clear":
            a = ra(args, kwargs, ("id",))
            return f"{a[0]}.clear()" if a else ""
        if func_name == "array_remove":
            a = ra(args, kwargs, ("id", "index"))
            if len(a) > 1:
                return (
                    f"({a[0]}.pop(int({a[1]})) "
                    f"if 0 <= int({a[1]}) < len({a[0]}) else np.nan)"
                )
            if a:
                return f"({a[0]}.pop() if {a[0]} else np.nan)"
            return "np.nan"
        if func_name == "array_includes":
            a = ra(args, kwargs, ("id", "value"))
            if len(a) > 1:
                return f"({a[1]} in {a[0]})"
            return "False"
        if func_name == "array_join":
            a = ra(args, kwargs, ("id", "separator"))
            if len(a) > 1:
                return f"(str({a[1]}).join(str(x) for x in {a[0]}))"
            if a:
                return f"(''.join(str(x) for x in {a[0]}))"
            return "''"
        if func_name in ("matrix_new", "matrix_new_float", "matrix_new_int"):
            a = ra(
                args,
                kwargs,
                ("rows", "columns", "initial_value"),
                aliases={
                    "cols": "columns",
                    "initial": "initial_value",
                    "value": "initial_value",
                },
            )
            rows = a[0] if a else "0"
            cols = a[1] if len(a) > 1 else "0"
            fill = a[2] if len(a) > 2 else "np.nan"
            return f"[[{fill} for _c in range(int({cols}))] for _r in range(int({rows}))]"
        if func_name == "matrix_get":
            a = ra(args, kwargs, ("id", "row", "column"), aliases={"col": "column"})
            if len(a) >= 3:
                return (
                    f"({a[0]}[int({a[1]})][int({a[2]})] "
                    f"if 0 <= int({a[1]}) < len({a[0]}) "
                    f"and 0 <= int({a[2]}) < (len({a[0]}[0]) if {a[0]} else 0) "
                    f"else np.nan)"
                )
            return "np.nan"
        if func_name == "matrix_set":
            a = ra(
                args,
                kwargs,
                ("id", "row", "column", "value"),
                aliases={"col": "column"},
            )
            if len(a) >= 4:
                return f"{a[0]}[int({a[1]})][int({a[2]})] = {a[3]}"
            return ""
        if func_name == "matrix_rows":
            a = ra(args, kwargs, ("id",))
            return f"len({a[0]})" if a else "0"
        if func_name == "matrix_columns":
            a = ra(args, kwargs, ("id",))
            if a:
                return f"(len({a[0]}[0]) if {a[0]} else 0)"
            return "0"
        if func_name == "matrix_fill":
            a = ra(args, kwargs, ("id", "value"))
            if len(a) >= 2:
                return (
                    f"[__r.__setitem__(__c, {a[1]}) "
                    f"for __r in {a[0]} for __c in range(len(__r))]"
                )
            return ""
        if func_name == "array_avg":
            a = ra(args, kwargs, ("id",))
            return f"(sum({a[0]}) / len({a[0]}) if {a[0]} else np.nan)" if a else "np.nan"
        if func_name == "array_min":
            a = ra(args, kwargs, ("id",))
            return f"(min({a[0]}) if {a[0]} else np.nan)" if a else "np.nan"
        if func_name == "array_max":
            a = ra(args, kwargs, ("id",))
            return f"(max({a[0]}) if {a[0]} else np.nan)" if a else "np.nan"
        if func_name == "array_sum":
            a = ra(args, kwargs, ("id",))
            return f"(sum({a[0]}) if {a[0]} else 0)" if a else "0"
        if func_name == "array_first":
            a = ra(args, kwargs, ("id",))
            return f"({a[0]}[0] if {a[0]} else np.nan)" if a else "np.nan"
        if func_name == "array_last":
            a = ra(args, kwargs, ("id",))
            return f"({a[0]}[-1] if {a[0]} else np.nan)" if a else "np.nan"
        # Unknown array_*/matrix_* — no-op-ish stub rather than crash
        if args:
            return f"{func_name}({', '.join(args)})"
        if kwargs:
            parts = [f"{k}={v}" for k, v in kwargs.items()]
            return f"{func_name}({', '.join(parts)})"
        return "np.nan"
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

        if func_name in ("indicator", "study"):
            return ""
        if func_name == "library":
            # Libraries: force object mode; unknown imports/exports no-op rather than crash
            self.object_mode = True
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

        if (
            func_name.startswith("label_set_")
            or func_name.startswith("line_set_")
            or func_name.startswith("box_set_")
            or func_name.startswith("polyline_set_")
            or func_name.startswith("table_set_")
            or func_name.startswith("table_cell_set")
            or func_name.startswith("linefill_set_")
        ):
            self.object_mode = True
            return self._emit_drawing_set(func_name, args, kwargs)
        if (
            func_name.startswith("label_get_")
            or func_name.startswith("line_get_")
            or func_name.startswith("box_get_")
        ):
            self.object_mode = True
            return "''" if "text" in func_name else "np.nan"

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

        if func_name.startswith("console_"):
            return ""
        if func_name in ("log_info", "log_warning", "log_error"):
            return ""

        if func_name in ("runtime_error", "runtime_error_code"):
            self.object_mode = True
            msg = args[0] if args else repr("runtime.error")
            return f"raise RuntimeError(str({msg}))"

        if func_name == "color_from_gradient":
            # color.from_gradient(value, bottom, top, bottom_color, top_color)
            # Weak stub: pick top/bottom color by midpoint (enough for plot colors)
            self.object_mode = True
            if len(args) >= 5:
                return (
                    f"({args[4]} if float({args[0]}) > "
                    f"(float({args[1]}) + float({args[2]})) / 2.0 else {args[3]})"
                )
            if len(args) >= 4:
                return args[3]
            return repr("#000000")
        if func_name == "color_new":
            # color.new(base, transp) — keep base color string
            return args[0] if args else repr("#000000")

        if func_name == "time":
            return "(float(__bar_idx) * 60000.0)"
        if func_name in ("time_close",):
            return "(float(__bar_idx) * 60000.0 + 59999.0)"
        if func_name == "timeframe_from_seconds":
            return repr("1D")
        if func_name == "timeframe_change":
            return "False"
        if func_name == "timestamp":
            self.object_mode = True
            return "0"

        if func_name in ("alertcondition", "alert"):
            return ""

        # UDF calls win over bare TA aliases (sma, …) and bare math (max/min/abs)
        if func_name in self.user_funcs:
            return self._emit_user_func_call(func_name, args)

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
        if func_name == "str_split":
            self.object_mode = True
            if len(args) >= 2:
                return f"str({args[0]}).split(str({args[1]}))"
            if args:
                return f"str({args[0]}).split()"
            return "[]"
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

        # Bare v3/v4 TA aliases (sma, ema, …) → ta_* so one handler path.
        # Prefer user-defined functions when the same name is declared (e.g. custom sma).
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
            "barssince": "ta_barssince",
            "linreg": "ta_linreg",
            "vwma": "ta_vwma",
            "mfi": "ta_mfi",
            "rising": "ta_rising",
            "falling": "ta_falling",
            "highestbars": "ta_highestbars",
            "lowestbars": "ta_lowestbars",
            "percentrank": "ta_percentrank",
            "obv": "ta_obv",
            "wma": "ta_wma",
            "roc": "ta_roc",
        }
        if func_name in _BARE_TA and func_name not in self.user_funcs:
            func_name = _BARE_TA[func_name]

        def _arr(expr: str) -> str:
            """Strip only a trailing ``[__bar_idx]`` from a pure series ref.

            Must not globally replace inside compounds — that turns
            ``(1 if isPnF_arr[__bar_idx] else 0)`` into ``(1 if isPnF_arr else 0)``
            and triggers array truth-value errors.
            """
            suffix = "[__bar_idx]"
            if expr.endswith(suffix):
                return expr[: -len(suffix)]
            return expr

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
            if not args:
                return "np.nan"
            period = kwargs.get("length", args[1] if len(args) > 1 else "14")
            return f"numba_sma({_arr(args[0])}, int({period}), __bar_idx)"
        if func_name == "ta_ema":
            if not args:
                return "np.nan"
            period = kwargs.get("length", args[1] if len(args) > 1 else "14")
            return f"numba_ema({_arr(args[0])}, int({period}), __bar_idx)"
        if func_name == "ta_rma":
            if not args:
                return "np.nan"
            period = kwargs.get("length", args[1] if len(args) > 1 else "14")
            return f"numba_rma({_arr(args[0])}, int({period}), __bar_idx)"
        if func_name == "ta_wma":
            if not args:
                return "np.nan"
            period = kwargs.get("length", args[1] if len(args) > 1 else "14")
            return f"numba_wma({_arr(args[0])}, int({period}), __bar_idx)"
        if func_name == "ta_rsi":
            if not args:
                return "np.nan"
            period = kwargs.get("length", args[1] if len(args) > 1 else "14")
            return f"numba_rsi({_arr(args[0])}, int({period}), __bar_idx)"
        if func_name == "ta_highest":
            # ta.highest(source, length) or ta.highest(length) → high source
            if len(args) >= 2:
                period = kwargs.get("length", args[1])
                return f"numba_highest({_arr(args[0])}, int({period}), __bar_idx)"
            if len(args) == 1:
                return f"numba_highest(high_arr, int({args[0]}), __bar_idx)"
            period = kwargs.get("length", "14")
            return f"numba_highest(high_arr, int({period}), __bar_idx)"
        if func_name == "ta_lowest":
            # ta.lowest(source, length) or ta.lowest(length) → low source
            if len(args) >= 2:
                period = kwargs.get("length", args[1])
                return f"numba_lowest({_arr(args[0])}, int({period}), __bar_idx)"
            if len(args) == 1:
                return f"numba_lowest(low_arr, int({args[0]}), __bar_idx)"
            period = kwargs.get("length", "14")
            return f"numba_lowest(low_arr, int({period}), __bar_idx)"
        if func_name == "ta_stdev":
            if not args:
                return "np.nan"
            period = kwargs.get("length", args[1] if len(args) > 1 else "14")
            return f"numba_stdev({_arr(args[0])}, int({period}), __bar_idx)"
        if func_name == "ta_change":
            if not args:
                return "np.nan"
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
            return f"numba_atr(high_arr, low_arr, close_arr, int({length}), __bar_idx)"
        if func_name == "ta_bb":
            # ta.bb(source, length, mult) or ta.bb(length, mult)
            if len(args) >= 3:
                src, length, mult = args[0], args[1], args[2]
            elif len(args) == 2:
                src, length, mult = "close_arr[__bar_idx]", args[0], args[1]
            else:
                src, length, mult = "close_arr[__bar_idx]", "20", "2.0"
            return f"numba_bb({_arr(src)}, int({length}), float({mult}), __bar_idx)"
        if func_name == "ta_macd":
            # ta.macd(source, fast, slow, signal)
            src = args[0] if args else "close_arr[__bar_idx]"
            fast = args[1] if len(args) > 1 else "12"
            slow = args[2] if len(args) > 2 else "26"
            signal = args[3] if len(args) > 3 else "9"
            return f"numba_macd({_arr(src)}, int({fast}), int({slow}), int({signal}), __bar_idx)"
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
            if _is_series_arr(src):
                return f"numba_cum({_arr(src)}, __bar_idx)"
            # Expression / ternary: accumulate scalar-at-bar into synthetic series.
            # (numba_cum needs a full array; global _arr strip is unsafe on compounds.)
            sid = f"__cum{self._expr_cum_i}_arr"
            self._expr_cum_i += 1
            self.arrays.add(sid)
            return f"numba_cum_expr({sid}, float({src}), __bar_idx)"
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


        if func_name == "ta_barssince":
            # Prefer history scan when condition is a series array; else weak current stub
            if args and _is_series_arr(args[0]):
                return f"numba_barssince({_arr(args[0])}, __bar_idx)"
            if args:
                return f"(0.0 if ({args[0]}) else np.nan)"
            return "np.nan"
        if func_name == "ta_linreg":
            # ta.linreg(source, length, offset=0)
            src = args[0] if args else "close_arr[__bar_idx]"
            length = args[1] if len(args) > 1 else "14"
            offset = args[2] if len(args) > 2 else "0"
            return f"numba_linreg({_arr(src)}, int({length}), int({offset}), __bar_idx)"
        if func_name == "ta_vwma":
            # ta.vwma(source, length) or ta.vwma(length) on close
            if len(args) >= 2 and _is_series_arr(args[0]):
                return f"numba_vwma({_arr(args[0])}, vol_arr, int({args[1]}), __bar_idx)"
            length = args[0] if args else "14"
            return f"numba_vwma(close_arr, vol_arr, int({length}), __bar_idx)"
        if func_name == "ta_mfi":
            # ta.mfi(length) | ta.mfi(source, length) | ta.mfi(h, l, c, v, length)
            if len(args) >= 5 and _is_series_arr(args[0]):
                return (
                    f"numba_mfi({_arr(args[0])}, {_arr(args[1])}, {_arr(args[2])}, "
                    f"{_arr(args[3])}, int({args[4]}), __bar_idx)"
                )
            if len(args) >= 2 and _is_series_arr(args[0]):
                src = _arr(args[0])
                return f"numba_mfi({src}, {src}, {src}, vol_arr, int({args[1]}), __bar_idx)"
            length = args[0] if args else "14"
            return f"numba_mfi(high_arr, low_arr, close_arr, vol_arr, int({length}), __bar_idx)"
        if func_name == "ta_rising":
            if len(args) >= 2:
                return f"numba_rising({_arr(args[0])}, int({args[1]}), __bar_idx)"
            if args and not _is_series_arr(args[0]):
                return f"numba_rising(close_arr, int({args[0]}), __bar_idx)"
            if args:
                return f"numba_rising({_arr(args[0])}, 1, __bar_idx)"
            return "numba_rising(close_arr, 1, __bar_idx)"
        if func_name == "ta_falling":
            if len(args) >= 2:
                return f"numba_falling({_arr(args[0])}, int({args[1]}), __bar_idx)"
            if args and not _is_series_arr(args[0]):
                return f"numba_falling(close_arr, int({args[0]}), __bar_idx)"
            if args:
                return f"numba_falling({_arr(args[0])}, 1, __bar_idx)"
            return "numba_falling(close_arr, 1, __bar_idx)"
        if func_name == "ta_highestbars":
            # ta.highestbars(source, length) or ta.highestbars(length) → high source
            if len(args) >= 2:
                period = kwargs.get("length", args[1])
                return f"numba_highestbars({_arr(args[0])}, int({period}), __bar_idx)"
            if len(args) == 1:
                # One-arg form is always length (even if the expr is a series scalar like amp_arr[i])
                return f"numba_highestbars(high_arr, int({args[0]}), __bar_idx)"
            period = kwargs.get("length", "14")
            return f"numba_highestbars(high_arr, int({period}), __bar_idx)"
        if func_name == "ta_lowestbars":
            # ta.lowestbars(source, length) or ta.lowestbars(length) → low source
            if len(args) >= 2:
                period = kwargs.get("length", args[1])
                return f"numba_lowestbars({_arr(args[0])}, int({period}), __bar_idx)"
            if len(args) == 1:
                return f"numba_lowestbars(low_arr, int({args[0]}), __bar_idx)"
            period = kwargs.get("length", "14")
            return f"numba_lowestbars(low_arr, int({period}), __bar_idx)"
        if func_name == "ta_percentrank":
            # ta.percentrank(source, length)
            if len(args) >= 2:
                return f"numba_percentrank({_arr(args[0])}, int({args[1]}), __bar_idx)"
            if args:
                return f"numba_percentrank(close_arr, int({args[0]}), __bar_idx)"
            return "np.nan"
        if func_name == "ta_obv":
            # ta.obv / ta.obv() / ta.obv(close, volume)
            if len(args) >= 2 and _is_series_arr(args[0]):
                return f"numba_obv({_arr(args[0])}, {_arr(args[1])}, __bar_idx)"
            return "numba_obv(close_arr, vol_arr, __bar_idx)"
        if func_name == "ta_roc":
            # ta.roc(source, length)
            if len(args) >= 2:
                return f"numba_roc({_arr(args[0])}, int({args[1]}), __bar_idx)"
            if args and not _is_series_arr(args[0]):
                return f"numba_roc(close_arr, int({args[0]}), __bar_idx)"
            if args:
                return f"numba_roc({_arr(args[0])}, 1, __bar_idx)"
            return "np.nan"
        if func_name in ("nz",):
            if not args:
                return "0.0"
            repl = args[1] if len(args) > 1 else "0.0"
            return f"numba_nz({args[0]}, {repl})"
        if func_name in ("math_abs", "abs"):
            return f"numba_abs({args[0]})" if args else "np.nan"
        if func_name in ("math_max", "max"):
            if len(args) >= 2:
                return f"numba_max({args[0]}, {args[1]})"
            return args[0] if args else "np.nan"
        if func_name in ("math_min", "min"):
            if len(args) >= 2:
                return f"numba_min({args[0]}, {args[1]})"
            return args[0] if args else "np.nan"
        if func_name in ("math_sqrt", "sqrt"):
            return f"np.sqrt({args[0]})" if args else "np.nan"
        if func_name == "avg":
            if not args:
                return "np.nan"
            return "(" + "+".join(args) + f") / {len(args)}"
        if func_name == "math_exp":
            return f"np.exp({args[0]})" if args else "np.nan"
        if func_name == "math_log":
            return f"np.log({args[0]})" if args else "np.nan"
        if func_name == "math_log10":
            return f"np.log10({args[0]})" if args else "np.nan"
        if func_name == "math_pow":
            if not args:
                return "np.nan"
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
            return f"(numba_sma({_arr(src_e)}, int({period}), __bar_idx) * float(int({period})))"
        if func_name == "math_avg":
            period = args[1] if len(args) > 1 else "14"
            src_e = args[0] if args else "close_arr[__bar_idx]"
            return f"numba_sma({_arr(src_e)}, int({period}), __bar_idx)"
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
            # Pine na(x) → bool; bare `na` constant is visit_Name → np.nan
            if args:
                # NaN-safe: x != x is True for float NaN; also treat None as na
                return f"(({args[0]}) is None or ({args[0]}) != ({args[0]}))"
            return "True"
        if func_name in ("float", "int", "bool", "string"):
            return args[0] if args else "np.nan"

        # Unknown call: object mode so we don't hard-fail under nopython
        # (still may NameError — better than invalid njit)
        if func_name not in ("unknown_func",):
            self.object_mode = True
        return f"{func_name}({', '.join(args)})"
    def _emit_user_func_call(self, func_name: str, args: list[str]) -> str:
        """Emit a call to a user-defined function with series/state plumbing."""
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
        ra = self._resolve_args
        if func_name == "map_new":
            return "{}"
        if func_name == "map_put":
            a = ra(args, kwargs, ("id", "key", "value"))
            if len(a) >= 3:
                return f"{a[0]}.__setitem__({a[1]}, {a[2]})"
            return ""
        if func_name == "map_get":
            a = ra(args, kwargs, ("id", "key"))
            if len(a) >= 2:
                return f"{a[0]}.get({a[1]}, np.nan)"
            return "np.nan"
        if func_name == "map_contains":
            a = ra(args, kwargs, ("id", "key"))
            if len(a) >= 2:
                return f"({a[1]} in {a[0]})"
            return "False"
        if func_name == "map_remove":
            a = ra(args, kwargs, ("id", "key"))
            if len(a) >= 2:
                return f"{a[0]}.pop({a[1]}, None)"
            return "None"
        if func_name == "map_clear":
            a = ra(args, kwargs, ("id",))
            return f"{a[0]}.clear()" if a else ""
        if func_name == "map_size":
            a = ra(args, kwargs, ("id",))
            return f"len({a[0]})" if a else "0"
        if func_name == "map_keys":
            a = ra(args, kwargs, ("id",))
            return f"list({a[0]}.keys())" if a else "[]"
        if func_name == "map_values":
            a = ra(args, kwargs, ("id",))
            return f"list({a[0]}.values())" if a else "[]"
        if func_name == "map_copy":
            a = ra(args, kwargs, ("id",))
            return f"dict({a[0]})" if a else "{}"
        return f"{func_name}({', '.join(args)})" if args else "np.nan"

    def _emit_drawing_set(self, func_name: str, args: list[str], kwargs: dict[str, str]) -> str:
        """Emit a drawing update event for label/line/box/table/polyline set_*.

        Records the mutator on ``__drawings`` so object-mode runs don't NameError.
        First arg is the handle from ``*.new`` when available.
        """
        target = args[0] if args else "None"
        rest = args[1:] if len(args) > 1 else []
        parts = [
            "'kind': 'set'",
            f"'method': {func_name!r}",
            f"'target': {target}",
            "'bar': __bar_idx",
        ]
        if rest:
            parts.append(f"'args': [{', '.join(rest)}]")
        for k, v in kwargs.items():
            parts.append(f"{k!r}: {v}")
        return f"__drawings.append({{{', '.join(parts)}}})"

    # ---------------------------------------------------------------- exprs

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
        event = f"{{{', '.join(parts)}}}"
        # Object constructors return a handle dict so later set_* can reference it.
        if func_name.endswith("_new"):
            return f"(__drawings.append(__d := {event}) or __d)"
        return f"__drawings.append({event})"
    def visit_BinOp(self, node: ast.BinOp):
        left = self.visit(node.left)
        right = self.visit(node.right)
        # Pine division by zero → na (not Python ZeroDivisionError)
        if isinstance(node.op, ast.Div):
            return f"(({left}) / ({right}) if ({right}) != 0 else np.nan)"
        if isinstance(node.op, ast.Mod):
            return f"(({left}) % ({right}) if ({right}) != 0 else np.nan)"
        op = {
            ast.Add: "+",
            ast.Sub: "-",
            ast.Mult: "*",
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

    @staticmethod
    def _safe_history_offset(offset_expr: str) -> str:
        """Coerce a series-history offset to a non-NaN int index.

        ``ta.highestbars`` / ``lowestbars`` (and ``math.abs`` of them) return
        float64; Numba rejects float array indices. NaN → 0 so indexing never
        raises (``int(nan)`` is invalid).
        """
        return f"(0 if ({offset_expr}) != ({offset_expr}) else int({offset_expr}))"

    def _history_subscript(self, base: str, offset_expr: str) -> str:
        """Emit ``base[bar - offset]`` with float/NaN-safe offset coercion."""
        off = self._safe_history_offset(offset_expr)
        return f"({base}[__bar_idx - ({off})] if __bar_idx >= ({off}) else np.nan)"

    def visit_Subscript(self, node: ast.Subscript):
        # History on UDF params/locals: use array base, never index a scalar float
        if (
            self.in_function
            and isinstance(node.value, ast.Name)
            and node.value.id in self.local_vars
        ):
            name = node.value.id
            py = self._py_ident(name)
            slice_val = self.visit(node.slice)
            if name in self.series_params:
                base = py
            elif name in self.series_locals:
                base = f"{py}_arr"
            else:
                # Late discovery (param history): keep param-as-array convention
                self.series_params.add(name)
                base = py
            return self._history_subscript(base, slice_val)

        arr = self.visit(node.value)
        slice_val = self.visit(node.slice)
        if arr.endswith("[__bar_idx]"):
            base_arr = arr[:-11]
            return self._history_subscript(base_arr, slice_val)
        # Guard: never emit None[i] from a strategy stub — prefer np.nan
        if arr in ("None", "np.nan"):
            return "np.nan"
        return f"{arr}[{slice_val}]"
    def visit_If(self, node: ast.If):
        test = self.visit(node.test)
        lines = [f"if {test}:"]
        ret_mode = self.if_return_mode

        def _emit_branch(stmts) -> list[str]:
            out: list[str] = []
            for i, stmt in enumerate(stmts):
                is_tail = i == len(stmts) - 1
                prev = self.if_return_mode
                # Keep return-mode only for tail nested if / if-expr
                if ret_mode and is_tail and (
                    isinstance(stmt, ast.If)
                    or (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.If))
                ):
                    self.if_return_mode = True
                    target = stmt.value if isinstance(stmt, ast.Expr) else stmt
                    val = self.visit(target)
                else:
                    self.if_return_mode = False
                    val = self.visit(stmt)
                    if ret_mode and is_tail and val and isinstance(stmt, ast.Expr):
                        stripped = val.lstrip()
                        if not stripped.startswith(
                            ("if ", "for ", "while ", "return ", "else:", "elif ")
                        ):
                            val = f"return {val}"
                self.if_return_mode = prev
                if val:
                    val = val.replace("\n", "\n    ")
                    out.append(f"    {val}")
            if not out:
                out.append("    return np.nan" if ret_mode else "    pass")
            elif ret_mode and not any("return " in ln for ln in out):
                out.append("    return np.nan")
            return out

        lines.extend(_emit_branch(node.body))
        if node.orelse:
            lines.append("else:")
            lines.extend(_emit_branch(node.orelse))
        elif ret_mode:
            lines.append("else:")
            lines.append("    return np.nan")
        return "\n".join(lines)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        func_name = node.name
        args = [arg.name for arg in node.args if hasattr(arg, "name")]
        arg_set = set(args)
        self.user_funcs.add(func_name)
        if getattr(node, "export", None):
            # export methods in libraries → always object mode
            self.object_mode = True
        prev_series = set(self.series_params)
        prev_series_locals = set(self.series_locals)
        prev_ident = dict(self.ident_map)
        self.in_function = True
        self.local_vars = set(args)
        # Rename params that shadow Python builtins (len, sum, id, …)
        self.ident_map = {a: self._safe_ident(a) for a in args}

        # Pass 0: assigned locals + names used under history subscript
        assigned: set[str] = set()
        history_names: set[str] = set()
        for stmt in node.body:
            self._collect_assigned_names(stmt, assigned)
            self._collect_history_names(stmt, history_names)

        # Safe names for assigned locals (sum, max, min, …)
        for n in assigned:
            self.ident_map[n] = self._safe_ident(n)

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
        last_ast = node.body[-1] if node.body else None
        # Pine if-expression as function result: emit returns on branches
        last_is_if_expr = isinstance(last_ast, ast.Expr) and isinstance(
            getattr(last_ast, "value", None), ast.If
        )
        last_is_if_stmt = isinstance(last_ast, ast.If)
        for i, stmt in enumerate(node.body):
            is_last = i == len(node.body) - 1
            if is_last and (last_is_if_expr or last_is_if_stmt):
                self.if_return_mode = True
                try:
                    if last_is_if_expr:
                        val = self.visit(stmt.value)
                    else:
                        val = self.visit(stmt)
                finally:
                    self.if_return_mode = False
            else:
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

        # series-local params use safe base name + _arr
        sl_params = [f"{self.ident_map.get(s, s)}_arr" for s in series_locals]
        needs_ctx = (
            any(tok in body_text for tok in _ctx_tokens)
            or bool(series_for_func)
            or bool(series_locals)
            or bool(st_refs)
        )
        # Emit safe Python param names for user-facing args
        param_list = [self.ident_map.get(a, a) for a in args]
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
        needs_strategy = "__strategy" in body_text
        if needs_strategy:
            self.object_mode = True
            self.uses_strategy = True
            if "__strategy" not in param_list:
                param_list = list(param_list) + ["__strategy"]
        self.func_needs_strategy[func_name] = needs_strategy

        deco = "@numba.njit(cache=False)" if not self.object_mode else ""
        lines = []
        if deco:
            lines.append(deco)
        lines.append(f"def {func_name}({', '.join(param_list)}):")
        if not body_lines:
            lines.append("    pass")
        else:
            # Only wrap a pure expression result — never `if`/`for`/`while` as `return if …`
            # (if-expr results already contain return statements via if_return_mode)
            returnable = (
                isinstance(last_ast, ast.Expr)
                and not isinstance(
                    getattr(last_ast, "value", None),
                    (ast.If, ast.ForTo, ast.While, ast.ForIn),
                )
                and not last_is_if_expr
            )
            for i, line in enumerate(body_lines):
                is_last = i == len(body_lines) - 1
                line = line.replace("\n", "\n    ")
                stripped = line.lstrip()
                if is_last and returnable and not stripped.startswith(
                    ("if ", "for ", "while ", "else:", "elif ", "try:", "with ", "return ")
                ):
                    lines.append(f"    return {line}")
                else:
                    lines.append(f"    {line}")
        self.functions.append("\n".join(lines))
        self.ident_map = prev_ident
        return ""

    # TA / math helpers whose first arg is a series source (when present).
    # 1-arg forms of highest/lowest/etc. take a period, not a source — see below.
    _SERIES_SRC_ALWAYS: frozenset[str] = frozenset(
        {
            "sma",
            "ema",
            "rma",
            "wma",
            "rsi",
            "stdev",
            "change",
            "bb",
            "macd",
            "linreg",
            "cci",
            "vwap",
            "cum",
            "percentile_nearest_rank",
            "valuewhen",
            "stoch",
            "barssince",
            "pivothigh",
            "pivotlow",
            "ta_sma",
            "ta_ema",
            "ta_rma",
            "ta_wma",
            "ta_rsi",
            "ta_stdev",
            "ta_change",
            "ta_bb",
            "ta_macd",
            "ta_linreg",
            "ta_cci",
            "ta_vwap",
            "ta_cum",
            "ta_percentile_nearest_rank",
            "ta_valuewhen",
            "ta_stoch",
            "ta_barssince",
            "ta_pivothigh",
            "ta_pivotlow",
            "math_sum",
            "math_avg",
        }
    )
    # These need ≥2 args for the first to be a source (1-arg = length on chart OHLC).
    _SERIES_SRC_MULTIARG: frozenset[str] = frozenset(
        {
            "highest",
            "lowest",
            "highestbars",
            "lowestbars",
            "rising",
            "falling",
            "vwma",
            "mfi",
            "ta_highest",
            "ta_lowest",
            "ta_highestbars",
            "ta_lowestbars",
            "ta_rising",
            "ta_falling",
            "ta_vwma",
            "ta_mfi",
        }
    )
    # Both operands can be series sources.
    _SERIES_SRC_BOTH: frozenset[str] = frozenset(
        {
            "crossover",
            "crossunder",
            "cross",
            "ta_crossover",
            "ta_crossunder",
            "ta_cross",
        }
    )
    def _call_func_key(self, func) -> str | None:
        """Normalize a Call.func node to bare or ta_* / math_* key for series marking."""
        if isinstance(func, ast.Specialize):
            func = func.value
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            ns = func.value.id
            if ns in ("ta", "math"):
                return f"{ns}_{func.attr}"
            # bare-style already covered by Name
        return None

    @staticmethod
    def _unwrap_call_arg(arg):
        """Unwrap Arg wrapper to (expr, keyword_name|None)."""
        if arg is None:
            return None, None
        if isinstance(arg, ast.Arg):
            return arg.value, getattr(arg, "name", None)
        return arg, None

    def _mark_name_series_param(self, expr) -> None:
        if isinstance(expr, ast.Name) and expr.id in self.local_vars:
            self.series_params.add(expr.id)

    def _mark_series_params(self, node) -> None:
        """Mark UDF params used as series: history subscripts or TA series sources."""
        if node is None or not hasattr(node, "__dict__"):
            return
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            if node.value.id in self.local_vars:
                self.series_params.add(node.value.id)
        if isinstance(node, ast.Call):
            key = self._call_func_key(node.func)
            if key is not None:
                pos: list = []
                kws: dict[str, object] = {}
                for raw in node.args or []:
                    expr, name = self._unwrap_call_arg(raw)
                    if name:
                        kws[str(name)] = expr
                    else:
                        pos.append(expr)
                # keyword source=...
                if "source" in kws:
                    self._mark_name_series_param(kws["source"])
                if key in self._SERIES_SRC_BOTH:
                    for e in pos[:2]:
                        self._mark_name_series_param(e)
                elif key in self._SERIES_SRC_ALWAYS:
                    if pos:
                        self._mark_name_series_param(pos[0])
                elif key in self._SERIES_SRC_MULTIARG:
                    # only mark first arg when a second positional (or length kw) exists
                    if len(pos) >= 2 or ("length" in kws and pos):
                        self._mark_name_series_param(pos[0])
                # valuewhen(condition, source, occurrence) — source is 2nd
                if key in ("valuewhen", "ta_valuewhen") and len(pos) >= 2:
                    self._mark_name_series_param(pos[0])  # cond series
                    self._mark_name_series_param(pos[1])  # source series
                # stoch(source, high, low, length) — first three can be series
                if key in ("stoch", "ta_stoch"):
                    for e in pos[:3]:
                        self._mark_name_series_param(e)
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
        # Loop counter is a per-bar scalar. Do NOT force in_function=True for
        # script-level loops — that turned series assigns into float locals
        # (``base = close_arr[i]``) which then failed on history (``base[1]``).
        added_local = False
        added_scalar = False
        if self.in_function:
            if target not in self.local_vars:
                self.local_vars.add(target)
                added_local = True
        else:
            if target not in self.scalar_vars:
                self.scalar_vars.add(target)
                added_scalar = True
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
        if added_local:
            self.local_vars.discard(target)
        if added_scalar:
            self.scalar_vars.discard(target)
        return "\n".join(lines)
    def visit_While(self, node: ast.While):
        test = self.visit(node.test)
        # Keep ambient in_function; do not force True (same rationale as ForTo).
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
