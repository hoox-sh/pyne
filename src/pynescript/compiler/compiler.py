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

"""Pine AST → Python/Numba source emitter.

Two backends (selected by :class:`CompilerVisitor` while walking the tree):

- **numeric** (default): module imports ``numba_builtins``, emits
  ``@numba.njit(cache=False) def execute_script_compiled(...)`` with a
  float64 bar loop. Plot results return as a **tuple** of series (host packs
  titles). Requires Numba at compile/load time.
- **object**: pure-Python bar loop when UDT, map, drawing, strategy, string/
  color series, library imports, or :attr:`force_object_mode` appear. Still
  star-imports :mod:`pynescript.compiler.numba_builtins` (``safe_*``, matrix,
  ``na_num``, non-jitted TA). Returns a **dict** (plots + ``__drawings`` /
  strategy extras).

Host packing / contracts
------------------------
- Generated entry point is always
  ``execute_script_compiled(open, high, low, close, vol, time)`` — the host
  is :mod:`pynescript.compiler.engine` (synthetic ``bar*60_000`` ms when time
  omitted; Runtime passes real OHLCV bar-open ms).
- ``request.security`` / ``security``: same-symbol OHLCV passthrough only;
  complex expressions emit ``na`` (no close-as-dividend invention).
- nopython fallback: engine re-visits with ``force_object_mode=True`` after a
  TypingError warm-up; this module only implements the emit switch.
- UDF series state lives in ``__st_{func}_{local}`` arrays; free chart series
  and fixed TA state (``__ema0_st``, …) are passed as explicit params (njit
  forbids free vars / closures).
- Pine ``na`` / ``None`` in object-mode arithmetic goes through :meth:`_na_wrap_num`
  → ``na_num``; history uses :meth:`_history_subscript` (NaN-safe int offsets).

This file is large by design (per-namespace call lowering). Prefer documenting
entry points and non-obvious helpers — not every ``visit_*`` leaf.
"""

from __future__ import annotations

import keyword
import re

