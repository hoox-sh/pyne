# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

from __future__ import annotations

import ast as pyast
from pynescript.ast import node as ast
from pynescript.ast.visitor import NodeVisitor


class CompilerVisitor(NodeVisitor):
    def __init__(self):
        super().__init__()
        self.arrays = set()
        self.plots = []
        self.functions = []
        self.in_function = False
        self.local_vars = set()

    def visit_Script(self, node: ast.Script):
        body_lines = []
        for stmt in node.body:
            val = self.visit(stmt)
            if val:
                body_lines.append(val)

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
                "@numba.njit",
                "def execute_script_compiled(open_arr, high_arr, low_arr, close_arr, vol_arr):",
                "    n_bars = len(close_arr)",
            ]
        )

        for arr in self.arrays:
            lines.append(f"    {arr} = np.full(n_bars, np.nan)")

        for idx in range(len(self.plots)):
            lines.append(f"    plot_{idx} = np.full(n_bars, np.nan)")

        lines.append("    for __bar_idx in range(n_bars):")

        for line in body_lines:
            line = line.replace("\n", "\n        ")
            lines.append(f"        {line}")

        ret = ", ".join([f"plot_{i}" for i in range(len(self.plots))])
        if not ret:
            ret = "None"

        # We return a dict in Python to match the runtime outputs
        dict_items = []
        for i, plot_info in enumerate(self.plots):
            title = plot_info["title"]
            dict_items.append(f"'{title}': plot_{i}")
        lines.append("    return {" + ", ".join(dict_items) + "}")
        return "\n".join(lines)

    def visit_Assign(self, node: ast.Assign):
        if isinstance(node.target, ast.Name):
            name = node.target.id
            val = self.visit(node.value)

            if self.in_function:
                self.local_vars.add(name)
                return f"{name} = {val}"

            self.arrays.add(f"{name}_arr")

            # Check if this is a `var` declaration
            is_var = hasattr(node, "mode") and isinstance(node.mode, ast.Var)
            if is_var:
                return f"{name}_arr[__bar_idx] = {val} if __bar_idx == 0 else {name}_arr[__bar_idx-1]"

            return f"{name}_arr[__bar_idx] = {val}"
        return ""

    def visit_Name(self, node: ast.Name):
        if self.in_function and node.id in self.local_vars:
            return node.id

        if node.id in ["open", "high", "low", "close", "volume"]:
            return f"{node.id}_arr[__bar_idx]"
        if node.id in ("bar_index",):
            return "__bar_idx"
        if node.id in ["ta", "math", "str", "array", "matrix", "syminfo", "timeframe", "color", "plot", "strategy", "input"]:
            return node.id
        # Undeclared names: treat as series arrays (declared via Assign)
        return f"{node.id}_arr[__bar_idx]"

    def visit_BinOp(self, node: ast.BinOp):
        left = self.visit(node.left)
        right = self.visit(node.right)
        op = ""
        if isinstance(node.op, ast.Add):
            op = "+"
        elif isinstance(node.op, ast.Sub):
            op = "-"
        elif isinstance(node.op, ast.Mult):
            op = "*"
        elif isinstance(node.op, ast.Div):
            op = "/"
        elif isinstance(node.op, ast.Mod):
            op = "%"
        return f"({left} {op} {right})"

    def visit_Compare(self, node: ast.Compare):
        left = self.visit(node.left)
        ops = []
        for op, comp in zip(node.ops, node.comparators):
            op_str = "=="
            if isinstance(op, ast.Gt):
                op_str = ">"
            elif isinstance(op, ast.Lt):
                op_str = "<"
            elif isinstance(op, ast.GtE):
                op_str = ">="
            elif isinstance(op, ast.LtE):
                op_str = "<="
            elif isinstance(op, ast.NotEq):
                op_str = "!="
            ops.append(f" {op_str} {self.visit(comp)}")
        return f"({left}{''.join(ops)})"

    def visit_Constant(self, node: ast.Constant):
        if isinstance(node.value, str):
            return repr(node.value)
        return str(node.value)

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            # Special case for log.*
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "log":
                func_name = f"log_{node.func.attr}"
            else:
                val = self.visit(node.func.value)
                if val.endswith("[__bar_idx]"):
                    val = val[:-11]
                func_name = f"{val}_{node.func.attr}"
        else:
            func_name = "unknown_func"

        args: list[str] = []
        kwargs: dict[str, str] = {}
        for arg in node.args:
            # Pine Arg nodes: optional .name for keyword, .value for expr
            if hasattr(arg, "value"):
                expr = self.visit(arg.value)
                if getattr(arg, "name", None):
                    kwargs[str(arg.name)] = expr
                else:
                    args.append(expr)
            else:
                args.append(self.visit(arg))

        # Declarations — no-ops in compiled bar loop
        if func_name in ("indicator", "strategy", "library"):
            return ""

        # input.* / input() → use default value (first arg) as compile-time const
        if func_name == "input" or func_name.startswith("input_"):
            if args:
                return args[0]
            if "defval" in kwargs:
                return kwargs["defval"]
            return "0.0"

        if func_name == "plot":
            title = f"Plot {len(self.plots)}"
            if "title" in kwargs:
                title = kwargs["title"].strip("\"'")
            elif len(args) > 1 and args[1]:
                title = args[1].strip("\"'")
            series_expr = args[0] if args else "np.nan"
            self.plots.append({"expr": series_expr, "title": title})
            idx = len(self.plots) - 1
            return f"plot_{idx}[__bar_idx] = {series_expr}"

        if func_name in ("hline", "bgcolor", "barcolor", "plotshape", "plotchar", "plotarrow", "plotbar", "plotcandle", "fill"):
            # Visual no-ops in numeric compile path (plots captured via plot())
            return ""

        if func_name in ["log_info", "log_warning", "log_error"]:
            # Skip logging inside njit (no objmode required for MVP)
            return ""

        def _arr_arg(expr: str) -> str:
            return expr.replace("[__bar_idx]", "")

        if func_name == "ta_sma":
            period = kwargs.get("length", args[1] if len(args) > 1 else "14")
            return f"numba_sma({_arr_arg(args[0])}, {period}, __bar_idx)"

        if func_name == "ta_ema":
            period = kwargs.get("length", args[1] if len(args) > 1 else "14")
            return f"numba_ema({_arr_arg(args[0])}, {period}, __bar_idx)"

        if func_name == "ta_rsi":
            period = kwargs.get("length", args[1] if len(args) > 1 else "14")
            return f"numba_rsi({_arr_arg(args[0])}, {period}, __bar_idx)"

        if func_name == "ta_highest":
            period = kwargs.get("length", args[1] if len(args) > 1 else "14")
            return f"numba_highest({_arr_arg(args[0])}, {period}, __bar_idx)"

        if func_name == "ta_lowest":
            period = kwargs.get("length", args[1] if len(args) > 1 else "14")
            return f"numba_lowest({_arr_arg(args[0])}, {period}, __bar_idx)"

        if func_name in ("nz", "math_abs", "abs"):
            if func_name == "nz":
                repl = args[1] if len(args) > 1 else "0.0"
                return f"numba_nz({args[0]}, {repl})"
            return f"numba_abs({args[0]})"

        if func_name in ("math_max", "math_min", "max", "min"):
            op = "numba_max" if "max" in func_name else "numba_min"
            return f"{op}({args[0]}, {args[1]})"

        if func_name in ("math_sqrt",):
            return f"np.sqrt({args[0]})"

        return f"{func_name}({', '.join(args)})"

    def visit_Attribute(self, node: ast.Attribute):
        val = self.visit(node.value)
        # Hack to strip `[__bar_idx]` from `close_arr[__bar_idx]` so it becomes `close_arr` temporarily
        if val.endswith("[__bar_idx]"):
            val = val[:-11]
        return f"{val}_{node.attr}"

    def visit_Expr(self, node: ast.Expr):
        return self.visit(node.value)

    def visit_Subscript(self, node: ast.Subscript):
        arr = self.visit(node.value)
        # arr is likely `close_arr[__bar_idx]`. We want to replace `[__bar_idx]` with `[__bar_idx - slice]`
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
                # Add 4 spaces for the indentation
                val = val.replace("\n", "\n    ")
                lines.append(f"    {val}")

        # If the if-block had no statements that return code, add pass
        if len(lines) == 1:
            lines.append("    pass")

        if node.orelse:
            lines.append("else:")
            orelse_count = 0
            for stmt in node.orelse:
                val = self.visit(stmt)
                if val:
                    val = val.replace("\n", "\n    ")
                    lines.append(f"    {val}")
                    orelse_count += 1
            if orelse_count == 0:
                lines.append("    pass")

        return "\n".join(lines)

    def visit_ReAssign(self, node: ast.ReAssign):
        target = self.visit(node.target)
        val = self.visit(node.value)
        return f"{target} = {val}"

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

        lines = ["@numba.njit", f"def {func_name}({', '.join(args)}):"]

        if not body_lines:
            lines.append("    pass")
        else:
            for i, line in enumerate(body_lines):
                # The last expression is an implicit return
                is_last = i == len(body_lines) - 1
                is_expr = isinstance(node.body[-1], ast.Expr)

                line = line.replace("\n", "\n    ")
                if is_last and is_expr:
                    lines.append(f"    return {line}")
                else:
                    lines.append(f"    {line}")

        self.functions.append("\n".join(lines))
        return ""  # Do not put in the global loop

    def visit_Return(self, node: ast.Return):
        if node.value:
            val = self.visit(node.value)
            return f"return {val}"
        return "return"

    def visit_ForTo(self, node: ast.ForTo):
        target = node.target.id if isinstance(node.target, ast.Name) else self.visit(node.target)
        start = self.visit(node.start)
        end = self.visit(node.end)
        step = self.visit(node.step) if getattr(node, "step", None) else "1"

        was_in_func = self.in_function
        self.in_function = True
        self.local_vars.add(target)

        lines = []
        lines.append(f"{target} = {start}")
        lines.append(f"__step_{target} = {step}")
        lines.append(f"while ({target} <= {end}) if __step_{target} > 0 else ({target} >= {end}):")

        body_has_code = False
        for stmt in node.body:
            val = self.visit(stmt)
            if val:
                val = val.replace("\n", "\n    ")
                lines.append(f"    {val}")
                body_has_code = True

        lines.append(f"    {target} += __step_{target}")

        self.in_function = was_in_func
        if not was_in_func:
            self.local_vars.remove(target)

        return "\n".join(lines)

    def visit_While(self, node: ast.While):
        test = self.visit(node.test)

        was_in_func = self.in_function
        self.in_function = True

        lines = [f"while {test}:"]

        body_has_code = False
        for stmt in node.body:
            val = self.visit(stmt)
            if val:
                val = val.replace("\n", "\n    ")
                lines.append(f"    {val}")
                body_has_code = True

        if not body_has_code:
            lines.append("    pass")

        self.in_function = was_in_func
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
        test = self.visit(node.test)
        body = self.visit(node.body)
        orelse = self.visit(node.orelse)
        return f"({body} if {test} else {orelse})"
