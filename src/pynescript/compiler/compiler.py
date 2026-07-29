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
        "complex",
    }
)

# Bare color identifiers (v3/v4 style: plot(..., color=green))
_COLOR_NAMES = frozenset(
    {
        "red",
        "green",
        "blue",
        "white",
        "black",
        "gray",
        "grey",
        "orange",
        "purple",
        "yellow",
        "aqua",
        "lime",
        "maroon",
        "navy",
        "olive",
        "silver",
        "teal",
        "fuchsia",
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

# Bare linestyle / plot style tokens used as identifiers (v3–v4 style)
_LINESTYLE_NAMES = frozenset(
    {
        "solid",
        "dotted",
        "dashed",
        "arrowup",
        "arrowdown",
        "circles",
        "cross",
        "linebr",
        "area",
        "columns",
        "histogram",
        "stepline",
        "steplinebr",
    }
)

# Method-style TA: ``expr.rma(p)`` / ``(x).sma(14)`` → ``ta.rma(expr, p)``
_METHOD_TA = frozenset(
    {
        "sma",
        "ema",
        "rma",
        "wma",
        "vwma",
        "rsi",
        "stdev",
        "stoch",
        "cci",
        "atr",
        "change",
        "roc",
        "mom",
        "highest",
        "lowest",
        "highestbars",
        "lowestbars",
        "cum",
        "sum",
        "dev",
        "variance",
        "linreg",
        "percentrank",
        "barssince",
        "rising",
        "falling",
        "alma",
        "hma",
        "tsi",
        "obv",
        "vwap",
        "tr",
        "correlation",
        "fixnan",
        "nz",
    }
)

# Method form: arr.push(x) / m.put(k,v) / t.cell(...) → array_push / map_put / table_cell
_ARRAY_METHODS: dict[str, str] = {
    "push": "array_push",
    "pop": "array_pop",
    "shift": "array_shift",
    "unshift": "array_unshift",
    "get": "array_get",
    "set": "array_set",
    "remove": "array_remove",
    "clear": "array_clear",
    "size": "array_size",
    "fill": "array_fill",
    "includes": "array_includes",
    "join": "array_join",
    "sort": "array_sort",
    "sort_indices": "array_sort_indices",
    "reverse": "array_reverse",
    "slice": "array_slice",
    "copy": "array_copy",
    "concat": "array_concat",
    "indexof": "array_indexof",
    "lastindexof": "array_lastindexof",
    "insert": "array_insert",
    "first": "array_first",
    "last": "array_last",
    "avg": "array_avg",
    "min": "array_min",
    "max": "array_max",
    "sum": "array_sum",
    "stdev": "array_stdev",
    "variance": "array_variance",
    "median": "array_median",
    "covariance": "array_covariance",
    # matrix methods (same surface as array for avg/max/…; extra matrix-only below)
    "row": "matrix_row",
    "col": "matrix_col",
    "submatrix": "matrix_submatrix",
    "add_col": "matrix_add_col",
    "add_column": "matrix_add_col",
    "remove_col": "matrix_remove_col",
    "remove_column": "matrix_remove_col",
    "add_row": "matrix_add_row",
    "remove_row": "matrix_remove_row",
    "reshape": "matrix_reshape",
    "swap_rows": "matrix_swap_rows",
    "swap_columns": "matrix_swap_columns",
    "sort": "matrix_sort",
    "reverse": "matrix_reverse",
    "eigenvalues": "matrix_eigenvalues",
    "eigenvectors": "matrix_eigenvectors",
    "rank": "matrix_rank",
    "trace": "matrix_trace",
    "rows": "matrix_rows",
    "columns": "matrix_columns",
}
_MAP_METHODS: dict[str, str] = {
    "put": "map_put",
    "get": "map_get",
    "remove": "map_remove",
    "clear": "map_clear",
    "contains": "map_contains",
    "keys": "map_keys",
    "values": "map_values",
    "size": "map_size",
    "copy": "map_copy",
}
_TABLE_METHODS: dict[str, str] = {
    "cell": "table_cell",
    "cell_set": "table_cell_set",
    "clear": "table_clear",
    "delete": "table_delete",
    "merge_cells": "table_merge_cells",
}
# Bare library-style verbs (no receiver) — avoid sum/min/max/size/clear clashes
_BARE_COLLECTION: dict[str, str] = {
    "push": "array_push",
    "pop": "array_pop",
    "shift": "array_shift",
    "unshift": "array_unshift",
    "includes": "array_includes",
    "indexof": "array_indexof",
    "lastindexof": "array_lastindexof",
    "concat": "array_concat",
    "put": "map_put",
    "cell": "table_cell",
}

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
        self.user_funcs: set[str] = set()  # user-defined function names (Pine ids)
        # Pine UDF name → safe Python def name (``from`` → ``from_``)
        self.func_name_map: dict[str, str] = {}
        self.series_params: set[str] = set()  # UDF params used as series (history)
        self.series_locals: set[str] = set()  # UDF locals used with history (current fn)
        self.param_names: set[str] = set()  # current UDF formal parameter names
        self.loop_counters: set[str] = set()  # active for-loop counter names (scalars)
        self.func_series_params: dict[str, set[str]] = {}
        self.func_series_locals: dict[str, list[str]] = {}  # func -> local names needing state arr
        self.func_st_params: dict[str, list[str]] = {}  # func -> transitive __st_* params
        self.func_param_names: dict[str, list[str]] = {}
        self.func_param_defaults: dict[str, dict[str, str]] = {}
        self.func_free_series: dict[str, list[str]] = {}
        self.func_free_scalars: dict[str, list[str]] = {}
        self.func_returns_sequence: set[str] = set()
        self.local_sequence_vars: set[str] = set()
        self._free_scalars_current: set[str] = set()
        self.func_needs_bar: dict[str, bool] = {}
        self.func_needs_strategy: dict[str, bool] = {}
        self.func_needs_drawings: dict[str, bool] = {}
        self.func_needs_n_bars: dict[str, bool] = {}
        self.string_series: set[str] = set()  # per-bar string/color series (object dtype)
        # Bar-constant string/color scalars (input.string, color.red, …). Distinct from
        # scalar_vars which also holds numeric intermediates and drawing/array handles.
        self.string_scalars: set[str] = set()
        self.import_aliases: set[str] = set()  # library import aliases (ae, activation, …)
        self._expr_cum_i: int = 0  # synthetic state arrays for cum(expr)
        self._expr_src_i: int = 0  # synthetic series for non-array TA sources
        self._ta_state_i: int = 0  # synthetic fixed-size state for incremental TA
        # Fixed-size state vectors: (name, length) allocated once outside bar loop
        self.fixed_state: list[tuple[str, int]] = []
        self._current_func_name: str | None = None  # active UDF for __st_* src arrays
        # Pine name → safe Python identifier within current UDF scope
        self.ident_map: dict[str, str] = {}
        # When True, visit_If emits `return` on tail expressions (UDF result if-expr)
        self.if_return_mode: bool = False


    @staticmethod
    def _is_simple_default_expr(expr: str) -> bool:
        """True if expr is safe to put as a Python default (literal-ish)."""
        e = expr.strip()
        if e in ("True", "False", "None", "np.nan"):
            return True
        if len(e) >= 2 and e[0] in ("'", '"') and e[-1] == e[0]:
            return True
        try:
            float(e)
            return True
        except ValueError:
            return False

    def _alloc_fixed_state(self, prefix: str, size: int) -> str:
        """Allocate a small float state vector for amortized-O(1) TA kernels."""
        name = f"__{prefix}{self._ta_state_i}_st"
        self._ta_state_i += 1
        self.fixed_state.append((name, size))
        return name

    @staticmethod
    def _safe_ident(name: str) -> str:
        """Avoid shadowing Python builtins/keywords used in generated code."""
        if not name:
            return name
        if name in _PY_RESERVED or keyword.iskeyword(name):
            return f"{name}_"
        return name

    # Chart OHLCV parameter array bases — user series with these names must not
    # clobber ``vol_arr`` / ``close_arr`` / … (e.g. ``string vol = "|HiVol"``).
    _CHART_ARR_BASES = frozenset({"open", "high", "low", "close", "vol"})

    def _series_arr_name(self, name: str) -> str:
        """Python array identifier for a user series (mangles chart collisions)."""
        if name in self._CHART_ARR_BASES:
            return f"__user_{name}_arr"
        return f"{name}_arr"

    def _is_object_dtype_arr(self, arr: str) -> bool:
        """True when ``arr`` is a string/color or UDT object series buffer."""
        if not arr.endswith("_arr"):
            return False
        base = arr[: -len("_arr")]
        if base.startswith("__user_"):
            base = base[len("__user_") :]
        return base in self.udt_vars or base in self.string_series

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


    @staticmethod
    def _strip_bar_idx(expr: str) -> str:
        """Strip only a trailing ``[__bar_idx]`` from a pure series ref."""
        suffix = "[__bar_idx]"
        if expr.endswith(suffix):
            return expr[: -len(suffix)]
        return expr

    def _is_series_arr_expr(self, expr: str) -> bool:
        """True when expr is a pure series array ref (optionally bar-indexed)."""
        a = self._strip_bar_idx(expr)
        if a.endswith("_arr") or a in (
            "open_arr",
            "high_arr",
            "low_arr",
            "close_arr",
            "vol_arr",
        ):
            return True
        if expr.endswith("[__bar_idx]") and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", a):
            return True
        return False

    def _materialize_series_source(self, expr: str) -> str:
        """Ensure a TA source is a full series array for numba_* history.

        Pure array refs pass through. Compounds (numba_abs(...), close*2) are
        written into a synthetic series via numba_store_src.
        Object mode uses store_src_py so list/str handles never do ``list + 0.0``.
        """
        if self._is_series_arr_expr(expr):
            return self._strip_bar_idx(expr)
        if self.in_function and self._current_func_name:
            sid = f"__st_{self._current_func_name}__src{self._expr_src_i}"
        else:
            sid = f"__src{self._expr_src_i}_arr"
        self._expr_src_i += 1
        self.arrays.add(sid)
        if self.object_mode or self.string_series or self.udt_vars or self.scalar_vars:
            # Coerce non-numeric (list/str handles) via safe_float — avoids
            # ``(list) + 0.0`` TypeError when Pine arrays feed TA sources.
            return f"store_src_py({sid}, {expr}, __bar_idx)"
        return f"numba_store_src({sid}, ({expr}) + 0.0, __bar_idx)"

    # ------------------------------------------------------------------ script
    def visit_Import(self, node: ast.Import):
        """Track ``import … as alias`` so library methods can be stubbed."""
        alias = node.alias or node.name
        if alias:
            self.import_aliases.add(alias)
            # Treat as a module-scope scalar so free-var plumbing can pass None
            self.scalar_vars.add(alias)
        self.object_mode = True
        return ""

    def visit_Script(self, node: ast.Script):
        body_lines: list[str] = []
        for stmt in node.body:
            val = self.visit(stmt)
            if val:
                body_lines.append(val)

        # Safety net: any ``*_arr`` referenced in body/functions must be allocated
        # (covers reassign-to-drawing discarding arrays, empty strategy stubs, …).
        _chart = {"open_arr", "high_arr", "low_arr", "close_arr", "vol_arr"}
        blob = "\n".join(body_lines) + "\n" + "\n".join(self.functions)
        for m in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*_arr)\b", blob):
            if m not in _chart and not m.startswith("__st_"):
                self.arrays.add(m)

        # String/color/UDT/map series must never enter njit (non-precise pyobject).
        if self.string_series or self.udt_vars or self.map_vars or self.scalar_vars:
            self.object_mode = True

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
        self._emit_fixed_state(lines, indent="    ")
        for idx in range(len(self.plots)):
            lines.append(f"    plot_{idx} = np.full(n_bars, np.nan)")
        lines.append("    for __bar_idx in range(n_bars):")
        if not body_lines:
            lines.append("        pass")
        for line in body_lines:
            line = line.replace("\n", "\n        ")
            lines.append(f"        {line}")

        # Tuple return avoids Numba typed.Dict construction/iteration overhead.
        if self.plots:
            plots_tuple = ", ".join(f"plot_{i}" for i in range(len(self.plots)))
            if len(self.plots) == 1:
                plots_tuple += ","
            lines.append(f"    return ({plots_tuple})")
        else:
            lines.append("    return ()")
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
            # Never reallocate chart OHLCV parameters (user `vol` string series is
            # mangled to __user_vol_arr via _series_arr_name).
            if arr in ("open_arr", "high_arr", "low_arr", "close_arr", "vol_arr"):
                continue
            # object series use object dtype
            if self._is_object_dtype_arr(arr):
                lines.append(f"    {arr} = np.empty(n_bars, dtype=object)")
            else:
                lines.append(f"    {arr} = np.full(n_bars, np.nan)")
        self._emit_series_local_state(lines, indent="    ")
        self._emit_fixed_state(lines, indent="    ")
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

        # Use repr so titles with apostrophes (Spearman's Rho) stay valid Python.
        dict_items = [f"{p['title']!r}: plot_{i}" for i, p in enumerate(self.plots)]
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
                # Drawing/UDT/string series locals need object dtype
                if s in self.udt_vars or s in self.string_series:
                    lines.append(
                        f"{indent}__st_{func_name}_{s} = np.empty(n_bars, dtype=object)"
                    )
                else:
                    lines.append(f"{indent}__st_{func_name}_{s} = np.full(n_bars, np.nan)")

    def _emit_fixed_state(self, lines: list[str], *, indent: str = "    ") -> None:
        """Preallocate small state vectors for incremental TA kernels."""
        for name, size in self.fixed_state:
            lines.append(f"{indent}{name} = np.full({size}, np.nan)")

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

    def _call_returns_sequence(self, node) -> bool:
        """True when *node* is a Call to a UDF known to return array/list handles."""
        if not isinstance(node, ast.Call):
            return False
        f = node.func
        if isinstance(f, ast.Specialize):
            f = f.value
        if isinstance(f, ast.Name) and f.id in self.func_returns_sequence:
            return True
        if isinstance(f, ast.Attribute) and f.attr in self.func_returns_sequence:
            return True
        return self._is_array_or_matrix_handle(node) or self._is_sequence_producing_call(node)

    def _ast_expr_is_sequence(self, ret_expr) -> bool:
        """True when an AST return/value expression yields an array/list handle.

        Numeric multi-return tuples like ``[alpha, beta]`` are *not* sequences —
        only tuples that contain array handles / sequence locals.
        """
        if ret_expr is None:
            return False
        if isinstance(ret_expr, ast.Tuple):
            return any(self._ast_expr_is_sequence(elt) for elt in ret_expr.elts)
        if isinstance(ret_expr, ast.Name) and ret_expr.id in self.local_sequence_vars:
            return True
        if self._is_array_or_matrix_handle(ret_expr) or self._is_sequence_producing_call(
            ret_expr
        ):
            return True
        if isinstance(ret_expr, ast.Call) and self._call_returns_sequence(ret_expr):
            return True
        return False

    def _return_expr_is_sequence(self, expr: str) -> bool:
        """Classify a generated ``return <expr>`` as array/list vs numeric."""
        if not expr:
            return False
        e = expr.strip()
        # List construction / array-ish literals in generated code
        if e.startswith("["):
            return True
        if "[np.nan]" in e or ("[]" in e and ("*" in e or "list(" in e)):
            return True
        if ".copy(" in e or ".extend(" in e:
            return True
        # Bare name → sequence local?
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", e):
            pine = e
            for k, v in self.ident_map.items():
                if v == e:
                    pine = k
                    break
            return pine in self.local_sequence_vars or e in self.local_sequence_vars
        # Tuple/list of names or mixed: sequence if any component is a sequence local
        # or contains nested list construction.
        if self.local_sequence_vars and (e.startswith("(") or "," in e):
            for sv in self.local_sequence_vars:
                py = self.ident_map.get(sv, sv)
                if re.search(rf"\b{re.escape(py)}\b", e) or re.search(
                    rf"\b{re.escape(sv)}\b", e
                ):
                    return True
        if self._looks_like_sequence_expr(e):
            # Pure ``(a, b)`` name-tuples of non-sequence locals are numeric multi-return
            if re.fullmatch(
                r"\(\s*[A-Za-z_][A-Za-z0-9_]*(\s*,\s*[A-Za-z_][A-Za-z0-9_]*)*\s*,?\s*\)",
                e,
            ):
                return False
            return True
        return False

    def _rhs_is_sequence(self, node, val: str | None = None) -> bool:
        """True when RHS is/list-like and must not be stored into float64 series."""
        if self._is_array_or_matrix_handle(node) or self._is_sequence_producing_call(node):
            return True
        if self._call_returns_sequence(node):
            return True
        if isinstance(node, ast.Tuple):
            # Whole-tuple assign to one name (rare) → keep as sequence/object.
            # Multi-target unpack goes through ``_visit_tuple_assign`` instead.
            return True
        if isinstance(node, ast.Name) and node.id in self.local_sequence_vars:
            return True
        if isinstance(node, ast.Name) and node.id in self.scalar_vars:
            # Re-bind of an existing array handle scalar (still a sequence at runtime
            # only if it was one — keep non-sequence scalars numeric via other paths).
            pass
        if val is not None and self._looks_like_sequence_expr(val):
            return True
        # UDF call text still looks like ``knn(...)`` — catch even if AST name missed
        if isinstance(val, str) and val:
            for uf in self.func_returns_sequence:
                if re.search(rf"\b{re.escape(uf)}\s*\(", val):
                    return True
        return False

    def _func_body_returns_string(self, body_lines: list[str]) -> bool:
        """True when UDF return expressions look like string/size/color literals.

        Switch/if-expr bodies often land as a bare ternary *before* the
        trailing ``return`` is prepended — so also inspect the last body line
        even without a ``return`` prefix.
        """
        if not body_lines:
            return False
        candidates: list[str] = []
        for line in body_lines:
            for raw in str(line).split("\n"):
                stripped = raw.strip()
                if stripped.startswith("return "):
                    candidates.append(stripped[len("return ") :].strip())
        # Last physical line of the last body chunk (switch → ternary)
        last_chunk = str(body_lines[-1]).split("\n")[-1].strip()
        if last_chunk.startswith("return "):
            candidates.append(last_chunk[len("return ") :].strip())
        else:
            candidates.append(last_chunk)
        return any(self._looks_like_string_expr(c) for c in candidates if c)

    def _call_returns_string(self, node) -> bool:
        """True when Call targets a known string-returning UDF."""
        if not isinstance(node, ast.Call):
            return False
        f = node.func
        if isinstance(f, ast.Specialize):
            f = f.value
        name = None
        if isinstance(f, ast.Name):
            name = f.id
        elif isinstance(f, ast.Attribute):
            name = f.attr
        if name and name in getattr(self, "func_returns_string", set()):
            return True
        return False

    def _func_body_returns_sequence(
        self, node, last_ast, body_lines: list[str]
    ) -> bool:
        """Infer UDF returns a list/array handle (not mere numeric multi-return).

        Numeric tuples like ``[alpha, beta]`` / ``[spike_up, spike_down]`` stay
        out of ``func_returns_sequence`` so multi-unpack can use float series.
        Array handles (``array.new*``, list locals) mark the UDF so callers store
        into scalar/object slots instead of float64 series.
        """
        ret_expr = None
        if isinstance(last_ast, ast.Expr):
            ret_expr = last_ast.value
        elif isinstance(last_ast, (ast.Assign, ast.ReAssign)):
            t = last_ast.target
            if isinstance(t, ast.Name) and t.id in self.local_sequence_vars:
                return True
            ret_expr = last_ast.value
        if self._ast_expr_is_sequence(ret_expr):
            return True
        # Walk *all* return lines (if/else branches), not only the last statement
        for line in body_lines:
            for raw in str(line).split("\n"):
                stripped = raw.strip()
                if stripped.startswith("return "):
                    expr = stripped[len("return ") :].strip()
                    if self._return_expr_is_sequence(expr):
                        return True
                    continue
                # Trailing expression result (no explicit return) as bare name
                if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", stripped):
                    pine = stripped
                    for k, v in self.ident_map.items():
                        if v == stripped:
                            pine = k
                            break
                    if pine in self.local_sequence_vars or stripped in self.local_sequence_vars:
                        return True
                if self._return_expr_is_sequence(stripped):
                    return True
        return False

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
        is_var = hasattr(node, "mode") and isinstance(node.mode, (ast.Var, ast.VarIp))

        # Pine if-expression RHS with side effects → statement-form assign.
        # Pure if-exprs lower to ternaries here (and via visit_If).
        if isinstance(node.value, ast.If):
            tern = self._try_if_as_ternary(node.value)
            if tern is None:
                # Multi-stmt branches: emit if that writes the series target
                target_store = f"{name}_arr[__bar_idx]"
                self.arrays.add(f"{name}_arr")
                return self._emit_if_assign(target_store, node.value)
            val = tern
        else:
            val = self.visit(node.value)

        # Explicit type annotation: `color x = …` / `string s = …`
        type_node = getattr(node, "type", None)
        type_id = type_node.id if isinstance(type_node, ast.Name) else None
        typed_stringy = type_id in ("color", "string", "str")
        # Explicit numeric/bool annotations must stay float64 series even when the
        # visited RHS contains string comparisons (switch Ma == 'EMA', UDT keys, …).
        typed_numeric = type_id in ("float", "int", "bool")
        # Drawing / table handles must never land in float64 series
        # (numpy float() on dict → TypeError).
        typed_drawing = type_id in (
            "line",
            "label",
            "box",
            "table",
            "polyline",
            "linefill",
            "hline",
        )
        typed_udt = type_id is not None and type_id in self.udt_types

        if self.in_function:
            self.local_vars.add(name)
            # Shadow UDF name: ``mama = mama(...)`` must not rebind the function
            if name in self.user_funcs and name not in self.ident_map:
                self.ident_map[name] = f"{self._safe_ident(name)}__loc"
            py = self._py_ident(name)
            # Array/list handles inside UDFs must be tracked as sequence locals
            # so the UDF is marked sequence-returning (knn → nearest_neighbors).
            if hasattr(self, "_rhs_is_sequence") and self._rhs_is_sequence(node.value, val):
                self.object_mode = True
                self.local_sequence_vars.add(name)
                return f"{py} = {val}"
            if name in self.series_locals:
                # Drawing / UDT handles must not go into float64 series-local arrays
                if val and (
                    "__drawings" in val
                    or val.startswith("{")
                    or "'kind':" in val
                    or '"kind":' in val
                ):
                    self.object_mode = True
                    # Track as UDT-like so object-dtype series-local is allocated
                    self.udt_vars.add(name)
                    return f"{py}_arr[__bar_idx] = {val}"
                return f"{py}_arr[__bar_idx] = {val}"
            return f"{py} = {val}"

        # Script-level shadow of a UDF (``dmx = dmx(period)``) → rename store target
        # so the call stays bound to the function while the result is a local.
        if name in self.user_funcs:
            loc = f"{self._safe_ident(name)}__loc"
            self.ident_map[name] = loc
            self.object_mode = True
            self.scalar_vars.add(loc)
            self.arrays.discard(f"{name}_arr")
            self.arrays.discard(f"{loc}_arr")
            if is_var:
                return f"if __bar_idx == 0:\n    {loc} = {val}"
            return f"{loc} = {val}"

        # `var table t = na` / `label l = na` → scalar handle (not float series)
        if typed_drawing:
            self.object_mode = True
            self.scalar_vars.add(name)
            self.arrays.discard(f"{name}_arr")
            if is_var:
                return f"if __bar_idx == 0:\n    {name} = {val}"
            return f"{name} = {val}"

        # `var MyState s = na` → object-dtype UDT series (not float64)
        if typed_udt:
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

        # UDF/list/array handle RHS → scalar handle (never float64 series)
        if hasattr(self, "_rhs_is_sequence") and self._rhs_is_sequence(node.value, val):
            self.object_mode = True
            self.scalar_vars.add(name)
            if self.in_function:
                self.local_vars.add(name)
                self.local_sequence_vars.add(name)
                return f"{self._py_ident(name)} = {val}"
            if is_var:
                return f"if {name} is None:\n    {name} = {val}"
            return f"{name} = {val}"

        # String / non-numeric const → scalar (object mode), not float series
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            self.object_mode = True
            self.scalar_vars.add(name)
            self.string_scalars.add(name)
            if is_var:
                return f"if __bar_idx == 0:\n    {name} = {val}"
            return f"{name} = {val}"

        # String/color RHS: bar-constant → scalar; per-bar (ternary colors, …) →
        # object-dtype series. Avoids float64 stores like m_arr[i] = 'EMA' or
        # color_arr[i] = '#22AB94' (TypingError setitem unicode / str→float).
        # Skip when the Pine type is explicitly numeric/bool.
        # Prefer AST stringiness; the visited-string heuristic is only a fallback
        # for color hex that AST missed — never override structured numeric
        # ternaries/switches (``f('SMA') ? sma() : ema()`` has quotes in cond).
        is_stringy_rhs = False
        if not typed_numeric:
            if typed_stringy or self._is_stringy_value(node.value):
                is_stringy_rhs = True
            elif self._call_returns_string(node.value):
                is_stringy_rhs = True
            elif self._looks_like_string_expr(val) and not isinstance(
                node.value, (ast.BinOp, ast.UnaryOp)
            ):
                # Conditional/Switch/Call returning size.tiny / color / string OK.
                # Quotes in *conditions* already stripped by _looks_like_string_expr.
                is_stringy_rhs = True
        if is_stringy_rhs:
            self.object_mode = True
            if not typed_stringy and self._is_bar_constant_stringy(node.value):
                self.scalar_vars.add(name)
                self.string_scalars.add(name)
                if is_var:
                    return f"if __bar_idx == 0:\n    {name} = {val}"
                return f"{name} = {val}"
            # Per-bar string/color series (e.g. close > open ? color.green : color.red)
            # Also `color x = f()` where UDF returns a color string.
            self.string_series.add(name)
            arr_n = self._series_arr_name(name)
            self.arrays.add(arr_n)
            if is_var:
                return (
                    f"if __bar_idx == 0:\n"
                    f"    {arr_n}[__bar_idx] = {val}\n"
                    f"else:\n"
                    f"    {arr_n}[__bar_idx] = {arr_n}[__bar_idx - 1]"
                )
            return f"{arr_n}[__bar_idx] = {val}"

        # Map / scalar object vars (var m = map.new...)
        if name in self.map_vars or name in self.scalar_vars:
            if is_var:
                return f"if __bar_idx == 0:\n    {name} = {val}"
            return f"{name} = {val}"

        # Existing string series re-assign / already tracked
        if name in self.string_series:
            self.object_mode = True
            arr_n = self._series_arr_name(name)
            self.arrays.add(arr_n)
            if is_var:
                return (
                    f"if __bar_idx == 0:\n"
                    f"    {arr_n}[__bar_idx] = {val}\n"
                    f"else:\n"
                    f"    {arr_n}[__bar_idx] = {arr_n}[__bar_idx - 1]"
                )
            return f"{arr_n}[__bar_idx] = {val}"

        # UDT series / chart.point dict / udt_index handle
        if (
            name in self.udt_vars
            or self._looks_like_udt_ctor(node.value)
            or self._looks_like_object_handle_expr(val)
        ):
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

        # array.new*/from/copy/slice / matrix.new* / drawing handles → scalar
        if self._is_drawing_new(node.value) or self._looks_like_drawing_handle_expr(val):
            self.object_mode = True
            self.scalar_vars.add(name)
            self.arrays.discard(f"{name}_arr")
            if is_var:
                return f"if __bar_idx == 0:\n    {name} = {val}"
            return f"{name} = {val}"

        if self._is_array_or_matrix_handle(node.value):
            self.object_mode = True
            self.scalar_vars.add(name)
            self.arrays.discard(f"{name}_arr")
            if is_var:
                return f"if __bar_idx == 0:\n    {name} = {val}"
            return f"{name} = {val}"

        # Sequence / list RHS must not land in float64 series
        # ("setting an array element with a sequence")
        if self._looks_like_sequence_expr(val) or self._is_sequence_producing_call(node.value):
            self.object_mode = True
            self.scalar_vars.add(name)
            self.arrays.discard(f"{name}_arr")
            if is_var:
                return f"if __bar_idx == 0:\n    {name} = {val}"
            return f"{name} = {val}"

        # Non-numeric cast results / opaque object handles → safe float series
        if val and (val.startswith("safe_float(") or val.startswith("safe_int(")):
            self.object_mode = True
            self.arrays.add(f"{name}_arr")
            if is_var:
                return (
                    f"{name}_arr[__bar_idx] = {val} if __bar_idx == 0 "
                    f"else {name}_arr[__bar_idx-1]"
                )
            return f"{name}_arr[__bar_idx] = {val}"

        if not val:
            return ""

        self.arrays.add(f"{name}_arr")
        # Coerce suspicious RHS into float series via safe cast (object mode)
        store_val = val
        if not self._is_safe_numeric_expr(val) and not self.in_function:
            self.object_mode = True
            store_val = f"safe_float({val})"
        if is_var:
            return (
                f"{name}_arr[__bar_idx] = {store_val} if __bar_idx == 0 "
                f"else {name}_arr[__bar_idx-1]"
            )
        return f"{name}_arr[__bar_idx] = {store_val}"

    _STRINGY_INPUT_ATTRS = frozenset(
        {
            "string",
            "text_area",
            "color",
            "symbol",
            "timeframe",
            "session",
            # note: "source" is a series (close/hl2/…) — NOT a string
        }
    )

    _NUMERIC_INPUT_ATTRS = frozenset(
        {
            "int",
            "integer",
            "float",
            "bool",
            "source",
            "price",
            "time",
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
            if node.id in _COLOR_NAMES:
                return True
            # Only true string/color scalars — not numeric intermediates / handles
            # that also live in scalar_vars (those made basis+dev look like concat).
            return node.id in self.string_scalars or node.id in self.string_series
        if isinstance(node, ast.Conditional):
            # Ternary colors/strings: either branch stringy is enough
            return self._is_stringy_value(node.body) or self._is_stringy_value(node.orelse)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            # string concat — both sides must be stringy (numeric + scalar was FP)
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
                    "format_time",
                    "repeat",
                    "replace",
                    "replace_all",
                    "lower",
                    "upper",
                    "trim",
                    "tostring_all",
                ):
                    return True
            if isinstance(f, ast.Name) and f.id in ("str", "tostring", "string"):
                return True
            # bare input(...) — Pine AST packs kwargs as Arg(name=..., value=...)
            if isinstance(f, ast.Name) and f.id == "input":
                return self._is_stringy_input_call(node)
        return False

    def _input_call_named_args(self, node) -> dict[str, object]:
        """Extract name→expr from a Pine ``input``/``input.*`` Call node."""
        out: dict[str, object] = {}
        for raw in getattr(node, "args", ()) or []:
            if hasattr(raw, "name") and getattr(raw, "name", None) and hasattr(raw, "value"):
                out[str(raw.name)] = raw.value
            elif not out and not hasattr(raw, "name"):
                # first bare positional is often defval for input(defval, title)
                out.setdefault("defval", raw if not hasattr(raw, "value") else raw.value)
        for kw in getattr(node, "keywords", ()) or ():
            if getattr(kw, "arg", None):
                out[str(kw.arg)] = kw.value
        return out

    def _is_stringy_input_call(self, node) -> bool:
        """True only for string/color/symbol inputs — not int/float/bool/source."""
        named = self._input_call_named_args(node)
        type_expr = named.get("type")
        if isinstance(type_expr, ast.Attribute) and isinstance(type_expr.value, ast.Name):
            if type_expr.value.id == "input" and type_expr.attr in self._NUMERIC_INPUT_ATTRS:
                return False
            if type_expr.value.id == "input" and type_expr.attr in self._STRINGY_INPUT_ATTRS:
                return True
        defval = named.get("defval")
        if defval is not None:
            if isinstance(defval, ast.Constant) and isinstance(defval.value, str):
                return True
            if isinstance(defval, ast.Constant) and isinstance(defval.value, (int, float, bool)):
                return False
            if isinstance(defval, ast.Name) and defval.id in (
                "close",
                "open",
                "high",
                "low",
                "volume",
                "hl2",
                "hlc3",
                "ohlc4",
                "true",
                "false",
            ):
                return False
            # color / string names
            if self._is_stringy_value(defval):
                return True
            return False
        # input("title only") / input with sole string positional → stringy
        args = list(getattr(node, "args", ()) or [])
        if len(args) == 1:
            a0 = args[0]
            aval = a0.value if hasattr(a0, "value") and getattr(a0, "name", None) is None else a0
            if hasattr(a0, "name") and a0.name:  # keyword-only single arg
                aval = a0.value
            if isinstance(aval, ast.Constant) and isinstance(aval.value, str):
                # title= alone is not a string input; bare input("hello") is
                if hasattr(a0, "name") and a0.name in ("title", "tooltip", "group", "inline"):
                    return False
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
            if node.id in _COLOR_NAMES:
                return True
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
        """Heuristic on visited Python: string/color literals, ternaries of strings.

        String *comparisons* inside conditions (``x == 'SMA'``) must not mark a
        numeric ternary as stringy. That mis-classification forced float series
        (e.g. ``signal = type == \"SMA\" ? sma(...) : ema(...)``) into
        ``dtype=object`` and broke njit helpers like ``numba_crossover``.
        """
        import re

        if not isinstance(val, str) or not val:
            return False
        # Drawing handles / dict events contain quotes but are not string series
        if "__drawings" in val or "'kind':" in val or '"kind":' in val:
            return False
        if val.startswith("numba_store(") or val.startswith("numba_store_src("):
            return False
        if CompilerVisitor._is_quoted_string_expr(val):
            return True
        # Color hex literals are always string/color series values
        if re.search(r"""['\"]#""", val):
            return True
        if ("'" not in val and '"' not in val) or " if " not in val:
            return False
        # Strip non-result quote uses so only ternary *result* branches remain:
        # - comparisons: ``== 'SMA'``, ``(Ma) == ('EMA')``, ``'EMA' != x``
        # - membership: ``in ['a','b']`` / ``in ('a','b')``
        # - dict/list keys from UDT field access: ``__u['BUY']``, ``{'__type__': ...}``
        _q = r"""['\"][^'\"]*['\"]"""
        stripped = re.sub(
            rf"""(?:==|!=|<=|>=|<|>)\s*\(?\s*{_q}\s*\)?""",
            " ",
            val,
        )
        stripped = re.sub(
            rf"""\(?\s*{_q}\s*\)?\s*(?:==|!=|<=|>=|<|>)""",
            " ",
            stripped,
        )
        stripped = re.sub(r"""\bin\s*\[[^\]]*\]""", " ", stripped)
        stripped = re.sub(r"""\bin\s*\([^)]*\)""", " ", stripped)
        # UDT / dict key and __type__ metadata (not series string values)
        stripped = re.sub(r"""\[['\"][^'\"]*['\"]\]""", " ", stripped)
        stripped = re.sub(r"""['\"]__type__['\"]\s*:""", " ", stripped)
        stripped = re.sub(r"""['\"]kind['\"]\s*:""", " ", stripped)
        # Call-arg string tags: f('Swish', …) / equal('Step', method) — condition only
        stripped = re.sub(
            r"""\b[A-Za-z_][\w]*\s*\(\s*['\"][^'\"]*['\"]""",
            " f( ",
            stripped,
        )
        # Remaining quotes → string/color result branches
        # e.g. ('buy' if cond else 'sell') or (c_arr[i] if f else 'red')
        return ("'" in stripped) or ('"' in stripped)

    def _is_drawing_new(self, node) -> bool:
        """True when RHS is a drawing constructor / handle (not a float series)."""
        if not isinstance(node, ast.Call):
            return False
        f = node.func
        if isinstance(f, ast.Specialize):
            f = f.value
        if isinstance(f, ast.Name) and f.id in (
            "hline",
            "bgcolor",
            "barcolor",
            "fill",
            "plotshape",
            "plotchar",
            "plotarrow",
        ):
            return True
        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
            if f.value.id in ("label", "line", "box", "table", "polyline", "linefill") and f.attr == "new":
                return True
        return False

    @staticmethod
    def _looks_like_drawing_handle_expr(val: str | None) -> bool:
        """Visited expr that yields a drawing/table handle dict (not a float)."""
        if not isinstance(val, str) or not val:
            return False
        s = val.strip()
        if "__drawings.append" in s:
            return True
        if "'kind':" in s or '"kind":' in s:
            return True
        return False

    @staticmethod
    def _has_toplevel_comma(s: str) -> bool:
        """True if ``s`` contains a comma outside nested (), [], {}."""
        depth = 0
        for ch in s:
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth = max(0, depth - 1)
            elif ch == "," and depth == 0:
                return True
        return False

    @staticmethod
    def _looks_like_object_handle_expr(val: str) -> bool:
        """Dict / UDT / chart.point / udt_index handle — never float64 series."""
        if not isinstance(val, str) or not val:
            return False
        s = val.strip()
        if s.startswith("{") and s.endswith("}"):
            return True
        if s.startswith("udt_index("):
            return True
        if "'__type__':" in s or '"__type__":' in s:
            return True
        if "'kind':" in s or '"kind":' in s:
            return True
        return False

    @staticmethod
    def _looks_like_sequence_expr(val: str) -> bool:
        """Visited Python expr that is a list/tuple literal or slice (sequence).

        Parenthesized arithmetic with commas only inside call args — e.g.
        ``(mult * numba_stdev_inc(src, n, i, st))`` — must NOT count as a tuple.
        """
        if not isinstance(val, str):
            return False
        s = val.strip()
        if s.startswith("[") and s.endswith("]"):
            # list literal only when top-level commas or empty/single elem without call shape
            inner = s[1:-1].strip()
            if not inner:
                return True
            if CompilerVisitor._has_toplevel_comma(inner):
                return True
            # bare `[x]` single-element list (not `arr[idx]` — those don't wrap whole expr)
            if not any(op in inner for op in ("(", ")", "+", "-", "*", "/", "%", "==", "!=", "<", ">")):
                return True
            return False
        if s.startswith("(") and s.endswith(")") and "," in s:
            inner = s[1:-1]
            if " if " not in inner and " else " not in inner:
                # Tuple only if comma is top-level: `(a, b)` not `(f(a, b))`
                if CompilerVisitor._has_toplevel_comma(inner):
                    return True
        # array.concat / extend lambdas return list handles
        if ".extend(" in s or ("list(" in s and "+" in s):
            return True
        return False

    def _is_sequence_producing_call(self, node) -> bool:
        """array.from / copy / slice / concat etc. produce sequence handles."""
        if not isinstance(node, ast.Call):
            return False
        f = node.func
        if isinstance(f, ast.Specialize):
            f = f.value
        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
            if f.value.id == "array" and f.attr in (
                "from",
                "copy",
                "slice",
                "concat",
                "new",
                "new_float",
                "new_int",
                "new_bool",
                "new_string",
                "new_color",
                "range",
            ):
                return True
            if f.attr in ("sequence_from_series", "sequence_float"):
                return True
        if isinstance(f, ast.Attribute) and f.attr in ("concat", "copy", "slice", "from"):
            return True
        if isinstance(f, ast.Name) and f.id in (
            "sequence_from_series",
            "str_split",
            "array_range",
        ):
            return True
        return False

    def _is_safe_numeric_expr(self, val: str) -> bool:
        """Heuristic: visited expr is safe to store in float64 / use under njit float()."""
        if not isinstance(val, str) or not val:
            return False
        s = val.strip()
        if s in ("np.nan", "True", "False"):
            return True
        if s in ("None",):
            return False
        # UDT field-read / walrus bind is never a float64 scalar.
        if "__u :=" in s or "isinstance(__u" in s:
            return False
        try:
            float(s)
            return True
        except ValueError:
            pass
        # Simple series element / history access only — not complex exprs that merely
        # *contain* ``_arr[`` (e.g. UDT field reads nested over ``foo_arr[__bar_idx]``).
        if s.endswith("[__bar_idx]"):
            base = s[: -len("[__bar_idx]")]
            if base.endswith("_arr"):
                name = base[: -len("_arr")]
                if name in self.string_series or name in self.udt_vars:
                    return False
                if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*_arr", base):
                    return True
            # Complex base ending in [__bar_idx] is not a plain numeric series load.
        elif "_arr[" in s and s.count("[") == 1 and re.match(
            r"^[A-Za-z_][A-Za-z0-9_]*_arr\[", s
        ):
            name = s.split("_arr[", 1)[0]
            if name in self.string_series or name in self.udt_vars:
                return False
            return True
        if s.startswith("numba_") or s.startswith("np."):
            return True
        if s in ("__bar_idx", "n_bars") or s.startswith("float(__bar_idx") or s.startswith(
            "float(n_bars"
        ):
            return True
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", s):
            if s in self.user_funcs or s in self.scalar_vars or s in self.map_vars:
                return False
            if s in self.string_series or s in self.udt_vars:
                return False
            # Unknown bare name might be a function or handle — not safe
            return False
        if ("'" in s or '"' in s or "{" in s or "[" in s):
            return False
        if re.search(
            r"\b(str|dict|list|append|__drawings|__type__|safe_float|safe_int)\b", s
        ):
            return False
        for uf in self.user_funcs:
            if re.search(rf"\b{re.escape(uf)}\b(?!\s*\()", s):
                return False
            # UDF *calls* are not known-numeric (may return string / None / UDT)
            if re.search(rf"\b{re.escape(uf)}\s*\(", s):
                return False
        # Any other call that is not numba_/np./safe_* is opaque
        for m in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", s):
            callee = m.group(1)
            if callee in (
                "numba_store",
                "numba_store_src",
                "store_src_py",
                "safe_float",
                "safe_int",
                "safe_len",
                "safe_period",
                "safe_iter",
                "udt_index",
                "float",
                "int",
                "bool",
                "abs",
                "min",
                "max",
                "sum",
                "len",
                "range",
                "list",
                "isinstance",
            ):
                continue
            if callee.startswith("numba_") or callee.startswith("np"):
                continue
            return False
        if re.fullmatch(r"[\w\s\+\-\*/%\(\)\.\,\<\>\=\!\&\|?:]+", s):
            return True
        return False

    @staticmethod
    def _looks_like_version_string(val: str) -> bool:
        """True for quoted version-like defaults such as '0.0.1' / \"1.2.3\"."""
        if not isinstance(val, str):
            return False
        s = val.strip()
        if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
            inner = s[1:-1]
            if re.fullmatch(r"\d+\.\d+\.\d+[\w\.\-]*", inner):
                return True
            if inner.count(".") >= 2 and re.fullmatch(r"[\d\.]+", inner):
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
                "concat",
                "copy",
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
        # Method form: a.concat(b) / a.copy() / a.slice(...)
        if isinstance(f, ast.Attribute) and f.attr in (
            "concat",
            "copy",
            "slice",
            "from",
        ):
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
            if not self.in_function:
                self.arrays.add(f"{el.id}_arr")
            else:
                self.local_vars.add(el.id)

        def _store_numeric(name: str, expr: str) -> str:
            if self.in_function:
                # Locals used as TA sources: keep as bar scalar (materialize does the rest)
                return f"{self._py_ident(name)} = {expr}"
            # Multi-return may include strings (shape names) — object series
            if self._looks_like_string_expr(expr):
                self.object_mode = True
                self.string_series.add(name)
                arr_n = self._series_arr_name(name)
                self.arrays.add(arr_n)
                return f"{arr_n}[__bar_idx] = {expr}"
            # Keep njit-friendly bare stores in numeric mode; object mode uses safe_float
            if self.object_mode:
                return f"{name}_arr[__bar_idx] = safe_float({expr})"
            return f"{name}_arr[__bar_idx] = {expr}"

        def _store_sequence(name: str, expr: str) -> str:
            """Array/list handle → scalar (or UDF local), never float64 series."""
            self.object_mode = True
            if self.in_function:
                self.local_vars.add(name)
                self.local_sequence_vars.add(name)
                return f"{self._py_ident(name)} = {expr}"
            self.scalar_vars.add(name)
            self.arrays.discard(f"{name}_arr")
            return f"{name} = {expr}"

        def _elem_expr(i: int) -> str:
            return (
                f"(__tup[{i}] if isinstance(__tup, (tuple, list)) "
                f"and len(__tup) > {i} else "
                f"(__tup if {i} == 0 and not isinstance(__tup, (tuple, list)) "
                f"else np.nan))"
            )

        def _unpack_call(call_code: str, *, as_sequence: bool) -> str:
            lines = [f"__tup = {call_code}"]
            store = _store_sequence if as_sequence else _store_numeric
            for i, name in enumerate(names):
                lines.append(store(name, _elem_expr(i)))
            return "\n".join(lines)

        # Prefer structured multi-return for known multi-value TA
        if isinstance(node.value, ast.Call):
            func = node.value.func
            if isinstance(func, ast.Specialize):
                func = func.value
            # request.security(sym, tf, [close, low, high]) — same-symbol unpack
            is_sec = False
            if isinstance(func, ast.Name) and func.id in ("security",):
                is_sec = True
            if (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "request"
                and func.attr in ("security", "security_lower_tf", "seed")
            ):
                is_sec = True
            if is_sec:
                # expression is 3rd positional (or named `expression`)
                expr_node = None
                pos = []
                for raw in node.value.args or []:
                    if hasattr(raw, "name") and getattr(raw, "name", None):
                        if str(raw.name) in ("expression", "expr"):
                            expr_node = raw.value
                    else:
                        pos.append(raw.value if hasattr(raw, "value") else raw)
                if expr_node is None and len(pos) >= 3:
                    expr_node = pos[2]
                if isinstance(expr_node, ast.Tuple):
                    lines = []
                    for name, el in zip(names, expr_node.elts, strict=False):
                        if self._ast_expr_is_sequence(el):
                            lines.append(_store_sequence(name, self.visit(el)))
                        else:
                            lines.append(_store_numeric(name, self.visit(el)))
                    return "\n".join(lines) if lines else ""
                # Multi-target from call expression: ``detect_spike(...)`` multi-return
                if expr_node is not None and len(names) > 1:
                    self.object_mode = True
                    call_code = (self.visit(expr_node) or "").strip()
                    if not call_code:
                        lines = []
                        for name in names:
                            lines.append(_store_numeric(name, "np.nan"))
                        return "\n".join(lines)
                    as_seq = self._call_returns_sequence(expr_node)
                    return _unpack_call(call_code, as_sequence=as_seq)
                # Single-target / non-tuple expression: assign first name only
                if expr_node is not None and names:
                    if self._ast_expr_is_sequence(expr_node) or self._call_returns_sequence(
                        expr_node
                    ):
                        return _store_sequence(names[0], self.visit(expr_node))
                    return _store_numeric(names[0], self.visit(expr_node))

            call_code = (self.visit(node.value) or "").strip()
            # Empty RHS: imported lib stubs (console.init, …) emit no code.
            # Never leave ``__tup = `` / ``x = `` — that is invalid Python.
            if not call_code:
                self.object_mode = True
                if len(names) > 1:
                    # Scalar handles (console table/log), not float series
                    lines = []
                    for name in names:
                        if not self.in_function:
                            self.scalar_vars.add(name)
                            self.arrays.discard(f"{name}_arr")
                            lines.append(f"{name} = None")
                        else:
                            lines.append(f"{self._py_ident(name)} = None")
                    return "\n".join(lines)
                if names:
                    name = names[0]
                    if not self.in_function:
                        self.scalar_vars.add(name)
                        self.arrays.discard(f"{name}_arr")
                        return f"{name} = None"
                    return f"{self._py_ident(name)} = None"
                return ""
            # Multi-return forms emit a temp unpack.
            # IMPORTANT: do NOT match bare "(" alone — nearly every parenthesized
            # numeric expr starts with "(" and would store a sequence into float.
            known_multi = call_code.startswith(
                (
                    "numba_bb(",
                    "numba_bb_inc(",
                    "numba_macd(",
                    "numba_macd_inc(",
                    "numba_dmi(",
                )
            )
            # Explicit multi-value stubs like "(0.0, 0.0, 25.0)" only
            stub_multi = (
                call_code.startswith("(")
                and call_code.rstrip().endswith(")")
                and "," in call_code
                and re.fullmatch(
                    r"\([^()]*\)",
                    call_code.strip(),
                )
                is not None
            )
            # console.init → ``(None, None)`` matches stub_multi shape but must be
            # scalar handles, not float64 series stores.
            none_stub = bool(
                re.fullmatch(r"\(None(\s*,\s*None)*\s*,?\)", call_code.strip())
            )
            if known_multi or (stub_multi and not none_stub):
                return _unpack_call(call_code, as_sequence=False)

            # Multi-target from UDF / unknown call: may return a tuple at runtime.
            # Sequence-returning UDFs (arrays) → scalar handles; numeric multi-return
            # → float series. Imported lib multi-return (console.init) → scalars.
            if len(names) > 1:
                self.object_mode = True
                uf_name = None
                is_import_method = False
                if isinstance(node.value, ast.Call):
                    f = node.value.func
                    if isinstance(f, ast.Specialize):
                        f = f.value
                    if isinstance(f, ast.Name):
                        uf_name = f.id
                    elif isinstance(f, ast.Attribute):
                        uf_name = f.attr
                        if isinstance(f.value, ast.Name) and (
                            f.value.id in getattr(self, "import_aliases", set())
                            or f.value.id in _NS
                        ):
                            is_import_method = True
                seq_udf = bool(uf_name and uf_name in self.func_returns_sequence) or (
                    self._call_returns_sequence(node.value)
                )
                as_sequence = seq_udf or is_import_method or none_stub
                return _unpack_call(call_code, as_sequence=as_sequence)

            # Single-target call
            if names:
                if self._call_returns_sequence(node.value):
                    return _store_sequence(names[0], call_code)
                return _store_numeric(names[0], call_code)
            return ""

        # Fallback: visit RHS once if it is a simple tuple literal
        if isinstance(node.value, ast.Tuple):
            lines = []
            for name, el in zip(names, node.value.elts, strict=False):
                if self._ast_expr_is_sequence(el):
                    lines.append(_store_sequence(name, self.visit(el)))
                else:
                    lines.append(_store_numeric(name, self.visit(el)))
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
            if isinstance(node.value, ast.If):
                tern = self._try_if_as_ternary(node.value)
                if tern is not None:
                    return f"{obj}[{node.target.attr!r}] = {tern}"
                target = f"{obj}[{node.target.attr!r}]"
                return self._emit_if_assign(target, node.value)
            val = self.visit(node.value)
            # UDT field write: p.x := 1
            return f"{obj}[{node.target.attr!r}] = {val}"
        # Series locals must write through their persistent array
        if (
            self.in_function
            and isinstance(node.target, ast.Name)
            and node.target.id in self.series_locals
        ):
            if isinstance(node.value, ast.If):
                tern = self._try_if_as_ternary(node.value)
                py = self._py_ident(node.target.id)
                target = f"{py}_arr[__bar_idx]"
                if tern is not None:
                    return f"{target} = {tern}"
                return self._emit_if_assign(target, node.value)
            val = self.visit(node.value)
            py = self._py_ident(node.target.id)
            # line/label/box handles into series-local → object dtype (not float64)
            if val and (
                "__drawings" in val
                or val.startswith("{")
                or "'kind':" in val
                or '"kind":' in val
            ):
                self.object_mode = True
                self.udt_vars.add(node.target.id)
            return f"{py}_arr[__bar_idx] = {val}"
        if self.in_function and isinstance(node.target, ast.Name):
            self.local_vars.add(node.target.id)
            py = self._py_ident(node.target.id)
            if isinstance(node.value, ast.If):
                tern = self._try_if_as_ternary(node.value)
                if tern is not None:
                    return f"{py} = {tern}"
                return self._emit_if_assign(py, node.value)
            val = self.visit(node.value)
            return f"{py} = {val}"
        # Script-level: drawing/table handle must not setitem float64 series
        # (var table t = na; t := table.new(...) was t_arr[i] = dict → float(dict)).
        if isinstance(node.target, ast.Name):
            name = node.target.id
            if isinstance(node.value, ast.If):
                tern = self._try_if_as_ternary(node.value)
                if tern is not None:
                    val = tern
                else:
                    target_store = f"{name}_arr[__bar_idx]"
                    self.arrays.add(f"{name}_arr")
                    return self._emit_if_assign(target_store, node.value)
            else:
                val = self.visit(node.value)
            if (
                name in self.scalar_vars
                or name in self.map_vars
                or self._is_drawing_new(node.value)
                or self._looks_like_drawing_handle_expr(val)
            ):
                self.object_mode = True
                self.scalar_vars.add(name)
                self.arrays.discard(f"{name}_arr")
                return f"{name} = {val}"
            if name in self.string_series or name in self.udt_vars:
                self.object_mode = True
                self.arrays.add(f"{name}_arr")
                return f"{name}_arr[__bar_idx] = {val}"
            if self._looks_like_object_handle_expr(val):
                self.object_mode = True
                self.udt_vars.add(name)
                self.arrays.add(f"{name}_arr")
                return f"{name}_arr[__bar_idx] = {val}"
            # Default series reassign
            if f"{name}_arr" in self.arrays or name not in self.scalar_vars:
                self.arrays.add(f"{name}_arr")
                store_val = val
                if not self._is_safe_numeric_expr(val):
                    self.object_mode = True
                    store_val = f"safe_float({val})"
                return f"{name}_arr[__bar_idx] = {store_val}"
            return f"{name} = {val}"
        target = self.visit(node.target)
        val = self.visit(node.value)
        return f"{target} = {val}"

    def visit_AugAssign(self, node: ast.AugAssign):
        """Pine ``a += x`` / ``b -= y`` (common in switch arms / loops)."""
        op = node.op
        if isinstance(op, ast.Add):
            op_s = "+"
        elif isinstance(op, ast.Sub):
            op_s = "-"
        elif isinstance(op, ast.Mult):
            op_s = "*"
        elif isinstance(op, ast.Div):
            op_s = "/"
        elif isinstance(op, ast.Mod):
            op_s = "%"
        else:
            op_s = "+"
        val = self.visit(node.value)
        if isinstance(node.target, ast.Name):
            name = node.target.id
            if self.in_function:
                self.local_vars.add(name)
                if name in self.series_locals:
                    py = self._py_ident(name)
                    base = f"{py}_arr[__bar_idx]"
                    return f"{base} = (({base}) {op_s} ({val}))"
                py = self._py_ident(name)
                return f"{py} = (({py}) {op_s} ({val}))"
            if name in self.scalar_vars or name in self.map_vars:
                return f"{name} = (({name}) {op_s} ({val}))"
            # Script-level series
            self.arrays.add(f"{name}_arr")
            base = f"{name}_arr[__bar_idx]"
            return f"{base} = (({base}) {op_s} ({val}))"
        if isinstance(node.target, ast.Attribute):
            self.object_mode = True
            obj = self.visit(node.target.value)
            key = node.target.attr
            return (
                f"{obj}[{key!r}] = (({obj}[{key!r}]) {op_s} ({val}))"
            )
        target = self.visit(node.target)
        return f"{target} = (({target}) {op_s} ({val}))"

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
        # Script-level (or free) rebinding of a UDF: ``sar = sar(...)`` then
        # ``sar > close`` must read ``sar__loc``, not the function object.
        # Call sites still use ``func.id`` directly (not visit_Name).
        if node.id in self.ident_map:
            mapped = self.ident_map[node.id]
            if mapped.endswith(("__loc", "__p")):
                if mapped in self.scalar_vars or mapped in self.map_vars:
                    return mapped
                if f"{mapped}_arr" in self.arrays:
                    return f"{mapped}_arr[__bar_idx]"
                if not self.in_function:
                    return mapped
        # Script-level scalars used inside a UDF must be free params (module-level
        # functions cannot close over execute_script locals).
        if self.in_function and node.id in (self.map_vars | self.scalar_vars):
            self._free_scalars_current.add(node.id)
            return self._py_ident(node.id) if node.id in self.ident_map else node.id
        if node.id in self.map_vars or node.id in self.scalar_vars:
            return self._py_ident(node.id) if node.id in self.ident_map else node.id
        # Built-in series / scalars (never allocate bare *_arr)
        if node.id == "tr":
            return "numba_tr(high_arr, low_arr, close_arr, __bar_idx)"
        if node.id == "obv":
            st = self._alloc_fixed_state("obv", 2)
            return f"numba_obv_inc(close_arr, vol_arr, __bar_idx, {st})"
        if node.id == "pvt":
            # Price Volume Trend: cum((close-close[1])/close[1] * volume)
            st = self._alloc_fixed_state("pvt", 2)
            return f"numba_pvt_inc(close_arr, vol_arr, __bar_idx, {st})"
        if node.id in ("accdist", "ad", "accumulation_distribution"):
            # Chaikin A/D line stub — volume-weighted mid position (good enough for src=)
            return (
                "((close_arr[__bar_idx] - low_arr[__bar_idx]) - "
                "(high_arr[__bar_idx] - close_arr[__bar_idx])) / "
                "((high_arr[__bar_idx] - low_arr[__bar_idx]) "
                "if (high_arr[__bar_idx] - low_arr[__bar_idx]) != 0 else np.nan) "
                "* vol_arr[__bar_idx]"
            )
        if node.id == "na":
            return "np.nan"
        if node.id == "color":
            self.object_mode = True
            return repr("#000000")
        if node.id in ("open", "high", "low", "close", "Open", "High", "Low", "Close"):
            return f"{node.id.lower()}_arr[__bar_idx]"
        if node.id in ("volume", "Volume"):
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
        if node.id == "hlcc4":
            # (high + low + close + close) / 4
            return (
                "((high_arr[__bar_idx] + low_arr[__bar_idx] + "
                "close_arr[__bar_idx] + close_arr[__bar_idx]) / 4.0)"
            )
        if node.id == "bar_index":
            return "__bar_idx"
        # v1–v3: bare `n` is bar_index unless the script defines its own `n`
        if node.id == "n" and (
            f"n_arr" not in self.arrays
            and "n" not in self.local_vars
            and "n" not in self.param_names
            and "n" not in self.scalar_vars
            and "n" not in self.series_params
            and "n" not in self.series_locals
        ):
            return "__bar_idx"
        # Built-in time series / calendar scalars (no time_arr allocation)
        if node.id == "last_bar_index":
            return "(n_bars - 1)"
        if node.id == "last_bar_time":
            return "(float(n_bars - 1) * 60000.0)"
        if node.id == "time":
            # ms timestamp stub: bar index * 60_000
            return "(float(__bar_idx) * 60000.0)"
        if node.id == "time_close":
            return "(float(__bar_idx) * 60000.0 + 59999.0)"
        if node.id == "timenow":
            return "(float(n_bars) * 60000.0)"
        if node.id in ("PI", "pi"):
            return "np.pi"
        if node.id == "max_bars_back":
            return "n_bars"
        if node.id == "tz":
            self.object_mode = True
            return repr("UTC")
        # Bare color names (green, red, …) — not series arrays
        if node.id in _COLOR_NAMES:
            self.object_mode = True
            cname = "gray" if node.id == "grey" else node.id
            return repr(self._color_const(cname))
        # Bare linestyle / plot style identifiers (linestyle=dotted)
        if node.id in _LINESTYLE_NAMES:
            self.object_mode = True
            return repr(node.id)
        # syminfo_* / timeframe_* flattened scalars (legacy / import style)
        if node.id.startswith("syminfo_"):
            attr = node.id[len("syminfo_") :]
            stubs = {
                "mintick": "0.01",
                "pointvalue": "1.0",
                "ticker": repr("SYMBOL"),
                "tickerid": repr("SYMBOL"),
                "currency": repr("USD"),
                "basecurrency": repr("USD"),
                "type": repr("stock"),
                "timezone": repr("UTC"),
                "session": repr("0930-1600"),
                "period": repr("1D"),
            }
            if attr in stubs:
                val = stubs[attr]
                if val.startswith("'") or val.startswith('"'):
                    self.object_mode = True
                return val
            return "0.0"
        if node.id.startswith("timeframe_"):
            attr = node.id[len("timeframe_") :]
            if attr == "period":
                self.object_mode = True
                return repr("1D")
            if attr == "multiplier":
                return "1"
            if attr in (
                "isintraday",
                "isdaily",
                "isweekly",
                "ismonthly",
                "isseconds",
                "isminutes",
                "ishours",
            ):
                return "True" if attr == "isdaily" else "False"
            if attr == "in_seconds":
                return "86400.0"
            self.object_mode = True
            return repr(attr)
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
        # User series win over namespace tokens (e.g. `barcolor = …` then barcolor(...))
        if node.id in self.udt_vars or node.id in self.string_series:
            return f"{node.id}_arr[__bar_idx]"
        # Inside UDF: free outer vars → bare name (scalar free param) *before*
        # treating script-level ``*_arr`` as series. Otherwise ``mult = input.float``
        # (allocates mult_arr) forces ``mult_arr[__bar_idx]`` inside the UDF and
        # mis-orders free_series ahead of free_scalars / __ema*_st.
        if self.in_function and node.id not in self.local_vars:
            if node.id in self.series_params or node.id in self.series_locals:
                py = self._py_ident(node.id)
                return f"{py}_arr[__bar_idx]" if node.id in self.series_locals else f"{py}[__bar_idx]"
            # History in this UDF → series free param (handled via free_series *_arr)
            if node.id in getattr(self, "history_names_current", set()):
                # Will land in free_series as {name}_arr via body scan
                return f"{node.id}_arr[__bar_idx]"
            # Bare free → scalar free param (mult, colBull, settings, …)
            self._free_scalars_current.add(node.id)
            return self._py_ident(node.id)
        if f"{node.id}_arr" in self.arrays and node.id not in self.scalar_vars:
            return f"{node.id}_arr[__bar_idx]"
        if node.id in self.import_aliases:
            # Library namespace as value — stub null handle
            self.object_mode = True
            return "None"
        if node.id in _NS:
            return node.id
        # UDF names used as values (rare) — not series
        if node.id in self.user_funcs:
            return node.id
        return f"{node.id}_arr[__bar_idx]"
    def visit_Attribute(self, node: ast.Attribute):
        # color.red etc.
        if isinstance(node.value, ast.Name) and node.value.id == "ta":
            # Bare series-style TA attrs (no Call) — always emit a call expr, never
            # the dead identifier ``ta_vwap`` / ``ta_obv`` / ``ta_tr``.
            if node.attr == "tr":
                return "numba_tr(high_arr, low_arr, close_arr, __bar_idx)"
            if node.attr == "obv":
                st = self._alloc_fixed_state("obv", 2)
                return f"numba_obv_inc(close_arr, vol_arr, __bar_idx, {st})"
            if node.attr == "vwap":
                st = self._alloc_fixed_state("vwap", 3)
                return f"numba_vwap_inc(close_arr, vol_arr, __bar_idx, {st})"
            if node.attr == "accdist":
                return (
                    "((close_arr[__bar_idx] - low_arr[__bar_idx]) - "
                    "(high_arr[__bar_idx] - close_arr[__bar_idx])) / "
                    "((high_arr[__bar_idx] - low_arr[__bar_idx]) "
                    "if (high_arr[__bar_idx] - low_arr[__bar_idx]) != 0 else np.nan) "
                    "* vol_arr[__bar_idx]"
                )
            # Method attrs used as Call targets (ta.sma → ta_sma) stay as identifiers.
            return f"ta_{node.attr}"
        if isinstance(node.value, ast.Name) and node.value.id == "color":
            return repr(self._color_const(node.attr))
        # alert.freq_once_per_bar_close / alert.freq_all
        if isinstance(node.value, ast.Name) and node.value.id == "alert":
            self.object_mode = True
            return repr(node.attr)
        # Must run before fallthrough (visit Name label → "label" then "label_style_x").
        if isinstance(node.value, ast.Name) and node.value.id in _STYLE_NS:
            if node.attr.startswith("style_"):
                return repr(node.attr)
        # math.pi / math.e / math.isfinite (bare) — predicates also handled in Call
        if isinstance(node.value, ast.Name) and node.value.id == "math":
            if node.attr == "pi":
                return "np.pi"
            if node.attr == "e":
                return "np.e"
            if node.attr == "isfinite":
                return "np.isfinite"
            if node.attr == "isnan":
                return "np.isnan"
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
        # UDT field read: p.x → p['x'] in object mode (na-safe: float/None → na).
        # Use a tuple bind so the name is bound *before* isinstance (walrus in the
        # true-branch of a ternary leaves __u unbound when the cond runs first).
        def _udt_field(base: str, attr: str) -> str:
            return (
                f"((__u := ({base}), "
                f"__u[{attr!r}] if isinstance(__u, dict) else np.nan)[1])"
            )

        # Chained field reads (``udt_series.field.nested``) always re-wrap: the
        # parent visit already emitted a walrus bind, which must not fall through
        # to ``{val}_{attr}`` (invalid Python like ``...)[1])_price``).
        if "__u :=" in val or "isinstance(__u" in val:
            self.object_mode = True
            return _udt_field(val, node.attr)

        # Method/call result field access: ``vwapData.prev(0).vwap``
        # Must not become ``prev(vwapData, 0)_vwap`` (invalid Python).
        if isinstance(node.value, ast.Call):
            self.object_mode = True
            return _udt_field(val, node.attr)
        if (
            isinstance(val, str)
            and "(" in val
            and not self._is_safe_numeric_expr(val)
            and not val.startswith(("numba_", "safe_", "np.", "str(", "float(", "int(", "bool("))
            and re.search(r"\b[A-Za-z_][A-Za-z0-9_]*\s*\(", val)
        ):
            self.object_mode = True
            return _udt_field(val, node.attr)

        if self.object_mode or (
            isinstance(node.value, ast.Name) and node.value.id in self.udt_vars
        ):
            self.object_mode = True
            # strip series indexing for type-ish access
            if val.endswith("[__bar_idx]"):
                # UDT series element may be na (nan) — never subscript a scalar
                return _udt_field(val, node.attr)
            if val in self.map_vars or val in self.scalar_vars:
                return _udt_field(val, node.attr)
            # Other object handles (e.g. array.get returning UDT)
            if not self._is_safe_numeric_expr(val):
                return _udt_field(val, node.attr)
        if val.endswith("[__bar_idx]"):
            val = val[:-11]
        # Avoid dead identifiers like ``numba_sma_inc(..._st)_rma`` when an
        # Attribute is applied to a numba_* call result (should be a call).
        if val.startswith("numba_") and "(" in val:
            attr = node.attr
            if attr == "tr":
                return "numba_tr(high_arr, low_arr, close_arr, __bar_idx)"
            if attr == "obv":
                st = self._alloc_fixed_state("obv", 2)
                return f"numba_obv_inc(close_arr, vol_arr, __bar_idx, {st})"
            if attr == "vwap":
                st = self._alloc_fixed_state("vwap", 3)
                src = self._materialize_series_source(val)
                return f"numba_vwap_inc({src}, vol_arr, __bar_idx, {st})"
            if attr in ("max", "min"):
                src = self._materialize_series_source(val)
                nb = "numba_highest" if attr == "max" else "numba_lowest"
                return f"{nb}({src}, __bar_idx + 1, __bar_idx)"
            # Unknown attr on numba result → function call form, not val_attr
            return f"{attr}({val})"
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
            # safe_int: size may be na / float NaN (int(nan) raises)
            return (
                f"([{fill}] * max(0, safe_int({size})) "
                f"if safe_int({size}) > 0 else [])"
            )
        if func_name == "array_sort":
            # Mutates in place; return id (Pine void / chain-friendly).
            # UDT dict elements need a key so bare ``.sort()`` does not compare dicts.
            a = ra(args, kwargs, ("id", "order"), aliases={"sort_field": "order"})
            # Also accept sort_field as a dedicated kw (array.sort(..., sort_field=…))
            sort_field = kwargs.get("sort_field")
            if not a and not sort_field:
                return "[]"
            arr = a[0] if a else "[]"
            order = a[1] if len(a) > 1 else None
            reverse = (
                f"reverse=({order} in ('descending', 'desc', -1, True))"
                if order is not None
                else "reverse=False"
            )
            if sort_field is not None:
                # Field name or index into UDT ordered values
                return (
                    f"((lambda __a, __sf: ("
                    f"__a.sort(key=lambda __e: ("
                    f"__e.get(__sf, np.nan) if isinstance(__e, dict) and isinstance(__sf, str) "
                    f"else (list(__e.values())[int(__sf)] if isinstance(__e, dict) "
                    f"and 0 <= int(safe_int(__sf)) < len(__e) else __e)), "
                    f"{reverse}), __a)[1])({arr}, {sort_field}))"
                )
            return (
                f"((lambda __a: ("
                f"__a.sort(key=lambda __e: ("
                f"next(iter(__e.values()), np.nan) if isinstance(__e, dict) else __e), "
                f"{reverse}), __a)[1])({arr}))"
            )
        if func_name == "array_reverse":
            a = ra(args, kwargs, ("id",))
            return f"({a[0]}.reverse(), {a[0]})[1]" if a else "[]"
        if func_name == "array_from":
            return f"[{', '.join(args)}]" if args else "[]"
        if func_name == "array_copy":
            a = ra(args, kwargs, ("id",))
            return f"list({a[0]})" if a else "[]"
        if func_name == "array_concat":
            # array.concat(id1, id2) — append id2 onto id1 (mutate) and return id1
            a = ra(
                args,
                kwargs,
                ("id1", "id2"),
                aliases={"id": "id1", "other": "id2"},
            )
            if len(a) >= 2:
                return (
                    f"((lambda __a, __b: (__a.extend(list(__b or [])), __a)[1])"
                    f"({a[0]} if {a[0]} is not None else [], {a[1]}))"
                )
            return f"list({a[0]} or [])" if a else "[]"
        if func_name == "array_covariance":
            # Stub: real cov needs two arrays + means; enough to avoid NameError
            return "0.0"
        if func_name == "matrix_copy":
            a = ra(args, kwargs, ("id",))
            return f"[list(__row) for __row in {a[0]}]" if a else "[]"
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
            a = ra(args, kwargs, ("id", "index", "column"), aliases={"col": "column", "row": "index"})
            # matrix.get(row, column) when 3 args
            if len(a) >= 3:
                return (
                    f"({a[0]}[int({a[1]})][int({a[2]})] "
                    f"if {a[0]} and 0 <= int({a[1]}) < len({a[0]}) "
                    f"and 0 <= int({a[2]}) < (len({a[0]}[int({a[1]})]) if {a[0]} else 0) "
                    f"else np.nan)"
                )
            if len(a) >= 2:
                # udt_index: works for list/ndarray and UDT dicts (complex as
                # {'real':…,'imag':…} passed where float[] is expected).
                return f"udt_index({a[0]}, {a[1]})"
            return "np.nan"
        if func_name == "array_set":
            # Method ``m.set(row, col, val)`` → 4 args after id prepend.
            # Method ``a.set(index, val)`` → 3 args.
            a = ra(
                args,
                kwargs,
                ("id", "index", "value", "column"),
                aliases={"col": "column", "row": "index"},
            )
            if len(args) >= 4:
                # Expression-safe matrix cell write (no bare ``=`` in call/ternary)
                return (
                    f"{args[0]}[int({args[1]})].__setitem__(int({args[2]}), {args[3]})"
                )
            if len(args) >= 3:
                return f"{args[0]}.__setitem__(int({args[1]}), {args[2]})"
            if len(a) >= 3:
                return f"{a[0]}.__setitem__(int({a[1]}), {a[2]})"
            return ""
        if func_name == "array_size":
            a = ra(args, kwargs, ("id",))
            # safe_len: scalars (misclassified array handles) → 0, not TypeError
            return f"safe_len({a[0]})" if a else "0"
        if func_name == "array_range":
            # array.range(start, stop) / array.range(length)
            if len(args) >= 2:
                return (
                    f"list(range(int(safe_float({args[0]})), "
                    f"int(safe_float({args[1]}))))"
                )
            if args:
                return f"list(range(int(safe_float({args[0]}))))"
            return "[]"
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
        if func_name in ("matrix_avg", "matrix_sum", "matrix_max", "matrix_min"):
            a = ra(args, kwargs, ("id",))
            if not a:
                return "np.nan" if func_name != "matrix_sum" else "0.0"
            if func_name == "matrix_sum":
                return f"safe_sum({a[0]})"
            if func_name == "matrix_avg":
                return (
                    f"((safe_sum({a[0]})) / (max(1, sum(len(__r) for __r in ({a[0]} or [])))) "
                    f"if {a[0]} else np.nan)"
                )
            if func_name == "matrix_max":
                return f"safe_max({a[0]})"
            return f"safe_min({a[0]})"
        if func_name == "matrix_row":
            a = ra(args, kwargs, ("id", "row"))
            if len(a) >= 2:
                return (
                    f"(list({a[0]}[int({a[1]})]) if {a[0]} and "
                    f"0 <= int({a[1]}) < len({a[0]}) else [])"
                )
            return "[]"
        if func_name == "matrix_col":
            a = ra(args, kwargs, ("id", "column"), aliases={"col": "column"})
            if len(a) >= 2:
                return (
                    f"([__r[int({a[1]})] for __r in {a[0]} "
                    f"if __r and 0 <= int({a[1]}) < len(__r)] if {a[0]} else [])"
                )
            return "[]"
        if func_name == "matrix_submatrix":
            a = ra(
                args,
                kwargs,
                ("id", "from_row", "to_row", "from_column", "to_column"),
                aliases={
                    "from_col": "from_column",
                    "to_col": "to_column",
                },
            )
            if not a:
                return "[]"
            m = a[0]
            fr = a[1] if len(a) > 1 else "0"
            tr = a[2] if len(a) > 2 else f"len({m})"
            fc = a[3] if len(a) > 3 else "0"
            tc = a[4] if len(a) > 4 else None
            if tc is None:
                return (
                    f"([__r[int({fc}):] for __r in ({m} or [])[int({fr}):int({tr})]])"
                )
            return (
                f"([__r[int({fc}):int({tc})] for __r in ({m} or [])[int({fr}):int({tr})]])"
            )
        if func_name in ("matrix_add_col", "matrix_add_column"):
            a = ra(
                args,
                kwargs,
                ("id", "column", "array_id"),
                aliases={
                    "col": "column",
                    "array": "array_id",
                    "id_array": "array_id",
                    "index": "column",
                },
            )
            # Prefer helper (handles empty matrix: column data defines row count)
            if not a:
                return "[]"
            if len(a) >= 3:
                return f"matrix_add_col({a[0]}, {a[1]}, {a[2]})"
            if len(a) == 2:
                return f"matrix_add_col({a[0]}, {a[1]})"
            return f"matrix_add_col({a[0]})"
        if func_name in ("matrix_remove_col", "matrix_remove_column"):
            a = ra(args, kwargs, ("id", "column"), aliases={"col": "column", "index": "column"})
            if len(a) >= 2:
                return f"matrix_remove_col({a[0]}, {a[1]})"
            if a:
                return f"matrix_remove_col({a[0]}, 0)"
            return "[]"
        if func_name == "matrix_remove_row":
            a = ra(args, kwargs, ("id", "row"), aliases={"index": "row"})
            if len(a) >= 2:
                return f"matrix_remove_row({a[0]}, {a[1]})"
            if a:
                return f"matrix_remove_row({a[0]}, 0)"
            return "[]"
        if func_name == "matrix_add_row":
            a = ra(
                args,
                kwargs,
                ("id", "row", "array_id"),
                aliases={"array": "array_id", "row_id": "array_id", "index": "row"},
            )
            if not a:
                return "[]"
            if len(a) >= 3:
                return f"matrix_add_row({a[0]}, {a[1]}, {a[2]})"
            if len(a) == 2:
                return f"matrix_add_row({a[0]}, {a[1]})"
            return f"matrix_add_row({a[0]})"
        if func_name == "matrix_reshape":
            a = ra(args, kwargs, ("id", "rows", "columns"), aliases={"cols": "columns"})
            if len(a) >= 3:
                return f"matrix_reshape({a[0]}, {a[1]}, {a[2]})"
            if a:
                return f"matrix_reshape({a[0]}, 0, 0)"
            return "[]"
        if func_name == "matrix_swap_rows":
            a = ra(args, kwargs, ("id", "row1", "row2"), aliases={"row_1": "row1", "row_2": "row2"})
            if len(a) >= 3:
                return f"matrix_swap_rows({a[0]}, {a[1]}, {a[2]})"
            return a[0] if a else "[]"
        if func_name == "matrix_swap_columns":
            a = ra(
                args,
                kwargs,
                ("id", "column1", "column2"),
                aliases={"col1": "column1", "col2": "column2"},
            )
            if len(a) >= 3:
                return f"matrix_swap_columns({a[0]}, {a[1]}, {a[2]})"
            return a[0] if a else "[]"
        if func_name == "matrix_sort":
            # matrix.sort(id, order?) — sort each row in place (object-mode stub)
            a = ra(args, kwargs, ("id", "order"))
            if not a:
                return "[]"
            return (
                f"((lambda __m: [__r.sort() for __r in (__m or []) if isinstance(__r, list)] "
                f"or __m)({a[0]}))"
            )
        if func_name == "matrix_reverse":
            a = ra(args, kwargs, ("id",))
            if not a:
                return "[]"
            return (
                f"((lambda __m: [__r.reverse() for __r in (__m or []) if isinstance(__r, list)] "
                f"or __m)({a[0]}))"
            )
        if func_name == "matrix_eigenvalues":
            a = ra(args, kwargs, ("id",))
            # Stub: empty list (full eigen not required for corpus compile)
            return "[]"
        if func_name == "matrix_eigenvectors":
            a = ra(args, kwargs, ("id",))
            return "[]"
        if func_name == "matrix_rank":
            a = ra(args, kwargs, ("id",))
            return f"(len({a[0]}) if {a[0]} else 0)" if a else "0"
        if func_name == "matrix_trace":
            a = ra(args, kwargs, ("id",))
            if not a:
                return "0.0"
            return (
                f"(sum(safe_float({a[0]}[__i][__i]) for __i in range(min(len({a[0]} or []), "
                f"len(({a[0]} or [[]])[0]) if {a[0]} else 0))) if {a[0]} else 0.0)"
            )
        if func_name == "array_sort_indices":
            a = ra(args, kwargs, ("id", "order"))
            if not a:
                return "[]"
            if len(a) > 1:
                return f"array_sort_indices({a[0]}, {a[1]})"
            return f"array_sort_indices({a[0]})"
        if func_name == "array_fill":
            a = ra(args, kwargs, ("id", "value", "index_from", "index_to"))
            if not a:
                return ""
            val = a[1] if len(a) > 1 else "np.nan"
            # Full fill (common); range form ignored for MVP
            return f"[__a.__setitem__(__i, {val}) for __a in [{a[0]}] for __i in range(len(__a))]"
        if func_name == "array_stdev":
            a = ra(args, kwargs, ("id",))
            if a:
                return (
                    f"(float(np.std({a[0]})) if {a[0]} and len({a[0]}) > 0 else np.nan)"
                )
            return "np.nan"
        if func_name == "array_variance":
            a = ra(args, kwargs, ("id",))
            if a:
                return (
                    f"(float(np.var({a[0]})) if {a[0]} and len({a[0]}) > 0 else np.nan)"
                )
            return "np.nan"
        if func_name == "array_avg":
            a = ra(args, kwargs, ("id",))
            # safe_sum skips non-numeric (str/color/line handles) so multi-script
            # corpus files that reuse name ``a`` across examples do not TypeError.
            return (
                f"((safe_sum({a[0]})) / (safe_len({a[0]}) if safe_len({a[0]}) else 1) "
                f"if safe_len({a[0]}) else np.nan)"
                if a
                else "np.nan"
            )
        if func_name == "array_min":
            a = ra(args, kwargs, ("id",))
            return f"safe_min({a[0]})" if a else "np.nan"
        if func_name == "array_max":
            a = ra(args, kwargs, ("id",))
            return f"safe_max({a[0]})" if a else "np.nan"
        if func_name == "array_sum":
            a = ra(args, kwargs, ("id",))
            return f"safe_sum({a[0]})" if a else "0.0"
        if func_name == "array_first":
            a = ra(args, kwargs, ("id",))
            return f"({a[0]}[0] if {a[0]} else np.nan)" if a else "np.nan"
        if func_name == "array_last":
            a = ra(args, kwargs, ("id",))
            return f"({a[0]}[-1] if {a[0]} else np.nan)" if a else "np.nan"
        if func_name == "array_indexof":
            a = ra(args, kwargs, ("id", "value"))
            if len(a) >= 2:
                return (
                    f"({a[0]}.index({a[1]}) if {a[0]} is not None "
                    f"and {a[1]} in {a[0]} else -1)"
                )
            return "-1"
        if func_name == "array_lastindexof":
            a = ra(args, kwargs, ("id", "value"))
            if len(a) >= 2:
                return (
                    f"((len({a[0]}) - 1 - {a[0]}[::-1].index({a[1]})) "
                    f"if {a[0]} is not None and {a[1]} in {a[0]} else -1)"
                )
            return "-1"
        if func_name == "array_insert":
            a = ra(args, kwargs, ("id", "index", "value"))
            if len(a) >= 3:
                return f"{a[0]}.insert(int({a[1]}), {a[2]})"
            return ""
        if func_name == "array_median":
            a = ra(args, kwargs, ("id",))
            if a:
                return (
                    f"(float(np.median({a[0]})) if {a[0]} and len({a[0]}) > 0 "
                    f"else np.nan)"
                )
            return "np.nan"
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
            "max_drawdown": "__strategy.max_drawdown",
            "max_runup": "__strategy.max_runup",
            "max_drawdown_percent": "__strategy.max_drawdown_percent",
            "max_runup_percent": "__strategy.max_runup_percent",
            "openprofit": "__strategy.openprofit",
            "grossprofit": "__strategy.grossprofit",
            "grossloss": "__strategy.grossloss",
            "wintrades": "__strategy.wintrades",
            "losstrades": "__strategy.losstrades",
        }
        if attr in series_map:
            self.object_mode = True
            self.uses_strategy = True
            return series_map[attr]
        # Qty type / risk constants used as values (not broker properties)
        if attr in (
            "percent_of_equity",
            "fixed",
            "cash",
            "cash_per_order",
            "cash_per_contract",
            "long",
            "short",
            "all",
        ):
            self.object_mode = True
            self.uses_strategy = True
            return repr(attr)
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
            "grey": "#787B86",
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

        method_src: str | None = None  # set for method-style TA (expr.rma(p))
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
            elif (
                isinstance(func.value, ast.Attribute)
                and isinstance(func.value.value, ast.Name)
                and func.value.value.id == "strategy"
                and func.value.attr == "risk"
            ):
                # strategy.risk.max_drawdown(...) / max_cons_loss_days(...) — no-op
                func_name = f"strategy_risk_{func.attr}"
            elif isinstance(func.value, ast.Name) and func.value.id == "log":
                func_name = f"log_{func.attr}"
            elif isinstance(func.value, ast.Name) and func.value.id == "ticker":
                # ticker.heikinashi / ticker.new / ticker.modify → symbol stub
                func_name = f"ticker_{func.attr}"
            elif (
                isinstance(func.value, ast.Name)
                and func.value.id in self.import_aliases
            ):
                # Library methods: ae.index_2d_to_1d / agen.sequence_float / …
                # Do not pass the alias as method_src (undefined free var).
                # BUT: ``import TradingView/ta/7`` (alias ``ta``) / math / str / …
                # must keep namespace prefix so ``ta.rma`` → ``ta_rma``, not bare
                # ``rma`` (which collides with user ``method rma`` → recursion).
                alias = func.value.id
                if alias in _NS or alias in (
                    "ta",
                    "math",
                    "str",
                    "array",
                    "matrix",
                    "map",
                    "color",
                    "strategy",
                    "input",
                    "request",
                    "ticker",
                    "timeframe",
                    "runtime",
                    "log",
                    "barstate",
                    "session",
                    "syminfo",
                    "timenow",
                ):
                    func_name = f"{alias}_{func.attr}"
                else:
                    func_name = func.attr
            elif (
                isinstance(func.value, ast.Name)
                and func.value.id in self.udt_types
                and func.attr == "new"
            ):
                return self._emit_udt_new(func.value.id, node)
            elif isinstance(func.value, ast.Name) and func.value.id in _NS:
                func_name = f"{func.value.id}_{func.attr}"
            elif func.attr in _METHOD_TA:
                # Method-style TA: ``(expr).rma(p)`` → ta.rma(expr, p)
                method_src = self.visit(func.value)
                if func.attr in ("fixnan", "nz"):
                    func_name = func.attr
                else:
                    func_name = f"ta_{func.attr}"
            elif func.attr in self.user_funcs:
                # User method: ``x.mg(6)`` / ``Close.linreg(8).mg(6)`` → mg(src, 6)
                method_src = self.visit(func.value)
                func_name = func.attr
            elif func.attr in ("max", "min"):
                # Float/series .max/.min must not steal array.max/array.min.
                #  - no extra args → ta.max/min (running extreme of series)
                #  - extra arg looks like length/const → ta.max(src, len)
                #  - extra arg is another series/value → math.max(a, b)
                #  - receiver is array/list handle → array.max/min
                method_src = self.visit(func.value)
                recv_name = (
                    func.value.id if isinstance(func.value, ast.Name) else None
                )
                recv_is_array_name = recv_name is not None and (
                    recv_name in self.scalar_vars or recv_name in self.map_vars
                )
                looks_series = (
                    method_src.endswith("[__bar_idx]")
                    or self._is_series_arr_expr(method_src)
                    or method_src.startswith("numba_")
                    or method_src.startswith("np.")
                )
                if recv_is_array_name or not looks_series:
                    func_name = _ARRAY_METHODS[func.attr]
                    self.object_mode = True
                elif not node.args:
                    func_name = f"ta_{func.attr}"
                else:
                    first = node.args[0]
                    raw = first.value if hasattr(first, "value") else first
                    is_len = isinstance(raw, ast.Constant) and isinstance(
                        getattr(raw, "value", None), (int, float)
                    )
                    func_name = f"ta_{func.attr}" if is_len else f"math_{func.attr}"
            elif func.attr in _ARRAY_METHODS:
                method_src = self.visit(func.value)
                func_name = _ARRAY_METHODS[func.attr]
                self.object_mode = True
            elif func.attr in _MAP_METHODS:
                method_src = self.visit(func.value)
                func_name = _MAP_METHODS[func.attr]
                self.object_mode = True
            elif func.attr in _TABLE_METHODS:
                method_src = self.visit(func.value)
                func_name = _TABLE_METHODS[func.attr]
                self.object_mode = True
            else:
                # Unknown method on a value — still call as func(src, …) not ``src_meth``
                method_src = self.visit(func.value)
                func_name = func.attr
                self.object_mode = True
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
        if method_src is not None:
            args = [method_src] + args

        # Bare collection verbs: push(arr, x) / put(map, k, v) / cell(...)
        if method_src is None and func_name in _BARE_COLLECTION:
            func_name = _BARE_COLLECTION[func_name]
            self.object_mode = True
        if func_name in ("from_index", "chart_point_from_index", "point_from_index"):
            self.object_mode = True
            # Pine chart.point fields: index/price (also x/y aliases for line stubs)
            if len(args) >= 3:
                return (
                    f"{{'x': {args[1]}, 'y': {args[2]}, "
                    f"'index': {args[1]}, 'price': {args[2]}}}"
                )
            if len(args) >= 2:
                return (
                    f"{{'x': {args[0]}, 'y': {args[1]}, "
                    f"'index': {args[0]}, 'price': {args[1]}}}"
                )
            return "{'x': __bar_idx, 'y': np.nan, 'index': __bar_idx, 'price': np.nan}"
        if func_name in ("modify", "ticker_modify"):
            self.object_mode = True
            return args[0] if args else repr("SYMBOL")
        # ticker.heikinashi / ticker.new / ticker.standard / …
        if func_name.startswith("ticker_"):
            self.object_mode = True
            if args:
                return f"str({args[0]})"
            return repr("SYMBOL")
        if func_name in ("max_bars_back", "max_bars_back_all"):
            return ""
        if func_name == "alert":
            return ""

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
            # Prefer explicit defval; else first positional value
            # (v5: input.int(2, title=..., group=...) — title/group are kwargs only)
            defval = kwargs.get("defval")
            if defval is None and args:
                # Skip title-like string positionals only when no numeric/bool defval
                # is present: first positional is almost always the default value.
                defval = args[0]
            # input.source → series (default close)
            if func_name == "input_source" or (
                func_name == "input" and kwargs.get("type", "").endswith("source")
            ):
                if defval is not None:
                    return defval
                return "close_arr[__bar_idx]"
            # Version-like / string defaults stay as string (object mode)
            if defval is not None and (
                self._looks_like_version_string(defval)
                or self._is_quoted_string_expr(defval)
                or func_name
                in (
                    "input_string",
                    "input_text_area",
                    "input_color",
                    "input_symbol",
                    "input_timeframe",
                    "input_session",
                )
            ):
                self.object_mode = True
                return defval if defval is not None else "''"
            if defval is not None:
                return defval
            # string/bool inputs without defval
            if func_name in ("input_string", "input_text_area"):
                self.object_mode = True
                return "''"
            if func_name == "input_bool":
                return "False"
            if func_name in (
                "input_color",
                "input_symbol",
                "input_timeframe",
                "input_session",
            ):
                self.object_mode = True
                return "''"
            return "0.0"

        # strategy.entry / close / order / cancel …
        if func_name.startswith("strategy_opentrades_") or func_name.startswith("strategy_closedtrades_"):
            return self._emit_strategy_trade_query(func_name[len("strategy_"):], args, kwargs)

        if func_name.startswith("strategy_"):
            return self._emit_strategy_call(func_name, args, kwargs)

        # Bare risk helpers sometimes appear after nested attr lowering
        if func_name in (
            "max_cons_loss_days",
            "max_cons_loss_days_percent",
            "max_drawdown",
            "max_intraday_loss",
            "max_intraday_filled_orders",
            "max_position_size",
            "allow_entry_in",
        ):
            return ""

        if func_name == "plot":
            title = f"Plot {len(self.plots)}"
            if "title" in kwargs:
                title = kwargs["title"].strip("\"'")
            elif len(args) > 1 and args[1]:
                title = args[1].strip("\"'")
            series_expr = args[0] if args else "np.nan"
            # Non-numeric plot sources (UDT, hline handle, string, sequence, color)
            # must use safe cast and object mode so float64 stores never raise.
            needs_safe = not self._is_safe_numeric_expr(series_expr)
            if series_expr in self.scalar_vars:
                needs_safe = True
            # UDF call results may be None (missing return) — always coerce
            if re.search(r"\b[A-Za-z_][A-Za-z0-9_]*\s*\(", series_expr):
                bare = series_expr.split("(", 1)[0].strip()
                if bare in self.user_funcs or bare in getattr(self, "func_name_map", {}):
                    needs_safe = True
                # Also any non-numba call in object mode
                if self.object_mode and not bare.startswith("numba_") and bare not in (
                    "safe_float",
                    "safe_int",
                    "safe_len",
                    "safe_period",
                    "float",
                    "int",
                    "bool",
                    "str",
                    "abs",
                    "min",
                    "max",
                    "sum",
                    "len",
                    "np",
                ):
                    needs_safe = True
            if series_expr.endswith("[__bar_idx]"):
                base = series_expr[: -len("[__bar_idx]")]
                if base.endswith("_arr"):
                    base_name = base[: -len("_arr")]
                    if base_name in self.string_series or base_name in self.udt_vars:
                        needs_safe = True
            if needs_safe and not series_expr.startswith("safe_float("):
                self.object_mode = True
                series_expr = f"safe_float({series_expr})"
            # UDT field already expanded
            self.plots.append({"expr": series_expr, "title": title})
            idx = len(self.plots) - 1
            # Always return an *expression* (plot() may be assigned:
            # ``p = plot(x)``). Bare ``plot_i[i] = …`` is a statement and
            # produces ``p_arr[i] = plot_i[i] = …`` SyntaxError.
            if self.object_mode:
                val = (
                    series_expr
                    if series_expr.startswith("safe_float(")
                    else f"safe_float({series_expr})"
                )
                return (
                    f"(plot_{idx}.__setitem__(__bar_idx, {val}) or plot_{idx}[__bar_idx])"
                )
            return f"numba_store(plot_{idx}, __bar_idx, {series_expr})"

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
        # Drawing getters: line.get_price(id, x) / id.get_y1() / id.get_x2()
        _DRAW_GET_KEYS = {
            "get_x1": "x1",
            "get_y1": "y1",
            "get_x2": "x2",
            "get_y2": "y2",
            "get_left": "left",
            "get_right": "right",
            "get_top": "top",
            "get_bottom": "bottom",
            "get_price": "y2",  # default; specialized below
        }
        bare_get = func_name
        if func_name.startswith("line_get_"):
            bare_get = func_name[len("line_") :]
        elif func_name.startswith("label_get_"):
            bare_get = func_name[len("label_") :]
        elif func_name.startswith("box_get_"):
            bare_get = func_name[len("box_") :]
        if (
            bare_get in _DRAW_GET_KEYS
            or func_name.startswith("label_get_")
            or func_name.startswith("line_get_")
            or func_name.startswith("box_get_")
        ):
            self.object_mode = True
            if "text" in func_name or bare_get == "get_text":
                return "''"
            handle = args[0] if args else "None"
            if bare_get == "get_price" or func_name == "line_get_price":
                return (
                    f"(safe_float({handle}.get('y2', {handle}.get('y1', np.nan))) "
                    f"if isinstance({handle}, dict) else np.nan)"
                )
            key = _DRAW_GET_KEYS.get(bare_get)
            if key:
                return (
                    f"(safe_float({handle}.get({key!r}, np.nan)) "
                    f"if isinstance({handle}, dict) else np.nan)"
                )
            return "np.nan"

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
            # Expression-safe stubs: empty string produced ``__tup = `` SyntaxError
            # on multi-assign like ``[__T, __C] = console.init(20)``.
            self.object_mode = True
            if func_name in ("console_init", "init") or func_name.endswith("_init"):
                return "(None, None)"
            return "None"
        if func_name in ("log_info", "log_warning", "log_error"):
            return "None"

        if func_name in ("runtime_error", "runtime_error_code"):
            # Expression-safe: never emit bare ``raise`` (invalid inside ternary /
            # ``return raise …``). ``pine_raise`` always raises at call time and
            # is exported by ``from numba_builtins import *``.
            self.object_mode = True
            msg = args[0] if args else repr("runtime.error")
            return f"pine_raise({msg})"

        if func_name == "color_from_gradient":
            # color.from_gradient(value, bottom, top, bottom_color, top_color)
            # Weak stub: pick top/bottom color by midpoint (enough for plot colors)
            self.object_mode = True
            if len(args) >= 5:
                return (
                    f"({args[4]} if safe_float({args[0]}) > "
                    f"(safe_float({args[1]}) + safe_float({args[2]})) / 2.0 else {args[3]})"
                )
            if len(args) >= 4:
                return args[3]
            return repr("#000000")
        if func_name in ("color_new", "color"):
            # color.new(base, transp) / v3–v4 color(base, transp) — keep base color string
            self.object_mode = True
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
            return self._emit_user_func_call(func_name, args, kwargs)

        # table.cell / table.cell_set / … (table_new already in drawing path)
        if func_name == "table_cell":
            # Return True so ``table.cell(...) and plot(...)`` is valid Python
            # (empty string would produce ``( and plot(...))`` SyntaxError).
            self.object_mode = True
            return "True"
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
            return "True"

        # str.* / tostring
        if func_name == "str_split":
            # Use helper: Pine empty sep splits to chars; Python str.split("") raises.
            self.object_mode = True
            if len(args) >= 2:
                return f"str_split({args[0]}, {args[1]})"
            if args:
                return f"str_split({args[0]})"
            return "[]"
        if func_name in ("sequence_from_series",) or func_name.endswith("_sequence_from_series"):
            self.object_mode = True
            # sequence_from_series(src, length?, shift?, direction?)
            a0 = args[0] if args else "close_arr"
            a1 = args[1] if len(args) > 1 else "None"
            a2 = args[2] if len(args) > 2 else "0"
            a3 = args[3] if len(args) > 3 else "True"
            return f"sequence_from_series({a0}, {a1}, {a2}, {a3}, __bar_idx)"
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
        if func_name == "str_repeat":
            self.object_mode = True
            if len(args) >= 2:
                return f"(str({args[0]}) * int({args[1]}))"
            return "''"
        if func_name == "str_format_time":
            # str.format_time(time, format, timezone?) — stub empty / simple str
            self.object_mode = True
            if args:
                return f"str({args[0]})"
            return "''"
        if func_name in ("str_tonumber", "tonumber"):
            self.object_mode = True
            if not args:
                return "np.nan"
            return f"safe_tonumber({args[0]})"
        if func_name in ("str_substring", "substring"):
            self.object_mode = True
            if not args:
                return "''"
            s = f"str({args[0]})"
            if len(args) >= 3:
                return (
                    f"({s}[int(safe_int({args[1]})):int(safe_int({args[2]}))])"
                )
            if len(args) >= 2:
                return f"({s}[int(safe_int({args[1]})):])"
            return s
        if func_name in ("str_pos", "pos"):
            # str.pos(source, str) → index or na (-1 Pine → we use -1; callers +1)
            self.object_mode = True
            if len(args) >= 2:
                return (
                    f"(str({args[0]}).find(str({args[1]})) "
                    f"if str({args[1]}) in str({args[0]}) else -1)"
                )
            return "-1"
        if func_name in ("str_startswith", "startswith"):
            self.object_mode = True
            if len(args) >= 2:
                return f"str({args[0]}).startswith(str({args[1]}))"
            return "False"
        if func_name in ("str_endswith", "endswith"):
            self.object_mode = True
            if len(args) >= 2:
                return f"str({args[0]}).endswith(str({args[1]}))"
            return "False"
        # Library ArrayExtension / Random / activation helpers (stubs)
        if func_name == "sequence_from_series":
            self.object_mode = True
            # sequence_from_series(src, length?, …) → list of recent values
            src = args[0] if args else "close_arr[__bar_idx]"
            length = args[1] if len(args) > 1 else kwargs.get("length", "100")
            base = src[: -len("[__bar_idx]")] if src.endswith("[__bar_idx]") else src
            if self._is_series_arr_expr(base) or base.endswith("_arr"):
                return (
                    f"(list({base}[max(0, __bar_idx - int({length}) + 1):__bar_idx + 1]))"
                )
            return f"([{src}] * max(1, int({length})))"
        if func_name == "sequence_float":
            self.object_mode = True
            # sequence_float(start, stop, step) or (agen, start, stop, step)
            a = args
            if len(a) >= 4:
                start, stop, step = a[1], a[2], a[3]
            elif len(a) >= 3:
                start, stop, step = a[0], a[1], a[2]
            else:
                start, stop, step = "0.0", "1.0", "0.1"
            return (
                f"(list(np.arange(float({start}), float({stop}) + float({step}) * 0.5, "
                f"float({step}))))"
            )
        if func_name in ("index_2d_to_1d", "index_1d_to_2d"):
            self.object_mode = True
            # index_2d_to_1d(dim_x, dim_y, ix, iy) — row-major
            a = args
            # Drop leading None library alias if present
            if a and a[0] in ("None", "ae"):
                a = a[1:]
            if func_name == "index_2d_to_1d" and len(a) >= 4:
                # dim_x, dim_y, index_x, index_y → index_x * dim_y + index_y
                return f"(int({a[2]}) * int({a[1]}) + int({a[3]}))"
            if func_name == "index_2d_to_1d" and len(a) >= 3:
                return f"(int({a[1]}) * int({a[0]}) + int({a[2]}))"
            return "0"
        if func_name == "function" and (
            # activation.function(value=…, name=…) MLActivationFunctions
            kwargs
            or (args and len(args) >= 1)
        ):
            self.object_mode = True
            # activation.function(value=_sum, name=activation_function)
            val = kwargs.get("value") or (args[0] if args else "0.0")
            name = kwargs.get("name") or (args[1] if len(args) > 1 else repr("sigmoid"))
            # simple sigmoid / identity stubs
            return (
                f"((1.0 / (1.0 + np.exp(-float({val})))) "
                f"if str({name}) in ('sigmoid', 'logistic') "
                f"else (max(0.0, float({val})) if str({name}) == 'relu' "
                f"else float({val})))"
            )

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
            "dev": "ta_dev",
            "change": "ta_change",
            "atr": "ta_atr",
            "dmi": "ta_dmi",
            "supertrend": "ta_supertrend",
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
            "sum": "ta_sum",
            "correlation": "ta_correlation",
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
            "mom": "ta_mom",
            "variance": "ta_variance",
            "alma": "ta_alma",
            "hma": "ta_hma",
            "tsi": "ta_tsi",
            "macd": "ta_macd",
            "bb": "ta_bb",
        }
        if func_name in _BARE_TA and func_name not in self.user_funcs:
            func_name = _BARE_TA[func_name]

        def _arr(expr: str) -> str:
            """Strip trailing bar index or materialize non-array TA sources."""
            return self._materialize_series_source(expr)

        def _is_series_arr(expr: str) -> bool:
            return self._is_series_arr_expr(expr)

        if func_name == "ta_sma":
            if not args:
                return "np.nan"
            period = kwargs.get("length", args[1] if len(args) > 1 else "14")
            st = self._alloc_fixed_state("sma", 2)
            return f"numba_sma_inc({_arr(args[0])}, {self._emit_period(period)}, __bar_idx, {st})"
        if func_name == "ta_ema":
            if not args:
                return "np.nan"
            period = kwargs.get("length", args[1] if len(args) > 1 else "14")
            st = self._alloc_fixed_state("ema", 2)
            return f"numba_ema_inc({_arr(args[0])}, {self._emit_period(period)}, __bar_idx, {st})"
        if func_name == "ta_rma":
            if not args:
                return "np.nan"
            period = kwargs.get("length", args[1] if len(args) > 1 else "14")
            st = self._alloc_fixed_state("rma", 2)
            return f"numba_rma_inc({_arr(args[0])}, {self._emit_period(period)}, __bar_idx, {st})"
        if func_name == "ta_wma":
            if not args:
                return "np.nan"
            period = kwargs.get("length", args[1] if len(args) > 1 else "14")
            st = self._alloc_fixed_state("wma", 3)
            return f"numba_wma_inc({_arr(args[0])}, {self._emit_period(period)}, __bar_idx, {st})"
        if func_name == "ta_rsi":
            if not args:
                return "np.nan"
            period = kwargs.get("length", args[1] if len(args) > 1 else "14")
            st = self._alloc_fixed_state("rsi", 3)
            return f"numba_rsi_inc({_arr(args[0])}, {self._emit_period(period)}, __bar_idx, {st})"
        if func_name == "ta_highest":
            # ta.highest(source, length) or ta.highest(length) → high source
            st = self._alloc_fixed_state("hh", 3)
            if len(args) >= 2:
                period = kwargs.get("length", args[1])
                return f"numba_highest_inc({_arr(args[0])}, {self._emit_period(period)}, __bar_idx, {st})"
            if len(args) == 1:
                return f"numba_highest_inc(high_arr, int({args[0]}), __bar_idx, {st})"
            period = kwargs.get("length", "14")
            return f"numba_highest_inc(high_arr, {self._emit_period(period)}, __bar_idx, {st})"
        if func_name == "ta_lowest":
            # ta.lowest(source, length) or ta.lowest(length) → low source
            st = self._alloc_fixed_state("ll", 3)
            if len(args) >= 2:
                period = kwargs.get("length", args[1])
                return f"numba_lowest_inc({_arr(args[0])}, {self._emit_period(period)}, __bar_idx, {st})"
            if len(args) == 1:
                return f"numba_lowest_inc(low_arr, int({args[0]}), __bar_idx, {st})"
            period = kwargs.get("length", "14")
            return f"numba_lowest_inc(low_arr, {self._emit_period(period)}, __bar_idx, {st})"
        if func_name == "ta_stdev":
            if not args:
                return "np.nan"
            period = kwargs.get("length", args[1] if len(args) > 1 else "14")
            st = self._alloc_fixed_state("stdev", 3)
            return f"numba_stdev_inc({_arr(args[0])}, {self._emit_period(period)}, __bar_idx, {st})"
        if func_name == "ta_change":
            if not args:
                return "np.nan"
            length = kwargs.get("length", args[1] if len(args) > 1 else "1")
            return f"numba_change({_arr(args[0])}, {length}, __bar_idx)"
        if func_name == "ta_mom":
            # ta.mom(source, length) ≡ source - source[length] (same as change)
            if not args:
                return "np.nan"
            length = kwargs.get("length", args[1] if len(args) > 1 else "1")
            return f"numba_change({_arr(args[0])}, {length}, __bar_idx)"
        if func_name == "ta_dmi":
            # ta.dmi(diLength, adxSmoothing) → (diplus, diminus, adx) stub
            return "(0.0, 0.0, 25.0)"
        if func_name == "ta_supertrend":
            # ta.supertrend(factor, atrPeriod) → (value, direction) stub
            return "(close_arr[__bar_idx], 1.0)"
        if func_name == "ta_atr":
            # ta.atr(length) uses high/low/close from chart arrays
            length = kwargs.get("length", args[0] if args else "14")
            st = self._alloc_fixed_state("atr", 2)
            if len(args) >= 4:
                # legacy ta.atr(high, low, close, length)
                return (
                    f"numba_atr_inc({_arr(args[0])}, {_arr(args[1])}, {_arr(args[2])}, "
                    f"int({args[3]}), __bar_idx, {st})"
                )
            return (
                f"numba_atr_inc(high_arr, low_arr, close_arr, {self._emit_period(length)}, __bar_idx, {st})"
            )
        if func_name == "ta_bb":
            # ta.bb(source, length, mult) or ta.bb(length, mult)
            if len(args) >= 3:
                src, length, mult = args[0], args[1], args[2]
            elif len(args) == 2:
                src, length, mult = "close_arr[__bar_idx]", args[0], args[1]
            else:
                src, length, mult = "close_arr[__bar_idx]", "20", "2.0"
            st = self._alloc_fixed_state("bb", 3)
            return (
                f"numba_bb_inc({_arr(src)}, {self._emit_period(length)}, float({mult}), __bar_idx, {st})"
            )
        if func_name == "ta_macd":
            # ta.macd(source, fast, slow, signal)
            src = args[0] if args else "close_arr[__bar_idx]"
            fast = args[1] if len(args) > 1 else "12"
            slow = args[2] if len(args) > 2 else "26"
            signal = args[3] if len(args) > 3 else "9"
            st = self._alloc_fixed_state("macd", 4)
            return (
                f"numba_macd_inc({_arr(src)}, int({fast}), int({slow}), int({signal}), "
                f"__bar_idx, {st})"
            )
        def _is_scalar_const(expr: str) -> bool:
            e = expr.strip()
            if e in ("True", "False", "None", "np.nan", "np.pi", "np.e"):
                return True
            return bool(re.fullmatch(r"[-+]?(\d+\.?\d*|\d*\.\d+)([eE][-+]?\d+)?", e))

        def _cross_pair(a_expr: str, b_expr: str, *, under: bool = False) -> str:
            """Series-vs-series or series-vs-scalar crossover/under."""
            a = _arr(a_expr) if a_expr else "close_arr"
            b_raw = b_expr if b_expr else "0.0"
            fn = "numba_crossunder" if under else "numba_crossover"
            fn_s = f"{fn}_scalar"
            if _is_scalar_const(b_raw):
                return f"{fn_s}({a}, float({b_raw}), __bar_idx)"
            # Materialized expr (numba_store_src) or pure array → series path
            b = _arr(b_raw)
            if (
                b.endswith("_arr")
                or b in ("open_arr", "high_arr", "low_arr", "close_arr", "vol_arr")
                or b.startswith("numba_store_src(")
            ):
                return f"{fn}({a}, {b}, __bar_idx)"
            # Last resort: treat as scalar (bool/int expressions)
            return f"{fn_s}({a}, float({b_raw}), __bar_idx)"

        if func_name == "ta_crossover":
            return _cross_pair(
                args[0] if args else "close_arr",
                args[1] if len(args) > 1 else "0.0",
                under=False,
            )
        if func_name == "ta_crossunder":
            return _cross_pair(
                args[0] if args else "close_arr",
                args[1] if len(args) > 1 else "0.0",
                under=True,
            )
        if func_name == "ta_cross":
            a0 = args[0] if args else "close_arr"
            b0 = args[1] if len(args) > 1 else "0.0"
            return (
                f"({_cross_pair(a0, b0, under=False)} or "
                f"{_cross_pair(a0, b0, under=True)})"
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
                st = self._alloc_fixed_state("cum", 2)
                return f"numba_cum_inc({_arr(src)}, __bar_idx, {st})"
            # Expression / ternary: accumulate scalar-at-bar into synthetic series.
            # (numba_cum needs a full array; global _arr strip is unsafe on compounds.)
            sid = f"__cum{self._expr_cum_i}_arr"
            self._expr_cum_i += 1
            self.arrays.add(sid)
            return f"numba_cum_expr({sid}, float({src}), __bar_idx)"
        if func_name == "ta_sum":
            # ta.sum(source, length) == rolling sum over length bars
            if not args:
                return "np.nan"
            period = kwargs.get("length", args[1] if len(args) > 1 else "14")
            st = self._alloc_fixed_state("sum", 2)
            return f"numba_sum_inc({_arr(args[0])}, {self._emit_period(period)}, __bar_idx, {st})"
        if func_name == "ta_dev":
            # Mean absolute deviation from SMA
            if not args:
                return "np.nan"
            period = kwargs.get("length", args[1] if len(args) > 1 else "14")
            st = self._alloc_fixed_state("dev", 2)
            return f"numba_dev_inc({_arr(args[0])}, {self._emit_period(period)}, __bar_idx, {st})"
        if func_name == "ta_variance":
            # Sample variance (n-1) — stdev**2
            if not args:
                return "np.nan"
            period = kwargs.get("length", args[1] if len(args) > 1 else "14")
            st = self._alloc_fixed_state("var", 3)
            return f"numba_variance_inc({_arr(args[0])}, {self._emit_period(period)}, __bar_idx, {st})"
        if func_name == "ta_correlation":
            # ta.correlation(source1, source2, length) Pearson
            st = self._alloc_fixed_state("corr", 6)
            if len(args) >= 3:
                return (
                    f"numba_correlation_inc({_arr(args[0])}, {_arr(args[1])}, "
                    f"int({args[2]}), __bar_idx, {st})"
                )
            if len(args) == 2:
                return (
                    f"numba_correlation_inc({_arr(args[0])}, close_arr, "
                    f"int({args[1]}), __bar_idx, {st})"
                )
            return "np.nan"
        if func_name == "ta_alma":
            # ta.alma(source, length, offset=0.85, sigma=6)
            if not args:
                return "np.nan"
            src = args[0]
            length = args[1] if len(args) > 1 else "9"
            offset = args[2] if len(args) > 2 else "0.85"
            sigma = args[3] if len(args) > 3 else "6.0"
            return (
                f"numba_alma({_arr(src)}, {self._emit_period(length)}, float({offset}), "
                f"float({sigma}), __bar_idx)"
            )
        if func_name == "ta_hma":
            # ta.hma(source, length)
            if not args:
                return "np.nan"
            if len(args) >= 2:
                return f"numba_hma({_arr(args[0])}, int({args[1]}), __bar_idx)"
            if not _is_series_arr(args[0]):
                return f"numba_hma(close_arr, int({args[0]}), __bar_idx)"
            return f"numba_hma({_arr(args[0])}, 9, __bar_idx)"
        if func_name == "ta_tsi":
            # ta.tsi(source, short, long) or ta.tsi(short, long) on close
            st = self._alloc_fixed_state("tsi", 6)
            if len(args) >= 3 and _is_series_arr(args[0]):
                return (
                    f"numba_tsi_inc({_arr(args[0])}, int({args[1]}), int({args[2]}), "
                    f"__bar_idx, {st})"
                )
            if len(args) >= 2:
                return (
                    f"numba_tsi_inc(close_arr, int({args[0]}), int({args[1]}), "
                    f"__bar_idx, {st})"
                )
            return "np.nan"
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
            st = self._alloc_fixed_state("stoch", 5)
            if len(args) >= 4:
                return (
                    f"numba_stoch_inc({_arr(args[0])}, {_arr(args[1])}, {_arr(args[2])}, "
                    f"int({args[3]}), __bar_idx, {st})"
                )
            length = args[0] if args else "14"
            return (
                f"numba_stoch_inc(close_arr, high_arr, low_arr, {self._emit_period(length)}, "
                f"__bar_idx, {st})"
            )
        if func_name == "ta_cci":
            # ta.cci(source, length) or ta.cci(length) → hlc3 approx as close
            st = self._alloc_fixed_state("cci", 2)
            if len(args) >= 2:
                return f"numba_cci_inc({_arr(args[0])}, int({args[1]}), __bar_idx, {st})"
            length = args[0] if args else "20"
            # typical price via (h+l+c)/3 not available as array — use close MVP
            return f"numba_cci_inc(close_arr, {self._emit_period(length)}, __bar_idx, {st})"
        if func_name == "ta_vwap":
            # ta.vwap / ta.vwap(source) — cumulative typical*vol / cum vol
            st = self._alloc_fixed_state("vwap", 3)
            if args and _is_series_arr(args[0]):
                return f"numba_vwap_inc({_arr(args[0])}, vol_arr, __bar_idx, {st})"
            # default source = hlc3; approximate with (h+l+c)/3 via close as MVP if no src
            # Use close for bare form; better: build from chart (still correct enough)
            return f"numba_vwap_inc(close_arr, vol_arr, __bar_idx, {st})"
        if func_name == "ta_max":
            # ta.max(source) → all-time high of series; ta.max(source, length) → highest
            if not args:
                return "np.nan"
            if len(args) >= 2:
                period = kwargs.get("length", args[1])
                st = self._alloc_fixed_state("hh", 3)
                return f"numba_highest_inc({_arr(args[0])}, {self._emit_period(period)}, __bar_idx, {st})"
            # Running max from bar 0..i (scan form; no fixed window state)
            return f"numba_highest({_arr(args[0])}, __bar_idx + 1, __bar_idx)"
        if func_name == "ta_min":
            # ta.min(source) → all-time low; ta.min(source, length) → lowest
            if not args:
                return "np.nan"
            if len(args) >= 2:
                period = kwargs.get("length", args[1])
                st = self._alloc_fixed_state("ll", 3)
                return f"numba_lowest_inc({_arr(args[0])}, {self._emit_period(period)}, __bar_idx, {st})"
            return f"numba_lowest({_arr(args[0])}, __bar_idx + 1, __bar_idx)"
        if func_name == "ta_sar":
            # ta.sar(start, inc, max) using chart high/low
            start = args[0] if args else "0.02"
            inc = args[1] if len(args) > 1 else "0.02"
            maximum = args[2] if len(args) > 2 else "0.2"
            st = self._alloc_fixed_state("sar", 5)
            if len(args) >= 5 and _is_series_arr(args[0]):
                return (
                    f"numba_sar_inc({_arr(args[0])}, {_arr(args[1])}, float({args[2]}), "
                    f"float({args[3]}), float({args[4]}), __bar_idx, {st})"
                )
            return (
                f"numba_sar_inc(high_arr, low_arr, float({start}), float({inc}), "
                f"float({maximum}), __bar_idx, {st})"
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
            return f"numba_percentile_nearest_rank({_arr(src)}, {self._emit_period(length)}, 50.0, __bar_idx)"


        if func_name == "ta_barssince":
            # Prefer history scan when condition is a series array; else weak current stub
            if args and _is_series_arr(args[0]):
                st = self._alloc_fixed_state("barsince", 2)
                return f"numba_barssince_inc({_arr(args[0])}, __bar_idx, {st})"
            if args:
                return f"(0.0 if ({args[0]}) else np.nan)"
            return "np.nan"
        if func_name == "ta_linreg":
            # ta.linreg(source, length, offset=0)
            src = args[0] if args else "close_arr[__bar_idx]"
            length = args[1] if len(args) > 1 else "14"
            offset = args[2] if len(args) > 2 else "0"
            st = self._alloc_fixed_state("linreg", 3)
            return (
                f"numba_linreg_inc({_arr(src)}, {self._emit_period(length)}, int({offset}), "
                f"__bar_idx, {st})"
            )
        if func_name == "ta_vwma":
            # ta.vwma(source, length) or ta.vwma(length) on close
            st = self._alloc_fixed_state("vwma", 3)
            if len(args) >= 2 and _is_series_arr(args[0]):
                return (
                    f"numba_vwma_inc({_arr(args[0])}, vol_arr, int({args[1]}), "
                    f"__bar_idx, {st})"
                )
            length = args[0] if args else "14"
            return f"numba_vwma_inc(close_arr, vol_arr, {self._emit_period(length)}, __bar_idx, {st})"
        if func_name == "ta_mfi":
            # ta.mfi(length) | ta.mfi(source, length) | ta.mfi(h, l, c, v, length)
            st = self._alloc_fixed_state("mfi", 3)
            if len(args) >= 5 and _is_series_arr(args[0]):
                return (
                    f"numba_mfi_inc({_arr(args[0])}, {_arr(args[1])}, {_arr(args[2])}, "
                    f"{_arr(args[3])}, int({args[4]}), __bar_idx, {st})"
                )
            if len(args) >= 2 and _is_series_arr(args[0]):
                src = _arr(args[0])
                return (
                    f"numba_mfi_inc({src}, {src}, {src}, vol_arr, int({args[1]}), "
                    f"__bar_idx, {st})"
                )
            length = args[0] if args else "14"
            return (
                f"numba_mfi_inc(high_arr, low_arr, close_arr, vol_arr, {self._emit_period(length)}, "
                f"__bar_idx, {st})"
            )
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
            st = self._alloc_fixed_state("hbars", 3)
            if len(args) >= 2:
                period = kwargs.get("length", args[1])
                return (
                    f"numba_highestbars_inc({_arr(args[0])}, {self._emit_period(period)}, "
                    f"__bar_idx, {st})"
                )
            if len(args) == 1:
                # One-arg form is always length (even if the expr is a series scalar like amp_arr[i])
                return f"numba_highestbars_inc(high_arr, int({args[0]}), __bar_idx, {st})"
            period = kwargs.get("length", "14")
            return f"numba_highestbars_inc(high_arr, {self._emit_period(period)}, __bar_idx, {st})"
        if func_name == "ta_lowestbars":
            # ta.lowestbars(source, length) or ta.lowestbars(length) → low source
            st = self._alloc_fixed_state("lbars", 3)
            if len(args) >= 2:
                period = kwargs.get("length", args[1])
                return (
                    f"numba_lowestbars_inc({_arr(args[0])}, {self._emit_period(period)}, "
                    f"__bar_idx, {st})"
                )
            if len(args) == 1:
                return f"numba_lowestbars_inc(low_arr, int({args[0]}), __bar_idx, {st})"
            period = kwargs.get("length", "14")
            return f"numba_lowestbars_inc(low_arr, {self._emit_period(period)}, __bar_idx, {st})"
        if func_name == "ta_percentrank":
            # ta.percentrank(source, length)
            if len(args) >= 2:
                return f"numba_percentrank({_arr(args[0])}, int({args[1]}), __bar_idx)"
            if args:
                return f"numba_percentrank(close_arr, int({args[0]}), __bar_idx)"
            return "np.nan"
        if func_name == "ta_obv":
            # ta.obv / ta.obv() / ta.obv(close, volume)
            st = self._alloc_fixed_state("obv", 2)
            if len(args) >= 2 and _is_series_arr(args[0]):
                return f"numba_obv_inc({_arr(args[0])}, {_arr(args[1])}, __bar_idx, {st})"
            return f"numba_obv_inc(close_arr, vol_arr, __bar_idx, {st})"
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
            # String/object series: avoid numba_nz (isnan on unicode fails)
            if (
                not self._is_safe_numeric_expr(args[0])
                or self._looks_like_string_expr(args[0])
                or args[0] in self.scalar_vars
            ):
                self.object_mode = True
                return (
                    f"({args[0]} if ({args[0]}) is not None "
                    f"and not (isinstance({args[0]}, float) "
                    f"and ({args[0]}) != ({args[0]})) else {repl})"
                )
            return f"numba_nz({args[0]}, {repl})"
        if func_name == "fixnan":
            # Full history carry-forward is expensive; nz(x, 0) stub is enough
            if not args:
                return "0.0"
            return f"numba_nz({args[0]}, 0.0)"
        if func_name in ("complex_new", "complex_arr_new"):
            # complex.new(real, imag) → object dict handle
            self.object_mode = True
            real = args[0] if args else "0.0"
            imag = args[1] if len(args) > 1 else "0.0"
            return "{'real': float(%s), 'imag': float(%s)}" % (real, imag)
        if func_name in ("math_abs", "abs"):
            return f"numba_abs({args[0]})" if args else "np.nan"
        if func_name in ("math_max", "max"):
            if not args:
                return "np.nan"
            if len(args) == 1:
                return args[0]
            # math.max takes 2+ values — nest pairwise numba_max
            expr = args[0]
            for a in args[1:]:
                expr = f"numba_max({expr}, {a})"
            return expr
        if func_name in ("math_min", "min"):
            if not args:
                return "np.nan"
            if len(args) == 1:
                return args[0]
            expr = args[0]
            for a in args[1:]:
                expr = f"numba_min({expr}, {a})"
            return expr
        if func_name in ("math_isfinite", "isfinite"):
            return f"np.isfinite({args[0]})" if args else "False"
        if func_name in ("math_isnan", "isnan"):
            return f"np.isnan({args[0]})" if args else "True"
        if func_name in ("math_sqrt", "sqrt"):
            return f"np.sqrt({args[0]})" if args else "np.nan"
        if func_name == "avg":
            if not args:
                return "np.nan"
            return "(" + "+".join(args) + f") / {len(args)}"
        if func_name in ("math_exp", "exp"):
            return f"np.exp({args[0]})" if args else "np.nan"
        if func_name in ("math_log", "log"):
            return f"np.log({args[0]})" if args else "np.nan"
        if func_name in ("math_log10", "log10"):
            return f"np.log10({args[0]})" if args else "np.nan"
        if func_name in ("math_pow", "pow"):
            if not args:
                return "np.nan"
            return f"({args[0]} ** {args[1]})" if len(args) > 1 else f"({args[0]} ** 2)"
        if func_name in ("math_round", "round"):
            if not args:
                return "0.0"
            # None / non-numeric → NaN (np.round(None) raises)
            if self.object_mode or not self._is_safe_numeric_expr(args[0]):
                self.object_mode = True
                return f"safe_float(np.round(safe_float({args[0]})))"
            return f"float(np.round({args[0]}))"
        if func_name in ("math_floor", "floor"):
            return f"float(np.floor({args[0]}))" if args else "0.0"
        if func_name in ("math_ceil", "ceil"):
            return f"float(np.ceil({args[0]}))" if args else "0.0"
        if func_name in ("math_sign", "sign"):
            return f"float(np.sign({args[0]}))" if args else "0.0"
        if func_name == "math_round_to_mintick":
            # Without symbol mintick series, round to integer ticks stub
            if not args:
                return "0.0"
            if self.object_mode or not self._is_safe_numeric_expr(args[0]):
                self.object_mode = True
                return f"safe_float(np.round(safe_float({args[0]})))"
            return f"float(np.round({args[0]}))"
        if func_name == "math_sum":
            period = args[1] if len(args) > 1 else "14"
            src_e = args[0] if args else "close_arr[__bar_idx]"
            return f"numba_sum({_arr(src_e)}, {self._emit_period(period)}, __bar_idx)"
        if func_name == "math_avg":
            period = args[1] if len(args) > 1 else "14"
            src_e = args[0] if args else "close_arr[__bar_idx]"
            return f"numba_sma({_arr(src_e)}, {self._emit_period(period)}, __bar_idx)"
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
        if func_name in ("math_tanh", "tanh"):
            return f"np.tanh(safe_float({args[0]}))" if args else "np.nan"
        if func_name in ("math_sinh", "sinh"):
            return f"np.sinh(safe_float({args[0]}))" if args else "np.nan"
        if func_name in ("math_cosh", "cosh"):
            return f"np.cosh(safe_float({args[0]}))" if args else "np.nan"
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
        if func_name == "iff":
            # v3 iff(cond, then, else)
            if len(args) >= 3:
                return f"({args[1]} if {args[0]} else {args[2]})"
            return "np.nan"
        if func_name == "heikinashi":
            # ticker transform stub — pass through expression / symbol
            return args[0] if args else "close_arr[__bar_idx]"
        if func_name == "float":
            if not args:
                return "np.nan"
            arg = args[0]
            # Known-numeric path: identity (float of float series / literals)
            if self._is_safe_numeric_expr(arg) and not self.object_mode:
                return arg
            # Object / UDT / hline handle / function / string → safe cast
            self.object_mode = True
            return f"safe_float({arg})"
        if func_name == "int":
            if not args:
                return "0"
            arg = args[0]
            if self._is_safe_numeric_expr(arg) and not self.object_mode:
                return f"int({arg})" if not arg.isdigit() else arg
            self.object_mode = True
            return f"safe_int({arg})"
        if func_name == "bool":
            if not args:
                return "False"
            arg = args[0]
            if self._is_safe_numeric_expr(arg) and not self.object_mode:
                return f"bool({arg})"
            self.object_mode = True
            return (
                f"(bool(safe_float({arg})) if not isinstance({arg}, str) "
                f"else bool({arg}))"
            )
        if func_name == "string":
            self.object_mode = True
            return f"str({args[0]})" if args else "''"

        # math.todegrees / math.toradians (and bare aliases)
        if func_name in ("math_todegrees", "todegrees"):
            a0 = args[0] if args else "0.0"
            return f"(safe_float({a0}) * 180.0 / 3.141592653589793)"
        if func_name in ("math_toradians", "toradians"):
            a0 = args[0] if args else "0.0"
            return f"(safe_float({a0}) * 3.141592653589793 / 180.0)"

        # Common external-library method stubs (import alias.method → bare name)
        if func_name in ("init", "console_init") or func_name.endswith("_init"):
            self.object_mode = True
            # DebugConsole.init → [table, array] multi-unpack expects a 2-tuple
            return "(None, None)"
        if func_name in (
            "rgb_to_hsl",
            "hsl_to_rgb",
            "perceptron",
            "layer",
            "function",
            "activation",
        ):
            self.object_mode = True
            return "None"
        if func_name in ("array_range",) or (
            func_name.endswith("_range") and "array" in func_name
        ):
            self.object_mode = True
            # array.range(start, end) or range(n) → list
            if len(args) >= 2:
                return f"list(range(int(safe_float({args[0]})), int(safe_float({args[1]}))))"
            if args:
                return f"list(range(int(safe_float({args[0]}))))"
            return "[]"

        # Unknown call: object mode + no-op stub to avoid NameError
        # (external library methods not present in corpus isolation).
        self.object_mode = True
        # Multi-unpack destinations need a sequence; single assign gets None.
        return "None"
    def _emit_user_func_call(
        self,
        func_name: str,
        args: list[str],
        kwargs: dict[str, str] | None = None,
    ) -> str:
        """Emit a call to a user-defined function with series/state plumbing.

        Maps keyword args by param name, fills missing params from declared
        defaults, and pads remaining gaps with ``np.nan``.
        """
        kwargs = kwargs or {}
        param_names = self.func_param_names.get(func_name, [])
        defaults = self.func_param_defaults.get(func_name, {})
        series_set = self.func_series_params.get(func_name, set())
        series_locals = self.func_series_locals.get(func_name, [])
        st_params = self.func_st_params.get(func_name, [])

        def _series_arg(pname: str | None, a: str) -> str:
            """Pass full series arrays for series params; materialize exprs."""
            if not pname or pname not in series_set:
                return a
            if a.endswith("[__bar_idx]"):
                return a[: -len("[__bar_idx]")]
            # Expression / scalar → materialize into synthetic series so
            # numba_* / history inside the UDF can index full arrays.
            return self._materialize_series_source(a)

        call_args: list[str] = []
        if param_names:
            for i, pname in enumerate(param_names):
                if i < len(args):
                    val = args[i]
                elif pname in kwargs:
                    val = kwargs[pname]
                elif pname in defaults:
                    val = defaults[pname]
                else:
                    val = "np.nan"
                call_args.append(_series_arg(pname, val))
            for i in range(len(param_names), len(args)):
                call_args.append(args[i])
        else:
            for a in args:
                call_args.append(a)
            for k in sorted(kwargs):
                if k not in param_names:
                    call_args.append(kwargs[k])

        # Param order must match visit_FunctionDef:
        #   formals, series_locals, st_refs, free_scalars, free_series,
        #   [__drawings], [n_bars], [chart...], [__strategy]
        for s in series_locals:
            call_args.append(f"__st_{func_name}_{s}")
        for st in st_params:
            call_args.append(st)
        free_scalars = getattr(self, "func_free_scalars", {}).get(func_name, [])
        for sc in free_scalars:
            # Prefer current bar of a series array when the outer var is series-like
            arr = f"{sc}_arr"
            if arr in self.arrays or sc in self.string_series or sc in self.udt_vars:
                call_args.append(f"{arr}[__bar_idx]")
            elif sc in self.import_aliases:
                # Library namespace — stub None (methods already lowered without alias)
                call_args.append("None")
            elif sc in self.scalar_vars or sc in self.map_vars:
                call_args.append(self._py_ident(sc) if sc in self.ident_map else sc)
            else:
                # Outer series written every bar as *_arr, or scalar not yet known
                if any(a == arr or a.startswith(sc) for a in self.arrays):
                    call_args.append(f"{arr}[__bar_idx]")
                else:
                    # May be input.color scalar assigned later — pass bare name
                    # only when it is a known outer; else None to avoid NameError
                    if sc in self.scalar_vars or sc in self.map_vars or sc in self.arrays:
                        call_args.append(sc)
                    else:
                        # Unknown free (import alias missed / undeclared) — safe stub
                        call_args.append("None")
        free_series = getattr(self, "func_free_series", {}).get(func_name, [])
        for fs in free_series:
            call_args.append(fs)
        if getattr(self, "func_needs_drawings", {}).get(func_name):
            call_args.append("__drawings")
        if getattr(self, "func_needs_n_bars", {}).get(func_name):
            call_args.append("n_bars")
        # Chart context only when the def was emitted with it (func_needs_bar).
        if self.func_needs_bar.get(func_name):
            for extra in (
                "open_arr",
                "high_arr",
                "low_arr",
                "close_arr",
                "vol_arr",
                "__bar_idx",
            ):
                call_args.append(extra)
        if self.func_needs_strategy.get(func_name):
            call_args.append("__strategy")
        # Emit safe def name for keywords (``from`` → ``from_``)
        py_name = self.func_name_map.get(func_name, func_name)
        return f"{py_name}({', '.join(call_args)})"


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
        if method == "default_entry_qty":
            # strategy.default_entry_qty(series) → default size stub
            return "1.0"
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
        # Object constructors + hline return a handle dict so later set_* /
        # float(handle) can reference it (float → na via safe_float).
        if func_name.endswith("_new") or func_name == "hline":
            return f"(__drawings.append(__d := {event}) or __d)"
        return f"(__drawings.append(__d := {event}) or __d)"

    def visit_BinOp(self, node: ast.BinOp):
        left = self.visit(node.left)
        right = self.visit(node.right)
        left_str = self._is_stringy_value(node.left) or self._looks_like_string_expr(left)
        right_str = self._is_stringy_value(node.right) or self._looks_like_string_expr(right)
        # Numeric array / numba results must never be treated as strings —
        # but only when the AST side is not actually stringy (color series).
        left_num = self._looks_like_numeric_expr(left) and not left_str
        right_num = self._looks_like_numeric_expr(right) and not right_str
        # Color/string arithmetic only when a side is stringy and not both clearly numeric
        # (false-positive stringy on `basis_arr[i] + dev` must stay numeric).
        if (left_str or right_str) and not (left_num and right_num):
            self.object_mode = True
            # Pine string + anything → string concat (never float + str TypeError)
            if isinstance(node.op, ast.Add) and (left_str or right_str):
                return f"(str({left}) + str({right}))"
            # Prefer numeric if only one side is stringy and op is not Add
            if (left_num or right_num) and not (left_str and right_str):
                pass  # fall through to numeric for non-Add
            else:
                # Sub/Mult/Div/Mod on strings or colors → na
                return "np.nan"
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

    @staticmethod
    def _looks_like_numeric_expr(val: str) -> bool:
        """True when visited expr is clearly a numeric series/scalar."""
        if not isinstance(val, str) or not val:
            return False
        if val.startswith("numba_") or val.startswith("np.") or val.startswith("safe_float"):
            return True
        if val.endswith("_arr[__bar_idx]") or val in (
            "open_arr[__bar_idx]",
            "high_arr[__bar_idx]",
            "low_arr[__bar_idx]",
            "close_arr[__bar_idx]",
            "vol_arr[__bar_idx]",
            "__bar_idx",
            "np.nan",
            "True",
            "False",
        ):
            return True
        try:
            float(val)
            return True
        except ValueError:
            pass
        # bare local that is arithmetic-shaped
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", val):
            return True  # locals like dev, basis used in arithmetic
        return False

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

    @staticmethod
    def _is_numeric_or_bool_literal(expr: str) -> bool:
        s = expr.strip()
        if s in ("True", "False", "None", "np.nan"):
            return True
        return bool(re.fullmatch(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", s))

    @staticmethod
    def _is_series_array_base(expr: str) -> bool:
        """True when *expr* is a full series buffer (with or without bar index)."""
        if expr.endswith("[__bar_idx]"):
            return True
        if expr in ("open_arr", "high_arr", "low_arr", "close_arr", "vol_arr"):
            return True
        # Allocated user series: foo_arr (not foo_arr[i] Python list indexing)
        if expr.endswith("_arr") and "[" not in expr:
            return True
        return False

    def _scalar_history_fallback(self, value_expr: str, offset_expr: str) -> str:
        """History on a non-series value.

        Literals/constants are bar-invariant → return the value when the offset
        is in range, else na. Function results / strategy stubs / other scalars
        cannot be rewound without a temp series → na (avoids getitem TypeError).
        """
        off = self._safe_history_offset(offset_expr)
        if self._is_numeric_or_bool_literal(value_expr):
            return f"({value_expr} if __bar_idx >= ({off}) else np.nan)"
        return "np.nan"

    def visit_Subscript(self, node: ast.Subscript):
        """Pine ``[]`` is the history operator — always route series via
        :meth:`_history_subscript` with a NaN-safe int offset. Never emit
        ``scalar[i]`` (Numba ``invalid index to scalar`` / Python TypeError).
        """
        slice_val = self.visit(node.slice)

        # --- UDF params / locals -------------------------------------------------
        if (
            self.in_function
            and isinstance(node.value, ast.Name)
            and node.value.id in self.local_vars
        ):
            name = node.value.id
            py = self._py_ident(name)
            if name in self.series_params:
                return self._history_subscript(py, slice_val)
            if name in self.series_locals:
                return self._history_subscript(f"{py}_arr", slice_val)
            # Loop counters are pure scalars — history is na
            if name in self.loop_counters:
                return self._scalar_history_fallback(py, slice_val)
            # Array / UDT handle (not a float series): int index via udt_index
            # so dict complex numbers work as ``c[0]``/``c[1]`` (real/imag).
            if (
                name in self.local_sequence_vars
                or name in self.scalar_vars
                or (
                    name in self.param_names
                    and name not in self.history_names_current
                )
            ):
                self.object_mode = True
                return f"udt_index({py}, {slice_val})"
            # Late discovery: formal used with history → series array param
            if name in self.param_names:
                self.series_params.add(name)
                return self._history_subscript(py, slice_val)
            # Assigned local without series allocation (or counter already local)
            return self._scalar_history_fallback(py, slice_val)

        # --- Script-level Name: ensure series buffer exists for history --------
        if isinstance(node.value, ast.Name):
            name = node.value.id
            if name in self.scalar_vars or name in self.map_vars:
                # Array/map handle: not a float series. History → na (array uses
                # array.get; map uses methods). Avoids float/None getitem.
                return "np.nan"
            if name in self.loop_counters:
                return self._scalar_history_fallback(
                    self._py_ident(name) if name in self.ident_map else name,
                    slice_val,
                )
            # First sight of history on a bare series name → allocate buffer
            if (
                name not in _NS
                and name not in _COLOR_NAMES
                and name not in (
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "na",
                    "tr",
                    "obv",
                    "hl2",
                    "hlc3",
                    "ohlc4",
                    "hlcc4",
                    "bar_index",
                    "time",
                    "timenow",
                    "time_close",
                    "true",
                    "True",
                    "false",
                    "False",
                    "PI",
                    "pi",
                )
                and name not in self.udt_types
                and f"{name}_arr" not in self.arrays
                and name not in self.string_series
            ):
                self.arrays.add(f"{name}_arr")

        arr = self.visit(node.value)

        # Series element at current bar → history on the underlying buffer
        if arr.endswith("[__bar_idx]"):
            return self._history_subscript(arr[: -len("[__bar_idx]")], slice_val)

        # Bare series array (rare; e.g. after stripping)
        if self._is_series_array_base(arr):
            return self._history_subscript(arr, slice_val)

        # None / na stubs from strategy / missing APIs
        if arr in ("None", "np.nan"):
            return "np.nan"

        # Strategy / broker scalars, call results, arithmetic, literals, …
        return self._scalar_history_fallback(arr, slice_val)

    def _switch_case_is_expr(self, case) -> bool:
        """True when a switch arm can live inside a Python ternary expression."""
        body = getattr(case, "body", None) or []
        if not body:
            return True
        for stmt in body:
            if isinstance(stmt, (ast.Assign, ast.ReAssign, ast.AugAssign)):
                if not isinstance(stmt.target, ast.Name):
                    return False
                continue
            if isinstance(stmt, ast.Expr):
                if isinstance(
                    stmt.value,
                    (ast.If, ast.ForTo, ast.ForIn, ast.While, ast.Switch),
                ):
                    return False
                continue
            if isinstance(stmt, (ast.If, ast.ForTo, ast.ForIn, ast.While, ast.Switch)):
                return False
            return False
        return True

    def _switch_assign_walrus(self, stmt) -> str | None:
        """``name := rhs`` for Assign/ReAssign/AugAssign of a simple Name."""
        if isinstance(stmt, ast.AugAssign) and isinstance(stmt.target, ast.Name):
            name = stmt.target.id
            if self.in_function:
                self.local_vars.add(name)
                self.ident_map.setdefault(name, self._safe_ident(name))
                py = self._py_ident(name)
            else:
                py = name
            # Expand a += x → (a := ((a) + (x)))
            op = stmt.op
            if isinstance(op, ast.Add):
                op_s = "+"
            elif isinstance(op, ast.Sub):
                op_s = "-"
            elif isinstance(op, ast.Mult):
                op_s = "*"
            elif isinstance(op, ast.Div):
                op_s = "/"
            elif isinstance(op, ast.Mod):
                op_s = "%"
            else:
                op_s = "+"
            rhs = self.visit(stmt.value)
            return f"({py} := (({py}) {op_s} ({rhs})))"
        if not isinstance(stmt, (ast.Assign, ast.ReAssign)):
            return None
        if not isinstance(stmt.target, ast.Name):
            return None
        name = stmt.target.id
        if self.in_function:
            self.local_vars.add(name)
            self.ident_map.setdefault(name, self._safe_ident(name))
            py = self._py_ident(name)
        else:
            py = name
        rhs = self.visit(stmt.value)
        return f"({py} := ({rhs}))"

    def visit_Switch(self, node: ast.Switch):
        """Lower ``switch`` / ``switch subject``.

        Pure expression arms → nested ternary (value context).
        Assign/ReAssign arms use walrus so ``_S := x`` is expression-safe.
        Arms with if/for/side-effect blocks → if/elif statement chain.
        """
        subject = self.visit(node.subject) if getattr(node, "subject", None) is not None else None
        cases = list(node.cases or [])
        pure = all(self._switch_case_is_expr(c) for c in cases)

        def _case_value_expr(case) -> str:
            body = getattr(case, "body", None) or []
            if not body:
                return "np.nan"
            if len(body) == 1:
                stmt = body[0]
                walrus = self._switch_assign_walrus(stmt)
                if walrus is not None:
                    return walrus
                if isinstance(stmt, ast.Expr):
                    val = self.visit(stmt.value)
                else:
                    val = self.visit(stmt)
                return val if val else "np.nan"
            # Multi-stmt arms need walrus binds — not nopython-safe.
            self.object_mode = True
            parts: list[str] = []
            for stmt in body[:-1]:
                walrus = self._switch_assign_walrus(stmt)
                if walrus is not None:
                    parts.append(walrus)
                    continue
                v = self.visit(stmt)
                if v:
                    parts.append(f"({v})")
            last_stmt = body[-1]
            walrus = self._switch_assign_walrus(last_stmt)
            if walrus is not None:
                last = walrus
            elif isinstance(last_stmt, ast.Expr):
                last = self.visit(last_stmt.value) or "np.nan"
            else:
                last = self.visit(last_stmt) or "np.nan"
            if not parts:
                return last
            parts.append(last)
            return f"({', '.join(parts)})[{len(parts) - 1}]"

        if pure:
            expr = "np.nan"
            for case in reversed(cases):
                case_val = _case_value_expr(case)
                pat = getattr(case, "pattern", None)
                if pat is None:
                    expr = case_val
                    continue
                pat_v = self.visit(pat)
                if subject is not None:
                    expr = f"({case_val} if ({subject}) == ({pat_v}) else {expr})"
                else:
                    expr = f"({case_val} if ({pat_v}) else {expr})"
            return expr

        # Statement form for arms with nested if/for/etc.
        self.object_mode = True
        lines: list[str] = []
        first = True
        default_body = None
        for case in cases:
            pat = getattr(case, "pattern", None)
            body = getattr(case, "body", None) or []
            if pat is None:
                default_body = body
                continue
            pat_v = self.visit(pat)
            cond = f"({subject}) == ({pat_v})" if subject is not None else f"({pat_v})"
            lines.append(f"if {cond}:" if first else f"elif {cond}:")
            first = False
            emitted = 0
            for stmt in body or []:
                val = self.visit(stmt)
                if val:
                    lines.append("    " + val.replace("\n", "\n    "))
                    emitted += 1
            if emitted == 0:
                lines.append("    pass")
        if default_body is not None:
            lines.append("else:")
            emitted = 0
            for stmt in default_body or []:
                val = self.visit(stmt)
                if val:
                    lines.append("    " + val.replace("\n", "\n    "))
                    emitted += 1
            if emitted == 0:
                lines.append("    pass")
        elif not lines:
            return "np.nan"
        return "\n".join(lines) if lines else "np.nan"

    def _as_bool_cond(self, expr: str, *, node=None) -> str:
        """Coerce a condition so bare series arrays never hit Python truth tests.

        - Full series buffers (``foo_arr``, ``close_arr``) → ``bool(foo_arr[__bar_idx])``
        - Already indexed / scalar comparisons pass through.
        - Defensive: ndarray truth is never taken (np.any for multi-element).
        """
        e = (expr or "").strip()
        if not e:
            return "False"
        # Already a comparison / boolean op / unary not — leave alone
        if any(op in e for op in ("==", "!=", "<=", ">=", " < ", " > ", " and ", " or ")):
            # Still may be `(arr) != 0` where arr is full series from a bad free-scalar
            # pass-through; wrap only plain `name_arr` tokens used as the sole test.
            pass
        if e.endswith("[__bar_idx]"):
            return e
        # Bare series array identifier
        if self._is_series_array_base(e) and not e.endswith("[__bar_idx]"):
            return f"bool({e}[__bar_idx])"
        # Name that is a tracked series → index current bar
        if node is not None and isinstance(node, ast.Name):
            nid = node.id
            if f"{nid}_arr" in self.arrays or nid in self.string_series:
                return f"bool({nid}_arr[__bar_idx])"
            if nid in self.series_params:
                return f"bool({self._py_ident(nid)}[__bar_idx])"
            if nid in self.series_locals:
                return f"bool({self._py_ident(nid)}_arr[__bar_idx])"
        # Identifier ending in _arr without index (free var / param mishap)
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*_arr", e):
            return f"bool({e}[__bar_idx])"
        return e
    def _try_if_as_ternary(self, node: ast.If) -> str | None:
        """Emit a Python ternary when every branch is a single pure expression.

        Pine if-expressions used as RHS (``x = if cond\n    a\nelse\n    b``)
        must not become multi-line ``if`` statements embedded in
        ``safe_float(if ...)`` — that is invalid Python.

        Statement-like arms (``for`` / ``while`` / multi-line / empty) must
        fall through to statement-form ``visit_If`` so we never produce
        ``(i = 0\\nwhile … if cond else np.nan)``.
        """
        def _single_pure_expr(stmts) -> str | None:
            if not stmts or len(stmts) != 1:
                return None
            s = stmts[0]
            if isinstance(s, (ast.ForTo, ast.ForIn, ast.While, ast.Break, ast.Continue)):
                return None
            if isinstance(s, (ast.Assign, ast.ReAssign)):
                return None
            if isinstance(s, ast.If):
                return self._try_if_as_ternary(s)
            if isinstance(s, ast.Expr):
                if isinstance(s.value, ast.If):
                    return self._try_if_as_ternary(s.value)
                if isinstance(
                    s.value, (ast.ForTo, ast.ForIn, ast.While, ast.Switch)
                ):
                    return None
                # Reject statement-like nested forms; plain exprs only.
                val = self.visit(s.value)
                if not val or not str(val).strip():
                    return None
                stripped = str(val).lstrip()
                if "\n" in val or stripped.startswith(
                    ("if ", "for ", "while ", "else:", "elif ", "return ", "raise ")
                ):
                    return None
                return val
            return None

        body = _single_pure_expr(node.body)
        if body is None:
            return None
        if node.orelse:
            else_e = _single_pure_expr(node.orelse)
            if else_e is None:
                return None
        else:
            else_e = "np.nan"
        test = self._as_bool_cond(self.visit(node.test), node=node.test)
        return f"({body} if {test} else {else_e})"

    def _coerce_if_assign_val(self, target_store: str, val: str) -> str:
        """Coerce if-branch values written into float64 series targets."""
        if not target_store.endswith("[__bar_idx]"):
            return val
        base = target_store[: -len("[__bar_idx]")]
        name = base[: -len("_arr")] if base.endswith("_arr") else base
        # Object / string series accept any Python value
        if name in self.string_series or name in self.udt_vars:
            return val
        if self._is_safe_numeric_expr(val):
            return val
        self.object_mode = True
        if val.startswith("safe_float("):
            return val
        return f"safe_float({val})"

    def _emit_if_assign(self, target_store: str, node: ast.If) -> str:
        """Emit multi-branch if that assigns ``target_store = <tail expr>`` per arm.

        Used for Pine if-expressions with mid-branch side effects
        (``x = if c\n    a := 1\n    true\nelse\n    false``).
        """
        test = self._as_bool_cond(self.visit(node.test), node=node.test)
        lines = [f"if {test}:"]

        def _emit_branch(stmts) -> list[str]:
            out: list[str] = []
            if not stmts:
                out.append(f"    {target_store} = np.nan")
                return out
            for i, stmt in enumerate(stmts):
                is_tail = i == len(stmts) - 1
                if is_tail and isinstance(stmt, ast.If):
                    # elif chain: nested if-assign
                    nested = self._emit_if_assign(target_store, stmt)
                    out.append("    " + nested.replace("\n", "\n    "))
                    continue
                if is_tail and isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.If):
                    nested = self._emit_if_assign(target_store, stmt.value)
                    out.append("    " + nested.replace("\n", "\n    "))
                    continue
                if is_tail and isinstance(stmt, ast.Expr):
                    val = self._coerce_if_assign_val(target_store, self.visit(stmt.value))
                    out.append(f"    {target_store} = {val}")
                    continue
                if is_tail and isinstance(stmt, (ast.Assign, ast.ReAssign)):
                    # assign then store the assigned name/value
                    line = self.visit(stmt)
                    if line:
                        out.append("    " + line.replace("\n", "\n    "))
                    # Prefer reading back LHS for series/scalars
                    if isinstance(stmt.target, ast.Name):
                        lhs = self.visit(ast.Name(id=stmt.target.id, ctx=ast.Load()))
                        lhs = self._coerce_if_assign_val(target_store, lhs)
                        out.append(f"    {target_store} = {lhs}")
                    else:
                        out.append(f"    {target_store} = np.nan")
                    continue
                # mid-branch statement (side effect)
                line = self.visit(stmt)
                if line:
                    out.append("    " + line.replace("\n", "\n    "))
            if not any(target_store in ln for ln in out):
                out.append(f"    {target_store} = np.nan")
            return out

        lines.extend(_emit_branch(node.body))
        if node.orelse:
            lines.append("else:")
            lines.extend(_emit_branch(node.orelse))
        else:
            lines.append("else:")
            lines.append(f"    {target_store} = np.nan")
        return "\n".join(lines)

    def visit_If(self, node: ast.If):
        # Expression-context pure if → ternary (avoids ``safe_float(if …)``).
        if not self.if_return_mode:
            tern = self._try_if_as_ternary(node)
            if tern is not None:
                return tern
        test = self._as_bool_cond(self.visit(node.test), node=node.test)
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
                        # Never return-wrap statements: for/while (Expr-wrapped),
                        # multi-line blocks, bare assigns, statement-form switch.
                        inner = stmt.value
                        stripped = val.lstrip()
                        first_phys = stripped.split("\n", 1)[0]
                        is_stmt_like = (
                            isinstance(
                                inner,
                                (ast.ForTo, ast.ForIn, ast.While, ast.If, ast.Switch),
                            )
                            or "\n" in val
                            or stripped.startswith(
                                (
                                    "if ",
                                    "for ",
                                    "while ",
                                    "return ",
                                    "else:",
                                    "elif ",
                                    "raise ",
                                )
                            )
                            or bool(
                                re.match(
                                    r"^[A-Za-z_][\w\.]*(\[[^\]]*\])?\s*=(?!=)",
                                    first_phys,
                                )
                            )
                        )
                        if not is_stmt_like:
                            val = f"return {val}"
                self.if_return_mode = prev
                if val:
                    val = val.replace("\n", "\n    ")
                    out.append(f"    {val}")
            if not out:
                out.append("    return np.nan" if ret_mode else "    pass")
            elif ret_mode and not any("return " in ln for ln in out):
                # Only append trailing return for pure-value ifs; statement-only
                # arms (for-loops) must not force a fake return np.nan after them
                # when the branch already ran as a statement.
                if not any(
                    ln.lstrip().startswith(("for ", "while ", "if ", "_i ", "__step"))
                    or "\n" in ln
                    for ln in out
                ):
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
        # Pine name (may be a Python keyword like ``from``) + safe def name
        pine_name = node.name
        func_name = self._safe_ident(pine_name)
        if func_name != pine_name:
            self.func_name_map[pine_name] = func_name
        args = [arg.name for arg in node.args if hasattr(arg, "name")]
        arg_set = set(args)
        # Register under both Pine and safe names so call lookup works either way
        self.user_funcs.add(pine_name)
        self.user_funcs.add(func_name)
        if getattr(node, "export", None) or getattr(node, "method", None):
            # export / method in libraries → always object mode
            self.object_mode = True
        prev_series = set(self.series_params)
        prev_series_locals = set(self.series_locals)
        prev_param_names = set(self.param_names)
        prev_ident = dict(self.ident_map)
        self.in_function = True
        # Metadata keys use Pine name (call sites resolve via Pine id / attr)
        self._current_func_name = pine_name
        self.local_vars = set(args)
        # Capture optional param defaults for call-site fill
        defaults_map: dict[str, str] = {}
        for arg in node.args:
            if not hasattr(arg, "name"):
                continue
            d = getattr(arg, "default", None)
            if d is not None:
                defaults_map[arg.name] = self.visit(d)
        self.func_param_defaults[pine_name] = defaults_map
        self.func_param_defaults[func_name] = defaults_map
        self.param_names = set(args)
        # Rename params that shadow Python builtins (len, sum, id, …)
        # Also params that shadow a *different* UDF (``model`` param vs ``export model``)
        # so ``model(1)`` still calls the function while the param is ``model__p``.
        self.ident_map = {}
        for a in args:
            if a in self.user_funcs and a not in (pine_name, func_name):
                self.ident_map[a] = f"{self._safe_ident(a)}__p"
            else:
                self.ident_map[a] = self._safe_ident(a)

        # Pass 0: assigned locals + names used under history subscript
        assigned: set[str] = set()
        history_names: set[str] = set()
        for stmt in node.body:
            self._collect_assigned_names(stmt, assigned)
            self._collect_history_names(stmt, history_names)
        self.history_names_current = set(history_names)

        # Safe names for assigned locals (sum, max, min, …).
        # Also rename locals that shadow a UDF (``mama = mama(...)`` → UnboundLocal).
        for n in assigned:
            if n in self.user_funcs or n == pine_name or n == func_name:
                self.ident_map[n] = f"{self._safe_ident(n)}__loc"
            else:
                self.ident_map[n] = self._safe_ident(n)

        # Params used with history → series_params (full arrays from caller)
        self.series_params = set()
        for stmt in node.body:
            self._mark_series_params(stmt)
        # Only param names from this function count as series_params for body gen
        # (never promote loop counters / non-params via history_names alone)
        series_for_func = {a for a in args if a in self.series_params or a in history_names}
        # Body gen sees only this function's series params (avoid cross-fn name clash)
        self.series_params = set(series_for_func)

        # Assigned non-params used with history → series_locals (persistent state arrs)
        # Exclude names that are only loop counters (not true series state)
        series_locals = sorted(
            n
            for n in history_names
            if n in assigned and n not in arg_set and n not in self.loop_counters
        )
        self.series_locals = set(series_locals)
        self.local_vars |= assigned
        self._free_scalars_current = set()

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

        free_scalars_set = {
            n
            for n in self._free_scalars_current
            if n not in arg_set
            and n not in assigned
            and n not in self.user_funcs
            and n not in self.loop_counters
            and n not in self.import_aliases
            and n not in _NS
            and n not in _COLOR_NAMES
            and n not in _ENUM_NS
        }
        # Transitive free scalars from nested UDF callees (e.g. suite helpers
        # calling ``_it`` need ``_private_suites`` even if not named in body text).
        body_text_for_free = "\n".join(body_lines)
        for callee, scs in getattr(self, "func_free_scalars", {}).items():
            if callee in (pine_name, func_name):
                continue
            # only if body actually calls that callee
            if not re.search(rf"\b{re.escape(callee)}\s*\(", body_text_for_free):
                # also check py-mapped name
                py_cal = self.func_name_map.get(callee, callee)
                if not re.search(rf"\b{re.escape(py_cal)}\s*\(", body_text_for_free):
                    continue
            for sc in scs:
                if (
                    sc not in arg_set
                    and sc not in assigned
                    and sc not in self.user_funcs
                    and sc not in self.loop_counters
                    and sc not in free_scalars_set
                ):
                    free_scalars_set.add(sc)
        free_scalars = sorted(free_scalars_set)
        # Metadata keyed by Pine name (call sites look up by Pine id/attr)
        self.func_free_scalars[pine_name] = free_scalars
        if self._func_body_returns_sequence(node, last_ast, body_lines) if hasattr(self, "_func_body_returns_sequence") else False:
            self.func_returns_sequence.add(pine_name)
        # Detect string/size-enum returning UDFs (``f_gTS → size.tiny``)
        if not hasattr(self, "func_returns_string"):
            self.func_returns_string: set[str] = set()
        if self._func_body_returns_string(body_lines):
            self.func_returns_string.add(pine_name)
            self.func_returns_string.add(func_name)
        # clear sequence locals for next function
        self.local_sequence_vars = set()
        self._free_scalars_current = set()
        self.history_names_current = set()

        self.in_function = False
        self._current_func_name = None
        self.local_vars = set()
        # Restore + accumulate series_params for call-site lowering of this fn's args
        self.series_params = prev_series | series_for_func
        self.series_locals = prev_series_locals
        self.param_names = prev_param_names
        self.func_series_params[pine_name] = series_for_func
        self.func_series_locals[pine_name] = list(series_locals)
        self.func_param_names[pine_name] = list(args)

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
        self.func_st_params[pine_name] = st_refs

        # series-local params use safe base name + _arr
        sl_params = [f"{self.ident_map.get(s, s)}_arr" for s in series_locals]
        # Free script-level series referenced inside the UDF (e.g. hma3 uses outer `lag`)
        # Functions are emitted at module scope, so they cannot close over execute_script locals.
        _chart = {"open_arr", "high_arr", "low_arr", "close_arr", "vol_arr"}
        _scalar_arrs = {
            f"{n}_arr"
            for n in (self.scalar_vars | self.map_vars | self.loop_counters)
        }
        # Param py names (formals may already be named ``x_arr`` / ``src_arr``)
        _param_py = {self._py_ident(a) for a in args}
        free_series = sorted(
            {
                m
                for m in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*_arr)\b", body_text)
                if m not in _chart
                and m not in sl_params
                and m not in _scalar_arrs
                and not m.startswith("__st_")
                and m not in {f"{self._py_ident(a)}_arr" for a in args}
                # Never re-inject a formal (even when already named ``*_arr``)
                and m not in _param_py
                and m not in {self._py_ident(a) for a in args if a in series_for_func}
                # Drop fake series for bare locals assigned inside the UDF
                and m[: -len("_arr")] not in assigned
            }
            | {
                # Incremental TA state buffers (__ema0_st, __atr0_st, …)
                m
                for m in re.findall(r"\b(__[A-Za-z][A-Za-z0-9_]*_st)\b", body_text)
                if m not in sl_params
            }
        )
        # Also bare series-param style names already covered; store for call site
        if not hasattr(self, "func_free_series"):
            self.func_free_series: dict[str, list[str]] = {}
        self.func_free_series[pine_name] = free_series
        # Ensure free series arrays are allocated in execute_script_compiled
        # (skip __*_st — those are sized by _alloc_fixed_state, not n_bars)
        for fs in free_series:
            if fs.endswith("_st") and fs.startswith("__"):
                continue
            self.arrays.add(fs)

        # Free runtime context: drawings surface + bar count (not chart OHLC).
        # UDFs are module-scope; they cannot close over execute_script locals.
        needs_drawings = "__drawings" in body_text
        needs_n_bars = bool(re.search(r"\bn_bars\b", body_text))
        self.func_needs_drawings[pine_name] = needs_drawings
        self.func_needs_n_bars[pine_name] = needs_n_bars
        if needs_drawings:
            self.object_mode = True

        needs_ctx = (
            any(tok in body_text for tok in _ctx_tokens)
            or bool(series_for_func)
            or bool(series_locals)
            or bool(st_refs)
            or bool(free_series)
            or bool(free_scalars)
        )
        # Emit safe Python param names for user-facing args.
        # Never put ``=default`` on the def when trailing required params
        # (series state / chart context) would follow — invalid Python.
        # Defaults are still applied at call sites via func_param_defaults.
        # Order must match _emit_user_func_call:
        #   args, sl, st, free_scalars, free_series, [__drawings], [n_bars],
        #   [chart...], [__strategy]
        param_list = []
        for a in args:
            param_list.append(self._py_ident(a))
        for p in sl_params:
            if p not in param_list:
                param_list.append(p)
        for p in st_refs:
            if p not in param_list:
                param_list.append(p)
        for p in free_scalars:
            py = self._py_ident(p)
            if py not in param_list:
                param_list.append(py)
        for p in free_series:
            if p not in param_list:
                param_list.append(p)
        if needs_drawings and "__drawings" not in param_list:
            param_list.append("__drawings")
        if needs_n_bars and "n_bars" not in param_list:
            param_list.append("n_bars")
        if needs_ctx:
            extra = ["open_arr", "high_arr", "low_arr", "close_arr", "vol_arr", "__bar_idx"]
            param_list.extend(e for e in extra if e not in param_list)
            self.func_needs_bar[pine_name] = True
        else:
            self.func_needs_bar[pine_name] = False
        needs_strategy = "__strategy" in body_text
        if needs_strategy:
            self.object_mode = True
            self.uses_strategy = True
            if "__strategy" not in param_list:
                param_list = list(param_list) + ["__strategy"]
        self.func_needs_strategy[pine_name] = needs_strategy

        deco = "@numba.njit(cache=False)" if not self.object_mode else ""
        lines = []
        if deco:
            lines.append(deco)
        # Safe Python identifier (``from`` → ``from_``); call sites use func_name_map
        lines.append(f"def {func_name}({', '.join(param_list)}):")
        if not body_lines:
            lines.append("    pass")
        else:
            # Only wrap a pure expression result — never `if`/`for`/`while` as `return if …`
            # (if-expr results already contain return statements via if_return_mode)
            # Also return the value of a final Assign/ReAssign (Pine `out := expr` UDFs).
            last_is_assign = isinstance(last_ast, (ast.Assign, ast.ReAssign))
            last_val = getattr(last_ast, "value", None) if isinstance(last_ast, ast.Expr) else None
            last_is_ctrl = isinstance(
                last_val, (ast.If, ast.ForTo, ast.While, ast.ForIn)
            ) or isinstance(last_ast, (ast.ForTo, ast.ForIn, ast.While))
            returnable = (
                (
                    isinstance(last_ast, ast.Expr)
                    and not last_is_ctrl
                    and not last_is_if_expr
                )
                or last_is_assign
            )
            # Pine ``for … in …`` as last stmt: last body expr is the loop value
            # (e.g. ``for x in arr\n    result`` returns last ``result``).
            last_is_for = isinstance(last_ast, (ast.ForIn, ast.ForTo)) or isinstance(
                last_val, (ast.ForIn, ast.ForTo)
            )
            for_ret_name: str | None = None
            if last_is_for and body_lines:
                # Find trailing bare name expression inside the for block only
                # (``for x in arr\n    result`` → return result). Do NOT fall back
                # to arbitrary assigned locals (``zone_color = …`` mid-loop is not
                # the function result and may be unbound).
                last_line = body_lines[-1]
                phys_lines = [ln.strip() for ln in last_line.split("\n") if ln.strip()]
                if phys_lines:
                    tail = phys_lines[-1]
                    m_tail = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)", tail)
                    if m_tail:
                        for_ret_name = m_tail.group(1)
            for i, line in enumerate(body_lines):
                is_last = i == len(body_lines) - 1
                line = line.replace("\n", "\n    ")
                stripped = line.lstrip()
                # Detect real assignment statements only — never treat kwargs in a
                # call (``__strategy.close(id=..., qty=...)``) as assignment. A
                # previous ``=``-anywhere regex produced truncated returns like
                # ``return __strategy.close(id``.
                first_phys = stripped.split("\n", 1)[0]
                looks_assign = last_is_assign or bool(
                    re.match(
                        r"^[A-Za-z_][\w\.]*(\[[^\]]*\])?\s*=(?!=)",
                        first_phys,
                    )
                )
                # Multi-line statement blocks (statement-form switch → if/elif)
                # must not become ``return if …``.
                looks_stmt_block = "\n" in stripped or stripped.startswith(
                    ("if ", "for ", "while ", "else:", "elif ", "try:", "with ", "return ")
                )
                if (
                    is_last
                    and returnable
                    and not looks_assign
                    and not looks_stmt_block
                ):
                    lines.append(f"    return {line}")
                else:
                    lines.append(f"    {line}")
                    if is_last and returnable and looks_assign:
                        # Pine UDF ending in `out := expr` should return that value
                        # (e.g. custom _rma). Prefer LHS read-back over np.nan.
                        lhs = first_phys.split("=", 1)[0].strip()
                        if lhs and not lhs.startswith(("if ", "for ", "while ")):
                            lines.append(f"    return {lhs}")
                        else:
                            lines.append("    return np.nan")
                    elif is_last and last_is_for and for_ret_name:
                        lines.append(f"    return {for_ret_name}")
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


    def _emit_period(self, expr: str, default: str = "0") -> str:
        """NaN-safe period/length coercion for TA and for-loops."""
        e = (expr or "").strip()
        if not e:
            return default
        # plain int literal
        if re.fullmatch(r"-?\d+", e):
            return e
        if self.object_mode:
            return f"safe_period({e}, {default})"
        return f"(0 if ({e}) != ({e}) else int({e}))"

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
        # Always track as loop counter so history on the counter never treats it
        # as a series array (``i[1]`` → na, not ``i[__bar_idx-1]``).
        self.loop_counters.add(target)
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
        try:
            for stmt in node.body:
                val = self.visit(stmt)
                if val:
                    val = val.replace("\n", "\n    ")
                    lines.append(f"    {val}")
        finally:
            self.loop_counters.discard(target)
        lines.append(f"    {target} += __step_{target}")
        if added_local:
            self.local_vars.discard(target)
        if added_scalar:
            self.scalar_vars.discard(target)
        return "\n".join(lines)

    def visit_ForIn(self, node: ast.ForIn):
        """``for eachLine in id`` — iterate array/collection handles (object mode).

        Pine ``for [index, value] in arr`` is lowered to ``enumerate``.
        """
        self.object_mode = True
        iterable = self.visit(node.iter)
        added_names: list[str] = []
        # Tuple target: for [index, value] in collection
        if isinstance(node.target, ast.Tuple) and getattr(node.target, "elts", None):
            elts = node.target.elts
            names: list[str] = []
            for el in elts:
                if isinstance(el, ast.Name):
                    names.append(el.id)
                else:
                    names.append(self.visit(el))
            for nm in names:
                self.loop_counters.add(nm)
                added_names.append(nm)
                if self.in_function:
                    self.local_vars.add(nm)
                else:
                    self.scalar_vars.add(nm)
            if len(names) == 2:
                # Index+value form — always enumerate (ignore element-is-tuple)
                tgt = f"{names[0]}, {names[1]}"
                lines = [f"for {tgt} in enumerate(safe_iter({iterable})):"]
            else:
                tgt = ", ".join(names)
                lines = [f"for {tgt} in safe_iter({iterable}):"]
        else:
            target = (
                node.target.id
                if isinstance(node.target, ast.Name)
                else self.visit(node.target)
            )
            self.loop_counters.add(target)
            added_names.append(target)
            if self.in_function:
                if target not in self.local_vars:
                    self.local_vars.add(target)
            else:
                if target not in self.scalar_vars:
                    self.scalar_vars.add(target)
            # Guard non-iterables (float/NaN from mis-typed series) so the bar loop
            # does not raise ``float is not iterable``.
            lines = [f"for {target} in safe_iter({iterable}):"]
        try:
            n = 0
            for stmt in node.body:
                val = self.visit(stmt)
                if val:
                    val = val.replace("\n", "\n    ")
                    lines.append(f"    {val}")
                    n += 1
            if n == 0:
                lines.append("    pass")
        finally:
            for nm in added_names:
                self.loop_counters.discard(nm)
                if self.in_function:
                    # keep if also a normal local; only added for loop scope
                    pass
                else:
                    # loop var is ephemeral per-bar
                    self.scalar_vars.discard(nm)
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