from typing import Any

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
        "kama",
        "cmf",
        "stochrsi",
        "willr",
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
    "binary_search": "array_binary_search",
    "binary_search_leftmost": "array_binary_search_leftmost",
    "binary_search_rightmost": "array_binary_search_rightmost",
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
    "mode": "array_mode",
    "standardize": "array_standardize",
    "normalized": "array_normalized",
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
    # NOTE: matrix.sort/reverse share method names with array; array wins in this
    # flat map. Type-aware dispatch would map m.sort → matrix_sort (tracked separately).
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
    """Lower a Pine :class:`~pynescript.ast.node.Script` AST to executable Python.

    Responsibilities
    ----------------
    - Walk statements/expressions and emit bar-loop body lines + nested UDFs.
    - Track series buffers (``*_arr``), plots, UDT/map/string series, strategy.
    - Flip :attr:`object_mode` when features are incompatible with nopython.
    - Emit either :meth:`_emit_numeric_mode` or :meth:`_emit_object_mode` from
      :meth:`visit_Script`.

    Parameters
    ----------
    force_object_mode:
        Engine recovery when nopython JIT cannot type the generated body
        (pyobject arrays / unicode ops). AST walk is identical; only the final
        emit path is pinned to object mode (strips ``@numba.njit`` from UDFs).

    Key attributes (filled during visit)
    ------------------------------------
    ``plots``:
        Ordered ``{"title": ...}`` entries used by the host for tuple→dict packing.
    ``object_mode`` / ``force_object_mode``:
        Backend selection flags.
    ``functions``:
        Pre-rendered UDF source strings (module scope above the bar loop).
    ``func_*`` maps:
        UDF metadata for call-site packing (series params/locals, free series/
        scalars, chart/strategy/drawings context) — see :meth:`visit_FunctionDef`
        and :meth:`_emit_user_func_call`.
    """

    def __init__(self, *, force_object_mode: bool = False):
        super().__init__()
        self.arrays: set[str] = set()
        self.plots: list[dict] = []
        self.functions: list[str] = []
        self.in_function = False
        self.local_vars: set[str] = set()
        # Object-mode state
        # force_object_mode: engine recovery when nopython JIT cannot type the
        # generated body (pyobject arrays / unicode ops). Still walks AST the
        # same way; only the final emit path is pinned to object mode.
        self.force_object_mode = bool(force_object_mode)
        self.object_mode = bool(force_object_mode)
        self.uses_strategy = False
        self.strategy_kwargs: dict[str, str] = {}
        # Name → const-like Python expr for strategy() ctor kwargs (literals / input defvals).
        # reference requires const for most strategy() params; pyne compile mirrors that by folding
        # bar-constant series (``lev = input.float(10)`` → ``leverage=10``) into the broker ctor.
        self.const_like_values: dict[str, str] = {}
        self.udt_types: dict[str, list[str]] = {}  # type name -> field names
        # type name -> field name -> emitted default expr (``false`` → ``False``)
        self.udt_field_defaults: dict[str, dict[str, str]] = {}
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
        # ``ticker.heikinashi`` / ``request.security(…HA…)`` → fill ha_*_arr each bar
        self.needs_heikinashi: bool = False
        # Fixed-size state vectors: (name, length) allocated once outside bar loop
        self.fixed_state: list[tuple[str, int]] = []
        # name → size for cloning UDF call-site state (Pine: each call is independent)
        self._fixed_state_size: dict[str, int] = {}
        self._udf_call_site_i: int = 0  # unique suffix for per-call-site state clones
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
        self._fixed_state_size[name] = size
        return name

    @staticmethod
    def _is_ta_state_buf(name: str) -> bool:
        """True for incremental TA fixed buffers (``__sma0_st``) or clones."""
        if not name.startswith("__") or not name:
            return False
        # Templates: __ema0_st; call-site clones: __ema0_st_c3, __st_f_x_c1
        if name.endswith("_st"):
            return True
        if re.search(r"_st_c\d+$", name):
            return True
        return False

    @staticmethod
    def _is_series_local_state(name: str) -> bool:
        """True for UDF series-local history arrays (``__st_fn_local``)."""
        return name.startswith("__st_")

    def _series_local_template_is_object(self, name: str) -> bool:
        """True when ``__st_{func}_{local}`` (or a ``_cN`` clone) needs object dtype.

        Call-site clones of chart.point / array / drawing series locals must not
        land in float64 buffers (``ValueError: setting an array element with a
        sequence`` when storing pivot lists or point dicts).
        """
        if not name.startswith("__st_"):
            return False
        base = re.sub(r"(_c\d+)+$", "", name)
        obj_sl = getattr(self, "object_series_locals", set())
        if not obj_sl:
            return False
        for func_name, slocs in getattr(self, "func_series_locals", {}).items():
            for s in slocs:
                if s in obj_sl and base == f"__st_{func_name}_{s}":
                    return True
        return False

    def _clone_state_arg_for_call(self, name: str) -> str:
        """Allocate an independent state buffer for one UDF call site.

        Pine gives each call of a function its own series execution context. The
        visitor previously passed the same ``__smaN_st`` / ``__st_fn_x`` buffers
        to every call of a UDF, so multi-length MA helpers (ribbon / KST / PPO)
        corrupted each other within a bar.
        """
        cs = self._udf_call_site_i
        clone = f"{name}_c{cs}"
        if self._is_ta_state_buf(name) and not self._is_series_local_state(name):
            size = self._fixed_state_size.get(name)
            if size is None:
                for n, s in self.fixed_state:
                    if n == name:
                        size = s
                        break
            if size is None:
                # Nested clone of a prior call-site buffer — inherit size via prefix
                base = re.sub(r"(_c\d+)+$", "", name)
                size = self._fixed_state_size.get(base, 8)
            self.fixed_state.append((clone, size))
            self._fixed_state_size[clone] = size
            return clone
        # Series-local history (full bar arrays) or unknown __st_* form
        self.arrays.add(clone)
        if self._series_local_template_is_object(name):
            if not hasattr(self, "object_state_bufs"):
                self.object_state_bufs = set()
            self.object_state_bufs.add(clone)
        return clone

    @staticmethod
    def _try_nonneg_int_const(expr: str) -> int | None:
        """Parse a non-negative integer literal from an emitted expr, else None."""
        e = (expr or "").strip()
        if re.fullmatch(r"\d+", e):
            return int(e)
        return None

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
        # Call-site clones of object UDF series locals (no ``_arr`` suffix)
        if arr in getattr(self, "object_state_bufs", set()):
            return True
        if self._series_local_template_is_object(arr):
            return True
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
        """True when expr is a pure series array ref (optionally bar-indexed).

        Must be a bare identifier (``foo_arr`` / ``close_arr[__bar_idx]``), never a
        compound such as ``(clv) * vol_arr[__bar_idx]`` — those end in ``_arr`` after
        stripping the index and would be wrongly passed to numba TA as the source.
        """
        a = self._strip_bar_idx(expr)
        if a in (
            "open_arr",
            "high_arr",
            "low_arr",
            "close_arr",
            "vol_arr",
        ):
            return True
        # Pure user/synthetic series arrays only (no ops / parens / spaces).
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*_arr", a):
            return True
        if expr.endswith("[__bar_idx]") and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", a):
            return True
        return False

    def _materialize_series_source(self, expr: str) -> str:
        """Ensure a TA source is a full series array for numba_* history.

        Pure array refs pass through. Compounds (numba_abs(...), close*2) are
        written into a synthetic series via numba_store_src.
        Object mode uses store_src_py so list/str handles never do ``list + 0.0``.

        Object-dtype series (string/UDT) must never be passed to njit TA kernels
        (``array(pyobject)`` TypingError) — re-materialize as float64 via
        ``store_src_py``.
        """
        if self._is_series_arr_expr(expr):
            base = self._strip_bar_idx(expr)
            if self._is_object_dtype_arr(base):
                # Rebuild a float64 synthetic series from object cells.
                if self.in_function and self._current_func_name:
                    sid = f"__st_{self._current_func_name}__src{self._expr_src_i}"
                else:
                    sid = f"__src{self._expr_src_i}_arr"
                self._expr_src_i += 1
                self.arrays.add(sid)
                self.object_mode = True
                return f"store_src_py({sid}, {base}[__bar_idx], __bar_idx)"
            return base
        if self.in_function and self._current_func_name:
            sid = f"__st_{self._current_func_name}__src{self._expr_src_i}"
        else:
            sid = f"__src{self._expr_src_i}_arr"
        self._expr_src_i += 1
        self.arrays.add(sid)
        # Loop counters alone are numeric scalars — do not force object materialize.
        _obj_scalars = self.scalar_vars - self.loop_counters
        if self.object_mode or self.string_series or self.udt_vars or _obj_scalars:
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
        """Root: visit body, allocate any missed ``*_arr``, choose backend emit.

        Forces object mode for string/UDT/map/scalar object handles or when
        :attr:`force_object_mode` is set (engine nopython recovery).
        """
        body_lines: list[str] = []
        for stmt in node.body:
            val = self.visit(stmt)
            if val:
                body_lines.append(val)

        # Safety net: any ``*_arr`` referenced in body/functions must be allocated
        # (covers reassign-to-drawing discarding arrays, empty strategy stubs, …).
        _chart = {
            "open_arr",
            "high_arr",
            "low_arr",
            "close_arr",
            "vol_arr",
            "time_arr",
        }
        blob = "\n".join(body_lines) + "\n" + "\n".join(self.functions)
        for m in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*_arr)\b", blob):
            if m not in _chart and not m.startswith("__st_"):
                self.arrays.add(m)

        # String/color/UDT/map series must never enter njit (non-precise pyobject).
        # Pure numeric loop counters live in scalar_vars only while the for-body
        # is visited (and are discarded after); any residual scalar_vars here are
        # object handles (maps, drawings, string inputs) and force object mode.
        _obj_scalars = self.scalar_vars - self.loop_counters
        if self.string_series or self.udt_vars or self.map_vars or _obj_scalars:
            self.object_mode = True
        if self.force_object_mode:
            self.object_mode = True

        if self.object_mode:
            return self._emit_object_mode(body_lines)
        return self._emit_numeric_mode(body_lines)

    def _emit_numeric_mode(self, body_lines: list[str]) -> str:
        """Emit njit bar-loop module; plots returned as a tuple for host packing.

        ``@numba.njit(cache=False)`` — code is exec'd from ``<string>`` so disk
        cache locators do not apply. Star-imports :mod:`numba_builtins`.
        """
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
                "def execute_script_compiled("
                "open_arr, high_arr, low_arr, close_arr, vol_arr, time_arr):",
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
        if self.needs_heikinashi:
            for hl in self._heikinashi_bar_update_lines():
                lines.append(f"        {hl}")
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
                "def execute_script_compiled("
                "open_arr, high_arr, low_arr, close_arr, vol_arr, time_arr):",
                "    n_bars = len(close_arr)",
                "    open_arr = np.asarray(open_arr, dtype=np.float64)",
                "    high_arr = np.asarray(high_arr, dtype=np.float64)",
                "    low_arr = np.asarray(low_arr, dtype=np.float64)",
                "    close_arr = np.asarray(close_arr, dtype=np.float64)",
                "    vol_arr = np.asarray(vol_arr, dtype=np.float64)",
                "    time_arr = np.asarray(time_arr, dtype=np.float64)",
                "    __drawings = []",
            ]
        )
        if self.uses_strategy:
            # Broker ctor kwargs from strategy() declaration when present.
            # Only const-like exprs (literals or folded input/const series) — never
            # ``name_arr[__bar_idx]`` (undefined at ctor time; not a reference const either).
            sk = self.strategy_kwargs
            ctor_args = []
            for key in (
                "initial_capital",
                "commission_value",
                "commission_type",
                "slippage",
                "mintick",
                "pyramiding",
                "avg_price_model",
                "default_qty_type",
                "default_qty_value",
                "leverage",
            ):
                if key not in sk:
                    continue
                resolved = self._resolve_strategy_ctor_kwarg(sk[key])
                if resolved is None:
                    continue
                py_key = "slippage_ticks" if key == "slippage" else key
                ctor_args.append(f"{py_key}={resolved}")
            ctor = ", ".join(ctor_args)
            lines.append(f"    __strategy = CompileStrategyBroker({ctor})")
            # End-of-bar history for strategy.position_size[n] (always when broker)
            self.arrays.add("__strategy_position_size_arr")
            self.arrays.add("__strategy_position_avg_price_arr")
            self.arrays.add("__strategy_closed_trades_arr")
        for arr in sorted(self.arrays):
            # Never reallocate chart OHLCV parameters (user `vol` string series is
            # mangled to __user_vol_arr via _series_arr_name).
            if arr in (
                "open_arr",
                "high_arr",
                "low_arr",
                "close_arr",
                "vol_arr",
                "time_arr",
            ):
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
        if self.needs_heikinashi:
            for hl in self._heikinashi_bar_update_lines():
                lines.append(f"        {hl}")
        if self.uses_strategy:
            # One-call bar setup + pending fill (same order as Runtime:
            # process pending → evaluate body). Broker uses _mark for market fills.
            lines.append(
                "        __strategy.begin_bar("
                "__bar_idx, "
                "open_arr[__bar_idx], high_arr[__bar_idx], "
                "low_arr[__bar_idx], close_arr[__bar_idx])"
            )
        if not body_lines and not self.uses_strategy:
            lines.append("        pass")
        for line in body_lines:
            line = line.replace("\n", "\n        ")
            lines.append(f"        {line}")
        if not body_lines and self.uses_strategy:
            lines.append("        pass")
        if self.uses_strategy:
            lines.append(
                "        __strategy_position_size_arr[__bar_idx] = "
                "float(__strategy.position_size)"
            )
            lines.append(
                "        __strategy_position_avg_price_arr[__bar_idx] = "
                "float(__strategy.position_avg_price)"
            )
            lines.append(
                "        __strategy_closed_trades_arr[__bar_idx] = "
                "float(__strategy.closed_trades)"
            )

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
        obj_sl = getattr(self, "object_series_locals", set())
        for func_name, slocs in sorted(self.func_series_locals.items()):
            for s in slocs:
                # Drawing/UDT/string/var-object series locals need object dtype
                if s in self.udt_vars or s in self.string_series or s in obj_sl:
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
        """Register UDT field names and defaults; forces object mode. No runtime emit."""
        self.object_mode = True
        fields: list[str] = []
        defaults: dict[str, str] = {}
        for stmt in node.body:
            if isinstance(stmt, ast.Assign) and isinstance(stmt.target, ast.Name):
                fields.append(stmt.target.id)
                val = getattr(stmt, "value", None)
                if val is not None:
                    defaults[stmt.target.id] = self.visit(val)
        self.udt_types[node.name] = fields
        self.udt_field_defaults[node.name] = defaults
        return ""  # type definitions are compile-time only

    def visit_EnumDef(self, node: ast.EnumDef):
        """Enums lower as string constants in object mode only."""
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
                # na-safe: nested UDT field may be nan (motion: this.__timer.offset)
                return f"udt_set_field({obj}, {node.target.attr!r}, {val})"
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
        typed_chart_point = self._is_chart_point_type(type_node)

        if self.in_function:
            self.local_vars.add(name)
            # Shadow UDF name: ``mama = mama(...)`` must not rebind the function
            if name in self.user_funcs and name not in self.ident_map:
                self.ident_map[name] = f"{self._safe_ident(name)}__loc"
            py = self._py_ident(name)
            # Persistent UDF locals (history series or ``var``) write through state arrs.
            # Check before sequence early-return so ``var arr = array.new…`` persists.
            if name in self.series_locals:
                # Drawing / UDT / list handles must not go into float64 series-local arrays
                looks_obj = bool(
                    val
                    and (
                        "__drawings" in val
                        or val.startswith("{")
                        or val.startswith("[")
                        or "'kind':" in val
                        or '"kind":' in val
                        or "array_" in val
                        or (hasattr(self, "_rhs_is_sequence") and self._rhs_is_sequence(node.value, val))
                    )
                )
                typed_obj = type_id in (
                    "line",
                    "label",
                    "box",
                    "table",
                    "polyline",
                    "linefill",
                    "hline",
                    "color",
                    "string",
                    "str",
                ) or (type_id is not None and type_id in self.udt_types)
                # Typed array: ``var chart.point[] pivotsH`` — type is Subscript
                type_is_array = type_node is not None and type(type_node).__name__ in (
                    "Subscript",
                    "Specialize",
                )
                if (
                    looks_obj
                    or typed_obj
                    or typed_drawing
                    or typed_udt
                    or typed_chart_point
                    or type_is_array
                ):
                    self.object_mode = True
                    # Track object-dtype UDF state only — do NOT add to global
                    # udt_vars (that would make free-scalar lineLast resolve as
                    # lineLast_arr[__bar_idx] in other UDFs / the bar loop).
                    if not hasattr(self, "object_series_locals"):
                        self.object_series_locals = set()
                    self.object_series_locals.add(name)
                    self.local_sequence_vars.add(name)
                # ``var`` init: only on first bar, else carry previous value (aliases
                # list handles so array.push mutations accumulate across bars).
                if is_var or name in getattr(self, "var_locals", set()):
                    return (
                        f"{py}_arr[__bar_idx] = {val} if __bar_idx == 0 "
                        f"else {py}_arr[__bar_idx - 1]"
                    )
                return f"{py}_arr[__bar_idx] = {val}"
            # Array/list handles inside UDFs must be tracked as sequence locals
            # so the UDF is marked sequence-returning (knn → nearest_neighbors).
            if hasattr(self, "_rhs_is_sequence") and self._rhs_is_sequence(node.value, val):
                self.object_mode = True
                self.local_sequence_vars.add(name)
                return f"{py} = {val}"
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

        # `var MyState s = na` / `var chart.point p = na` → object-dtype series
        if typed_udt or typed_chart_point:
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

        # Detect map.new *before* bare ``{}`` is classified as a UDT/object handle
        # (map.new lowers to ``{}`` which would otherwise become m_arr series).
        if self._is_map_new(node.value):
            self.object_mode = True
            self.map_vars.add(name)
            self.arrays.discard(f"{name}_arr")
            if is_var:
                return f"if __bar_idx == 0:\n    {name} = {{}}"
            return f"{name} = {{}}"

        # UDT series / chart.point dict / udt_index handle / UDT ref (p2 = p1)
        # / Type.copy(p1) (shallow dict clone)
        rhs_is_udt_name = (
            isinstance(node.value, ast.Name) and node.value.id in self.udt_vars
        )
        if (
            name in self.udt_vars
            or self._looks_like_udt_ctor(node.value)
            or self._looks_like_udt_copy(node.value)
            or self._looks_like_object_handle_expr(val)
            or rhs_is_udt_name
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
        # Track bar-constant literals / input defvals for strategy() ctor folding
        if self._looks_like_const_expr(store_val):
            self.const_like_values[name] = store_val
        if is_var:
            return (
                f"{name}_arr[__bar_idx] = {store_val} if __bar_idx == 0 "
                f"else {name}_arr[__bar_idx-1]"
            )
        return f"{name}_arr[__bar_idx] = {store_val}"

    def _looks_like_const_expr(self, expr: str) -> bool:
        """True for numeric / string / bool Python literals usable in broker ctor."""
        s = (expr or "").strip()
        if not s:
            return False
        if s in {"True", "False", "None", "true", "false"}:
            return True
        if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
            return True
        # bare number (int / float / scientific)
        try:
            float(s)
            return True
        except ValueError:
            return False

    def _resolve_strategy_ctor_kwarg(self, expr: str) -> str | None:
        """Fold strategy() kwargs to const-like ctor args; drop non-const series refs.

        reference ``strategy()`` declaration params require *const* (not input/simple/series).
        PYNE still allows ``lev = input.float(10)`` then ``strategy(..., leverage=lev)``
        by folding the input's constant defval into the compile broker ctor.
        """
        import re

        s = (expr or "").strip()
        if not s:
            return None
        if self._looks_like_const_expr(s):
            return s
        m = re.fullmatch(r"([A-Za-z_]\w*)_arr\[__bar_idx\]", s)
        if m:
            return self.const_like_values.get(m.group(1))
        if re.fullmatch(r"[A-Za-z_]\w*", s):
            return self.const_like_values.get(s)
        return None

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
    def _is_chart_point_type(type_node) -> bool:
        """True for Pine ``chart.point`` (or bare ``point``) type annotations.

        ``var chart.point lastH = na`` must allocate ``dtype=object`` series, not
        float64 — otherwise assigning a point dict raises
        ``TypeError: float() argument … not 'dict'``.
        """
        if type_node is None:
            return False
        if isinstance(type_node, ast.Name) and type_node.id == "point":
            return True
        if isinstance(type_node, ast.Attribute) and type_node.attr == "point":
            return isinstance(type_node.value, ast.Name) and type_node.value.id == "chart"
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
        # Type.copy / shallow clone emit ``(dict(x) if isinstance(x, dict) else …)``
        if s.startswith("dict(") or s.startswith("(dict("):
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
                "sort_indices",
                "standardize",
                "normalized",
            ):
                return True
            if f.value.id == "matrix" and f.attr in (
                "row",
                "col",
                "submatrix",
                "remove_row",
                "remove_col",
                "remove_column",
                "copy",
                "eigenvalues",
                "eigenvectors",
            ):
                return True
            # map.keys / map.values return array handles (not float series)
            if f.value.id == "map" and f.attr in ("keys", "values", "copy"):
                # copy is a map handle; keys/values are arrays — both object
                return f.attr in ("keys", "values")
            if f.attr in ("sequence_from_series", "sequence_float"):
                return True
        if isinstance(f, ast.Attribute) and f.attr in (
            "concat",
            "copy",
            "slice",
            "from",
            "sort_indices",
            "standardize",
            "normalized",
            "row",
            "col",
            "submatrix",
            "remove_row",
            "remove_col",
            "remove_column",
            "keys",
            "values",
        ):
            # UDT Type.copy / instance.copy yield dict handles, not arrays
            if isinstance(f.value, ast.Name) and (
                f.value.id in self.udt_types or f.value.id in self.udt_vars
            ):
                return False
            # map.copy is a map handle (not a sequence); keys/values are arrays
            if f.attr == "copy" and isinstance(f.value, ast.Name) and f.value.id == "map":
                return False
            if f.attr in ("keys", "values"):
                return True
            return True
        if isinstance(f, ast.Name) and f.id in (
            "sequence_from_series",
            "str_split",
            "array_range",
            "array_sort_indices",
            "array_standardize",
            "array_normalized",
            "matrix_remove_row",
            "matrix_remove_col",
            "map_keys",
            "map_values",
        ):
            return True
        return False

    @staticmethod
    def _strip_series_index_loads(expr: str) -> str:
        """Replace ``name_arr[...]`` (balanced brackets) with ``0.0`` for safety scans."""
        out: list[str] = []
        i = 0
        n = len(expr)
        ident_re = re.compile(r"[A-Za-z_][A-Za-z0-9_]*_arr")
        while i < n:
            m = ident_re.match(expr, i)
            if m and m.end() < n and expr[m.end()] == "[":
                # Walk balanced [...]
                j = m.end() + 1
                depth = 1
                while j < n and depth:
                    ch = expr[j]
                    if ch == "[":
                        depth += 1
                    elif ch == "]":
                        depth -= 1
                    j += 1
                if depth == 0:
                    out.append("0.0")
                    i = j
                    continue
            out.append(expr[i])
            i += 1
        return "".join(out)

    def _is_safe_numeric_expr(self, val: str) -> bool:
        """Heuristic: visited expr is safe to store in float64 / use under njit float().

        Accepts compound arithmetic of series loads, history ternaries, and
        ``numba_*`` / ``np.*`` calls so scripts like ``plot(ta.sma(close,a)*b)``
        and ``for i = 0 to n: s := s + close[i]`` stay on the nopython path.
        """
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
        if s in ("__bar_idx", "n_bars"):
            return True
        if s.startswith("float(__bar_idx") or s.startswith("float(n_bars"):
            return True
        # Pure numba_/np.* calls (and compounds that only wrap them) are numeric.
        if s.startswith("numba_") or s.startswith("np."):
            # Still reject if string/object helpers sneaked in as args.
            if re.search(r"\b(safe_float|safe_int|nz_py|store_src_py|udt_|str\()\b", s):
                return False
            if "'" in s or '"' in s or "{" in s:
                return False
            return True
        # Bare identifiers: only known numeric loop counters / never handles.
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", s):
            if s in self.loop_counters:
                return True
            if s in self.user_funcs or s in self.scalar_vars or s in self.map_vars:
                return False
            if s in self.string_series or s in self.udt_vars or s in self.string_scalars:
                return False
            # Unknown bare name might be a function or handle — not safe
            return False

        # Object / string helpers force the Python path (not njit-safe).
        if "'" in s or '"' in s or "{" in s:
            return False
        if re.search(
            r"\b(str|dict|list|append|__drawings|__type__|safe_float|safe_int|"
            r"nz_py|store_src_py|udt_index|udt_set_field|safe_iter|safe_period|"
            r"safe_len|str_)\b",
            s,
        ):
            return False

        # Reject string/UDT series buffers anywhere in the expression.
        for name in self.string_series | self.udt_vars:
            if re.search(rf"\b{re.escape(name)}_arr\b", s):
                return False

        # UDF names (call or bare) are not known-numeric.
        for uf in self.user_funcs:
            if re.search(rf"\b{re.escape(uf)}\b", s):
                return False
        for py_name in getattr(self, "func_name_map", {}).values():
            if py_name and re.search(rf"\b{re.escape(py_name)}\s*\(", s):
                return False

        # All callees must be numeric-safe under njit.
        # Match ``np.tanh`` / ``numba_sma_inc`` as a single callee token.
        # Ternaries look like ``if (`` / ``and (`` — those keywords are not calls.
        _ALLOWED_CALLEES = frozenset(
            {
                "float",
                "int",
                "bool",
                "abs",
                "min",
                "max",
                "sum",
                "len",
                "range",
                "numba_store",
                "numba_store_src",
            }
        )
        _KW_NOT_CALLS = frozenset(
            {"if", "else", "and", "or", "not", "in", "is", "for", "while", "lambda"}
        )
        for m in re.finditer(r"\b((?:np\.)?[A-Za-z_][A-Za-z0-9_]*)\s*\(", s):
            callee = m.group(1)
            if callee in _KW_NOT_CALLS or callee in _ALLOWED_CALLEES:
                continue
            if callee.startswith("numba_") or callee.startswith("np."):
                continue
            return False

        # Replace known-safe series loads with a numeric placeholder so residual
        # brackets (if any) fail closed. History uses ``name_arr[expr]`` and the
        # index may itself contain nested ``other_arr[...]`` (balanced).
        t2 = self._strip_series_index_loads(s)
        if "[" in t2 or "]" in t2:
            return False
        # ``np.round`` / ``np.nan`` leave a bare attr word after ``np.`` — drop those.
        t2 = re.sub(r"\bnp\.[A-Za-z_][A-Za-z0-9_]*", "np", t2)

        # Residual bare names must not be object handles.
        for bare in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\b", t2):
            if bare in (
                "np",
                "nan",
                "pi",
                "e",
                "inf",
                "True",
                "False",
                "None",
                "if",
                "else",
                "and",
                "or",
                "not",
                "in",
                "is",
                "float",
                "int",
                "bool",
                "abs",
                "min",
                "max",
                "sum",
                "len",
                "range",
                "__bar_idx",
                "n_bars",
            ):
                continue
            if bare.startswith("numba_"):
                continue
            if bare.endswith("_arr") or bare.endswith("_st"):
                continue
            if bare in self.loop_counters:
                continue
            if bare in self.user_funcs or bare in self.scalar_vars or bare in self.map_vars:
                return False
            if bare in self.string_series or bare in self.udt_vars or bare in self.string_scalars:
                return False
            # Unknown free identifier — not proven numeric
            return False

        # Operators / numbers / allowed calls only
        if re.fullmatch(r"[\w\s\+\-\*/%\(\)\.\,\<\>\=\!\&\|?:]+", t2):
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
            if f.value.id == "array" and (
                f.attr
                in (
                    "new",
                    "from",
                    "copy",
                    "slice",
                    "concat",
                    "sort_indices",
                    "standardize",
                    "normalized",
                    "new_float",
                    "new_int",
                    "new_bool",
                    "new_string",
                    "new_color",
                    "new_line",
                    "new_label",
                    "new_box",
                    "new_table",
                    "new_linefill",
                )
                or f.attr.startswith("new_")
            ):
                return True
            if f.value.id == "matrix" and (
                f.attr.startswith("new")
                or f.attr
                in (
                    "row",
                    "col",
                    "submatrix",
                    "remove_row",
                    "remove_col",
                    "remove_column",
                    "copy",
                    "eigenvalues",
                    "eigenvectors",
                )
            ):
                return True
        # Method form: a.concat(b) / a.copy() / a.slice(...) / m.remove_row(...)
        # Do NOT treat UDT Type.copy / udt_var.copy as array handles.
        if isinstance(f, ast.Attribute) and f.attr in (
            "concat",
            "copy",
            "slice",
            "from",
            "sort_indices",
            "standardize",
            "normalized",
            "row",
            "col",
            "submatrix",
            "remove_row",
            "remove_col",
            "remove_column",
        ):
            if isinstance(f.value, ast.Name) and (
                f.value.id in self.udt_types or f.value.id in self.udt_vars
            ):
                return False
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
            pine_name = el.id
            names.append(pine_name)
            if not self.in_function:
                # Script-level UDF shadow: ``[pvsraVolume, ...] = pvsraVolume(...)``
                # must store under ``pvsraVolume__loc`` so the call still binds to
                # the def (Python would otherwise treat the name as a local None).
                if pine_name in self.user_funcs:
                    loc = f"{self._safe_ident(pine_name)}__loc"
                    self.ident_map[pine_name] = loc
                    self.object_mode = True
                    self.arrays.discard(f"{pine_name}_arr")
                    self.arrays.discard(f"{loc}_arr")
                else:
                    self.arrays.add(f"{pine_name}_arr")
            else:
                self.local_vars.add(pine_name)
                if pine_name in self.user_funcs and pine_name not in self.ident_map:
                    self.ident_map[pine_name] = f"{self._safe_ident(pine_name)}__loc"

        def _target_py(name: str) -> str:
            """Python store id for an unpack target (UDF-shadow → ``name__loc``)."""
            mapped = self.ident_map.get(name)
            if mapped and mapped.endswith(("__loc", "__p")):
                return mapped
            if self.in_function:
                return self._py_ident(name)
            return name

        def _store_numeric(name: str, expr: str) -> str:
            py = _target_py(name)
            if self.in_function:
                # Locals used as TA sources: keep as bar scalar (materialize does the rest)
                return f"{py} = {expr}"
            # UDF shadow → scalar local (never rebind the function / never *_arr under fn name)
            if py != name and py.endswith("__loc"):
                self.object_mode = True
                self.scalar_vars.add(py)
                self.arrays.discard(f"{name}_arr")
                self.arrays.discard(f"{py}_arr")
                return f"{py} = {expr}"
            # Multi-return may include strings (shape names) — object series
            if self._looks_like_string_expr(expr):
                self.object_mode = True
                self.string_series.add(name)
                arr_n = self._series_arr_name(name)
                self.arrays.add(arr_n)
                return f"{arr_n}[__bar_idx] = {expr}"
            # Keep njit-friendly bare stores in numeric mode; object mode uses safe_float
            if self.object_mode:
                return f"{py}_arr[__bar_idx] = safe_float({expr})"
            return f"{py}_arr[__bar_idx] = {expr}"

        def _store_sequence(name: str, expr: str) -> str:
            """Array/list handle → scalar (or UDF local), never float64 series."""
            self.object_mode = True
            py = _target_py(name)
            if self.in_function:
                self.local_vars.add(name)
                self.local_sequence_vars.add(name)
                return f"{py} = {expr}"
            self.scalar_vars.add(py)
            self.arrays.discard(f"{name}_arr")
            self.arrays.discard(f"{py}_arr")
            return f"{py} = {expr}"

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
                # ``ticker.heikinashi(...)`` — rewrite simple OHLCV elts to HA series
                sym_node = pos[0] if pos else None
                use_ha = self._ast_is_heikinashi_ticker(sym_node)
                if use_ha:
                    self._ensure_heikinashi_arrays()
                if isinstance(expr_node, ast.Tuple):
                    lines = []
                    for name, el in zip(names, expr_node.elts, strict=False):
                        if self._ast_expr_is_sequence(el):
                            lines.append(_store_sequence(name, self.visit(el)))
                        else:
                            rhs = self.visit(el)
                            if use_ha:
                                rhs = self._map_ohlcv_expr_to_heikinashi(rhs)
                            lines.append(_store_numeric(name, rhs))
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
                        py = _target_py(name)
                        if not self.in_function:
                            self.scalar_vars.add(py)
                            self.arrays.discard(f"{name}_arr")
                            self.arrays.discard(f"{py}_arr")
                            lines.append(f"{py} = None")
                        else:
                            lines.append(f"{py} = None")
                    return "\n".join(lines)
                if names:
                    name = names[0]
                    py = _target_py(name)
                    if not self.in_function:
                        self.scalar_vars.add(py)
                        self.arrays.discard(f"{name}_arr")
                        self.arrays.discard(f"{py}_arr")
                        return f"{py} = None"
                    return f"{py} = None"
                return ""
            # Multi-return forms emit a temp unpack.
            # IMPORTANT: do NOT match bare "(" alone — nearly every parenthesized
            # numeric expr starts with "(" and would store a sequence into float.
            known_multi = call_code.startswith(
                (
                    "numba_bb(",
                    "numba_bb_inc(",
                    "numba_kc(",
                    "numba_kc_inc(",
                    "numba_macd(",
                    "numba_macd_inc(",
                    "numba_dmi(",
                    "numba_dmi_inc(",
                    "numba_supertrend(",
                    "numba_supertrend_inc(",
                    "numba_stochrsi(",
                    "numba_stochrsi_inc(",
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

    def _looks_like_udt_copy(self, node) -> bool:
        """Type.copy(inst) / inst.copy() — UDT handle, never float series."""
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            return False
        if node.func.attr != "copy":
            return False
        if isinstance(node.func.value, ast.Name):
            return (
                node.func.value.id in self.udt_types
                or node.func.value.id in self.udt_vars
            )
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
                    return f"udt_set_field({obj}, {node.target.attr!r}, {tern})"
                # Multi-stmt if → assign via temp then udt_set_field is hard;
                # fall back to direct dict write only when obj is a plain name.
                target = f"{obj}[{node.target.attr!r}]"
                return self._emit_if_assign(target, node.value)
            val = self.visit(node.value)
            # UDT field write: p.x := 1 (na-safe for nested handles)
            return f"udt_set_field({obj}, {node.target.attr!r}, {val})"
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
                if not hasattr(self, "object_series_locals"):
                    self.object_series_locals = set()
                self.object_series_locals.add(node.target.id)
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
            # UDT reference reassign: pivot2 := pivot1 (share / rebind handle)
            if isinstance(node.value, ast.Name) and node.value.id in self.udt_vars:
                self.object_mode = True
                self.udt_vars.add(name)
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
            # Single-eval of *obj* (may contain walrus binds) then na-safe RMW.
            return (
                f"(lambda __o: udt_set_field(__o, {key!r}, "
                f"((__o.get({key!r}, np.nan) if isinstance(__o, dict) else np.nan) "
                f"{op_s} ({val}))))({obj})"
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
        # User-defined series always win over built-in bare names. Pine allows
        # ``ad = ta.cum(...)`` / ``tr = …``; without this check, visit_Name would
        # re-emit the builtin formula at every load site (plot(ad) silently wrong).
        # Exception: bare v3 ``tickerid`` / ``ticker`` are chart identity stubs
        # (not series) — even if a prior scan allocated ``tickerid_arr``.
        if node.id in ("tickerid", "ticker") and node.id not in self.ident_map:
            self.object_mode = True
            return repr("SYMBOL")
        _arr_name = f"{node.id}_arr"
        if _arr_name in self.arrays:
            return f"{_arr_name}[__bar_idx]"
        # Built-in series / scalars (never allocate bare *_arr unless user-defined)
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
            # Cumulative Chaikin A/D (matches interpret ``_accdist`` / reference ta.accdist).
            st = self._alloc_fixed_state("ad", 2)
            return (
                f"numba_accdist_inc(high_arr, low_arr, close_arr, vol_arr, "
                f"__bar_idx, {st})"
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
            "n_arr" not in self.arrays
            and "n" not in self.local_vars
            and "n" not in self.param_names
            and "n" not in self.scalar_vars
            and "n" not in self.series_params
            and "n" not in self.series_locals
        ):
            return "__bar_idx"
        # Built-in time series / calendar (host ``time_arr``; synthetic when omitted)
        if node.id == "last_bar_index":
            return "(n_bars - 1)"
        if node.id == "last_bar_time":
            return "time_arr[n_bars - 1]"
        if node.id == "time":
            return "time_arr[__bar_idx]"
        if node.id == "time_close":
            # No separate close-time series on compile path — open + 1ms short of bar.
            return "(time_arr[__bar_idx] + 59999.0)"
        if node.id == "timenow":
            return "time_arr[n_bars - 1]"
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
            # Derive from bar open time (parity with interpret LazyCalendarContext).
            _cal_idx = {
                "year": 0,
                "month": 1,
                "dayofmonth": 2,
                "hour": 3,
                "minute": 4,
                "second": 5,
                "dayofweek": 6,
            }
            return f"numba_utc_parts(time_arr[__bar_idx])[{_cal_idx[node.id]}]"
        if node.id in ("true", "True"):
            return "True"
        if node.id in ("false", "False"):
            return "False"
        if node.id in self.udt_types:
            return node.id  # type name for .new
        # User series win over namespace tokens (e.g. `barcolor = …` then barcolor(...))
        if node.id in self.udt_vars or node.id in self.string_series:
            return f"{node.id}_arr[__bar_idx]"
        # Built-in namespaces as bare names — not free scalars.
        # User vars that *shadow* a namespace are handled earlier via scalar_vars /
        # map_vars (and must become free params for module-scope UDFs).
        if node.id in _NS and node.id not in (self.map_vars | self.scalar_vars):
            return node.id
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
        # (``_NS`` pure tokens already returned earlier; user shadows use scalar path)
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
            if node.attr == "accdist" or node.attr == "ad":
                # Cumulative A/D line (not single-bar CLV*vol).
                st = self._alloc_fixed_state("ad", 2)
                return (
                    f"numba_accdist_inc(high_arr, low_arr, close_arr, vol_arr, "
                    f"__bar_idx, {st})"
                )
            if node.attr in ("pvt", "vpt"):
                st = self._alloc_fixed_state("pvt", 2)
                return f"numba_pvt_inc(close_arr, vol_arr, __bar_idx, {st})"
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
        # math.pi / math.e / math.rphi / math.isfinite (bare) — predicates also in Call
        if isinstance(node.value, ast.Name) and node.value.id == "math":
            if node.attr == "pi":
                return "np.pi"
            if node.attr == "e":
                return "np.e"
            if node.attr in ("rphi", "phi"):
                # Golden-ratio conjugate: 2/(1+√5) ≈ 0.6180339887 (matches evaluator)
                return "(2.0 / (1.0 + np.sqrt(5.0)))"
            if node.attr == "isfinite":
                return "np.isfinite"
            if node.attr == "isnan":
                return "np.isnan"
            # leave method attrs for Call (math.abs → math_abs)
            return f"math_{node.attr}"
        # barmerge.lookahead_on / gaps_off — bool constants for request.security
        if isinstance(node.value, ast.Name) and node.value.id == "barmerge":
            if node.attr in ("lookahead_on", "gaps_on"):
                return "True"
            if node.attr in ("lookahead_off", "gaps_off"):
                return "False"
            return "False"
        # label.all / line.all / box.all / table.all / polyline.all → drawing list
        if isinstance(node.value, ast.Name) and node.value.id in (
            "label",
            "line",
            "box",
            "table",
            "polyline",
            "linefill",
        ):
            if node.attr == "all":
                self.object_mode = True
                kind = node.value.id
                return (
                    f"[__d for __d in __drawings if isinstance(__d, dict) "
                    f"and __d.get('kind') == {kind!r}]"
                )
            # bare style-ish attrs already handled via _STYLE_NS; leave rest
        # dayofweek.monday … dayofweek.sunday — integer constants (Reference Pine: Sunday=1 … Saturday=7)
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
            # Boolean chart mode flags (defaults match backend.runtime.Chart)
            if node.attr in (
                "is_heikinashi",
                "is_heikin_ashi",
                "is_renko",
                "is_kagi",
                "is_linebreak",
                "is_line_break",
                "is_pnf",
                "is_pointfigure",
                "is_point_figure",
                "is_range",
            ):
                return "False"
            if node.attr == "is_standard":
                return "True"
            # Viewport times track host/synthetic ``time_arr`` (same as bare ``time``).
            if node.attr == "left_visible_bar_time":
                return "time_arr[0]"
            if node.attr == "right_visible_bar_time":
                return "time_arr[n_bars - 1]"
            # Unknown chart.* → na-ish None, not a truthy qualified string
            return "None"
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

        if func_name == "array_new" or func_name.startswith("array_new_"):
            a = ra(
                args,
                kwargs,
                ("size", "initial_value"),
                aliases={"initial": "initial_value", "value": "initial_value"},
            )
            size = a[0] if a else (kwargs.get("size") or "0")
            # Drawing / table / string element arrays default to None cells, not NaN
            default_fill = (
                "None"
                if any(
                    t in func_name
                    for t in (
                        "line",
                        "label",
                        "box",
                        "table",
                        "string",
                        "color",
                        "polyline",
                    )
                )
                else "np.nan"
            )
            fill = a[1] if len(a) > 1 else default_fill
            # safe_int: size may be na / float NaN (int(nan) raises)
            return (
                f"([{fill}] * max(0, safe_int({size})) "
                f"if safe_int({size}) > 0 else [])"
            )
        if func_name == "array_sort":
            # Mutates in place; return id (Pine void / chain-friendly).
            # Forms: (id), (id, order), (id, order, sort_field), sort_field= kw.
            a = ra(args, kwargs, ("id", "order", "sort_field"))
            if not a:
                return "[]"
            arr = a[0]
            order = a[1] if len(a) > 1 else None
            sort_field = a[2] if len(a) > 2 else kwargs.get("sort_field")
            # Prefer helper (na-last + UDT/dict field key) over inline lambda
            if sort_field is not None and order is not None:
                return f"array_sort({arr}, {order}, {sort_field})"
            if sort_field is not None:
                return f"array_sort({arr}, 'ascending', {sort_field})"
            if order is not None:
                return f"array_sort({arr}, {order})"
            return f"array_sort({arr})"
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
            # safe_list_append: no-op when id is float/None (misclassified series)
            if len(a) > 1:
                return f"safe_list_append({a[0]}, {a[1]})"
            if a:
                return f"safe_list_append({a[0]}, np.nan)"
            return ""
        if func_name == "array_pop":
            a = ra(args, kwargs, ("id",))
            return f"safe_list_pop({a[0]})" if a else "np.nan"
        if func_name == "array_shift":
            a = ra(args, kwargs, ("id",))
            return f"safe_list_pop({a[0]}, 0)" if a else "np.nan"
        if func_name == "array_unshift":
            a = ra(args, kwargs, ("id", "value"))
            if len(a) > 1:
                return f"safe_list_insert({a[0]}, 0, {a[1]})"
            if a:
                return f"safe_list_insert({a[0]}, 0, np.nan)"
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
            # Use safe_list_set (grow/no-op) so OOB indices soft-fail like interpret.
            a = ra(
                args,
                kwargs,
                ("id", "index", "value", "column"),
                aliases={"col": "column", "row": "index"},
            )
            if len(args) >= 4:
                return (
                    f"{args[0]}[int({args[1]})].__setitem__(int({args[2]}), {args[3]})"
                )
            if len(args) >= 3:
                return f"safe_list_set({args[0]}, {args[1]}, {args[2]})"
            if len(a) >= 3:
                return f"safe_list_set({a[0]}, {a[1]}, {a[2]})"
            return ""
        if func_name == "array_size":
            a = ra(args, kwargs, ("id",))
            # safe_len: scalars (misclassified array handles) → 0, not TypeError
            return f"safe_len({a[0]})" if a else "0"
        if func_name == "array_range":
            # Pine array.range(id) = max - min; not Python range()
            a = ra(args, kwargs, ("id",))
            if a:
                return f"array_range({a[0]})"
            if args:
                return f"array_range({args[0]})"
            return "np.nan"
        if func_name == "array_clear":
            a = ra(args, kwargs, ("id",))
            return f"safe_list_clear({a[0]})" if a else ""
        if func_name == "array_remove":
            a = ra(args, kwargs, ("id", "index"))
            if len(a) > 1:
                return f"safe_list_pop({a[0]}, int(safe_int({a[1]})))"
            if a:
                return f"safe_list_pop({a[0]})"
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
            a = ra(args, kwargs, ("id", "order", "sort_field"))
            if not a:
                return "[]"
            sort_field = a[2] if len(a) > 2 else kwargs.get("sort_field")
            if sort_field is not None and len(a) > 1:
                return f"array_sort_indices({a[0]}, {a[1]}, {sort_field})"
            if sort_field is not None:
                return f"array_sort_indices({a[0]}, 'ascending', {sort_field})"
            if len(a) > 1:
                return f"array_sort_indices({a[0]}, {a[1]})"
            return f"array_sort_indices({a[0]})"
        if func_name == "array_fill":
            a = ra(args, kwargs, ("id", "value", "index_from", "index_to"))
            if not a:
                return ""
            val = a[1] if len(a) > 1 else "np.nan"
            if len(a) >= 4:
                return f"array_fill({a[0]}, {val}, {a[2]}, {a[3]})"
            if len(a) == 3:
                return f"array_fill({a[0]}, {val}, {a[2]})"
            # Dual: matrix (list-of-lists) fills each cell; flat array fills slots
            return f"array_fill({a[0]}, {val})"
        if func_name == "array_mode":
            a = ra(args, kwargs, ("id",))
            return f"array_mode({a[0]})" if a else "np.nan"
        if func_name == "array_standardize":
            a = ra(args, kwargs, ("id",))
            return f"array_standardize({a[0]})" if a else "[]"
        if func_name == "array_normalized":
            a = ra(args, kwargs, ("id",))
            return f"array_normalized({a[0]})" if a else "[]"
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
        if func_name in (
            "array_binary_search",
            "array_binary_search_leftmost",
            "array_binary_search_rightmost",
        ):
            # Forms: (id, value), (id, value, sort_field), sort_field= kw.
            a = ra(args, kwargs, ("id", "value", "sort_field"))
            if len(a) >= 3:
                return f"{func_name}({a[0]}, {a[1]}, {a[2]})"
            if len(a) >= 2:
                return f"{func_name}({a[0]}, {a[1]})"
            return "-1"
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
                return f"safe_list_insert({a[0]}, {a[1]}, {a[2]})"
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
            # open_entry_count tracks open_legs (pyramiding-aware); 0 when flat.
            "opentrades": "__strategy.open_entry_count",
            "initial_capital": "__strategy.initial_capital",
            "leverage": "__strategy.leverage",
            "max_drawdown": "__strategy.max_drawdown",
            "max_runup": "__strategy.max_runup",
            "max_drawdown_percent": "__strategy.max_drawdown_percent",
            "max_runup_percent": "__strategy.max_runup_percent",
            "openprofit": "__strategy.openprofit",
            "grossprofit": "__strategy.grossprofit",
            "grossloss": "__strategy.grossloss",
            "wintrades": "__strategy.wintrades",
            "losstrades": "__strategy.losstrades",
            "margin_liquidation_price": "__strategy.margin_liquidation_price",
        }
        if attr in series_map:
            self.object_mode = True
            self.uses_strategy = True
            # Always allocate end-of-bar history buffers (used by [n] subscripts).
            self.arrays.add("__strategy_position_size_arr")
            self.arrays.add("__strategy_position_avg_price_arr")
            self.arrays.add("__strategy_closed_trades_arr")
            return series_map[attr]
        # Qty type / risk / avg-price constants used as values (not broker properties)
        if attr in (
            "percent_of_equity",
            "fixed",
            "cash",
            "cash_per_order",
            "cash_per_contract",
            "long",
            "short",
            "all",
            "avg_price_stock",
            "avg_price_futures",
            "avg_price_inverse",
        ):
            self.object_mode = True
            self.uses_strategy = True
            # Strip avg_price_ prefix so strategy.avg_price_futures → "futures"
            if attr.startswith("avg_price_"):
                return repr(attr[len("avg_price_") :])
            return repr(attr)
        # oca / commission nested attrs: strategy.oca → leave for outer attr
        if attr in ("oca", "commission", "direction", "risk", "avg_price"):
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
        """Lower Pine calls: ta/math/array/matrix/map/strategy/drawing/UDFs.

        Large dispatch: namespace attrs, method-style TA, bare collection verbs,
        strategy/drawing (force object mode), and :meth:`_emit_user_func_call`.
        Unknown external methods stub to ``None`` in object mode.
        """
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
                # strategy.risk.* → strategy_risk_* (emit subset on CompileStrategyBroker)
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
                # BUT: ``import reference Pine/ta/7`` (alias ``ta``) / math / str / …
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
            elif (
                isinstance(func.value, ast.Name)
                and func.value.id in self.udt_types
                and func.attr == "copy"
            ):
                # Type.copy(instance) → shallow dict copy (not array_copy → list(Type))
                self.object_mode = True
                inst = "None"
                for arg in node.args:
                    if hasattr(arg, "value"):
                        if getattr(arg, "name", None) in (None, "id", "this", "source"):
                            inst = self.visit(arg.value)
                            break
                        if getattr(arg, "name", None):
                            continue
                    else:
                        inst = self.visit(arg)
                        break
                else:
                    if node.args:
                        raw0 = node.args[0]
                        inst = self.visit(raw0.value if hasattr(raw0, "value") else raw0)
                return (
                    f"(dict({inst}) if isinstance({inst}, dict) else "
                    f"(dict({inst}) if {inst} is not None else {{}}))"
                )
            elif (
                isinstance(func.value, ast.Name)
                and func.value.id in self.udt_vars
                and func.attr == "copy"
            ):
                # instance.copy() method form on UDT series/scalar
                self.object_mode = True
                method_src = self.visit(func.value)
                return (
                    f"(dict({method_src}) if isinstance({method_src}, dict) else {{}})"
                )
            elif isinstance(func.value, ast.Name) and func.value.id in _NS:
                func_name = f"{func.value.id}_{func.attr}"
            elif func.attr in _METHOD_TA:
                # Method-style TA: ``(expr).rma(p)`` → ta.rma(expr, p)
                method_src = self.visit(func.value)
                if func.attr in ("fixnan", "nz"):
                    func_name = func.attr
                else:
                    func_name = f"ta_{func.attr}"
            elif func.attr in self.user_funcs and self._udf_formal_count(func.attr) >= 1:
                # User method: ``x.mg(6)`` / ``Close.linreg(8).mg(6)`` → mg(src, 6)
                # Only when the UDF has ≥1 formal so the receiver can bind as
                # the first arg. Zero-arg free funcs (e.g. ``update()``) must
                # not steal ``obj.update()`` library/UDT methods.
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
        # chart.point.from_index / from_time / new / now / copy
        _chart_point_ctor = func_name in (
            "from_index",
            "chart_point_from_index",
            "point_from_index",
            "from_time",
            "chart_point_from_time",
            "point_from_time",
            "chart_point_new",
            "point_new",
            "chart_point_now",
            "point_now",
            "chart_point_copy",
            "point_copy",
        )
        # Bare ``.new`` / ``.now`` / ``.copy`` only when receiver is chart.point
        if not _chart_point_ctor and func_name in ("new", "now", "copy"):
            recv = getattr(node.func, "value", None)
            if (
                isinstance(recv, ast.Attribute)
                and recv.attr == "point"
                and isinstance(recv.value, ast.Name)
                and recv.value.id == "chart"
            ):
                _chart_point_ctor = True
            elif isinstance(func, ast.Attribute) and isinstance(func.value, ast.Attribute):
                if (
                    func.value.attr == "point"
                    and isinstance(func.value.value, ast.Name)
                    and func.value.value.id == "chart"
                ):
                    _chart_point_ctor = True
        if _chart_point_ctor:
            self.object_mode = True
            # Pine chart.point fields: time/index/price (+ x/y aliases for line stubs)
            # method_src was prepended for method form — strip for namespace ctors
            ctor_args = args
            if method_src is not None and len(ctor_args) >= 1:
                # chart.point.X(...) is Attribute call; method_src is "chart.point"
                # expression junk — drop leading receiver when it is not a point copy src
                if func_name in ("copy", "chart_point_copy", "point_copy"):
                    pass  # keep point arg
                elif method_src is not None:
                    # Namespace form wrongly got method_src; drop if first arg looks like ns
                    # (we rebuild from node.args below via ctor_args already including method_src)
                    ctor_args = args[1:] if args else args
            # Re-resolve from raw node.args to avoid method_src pollution
            ctor_args = []
            for arg in node.args:
                if hasattr(arg, "value"):
                    ctor_args.append(self.visit(arg.value))
                else:
                    ctor_args.append(self.visit(arg))
            attr = func.attr if isinstance(func, ast.Attribute) else func_name
            if attr in ("from_time",) or func_name in (
                "from_time",
                "chart_point_from_time",
                "point_from_time",
            ):
                t = ctor_args[0] if len(ctor_args) >= 1 else "np.nan"
                p = ctor_args[1] if len(ctor_args) >= 2 else "np.nan"
                return (
                    f"{{'x': {t}, 'y': {p}, 'time': {t}, "
                    f"'index': np.nan, 'price': {p}}}"
                )
            if attr in ("now",) or func_name in (
                "now",
                "chart_point_now",
                "point_now",
            ):
                p = ctor_args[0] if ctor_args else "np.nan"
                return (
                    f"{{'x': __bar_idx, 'y': {p}, 'time': (float(__bar_idx) * 60000.0), "
                    f"'index': __bar_idx, 'price': {p}}}"
                )
            if attr in ("copy",) or func_name in (
                "copy",
                "chart_point_copy",
                "point_copy",
            ):
                src_p = ctor_args[0] if ctor_args else "None"
                return (
                    f"(dict({src_p}) if isinstance({src_p}, dict) else "
                    f"{{'x': np.nan, 'y': np.nan, 'index': np.nan, 'price': np.nan}})"
                )
            # from_index / new(time, price) — time-or-index + price
            if len(ctor_args) >= 2:
                a0, a1 = ctor_args[0], ctor_args[1]
                if attr in ("new",) or func_name in ("chart_point_new", "point_new"):
                    return (
                        f"{{'x': {a0}, 'y': {a1}, 'time': {a0}, "
                        f"'index': np.nan, 'price': {a1}}}"
                    )
                return (
                    f"{{'x': {a0}, 'y': {a1}, "
                    f"'index': {a0}, 'price': {a1}}}"
                )
            if len(ctor_args) >= 1:
                return (
                    f"{{'x': {ctor_args[0]}, 'y': np.nan, "
                    f"'index': {ctor_args[0]}, 'price': np.nan}}"
                )
            return "{'x': __bar_idx, 'y': np.nan, 'index': __bar_idx, 'price': np.nan}"
        if func_name in ("modify", "ticker_modify"):
            self.object_mode = True
            return args[0] if args else repr("SYMBOL")
        # ticker.heikinashi — chart HA transform (not a foreign symbol)
        if func_name in ("ticker_heikinashi", "heikinashi"):
            self._ensure_heikinashi_arrays()
            return repr("__HEIKINASHI__")
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

        # hline → constant numeric series (interpret parity) + __drawings event.
        # Titles uniquified like Runtime interpret packaging (hline, hline_2, …).
        if func_name == "hline":
            self.object_mode = True
            price_expr = args[0] if args else "np.nan"
            title = "hline"
            if "title" in kwargs:
                title = self._literal_str(kwargs["title"], default="hline") or "hline"
            elif len(args) > 1 and args[1]:
                title = self._literal_str(args[1], default="hline") or "hline"
            title = self._unique_plot_title(title)
            store_expr = (
                price_expr
                if price_expr.startswith("safe_float(")
                else f"safe_float({price_expr})"
            )
            self.plots.append({"expr": price_expr, "title": title, "kind": "hline"})
            idx = len(self.plots) - 1
            # Stamp uniquified title onto the drawing event for consistent keys.
            draw_kwargs = dict(kwargs)
            draw_kwargs["title"] = repr(title)
            drawing = self._emit_drawing(func_name, args, draw_kwargs)
            return f"(plot_{idx}.__setitem__(__bar_idx, {store_expr}) or {drawing})"

        # fill(plot1, plot2, color=…, title=…) → series key (interpret parity) +
        # __drawings event. Interpret stores a null color column (JSON nulls) and
        # puts band color/plot refs in plot_meta; compile leaves the series as na
        # (float64 nan → null) so AXIS / compare_interp_compile key sets match.
        if func_name == "fill":
            self.object_mode = True
            title = "fill"
            if "title" in kwargs:
                title = self._literal_str(kwargs["title"], default="fill") or "fill"
            elif len(args) > 3 and args[3]:
                title = self._literal_str(args[3], default="fill") or "fill"
            title = self._unique_plot_title(title)
            self.plots.append({"expr": "None", "title": title, "kind": "fill"})
            draw_kwargs = dict(kwargs)
            draw_kwargs["title"] = repr(title)
            return self._emit_drawing(func_name, args, draw_kwargs)

        if func_name == "plot":
            # Match Runtime interpret packaging: untitled plots use plot_0, plot_1, …
            title = f"plot_{len(self.plots)}"
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
            # time(timeframe) / time() — chart open when no session args
            return "time_arr[__bar_idx]"
        if func_name in ("time_close",):
            return "(time_arr[__bar_idx] + 59999.0)"
        if func_name == "timeframe_from_seconds":
            return repr("1D")
        if func_name == "timeframe_change":
            return "False"
        if func_name == "timestamp":
            # Real UTC ms from components (or string → na on compile path).
            # Year-first: timestamp(y, m, d[, h, mi, s]); timezone-first skipped.
            if len(args) >= 3:
                # Leading timezone string form: timestamp("GMT", y, m, d, …)
                # Detect stringy first arg → drop it (UTC stub).
                a = list(args)
                a0 = a[0].strip() if a else ""
                if (
                    len(a) >= 4
                    and len(a0) >= 2
                    and (
                        (a0[0] == a0[-1] == "'")
                        or (a0[0] == a0[-1] == '"')
                        or "timezone" in a0
                        or a0.startswith("str(")
                    )
                ):
                    a = a[1:]
                if len(a) >= 3:
                    y, m, d = a[0], a[1], a[2]
                    h = a[3] if len(a) > 3 else "0.0"
                    mi = a[4] if len(a) > 4 else "0.0"
                    s = a[5] if len(a) > 5 else "0.0"
                    return f"numba_timestamp({y}, {m}, {d}, {h}, {mi}, {s})"
            if len(args) == 1:
                # Single numeric ms passthrough; strings → na
                return f"safe_float({args[0]})"
            return "np.nan"

        if func_name in ("alertcondition", "alert"):
            return ""

        # UDF calls win over bare TA aliases (sma, …) and bare math (max/min/abs)
        if func_name in self.user_funcs:
            # Method form ``obj.f()`` on a zero-arg free UDF is not Pine method
            # syntax — treat as unknown library/UDT method (no-op stub).
            if method_src is not None and self._udf_formal_count(func_name) == 0:
                self.object_mode = True
                return "None"
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

        # bare v3 security(...) / request.security — same-symbol OHLCV only.
        # Complex expressions (UDFs, ta.*, year_sum, …) would invent chart series
        # as foreign-symbol data (e.g. dividend_yield close-as-dividend). Emit na.
        # Foreign tickers with simple ``close`` (CVI UPVOL/DNVOL) also invent
        # chart-close as advance/decline volume — require chart-symbol identity.
        if func_name in (
            "security",
            "request_security",
            "request_security_lower_tf",
            "request_seed",
        ):
            sym = args[0] if args else ""
            expr = args[2] if len(args) >= 3 else "close_arr[__bar_idx]"
            if self._is_heikinashi_security_symbol(sym) and self._is_simple_security_expr(expr):
                self._ensure_heikinashi_arrays()
                return self._map_ohlcv_expr_to_heikinashi(expr)
            if self._is_chart_security_symbol(sym) and self._is_simple_security_expr(expr):
                return expr
            return "np.nan"

        # Other request.* APIs — numeric NaN stub (no invent; interpret uses mocks)
        if func_name.startswith("request_"):
            self.object_mode = True
            return "np.nan"

        # Calendar / time extractors (optional time argument; else bar open)
        _cal_fn = {
            "year": 0,
            "month": 1,
            "dayofmonth": 2,
            "hour": 3,
            "minute": 4,
            "second": 5,
            "dayofweek": 6,
        }
        if func_name in _cal_fn:
            src = args[0] if args else "time_arr[__bar_idx]"
            return f"numba_utc_parts({src})[{_cal_fn[func_name]}]"
        if func_name == "dayofyear":
            # Weak: day-of-month only when no full DOY helper (rare on compile path)
            src = args[0] if args else "time_arr[__bar_idx]"
            return f"numba_utc_parts({src})[2]"

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
            "adx": "ta_adx",
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
            "rci": "ta_rci",
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
            "bbw": "ta_bbw",
            "kc": "ta_kc",
            "median": "ta_median",
            "wpr": "ta_wpr",
            "cmo": "ta_cmo",
            "dema": "ta_dema",
            "tema": "ta_tema",
            "swma": "ta_swma",
            "kama": "ta_kama",
            "cmf": "ta_cmf",
            "stochrsi": "ta_stochrsi",
            "willr": "ta_wpr",
            "accdist": "ta_accdist",
            "pvt": "ta_pvt",
            "vpt": "ta_pvt",
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
            # ta.dmi(diLength, adxSmoothing) → (+DI, -DI, ADX); legacy 4-arg OHLC
            st = self._alloc_fixed_state("dmi", 40)
            if len(args) >= 4 and _is_series_arr(args[0]):
                di_len = self._emit_period(args[3])
                return (
                    f"numba_dmi_inc({_arr(args[0])}, {_arr(args[1])}, {_arr(args[2])}, "
                    f"{di_len}, {di_len}, __bar_idx, {st})"
                )
            if len(args) >= 2:
                di_len = kwargs.get("diLength", args[0])
                adx_s = kwargs.get("adxSmoothing", args[1])
                return (
                    f"numba_dmi_inc(high_arr, low_arr, close_arr, "
                    f"{self._emit_period(di_len)}, {self._emit_period(adx_s)}, __bar_idx, {st})"
                )
            if len(args) == 1:
                di_len = self._emit_period(args[0])
                return (
                    f"numba_dmi_inc(high_arr, low_arr, close_arr, "
                    f"{di_len}, {di_len}, __bar_idx, {st})"
                )
            return (
                f"numba_dmi_inc(high_arr, low_arr, close_arr, 14, 14, __bar_idx, {st})"
            )
        if func_name == "ta_adx":
            # ta.adx(length) / ta.adx(diLength, adxSmoothing) / legacy 4-arg
            st = self._alloc_fixed_state("adx", 22)
            if len(args) >= 4 and _is_series_arr(args[0]):
                return (
                    f"numba_adx_inc({_arr(args[0])}, {_arr(args[1])}, {_arr(args[2])}, "
                    f"int({args[3]}), __bar_idx, {st})"
                )
            if len(args) >= 2 and not _is_series_arr(args[0]):
                # diLength, adxSmoothing — ADX period is adxSmoothing (interpret)
                adx_len = kwargs.get("adxSmoothing", args[1])
                return (
                    f"numba_adx_inc(high_arr, low_arr, close_arr, "
                    f"{self._emit_period(adx_len)}, __bar_idx, {st})"
                )
            if len(args) == 1:
                return (
                    f"numba_adx_inc(high_arr, low_arr, close_arr, "
                    f"{self._emit_period(args[0])}, __bar_idx, {st})"
                )
            length = kwargs.get("length", "14")
            return (
                f"numba_adx_inc(high_arr, low_arr, close_arr, "
                f"{self._emit_period(length)}, __bar_idx, {st})"
            )
        if func_name == "ta_supertrend":
            # ta.supertrend(factor, atrPeriod) → (value, direction); simplified oracle
            st = self._alloc_fixed_state("st", 2)
            if len(args) >= 4 and _is_series_arr(args[0]):
                # legacy (high, low, length, multiplier)
                factor = args[3]
                atr_p = args[2]
                return (
                    f"numba_supertrend_inc({_arr(args[0])}, {_arr(args[1])}, close_arr, "
                    f"float({factor}), {self._emit_period(atr_p)}, __bar_idx, {st})"
                )
            if len(args) >= 2:
                factor = kwargs.get("factor", args[0])
                atr_p = kwargs.get("atrPeriod", args[1])
                return (
                    f"numba_supertrend_inc(high_arr, low_arr, close_arr, "
                    f"float({factor}), {self._emit_period(atr_p)}, __bar_idx, {st})"
                )
            return (
                f"numba_supertrend_inc(high_arr, low_arr, close_arr, "
                f"3.0, 10, __bar_idx, {st})"
            )
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
        if func_name == "ta_kc":
            # ta.kc(source, length, mult) → (middle, upper, lower); ATR from chart H/L/C
            # Legacy: ta.kc(high, low, close, length) mult defaults to 1
            st = self._alloc_fixed_state("kc", 4)
            if len(args) >= 4 and _is_series_arr(args[0]) and _is_series_arr(args[1]):
                length = kwargs.get("length", args[3] if len(args) > 3 else "20")
                mult = kwargs.get("mult", args[4] if len(args) > 4 else "1.0")
                return (
                    f"numba_kc_inc({_arr(args[2])}, {_arr(args[0])}, {_arr(args[1])}, "
                    f"{_arr(args[2])}, {self._emit_period(length)}, float({mult}), __bar_idx, {st})"
                )
            if len(args) >= 3:
                src, length, mult = args[0], args[1], args[2]
            elif len(args) == 2:
                src, length, mult = "close_arr[__bar_idx]", args[0], args[1]
            else:
                src, length, mult = "close_arr[__bar_idx]", "20", "1.0"
            return (
                f"numba_kc_inc({_arr(src)}, high_arr, low_arr, close_arr, "
                f"{self._emit_period(length)}, float({mult}), __bar_idx, {st})"
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
        if func_name == "ta_bbw":
            # ta.bbw(source, length, mult) or ta.bbw(length, mult) → (upper-lower)/mid
            if len(args) >= 3:
                src, length, mult = args[0], args[1], args[2]
            elif len(args) == 2:
                src, length, mult = "close_arr[__bar_idx]", args[0], args[1]
            else:
                src, length, mult = "close_arr[__bar_idx]", "20", "2.0"
            st = self._alloc_fixed_state("bbw", 3)
            return (
                f"numba_bbw_inc({_arr(src)}, {self._emit_period(length)}, float({mult}), "
                f"__bar_idx, {st})"
            )
        if func_name == "ta_median":
            # ta.median(source, length) or ta.median(length) on close
            if len(args) >= 2:
                return (
                    f"numba_median({_arr(args[0])}, {self._emit_period(args[1])}, __bar_idx)"
                )
            if args and not _is_series_arr(args[0]):
                return f"numba_median(close_arr, {self._emit_period(args[0])}, __bar_idx)"
            if args:
                return f"numba_median({_arr(args[0])}, 14, __bar_idx)"
            return "np.nan"
        if func_name in ("ta_wpr", "ta_willr"):
            # ta.wpr / ta.willr(length) | ta.wpr(high, low, close, length)
            if len(args) >= 4 and _is_series_arr(args[0]):
                return (
                    f"numba_wpr({_arr(args[0])}, {_arr(args[1])}, {_arr(args[2])}, "
                    f"int({args[3]}), __bar_idx)"
                )
            length = args[0] if args else "14"
            return f"numba_wpr(high_arr, low_arr, close_arr, {self._emit_period(length)}, __bar_idx)"
        if func_name == "ta_cmo":
            # ta.cmo(source, length) or ta.cmo(length) on close
            if len(args) >= 2:
                return (
                    f"numba_cmo({_arr(args[0])}, {self._emit_period(args[1])}, __bar_idx)"
                )
            if args and not _is_series_arr(args[0]):
                return f"numba_cmo(close_arr, {self._emit_period(args[0])}, __bar_idx)"
            if args:
                return f"numba_cmo({_arr(args[0])}, 14, __bar_idx)"
            return "np.nan"
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
                or b in (
                    "open_arr",
                    "high_arr",
                    "low_arr",
                    "close_arr",
                    "vol_arr",
                    "time_arr",
                )
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
            # Const length → weight-precompute alma_inc; else full numba_alma.
            if not args:
                return "np.nan"
            src = args[0]
            length = args[1] if len(args) > 1 else "9"
            offset = args[2] if len(args) > 2 else "0.85"
            sigma = args[3] if len(args) > 3 else "6.0"
            length_c = self._try_nonneg_int_const(str(length).strip())
            if length_c is not None and length_c > 0:
                st = self._alloc_fixed_state("alma", 2 + length_c)
                return (
                    f"numba_alma_inc({_arr(src)}, {length_c}, float({offset}), "
                    f"float({sigma}), __bar_idx, {st})"
                )
            return (
                f"numba_alma({_arr(src)}, {self._emit_period(length)}, float({offset}), "
                f"float({sigma}), __bar_idx)"
            )
        if func_name == "ta_hma":
            # ta.hma(source, length) — multi-stage incremental WMA + raw series
            if not args:
                return "np.nan"
            st = self._alloc_fixed_state("hma", 7)
            raw = f"__hma_raw{self._ta_state_i}_arr"
            self._ta_state_i += 1
            self.arrays.add(raw)
            if len(args) >= 2:
                return (
                    f"numba_hma_inc({_arr(args[0])}, int({args[1]}), __bar_idx, {st}, {raw})"
                )
            if not _is_series_arr(args[0]):
                return f"numba_hma_inc(close_arr, int({args[0]}), __bar_idx, {st}, {raw})"
            return f"numba_hma_inc({_arr(args[0])}, 9, __bar_idx, {st}, {raw})"
        if func_name == "ta_dema":
            # ta.dema(source, length) — nested EMA + e1 intermediate series
            if not args:
                return "np.nan"
            st = self._alloc_fixed_state("dema", 3)
            e1 = f"__dema_e1{self._ta_state_i}_arr"
            self._ta_state_i += 1
            self.arrays.add(e1)
            if len(args) >= 2:
                return (
                    f"numba_dema_inc({_arr(args[0])}, int({args[1]}), __bar_idx, {st}, {e1})"
                )
            if not _is_series_arr(args[0]):
                return f"numba_dema_inc(close_arr, int({args[0]}), __bar_idx, {st}, {e1})"
            return f"numba_dema_inc({_arr(args[0])}, 9, __bar_idx, {st}, {e1})"
        if func_name == "ta_tema":
            # ta.tema(source, length) — triple nested EMA + two intermediate series
            if not args:
                return "np.nan"
            st = self._alloc_fixed_state("tema", 4)
            sid = self._ta_state_i
            self._ta_state_i += 1
            e1 = f"__tema_e1{sid}_arr"
            e2 = f"__tema_e2{sid}_arr"
            self.arrays.add(e1)
            self.arrays.add(e2)
            if len(args) >= 2:
                return (
                    f"numba_tema_inc({_arr(args[0])}, int({args[1]}), __bar_idx, {st}, "
                    f"{e1}, {e2})"
                )
            if not _is_series_arr(args[0]):
                return (
                    f"numba_tema_inc(close_arr, int({args[0]}), __bar_idx, {st}, {e1}, {e2})"
                )
            return f"numba_tema_inc({_arr(args[0])}, 9, __bar_idx, {st}, {e1}, {e2})"
        if func_name == "ta_swma":
            # ta.swma(source) — fixed 4-period symmetric weights (O(1) full formula)
            if not args:
                return "np.nan"
            if _is_series_arr(args[0]) or args[0].endswith("_arr") or "[" in args[0]:
                return f"numba_swma({_arr(args[0])}, __bar_idx)"
            return "numba_swma(close_arr, __bar_idx)"
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
                occ_c = self._try_nonneg_int_const(occ)
                if occ_c is not None:
                    # Packed ring: [n_found, head, last_i, hist_0..hist_occ]
                    st = self._alloc_fixed_state("vw", 3 + occ_c + 1)
                    return (
                        f"numba_valuewhen_inc({_arr(args[0])}, {_arr(args[1])}, "
                        f"int({occ}), __bar_idx, {st})"
                    )
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
            # ta.vwap([source[, anchor]]) — cumulative source*vol / cum vol.
            # Default source is hlc3 (not close). Optional anchor bool resets
            # the cumulative window when true (reference ``ta.vwap(src, anchor)``).
            st = self._alloc_fixed_state("vwap", 3)
            if args:
                src = _arr(args[0])
            else:
                src = _arr(
                    "((high_arr[__bar_idx] + low_arr[__bar_idx] + "
                    "close_arr[__bar_idx]) / 3.0)"
                )
            if len(args) >= 2:
                # Materialize anchor as 1.0/0.0 series for incremental reset.
                anc = _arr(f"(1.0 if ({args[1]}) else 0.0)")
                return (
                    f"numba_vwap_anchor_inc({src}, vol_arr, {anc}, "
                    f"__bar_idx, {st})"
                )
            return f"numba_vwap_inc({src}, vol_arr, __bar_idx, {st})"
        if func_name == "ta_max":
            # ta.max(source) → all-time high of series; ta.max(source, length) → highest
            if not args:
                return "np.nan"
            if len(args) >= 2:
                period = kwargs.get("length", args[1])
                st = self._alloc_fixed_state("hh", 3)
                return f"numba_highest_inc({_arr(args[0])}, {self._emit_period(period)}, __bar_idx, {st})"
            # Running max from bar 0..i — O(1) incremental (was O(i) full scan)
            st = self._alloc_fixed_state("rmax", 2)
            return f"numba_running_max_inc({_arr(args[0])}, __bar_idx, {st})"
        if func_name == "ta_min":
            # ta.min(source) → all-time low; ta.min(source, length) → lowest
            if not args:
                return "np.nan"
            if len(args) >= 2:
                period = kwargs.get("length", args[1])
                st = self._alloc_fixed_state("ll", 3)
                return f"numba_lowest_inc({_arr(args[0])}, {self._emit_period(period)}, __bar_idx, {st})"
            st = self._alloc_fixed_state("rmin", 2)
            return f"numba_running_min_inc({_arr(args[0])}, __bar_idx, {st})"
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
        if func_name == "ta_rci":
            # ta.rci(source, length) — Spearman rank correlation (no fixed state)
            if len(args) >= 2 and _is_series_arr(args[0]):
                return (
                    f"numba_rci({_arr(args[0])}, {self._emit_period(args[1])}, __bar_idx)"
                )
            if len(args) >= 2:
                return (
                    f"numba_rci({_arr(args[0])}, {self._emit_period(args[1])}, __bar_idx)"
                )
            length = args[0] if args else "10"
            return f"numba_rci(close_arr, {self._emit_period(length)}, __bar_idx)"
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
            st = self._alloc_fixed_state("rise", 2)
            if len(args) >= 2:
                return f"numba_rising_inc({_arr(args[0])}, int({args[1]}), __bar_idx, {st})"
            if args and not _is_series_arr(args[0]):
                return f"numba_rising_inc(close_arr, int({args[0]}), __bar_idx, {st})"
            if args:
                return f"numba_rising_inc({_arr(args[0])}, 1, __bar_idx, {st})"
            return f"numba_rising_inc(close_arr, 1, __bar_idx, {st})"
        if func_name == "ta_falling":
            st = self._alloc_fixed_state("fall", 2)
            if len(args) >= 2:
                return f"numba_falling_inc({_arr(args[0])}, int({args[1]}), __bar_idx, {st})"
            if args and not _is_series_arr(args[0]):
                return f"numba_falling_inc(close_arr, int({args[0]}), __bar_idx, {st})"
            if args:
                return f"numba_falling_inc({_arr(args[0])}, 1, __bar_idx, {st})"
            return f"numba_falling_inc(close_arr, 1, __bar_idx, {st})"
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
        if func_name == "ta_kama":
            # ta.kama(source, length[, fast=2, slow=30])
            if not args:
                return "np.nan"
            src = args[0]
            if len(args) == 1 and not _is_series_arr(args[0]):
                src = "close_arr[__bar_idx]"
                length = args[0]
                fast, slow = "2", "30"
            else:
                length = args[1] if len(args) > 1 else "10"
                fast = kwargs.get("fastLength", args[2] if len(args) > 2 else "2")
                slow = kwargs.get("slowLength", args[3] if len(args) > 3 else "30")
            st = self._alloc_fixed_state("kama", 3)
            return (
                f"numba_kama_inc({_arr(src)}, {self._emit_period(length)}, "
                f"int({fast}), int({slow}), __bar_idx, {st})"
            )
        if func_name == "ta_cmf":
            # ta.cmf(period) | ta.cmf(close, high, low, volume, period)
            st = self._alloc_fixed_state("cmf", 3)
            if len(args) >= 5 and _is_series_arr(args[0]):
                return (
                    f"numba_cmf_inc({_arr(args[1])}, {_arr(args[2])}, {_arr(args[0])}, "
                    f"{_arr(args[3])}, {self._emit_period(args[4])}, __bar_idx, {st})"
                )
            period = args[0] if args else "20"
            return (
                f"numba_cmf_inc(high_arr, low_arr, close_arr, vol_arr, "
                f"{self._emit_period(period)}, __bar_idx, {st})"
            )
        if func_name == "ta_stochrsi":
            # ta.stochrsi(rsiLength, stochLength) on close → (stochrsi, signal)
            if len(args) >= 3 and _is_series_arr(args[0]):
                src = _arr(args[0])
                rsi_len = args[1]
                stoch_len = args[2]
            elif len(args) >= 2:
                src = "close_arr"
                rsi_len = kwargs.get("rsi_length", args[0])
                stoch_len = kwargs.get("stoch_length", args[1])
            elif len(args) == 1:
                src = "close_arr"
                rsi_len = args[0]
                stoch_len = args[0]
            else:
                src = "close_arr"
                rsi_len, stoch_len = "14", "14"
            stoch_c = self._try_nonneg_int_const(str(stoch_len).strip())
            if stoch_c is not None and stoch_c > 0:
                st = self._alloc_fixed_state("srsi", 3 + stoch_c)
                return (
                    f"numba_stochrsi_inc({src if src.endswith('_arr') else _arr(src)}, "
                    f"{self._emit_period(rsi_len)}, {stoch_c}, __bar_idx, {st})"
                )
            return (
                f"numba_stochrsi({src if src.endswith('_arr') else _arr(src)}, "
                f"{self._emit_period(rsi_len)}, {self._emit_period(stoch_len)}, "
                f"__bar_idx)"
            )
        if func_name in ("ta_accdist", "ta_ad"):
            st = self._alloc_fixed_state("ad", 2)
            if len(args) >= 4 and _is_series_arr(args[0]):
                return (
                    f"numba_accdist_inc({_arr(args[0])}, {_arr(args[1])}, "
                    f"{_arr(args[2])}, {_arr(args[3])}, __bar_idx, {st})"
                )
            return (
                f"numba_accdist_inc(high_arr, low_arr, close_arr, vol_arr, "
                f"__bar_idx, {st})"
            )
        if func_name in ("ta_pvt", "ta_vpt"):
            st = self._alloc_fixed_state("pvt", 2)
            if len(args) >= 2 and _is_series_arr(args[0]):
                return f"numba_pvt_inc({_arr(args[0])}, {_arr(args[1])}, __bar_idx, {st})"
            return f"numba_pvt_inc(close_arr, vol_arr, __bar_idx, {st})"
        if func_name in ("nz",):
            if not args:
                return "0.0"
            repl = args[1] if len(args) > 1 else "0.0"
            # String/object series: avoid numba_nz (isnan on unicode fails)
            if (
                self.object_mode
                or not self._is_safe_numeric_expr(args[0])
                or self._looks_like_string_expr(args[0])
                or self._looks_like_string_expr(repl)
                or args[0] in self.scalar_vars
                or args[0] in self.string_series
                or args[0] in self.string_scalars
            ):
                self.object_mode = True
                return f"nz_py({args[0]}, {repl})"
            return f"numba_nz({args[0]}, {repl})"
        if func_name == "fixnan":
            # Full history carry-forward is expensive; nz(x, 0) stub is enough
            # for numeric series. Color/string series must not use numba_nz
            # (TypingError: isnan(unicode_type)).
            if not args:
                return "0.0"
            arg = args[0]
            if (
                self.object_mode
                or not self._is_safe_numeric_expr(arg)
                or self._looks_like_string_expr(arg)
                or arg in self.string_series
                or arg in self.string_scalars
            ):
                self.object_mode = True
                # None replacement keeps color/string na as None (plot skips);
                # numeric na → 0.0 matches the numeric stub / evaluator.
                if self._looks_like_string_expr(arg):
                    return f"nz_py({arg}, None)"
                return f"nz_py({arg}, 0.0)"
            return f"numba_nz({arg}, 0.0)"
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
            st = self._alloc_fixed_state("msum", 2)
            return (
                f"numba_sum_inc({_arr(src_e)}, {self._emit_period(period)}, __bar_idx, {st})"
            )
        if func_name == "math_avg":
            # reference ``math.avg(number0, number1, ...)`` — arithmetic mean of the
            # arguments (not a rolling window; use ta.sma / math.sum for that).
            # Prior emit treated the 2-arg form as SMA(source, length), which
            # crashed on ``math.avg(get, array.get(levels, j+1))`` by feeding
            # object-dtype series into numba_sma_inc.
            if not args:
                return "np.nan"
            if len(args) == 1:
                a0 = args[0]
                if self.object_mode or not self._is_safe_numeric_expr(a0):
                    self.object_mode = True
                    return f"safe_float({a0})"
                return f"({a0})"
            needs_safe = self.object_mode or any(
                not self._is_safe_numeric_expr(a) for a in args
            )
            if needs_safe:
                self.object_mode = True
                joined = " + ".join(f"safe_float({a})" for a in args)
                return f"(({joined}) / {len(args)})"
            # Emit via np.add/np.divide so the whole expr is ``_is_safe_numeric``
            # (startswith ``np.``) and stays on the nopython path. A raw
            # ``(a+b)/n`` form contains ``[`` from series loads and would force
            # object mode at plot/store sites.
            acc = args[0]
            for a in args[1:]:
                acc = f"np.add({acc}, {a})"
            return f"np.divide({acc}, {float(len(args))})"
        if func_name == "math_random":
            # Deterministic stub (midpoint). Pure float — stay numeric/nopython.
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
            # Mirror cos/sin: bare np.* so pure-numeric scripts stay nopython
            # (safe_float is pure Python and thrashing object_mode via plot).
            return f"np.tanh({args[0]})" if args else "np.nan"
        if func_name in ("math_sinh", "sinh"):
            return f"np.sinh({args[0]})" if args else "np.nan"
        if func_name in ("math_cosh", "cosh"):
            return f"np.cosh({args[0]})" if args else "np.nan"
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
            # Bare heikinashi(symbol) — same as ticker.heikinashi (chart HA)
            self._ensure_heikinashi_arrays()
            return repr("__HEIKINASHI__")
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
            if self.object_mode or not self._is_safe_numeric_expr(a0):
                self.object_mode = True
                return f"(safe_float({a0}) * 180.0 / 3.141592653589793)"
            return f"(({a0}) * 180.0 / 3.141592653589793)"
        if func_name in ("math_toradians", "toradians"):
            a0 = args[0] if args else "0.0"
            if self.object_mode or not self._is_safe_numeric_expr(a0):
                self.object_mode = True
                return f"(safe_float({a0}) * 3.141592653589793 / 180.0)"
            return f"(({a0}) * 3.141592653589793 / 180.0)"

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
        #
        # Pine: each call of a UDF has independent series/TA state. Clone
        # ``__st_*`` series-locals and ``__*_st`` incremental buffers so multi
        # call-sites (MA ribbon, KST smaroc, PPO esma) do not share state.
        self._udf_call_site_i += 1
        for s in series_locals:
            call_args.append(self._clone_state_arg_for_call(f"__st_{func_name}_{s}"))
        for st in st_params:
            if self._is_series_local_state(st) or self._is_ta_state_buf(st):
                call_args.append(self._clone_state_arg_for_call(st))
            else:
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
            if self._is_ta_state_buf(fs) or self._is_series_local_state(fs):
                call_args.append(self._clone_state_arg_for_call(fs))
            else:
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
                "time_arr",
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
            return self._emit_strategy_risk_call(method, args, kwargs)
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
        # Pine strategy.exit(id, from_entry, qty, qty_percent, profit, limit, loss, stop,
        # trail_price, trail_points, trail_offset, …)
        # First positional is the *exit order* name (→ comment), not the position id.
        # Always emit from_entry= so market exits filter multi-leg open size too
        # (broker only treats bare id= as from_entry when stop/limit/trail make is_exit).
        if method == "exit":
            param_names: tuple[str, ...] = (
                "_exit_id",
                "from_entry",
                "qty",
                "qty_percent",
                "profit",
                "limit",
                "loss",
                "stop",
                "trail_price",
                "trail_points",
                "trail_offset",
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
            if method == "exit" and key == "id":
                # keyword id= is the exit order name, not the position id
                key = "_exit_id"
            # from_entry stays from_entry (positional + kwarg) — do not remap to id
            seen[key] = v  # later wins

        if method == "exit":
            exit_id = seen.pop("_exit_id", None)
            if exit_id is not None and "comment" not in seen:
                seen["comment"] = exit_id

        # Do not default price=float(close) — begin_bar already set _mark=close.
        # Explicit price= from user kwargs still passes through via ``seen``.
        parts = [f"{k}={v}" for k, v in seen.items()]
        return f"__strategy.{broker_method}({', '.join(parts)})"

    def _emit_strategy_risk_call(self, method: str, args: list[str], kwargs: dict[str, str]) -> str:
        """Emit ``strategy.risk.*`` when broker supports it; else silent no-op.

        Wired (state + enforcement on entry; interpret-aligned halt cascade):
        - ``allow_entry_in`` → ``__strategy.risk_allow_entry_in``
        - ``max_position_size`` → ``__strategy.risk_max_position_size``
        - ``max_drawdown`` → ``__strategy.risk_max_drawdown`` (abs or % of peak)
        - ``max_cons_loss_days`` → ``__strategy.risk_max_cons_loss_days``
        - ``max_intraday_loss`` → ``__strategy.risk_max_intraday_loss``
        - ``max_intraday_filled_orders`` → ``__strategy.risk_max_intraday_filled_orders``
        """
        self.object_mode = True
        self.uses_strategy = True
        risk = method[len("risk_") :]
        if risk == "allow_entry_in":
            val = args[0] if args else kwargs.get("value", repr("all"))
            return f"__strategy.risk_allow_entry_in({val})"
        if risk == "max_position_size":
            # positional percent or keyword percent=
            val = args[0] if args else kwargs.get("percent", kwargs.get("value", "None"))
            return f"__strategy.risk_max_position_size({val})"
        if risk == "max_drawdown":
            val = args[0] if args else kwargs.get("value", "None")
            rtype = args[1] if len(args) > 1 else kwargs.get("type", repr("absolute"))
            return f"__strategy.risk_max_drawdown({val}, {rtype})"
        if risk == "max_cons_loss_days":
            days = args[0] if args else kwargs.get("days", kwargs.get("value", "None"))
            return f"__strategy.risk_max_cons_loss_days({days})"
        if risk == "max_intraday_loss":
            val = args[0] if args else kwargs.get("percent", kwargs.get("value", "None"))
            return f"__strategy.risk_max_intraday_loss({val})"
        if risk == "max_intraday_filled_orders":
            val = args[0] if args else kwargs.get(
                "max_orders", kwargs.get("value", kwargs.get("max", "None"))
            )
            return f"__strategy.risk_max_intraday_filled_orders({val})"
        return ""  # remaining risk.* still no-op on compile path

    def _emit_strategy_trade_query(self, method: str, args: list[str], kwargs: dict[str, str]) -> str:
        """Emit strategy.opentrades.* / strategy.closedtrades.* from broker records.

        Real fields when data exists on ``CompileStrategyBroker`` (open_legs /
        closed_trade_records), including per-trade comments and approximate
        max_drawdown / max_runup (OHLC MTM extremes).
        """
        self.object_mode = True
        self.uses_strategy = True
        idx = args[0] if args else kwargs.get("trade_num", kwargs.get("trade_index", "0"))
        if method.startswith("opentrades_"):
            attr = method[len("opentrades_") :]
            real = {
                "size": "opentrades_size",
                "entry_price": "opentrades_entry_price",
                "entry_id": "opentrades_entry_id",
                "entry_bar_index": "opentrades_entry_bar_index",
                "entry_time": "opentrades_entry_time",
                "commission": "opentrades_commission",
                "profit": "opentrades_profit",
                "entry_comment": "opentrades_entry_comment",
                "max_drawdown": "opentrades_max_drawdown",
                "max_runup": "opentrades_max_runup",
            }
            if attr in real:
                return f"__strategy.{real[attr]}({idx})"
            if attr in ("comment",):
                return f"__strategy.opentrades_entry_comment({idx})"
            return "0.0"
        if method.startswith("closedtrades_"):
            attr = method[len("closedtrades_") :]
            real = {
                "profit": "closedtrades_profit",
                "size": "closedtrades_size",
                "entry_price": "closedtrades_entry_price",
                "exit_price": "closedtrades_exit_price",
                "commission": "closedtrades_commission",
                "entry_id": "closedtrades_entry_id",
                "exit_id": "closedtrades_exit_id",
                "entry_bar_index": "closedtrades_entry_bar_index",
                "exit_bar_index": "closedtrades_exit_bar_index",
                "entry_time": "closedtrades_entry_time",
                "exit_time": "closedtrades_exit_time",
                "entry_comment": "closedtrades_entry_comment",
                "exit_comment": "closedtrades_exit_comment",
                "max_drawdown": "closedtrades_max_drawdown",
                "max_runup": "closedtrades_max_runup",
            }
            if attr in real:
                return f"__strategy.{real[attr]}({idx})"
            if attr in ("comment",):
                return f"__strategy.closedtrades_entry_comment({idx})"
            return "0.0"
        return "0.0"
    def _emit_udt_new(self, type_name: str, node: ast.Call) -> str:
        """Construct a UDT as an ordered-field dict (object mode only)."""
        self.object_mode = True
        fields = self.udt_types.get(type_name, [])
        defaults = self.udt_field_defaults.get(type_name, {})
        args: list[str] = []
        for arg in node.args:
            if hasattr(arg, "value"):
                args.append(self.visit(arg.value))
            else:
                args.append(self.visit(arg))
        items = [f"'__type__': {type_name!r}"]
        for i, f in enumerate(fields):
            # Omitted ctor args use the type-body default. ``np.nan`` for
            # missing bools is ``True`` under ``bool()`` and flips BE/flags.
            if i < len(args):
                v = args[i]
            else:
                v = defaults.get(f, "np.nan")
            items.append(f"{f!r}: {v}")
        return "{" + ", ".join(items) + "}"

    def _emit_map(self, func_name: str, args: list[str], kwargs: dict[str, str]) -> str:
        """Lower map.* to dict operations (object mode)."""
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

    @staticmethod
    def _literal_str(expr: str, default: str = "") -> str:
        """Best-effort unquote a compiled string expression to a Python str.

        Used for hline titles at emit time (series map keys). Dynamic title
        expressions fall back to ``default`` when not a simple quoted literal.
        """
        if not expr:
            return default
        e = expr.strip()
        if len(e) >= 2 and e[0] == e[-1] and e[0] in "\"'":
            inner = e[1:-1]
            return inner if inner else default
        # Match historical plot() title extraction for odd shapes.
        stripped = e.strip("\"'")
        return stripped if stripped else default

    def _unique_plot_title(self, title: str) -> str:
        """Return a series key unused by already-registered plots (hline_2, …)."""
        existing = {p.get("title") for p in self.plots}
        if title not in existing:
            return title
        base = title
        suffix = 2
        while f"{base}_{suffix}" in existing:
            suffix += 1
        return f"{base}_{suffix}"

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
        """Append a drawing/plotstyle event to ``__drawings``; return handle dict.

        Forces object mode. ``*_new`` / ``hline`` return a handle so later
        ``set_*`` and ``safe_float(handle)`` soft-fail to na.
        """
        kind = func_name.replace("_new", "").replace("_delete", "")
        if func_name.endswith("_delete"):
            # Record delete on __drawings so fold_compile_drawing_mutations can
            # drop the target handle (shared identity from *.new).
            target = args[0] if args else "None"
            parts = [
                "'kind': 'delete'",
                f"'method': {func_name!r}",
                f"'target': {target}",
                "'bar': __bar_idx",
            ]
            return f"__drawings.append({{{', '.join(parts)}}})"
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
            if "title" in kwargs:
                parts.append(f"'title': {kwargs['title']}")
            elif len(args) > 3:
                parts.append(f"'title': {args[3]}")
            if "color" in kwargs:
                parts.append(f"'color': {kwargs['color']}")
            elif len(args) > 2:
                parts.append(f"'color': {args[2]}")
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

    def _na_wrap_num(self, expr: str) -> str:
        """Coerce possible ``None`` operands to float for object-mode arithmetic.

        Numeric njit path leaves exprs bare (float64 / nan only — never None).
        Object mode uses :func:`na_num` (None→nan, identity for float/int).
        """
        if not self.object_mode:
            return expr
        if not isinstance(expr, str):
            return expr
        e = expr.strip()
        if not e or e == "np.nan":
            return expr
        # Pine ``na`` lowers to Python ``None`` — must wrap (not a numeric literal)
        if e == "None":
            return "np.nan"
        if e in ("True", "False", "__bar_idx", "n_bars"):
            return expr
        if e.startswith("na_num(") or e.startswith("safe_float(") or e.startswith("safe_int("):
            return expr
        # Pure numeric / bool literals (not None) need no wrap
        if e not in ("None",) and self._is_numeric_or_bool_literal(e):
            return expr
        return f"na_num({expr})"

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
        # Object-mode: None (Pine na) must not raise TypeError on +/*/-/…
        left = self._na_wrap_num(left)
        right = self._na_wrap_num(right)
        # Pine division by zero → na (not Python ZeroDivisionError).
        # Use helpers so side-effecting RHS (numba_*_inc) is not evaluated twice
        # when the zero-check re-embeds the expression (CMF: sum(vol) / sum(vol)).
        if isinstance(node.op, ast.Div):
            return f"numba_safe_div({left}, {right})"
        if isinstance(node.op, ast.Mod):
            return f"numba_safe_mod({left}, {right})"
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
        left_raw = self.visit(node.left)
        # String / color equality must stay unwrapped (na_num("A") → nan breaks
        # ``matrix.get(...) == "A"``). Numeric relational ops need None→nan.
        left_str = self._is_stringy_value(node.left) or self._looks_like_string_expr(
            left_raw
        )
        ops = []
        wrap_all_numeric = True
        raw_rights: list[str] = []
        for op, comp in zip(node.ops, node.comparators):
            op_str = {
                ast.Gt: ">",
                ast.Lt: "<",
                ast.GtE: ">=",
                ast.LtE: "<=",
                ast.Eq: "==",
                ast.NotEq: "!=",
            }.get(type(op), "==")
            right_raw = self.visit(comp)
            right_str = self._is_stringy_value(comp) or self._looks_like_string_expr(
                right_raw
            )
            if left_str or right_str or isinstance(op, (ast.Eq, ast.NotEq)):
                # Eq/NotEq: only wrap when neither side looks stringy and both
                # look numeric (or unknown) — still avoid wrapping pure strings.
                if left_str or right_str:
                    wrap_all_numeric = False
            raw_rights.append((op_str, right_raw, right_str))
        if wrap_all_numeric and not left_str:
            # Relational (and non-string Eq): na-safe numeric compare.
            # Pine: any comparison with na is False except na==na (True).
            # IEEE ``x != nan`` is True — wrong for pyramid_entry etc.
            left = self._na_wrap_num(left_raw)
            parts: list[str] = []
            for op_str, right_raw, right_str in raw_rights:
                if right_str:
                    right = right_raw
                    parts.append(f"({left} {op_str} {right})")
                else:
                    right = self._na_wrap_num(right_raw)
                    if op_str == "==":
                        parts.append(f"numba_pine_eq({left}, {right})")
                    elif op_str == "!=":
                        parts.append(f"numba_pine_ne({left}, {right})")
                    else:
                        parts.append(f"({left} {op_str} {right})")
            if len(parts) == 1:
                return parts[0]
            return "(" + " and ".join(parts) + ")"
        left = left_raw
        for op_str, right_raw, _rs in raw_rights:
            ops.append(f" {op_str} {right_raw}")
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
        """Emit ``base[bar - offset]`` with float/NaN-safe offset coercion.

        Also clamps the computed index to ``[0, len(base))`` so negative
        offsets (future references, e.g. ``high[-highestbars(...)]``) do not
        raise ``index N is out of bounds for axis 0 with size M`` near series
        end — soft-fail to na instead.
        """
        off = self._safe_history_offset(offset_expr)
        # idx = bar - offset; require 0 <= idx < len(base)
        return (
            f"({base}[__bar_idx - ({off})] "
            f"if (__bar_idx >= ({off}) and (__bar_idx - ({off})) < len({base})) "
            f"else np.nan)"
        )

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
        if expr in (
            "open_arr",
            "high_arr",
            "low_arr",
            "close_arr",
            "vol_arr",
            "time_arr",
        ):
            return True
        # Allocated user series: foo_arr (not foo_arr[i] Python list indexing)
        if expr.endswith("_arr") and "[" not in expr:
            return True
        return False

    @staticmethod
    def _is_chart_security_symbol(sym: str) -> bool:
        """True when the security symbol is clearly the host chart (same-symbol).

        Runtime/foreign string tickers (``UPVOL.NY``, ``ESD_FACTSET``, series
        of exchange codes) must not passthrough chart OHLCV.

        Compile lowers ``syminfo.ticker`` / ``tickerid`` / ``root`` / bare
        ``tickerid`` to the string literal ``'SYMBOL'`` / ``\"SYMBOL\"`` (see
        attr/name stubs). Treat those placeholders as chart identity so
        same-symbol simple OHLCV ``request.security`` / ``security`` passthrough
        matches interpret (and ``test_request_security_syminfo_time_stubs`` /
        ``test_bare_security_passthrough``).
        """
        if not isinstance(sym, str):
            return False
        s = sym.strip()
        if not s:
            return False
        # syminfo.ticker / tickerid / root lowered as chart identity strings
        if "syminfo" in s.lower() and any(
            k in s for k in ("ticker", "tickerid", "root", "prefix")
        ):
            return True
        # Bare chart placeholders occasionally emitted
        if s in (
            "''",
            '""',
            "None",
            "np.nan",
            "syminfo_ticker",
            "syminfo_tickerid",
        ):
            return True
        # Quoted empty
        if re.fullmatch(r"['\"]['\"]", s):
            return True
        # Unquoted or quoted SYMBOL placeholder from syminfo/tickerid stubs
        if s in ("SYMBOL", "'SYMBOL'", '"SYMBOL"'):
            return True
        if re.fullmatch(r"['\"]SYMBOL['\"]", s):
            return True
        # Heikin-Ashi of the chart is still same-symbol (transformed OHLCV)
        if CompilerVisitor._is_heikinashi_security_symbol(s):
            return True
        return False

    @staticmethod
    def _is_heikinashi_security_symbol(sym: str) -> bool:
        """True when compile lowered ``ticker.heikinashi(...)`` to HA marker."""
        if not isinstance(sym, str):
            return False
        s = sym.strip()
        if s in ("__HEIKINASHI__", "'__HEIKINASHI__'", '"__HEIKINASHI__"'):
            return True
        if re.fullmatch(r"['\"]__HEIKINASHI__['\"]", s):
            return True
        # str(…) form sometimes wraps the marker
        if "__HEIKINASHI__" in s and "HA(" not in s.upper():
            return True
        return False

    def _ensure_heikinashi_arrays(self) -> None:
        """Allocate ha_open/high/low/close series for Heikin-Ashi security."""
        self.needs_heikinashi = True
        for name in ("ha_open_arr", "ha_high_arr", "ha_low_arr", "ha_close_arr"):
            self.arrays.add(name)

    @staticmethod
    def _map_ohlcv_expr_to_heikinashi(expr: str) -> str:
        """Rewrite chart OHLCV sample expressions to Heikin-Ashi arrays."""
        if not isinstance(expr, str):
            return expr
        e = expr.strip()
        mapping = {
            "open_arr[__bar_idx]": "ha_open_arr[__bar_idx]",
            "high_arr[__bar_idx]": "ha_high_arr[__bar_idx]",
            "low_arr[__bar_idx]": "ha_low_arr[__bar_idx]",
            "close_arr[__bar_idx]": "ha_close_arr[__bar_idx]",
            "Open_arr[__bar_idx]": "ha_open_arr[__bar_idx]",
            "High_arr[__bar_idx]": "ha_high_arr[__bar_idx]",
            "Low_arr[__bar_idx]": "ha_low_arr[__bar_idx]",
            "Close_arr[__bar_idx]": "ha_close_arr[__bar_idx]",
        }
        if e in mapping:
            return mapping[e]
        # Bare array refs (rare)
        for src, dst in (
            ("open_arr", "ha_open_arr"),
            ("high_arr", "ha_high_arr"),
            ("low_arr", "ha_low_arr"),
            ("close_arr", "ha_close_arr"),
        ):
            if e == src:
                return dst
        return e

    @staticmethod
    def _ast_is_heikinashi_ticker(node: Any) -> bool:
        """True for ``ticker.heikinashi(...)`` / bare ``heikinashi(...)`` AST."""
        if node is None:
            return False
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Specialize):
                func = func.value
            if isinstance(func, ast.Attribute) and getattr(func, "attr", None) == "heikinashi":
                return True
            if isinstance(func, ast.Name) and getattr(func, "id", None) == "heikinashi":
                return True
        return False

    @staticmethod
    def _heikinashi_bar_update_lines() -> list[str]:
        """Python lines that write ha_*_arr[__bar_idx] from chart OHLCV."""
        return [
            "_ha_c = (open_arr[__bar_idx] + high_arr[__bar_idx] + "
            "low_arr[__bar_idx] + close_arr[__bar_idx]) * 0.25",
            "if __bar_idx == 0 or np.isnan(ha_open_arr[__bar_idx - 1]):",
            "    _ha_o = (open_arr[__bar_idx] + close_arr[__bar_idx]) * 0.5",
            "else:",
            "    _ha_o = (ha_open_arr[__bar_idx - 1] + ha_close_arr[__bar_idx - 1]) * 0.5",
            "ha_open_arr[__bar_idx] = _ha_o",
            "ha_close_arr[__bar_idx] = _ha_c",
            "ha_high_arr[__bar_idx] = max(high_arr[__bar_idx], _ha_o, _ha_c)",
            "ha_low_arr[__bar_idx] = min(low_arr[__bar_idx], _ha_o, _ha_c)",
        ]

    @staticmethod
    def _is_simple_security_expr(expr: str) -> bool:
        """True for chart OHLCV (current or history) safe as same-symbol stub.

        Complex expressions (UDF calls, ``ta.*``, arithmetic) must not lower as
        foreign-symbol series — that invents close-as-dividend style plots.
        """
        if not isinstance(expr, str):
            return False
        e = expr.strip()
        if not e:
            return False
        chart = r"(?:open|high|low|close|vol|hl2|hlc3|ohlc4)_arr"
        if re.fullmatch(rf"{chart}\[__bar_idx\]", e):
            return True
        # History ternary: (close_arr[__bar_idx - (off)] if … else np.nan)
        if re.match(rf"^\({chart}\[__bar_idx", e):
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

        # strategy.position_size[n] / avg_price[n] / closedtrades[n]
        # Live mid-bar value for offset 0; end-of-bar snapshot arrays for n≥1.
        _strat_hist = {
            "__strategy.position_size": (
                "__strategy_position_size_arr",
                "__strategy.position_size",
            ),
            "__strategy.position_avg_price": (
                "__strategy_position_avg_price_arr",
                "__strategy.position_avg_price",
            ),
            "__strategy.closed_trades": (
                "__strategy_closed_trades_arr",
                "__strategy.closed_trades",
            ),
        }
        if arr in _strat_hist:
            self.uses_strategy = True
            self.object_mode = True
            hist_arr, live = _strat_hist[arr]
            self.arrays.add(hist_arr)
            off = self._safe_history_offset(slice_val)
            # offset 0 → live (entries this bar update size before plots)
            return (
                f"({live} if ({off}) == 0 else "
                f"({hist_arr}[__bar_idx - ({off})] "
                f"if (__bar_idx >= ({off}) and "
                f"(__bar_idx - ({off})) < len({hist_arr})) else np.nan))"
            )

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
        """Emit a module-scope UDF with series/state/context packing.

        Analysis passes (in order):

        1. Collect assigned locals + history subscript bases.
        2. Mark series params (history / TA consumers) and series locals
           (persistent ``__st_{fn}_{local}`` across bars).
        3. Body gen with :attr:`ident_map` (keyword/builtin shadows, UDF name
           collisions → ``__p`` / ``__loc`` suffixes).
        4. Free scalars/series from outer script (UDFs cannot close over the
           bar-loop frame under njit) plus transitive callee free vars.
        5. Trailing params: drawings, ``n_bars``, chart OHLCV + ``__bar_idx``,
           ``__strategy`` when referenced.

        Call sites must match param order via :meth:`_emit_user_func_call`.
        Numeric mode prefixes ``@numba.njit(cache=False)``; object mode omits it.
        """
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
        # Early formal list so recursive/body method-form checks see arity
        # (full free-scalar / series metadata is still filled after body gen).
        self.func_param_names[pine_name] = list(args)
        self.func_param_names[func_name] = list(args)
        if getattr(node, "export", None) or getattr(node, "method", None):
            # export / method in libraries → always object mode
            self.object_mode = True
        # Save full parent scope so nested UDF defs (docs-invalid, but present in
        # corpus demos) do not clobber the enclosing function's locals/params.
        prev_in_function = self.in_function
        prev_series = set(self.series_params)
        prev_series_locals = set(self.series_locals)
        prev_param_names = set(self.param_names)
        prev_ident = dict(self.ident_map)
        prev_local_vars = set(self.local_vars)
        prev_history = set(getattr(self, "history_names_current", set()))
        prev_free_scalars = set(getattr(self, "_free_scalars_current", set()))
        prev_func_name = getattr(self, "_current_func_name", None)
        prev_local_seq = set(getattr(self, "local_sequence_vars", set()))
        prev_if_return = bool(getattr(self, "if_return_mode", False))
        prev_var_locals = set(getattr(self, "var_locals", set()))
        self.in_function = True
        # Metadata keys use Pine name (call sites resolve via Pine id / attr)
        self._current_func_name = pine_name
        self.local_vars = set(args)
        self.local_sequence_vars = set()
        self.if_return_mode = False
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

        # Pass 0: assigned locals + names used under history subscript + var locals
        assigned: set[str] = set()
        history_names: set[str] = set()
        var_names: set[str] = set()
        for stmt in node.body:
            self._collect_assigned_names(stmt, assigned)
            self._collect_history_names(stmt, history_names)
            self._collect_var_names(stmt, var_names)
        self.history_names_current = set(history_names)
        self.var_locals = {
            n for n in var_names if n in assigned and n not in arg_set and n not in self.loop_counters
        }

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

        # Assigned non-params used with history OR declared ``var`` → series_locals
        # (persistent ``__st_{fn}_{local}`` across bars). ``var`` inside a UDF must
        # survive bar-to-bar calls (auto_fib pivot arrays / line handles).
        # Exclude names that are only loop counters (not true series state)
        series_locals = sorted(
            n
            for n in (history_names | self.var_locals)
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

        # Keep free scalars even when they shadow a built-in namespace name
        # (``var matrix = matrix.new...`` then UDF uses ``matrix`` as the handle).
        free_scalars_set = {
            n
            for n in self._free_scalars_current
            if n not in arg_set
            and n not in assigned
            and n not in self.user_funcs
            and n not in self.loop_counters
            and n not in self.import_aliases
            and (
                n in self.scalar_vars
                or n in self.map_vars
                or (
                    n not in _NS
                    and n not in _COLOR_NAMES
                    and n not in _ENUM_NS
                )
            )
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
        # Record series metadata for call-site lowering (keep parent scope intact
        # until the end of this method — nested defs must not leave in_function=False).
        self.func_series_params[pine_name] = series_for_func
        self.func_series_locals[pine_name] = list(series_locals)
        self.func_param_names[pine_name] = list(args)
        # Temporarily expose this fn's series_params for free_series / needs_ctx
        # analysis below; restored (with optional accumulate) at function end.
        self.series_params = set(series_for_func)
        self.series_locals = set(series_locals)
        self.param_names = set(args)

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
            "time_arr",
        )
        # Nested callees may need __st_* state arrays passed through this frame
        st_refs = sorted(set(re.findall(r"__st_[A-Za-z_][A-Za-z0-9_]*", body_text)))
        self.func_st_params[pine_name] = st_refs

        # series-local params use safe base name + _arr
        sl_params = [f"{self.ident_map.get(s, s)}_arr" for s in series_locals]
        # Free script-level series referenced inside the UDF (e.g. hma3 uses outer `lag`)
        # Functions are emitted at module scope, so they cannot close over execute_script locals.
        _chart = {
            "open_arr",
            "high_arr",
            "low_arr",
            "close_arr",
            "vol_arr",
            "time_arr",
        }
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
                # plus call-site clones (__rma0_st_c1) used by nested UDF calls.
                m
                for m in re.findall(
                    r"\b(__[A-Za-z][A-Za-z0-9_]*_st(?:_c\d+)*)\b", body_text
                )
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
            extra = [
                "open_arr",
                "high_arr",
                "low_arr",
                "close_arr",
                "vol_arr",
                "time_arr",
                "__bar_idx",
            ]
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
            # Pine ``for … in …`` / ``for i = a to b`` as last stmt: last body
            # expr is the loop value (e.g. ``for x in arr\n    result`` or
            # factorial ``for i = 1 to n\n    r := r * i\n    r``).
            last_is_for = isinstance(last_ast, (ast.ForIn, ast.ForTo)) or isinstance(
                last_val, (ast.ForIn, ast.ForTo)
            )
            for_ret_name: str | None = None
            if last_is_for and body_lines:
                # Find trailing bare name expression inside the for block only
                # (``for x in arr\n    result`` → return result). Do NOT fall back
                # to arbitrary assigned locals (``zone_color = …`` mid-loop is not
                # the function result and may be unbound).
                # ForTo emission appends ``i += __step_i`` after the body — skip
                # that auto-increment so ``r`` (the Pine result) is still found.
                last_line = body_lines[-1]
                phys_lines = [ln.strip() for ln in last_line.split("\n") if ln.strip()]
                _step_inc = re.compile(
                    r"^[A-Za-z_][A-Za-z0-9_]*\s*\+=\s*__step_[A-Za-z_][A-Za-z0-9_]*$"
                )
                for tail in reversed(phys_lines):
                    if _step_inc.match(tail):
                        continue
                    m_tail = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)", tail)
                    if m_tail:
                        for_ret_name = m_tail.group(1)
                    break
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
        # Restore parent UDF scope (critical for nested FunctionDef demos)
        self.in_function = prev_in_function
        self._current_func_name = prev_func_name
        self.local_vars = prev_local_vars
        # Top-level: accumulate series_params for later call-site lowering;
        # nested: pure restore so outer UDF body still sees its own params.
        if prev_in_function:
            self.series_params = prev_series
            self.series_locals = prev_series_locals
        else:
            self.series_params = prev_series | series_for_func
            self.series_locals = prev_series_locals
        self.param_names = prev_param_names
        self.ident_map = prev_ident
        self.history_names_current = prev_history
        self._free_scalars_current = prev_free_scalars
        self.local_sequence_vars = prev_local_seq
        self.if_return_mode = prev_if_return
        self.var_locals = prev_var_locals
        return ""

    def _udf_formal_count(self, name: str) -> int:
        """Number of user formals for a UDF (0 if unknown / not yet registered)."""
        params = self.func_param_names.get(name)
        if params is not None:
            return len(params)
        # Currently emitting this function: use live param_names
        if name == getattr(self, "_current_func_name", None):
            return len(getattr(self, "param_names", set()) or [])
        return 0

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
            "rci",
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
            "ta_rci",
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

    def _collect_var_names(self, node, out: set[str]) -> None:
        """Collect Name targets of ``var`` / ``varip`` Assign in a subtree."""
        if node is None or not hasattr(node, "__dict__"):
            return
        if isinstance(node, ast.Assign):
            mode = getattr(node, "mode", None)
            if mode is not None and type(mode).__name__ in ("Var", "VarIp"):
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
                    self._collect_var_names(c, out)
            else:
                self._collect_var_names(child, out)


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
        # Pine: omitted ``by`` → +1 when from<=to, -1 when from>to
        # (``for i = size-1 to 0`` must walk downward; hardcoding 1 is a no-op).
        has_explicit_step = getattr(node, "step", None) is not None
        step = self.visit(node.step) if has_explicit_step else None
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
        end_tmp = f"__end_{target}"
        if has_explicit_step:
            step_expr = step if step is not None else "1"
        else:
            # Evaluate end once; auto-step from start vs end at loop entry.
            # Numeric path: bare compare (na_num is Python-only — breaks njit).
            if self.object_mode:
                step_expr = f"(1 if (na_num({target}) <= na_num({end_tmp})) else -1)"
            else:
                step_expr = f"(1 if ({target}) <= ({end_tmp}) else -1)"
        lines = [
            f"{target} = {start}",
            f"{end_tmp} = {end}",
            f"__step_{target} = {step_expr}",
            f"while ({target} <= {end_tmp}) if __step_{target} > 0 else ({target} >= {end_tmp}):",
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
        # Object-mode: ``-None`` / ``+None`` must not TypeError
        if isinstance(node.op, (ast.UAdd, ast.USub)):
            operand = self._na_wrap_num(operand)
        if isinstance(node.op, ast.UAdd):
            return f"(+{operand})"
        if isinstance(node.op, ast.USub):
            return f"(-{operand})"
        return operand

    def visit_Conditional(self, node: ast.Conditional):
        return f"({self.visit(node.body)} if {self.visit(node.test)} else {self.visit(node.orelse)})"

    def visit_Tuple(self, node: ast.Tuple):
        return "(" + ", ".join(self.visit(e) for e in node.elts) + ")"
