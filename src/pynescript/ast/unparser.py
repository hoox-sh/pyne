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

"""AST to Pine Script Source Code Generator.

Converts AST nodes back to syntactically correct Pine Script source code.
Preserves formatting intent while handling operator precedence and special
Pine Script syntax conventions.

Main Classes:
- Precedence: Operator precedence levels for parenthesization decisions
- NodeUnparser: Main visitor that generates source code from AST nodes
  (implements visit_* methods for each AST node type)
"""

from __future__ import annotations

import json
import threading

from enum import IntEnum
from enum import auto
from typing import ClassVar

from pynescript.ast import node as ast
from pynescript.ast.visitor import NodeVisitor


# Precomputed indent prefixes (4 spaces per level). Avoids repeated "    " * n.
_INDENT_CACHE: tuple[str, ...] = tuple("    " * i for i in range(64))

class _NullCM:
    """Zero-allocation no-op context manager (replaces contextlib.nullcontext)."""

    __slots__ = ()

    def __enter__(self):
        return None

    def __exit__(self, *exc):
        return False


_NULL_CM = _NullCM()


class _DelimitCM:
    """Lightweight start/end delimiter without contextlib.contextmanager."""

    __slots__ = ("_end", "_src")

    def __init__(self, src: list[str], start: str, end: str):
        self._src = src
        self._end = end
        src.append(start)

    def __enter__(self):
        return None

    def __exit__(self, *exc):
        self._src.append(self._end)
        return False


class _BlockCM:
    """Indent block without contextlib.contextmanager."""

    __slots__ = ("_u",)

    def __init__(self, unparser: NodeUnparser, extra: str | None):
        self._u = unparser
        if extra:
            unparser._source.append(extra)
        unparser._indent += 1

    def __enter__(self):
        return None

    def __exit__(self, *exc):
        self._u._indent -= 1
        return False


class Precedence(IntEnum):
    """Operator precedence levels for correct parenthesization in output.

    Higher values bind tighter. Used to determine when to add parentheses
    around sub-expressions to preserve evaluation order.
    """

    TEST = auto()  # '?', ':' - ternary conditional (lowest)
    OR = auto()  # 'or'
    AND = auto()  # 'and'
    BITOR = auto()  # '|'
    BITXOR = auto()  # '^'
    BITAND = auto()  # '&'
    EQ = auto()  # '==', '!='
    INEQ = auto()  # '>', '<', '>=', '<='
    CMP = INEQ  # Alias for comparison
    SHIFT = auto()  # '<<', '>>'
    EXPR = auto()
    ARITH = auto()  # '+', '-'
    TERM = auto()  # '*', '/', '%'
    FACTOR = auto()  # unary '+', unary '-', 'not', '~'
    NOT = FACTOR  # Alias for unary not
    ATOM = auto()  # Highest precedence - literals, names, parenthesized exprs

    def next(self):
        """Get the next higher precedence level."""
        return _PRECEDENCE_NEXT[self]


# Precomputed successor map so next() never raises / constructs via try/except.
_PRECEDENCE_NEXT: dict[Precedence, Precedence] = {}
for _p in Precedence:
    try:
        _PRECEDENCE_NEXT[_p] = Precedence(_p + 1)
    except ValueError:
        _PRECEDENCE_NEXT[_p] = _p
# Aliases share the same int value; ensure all members resolve.
for _p in Precedence:
    _PRECEDENCE_NEXT.setdefault(_p, _p)


class NodeUnparser(NodeVisitor):
    # ruff: noqa: N802

    def __init__(self):
        super().__init__()  # Initialize visitor cache
        self._source: list[str] = []
        self._precedences: dict = {}
        self._indent = 0
        # Type-object keyed dispatch (faster than class-name strings).
        self._type_visitor_cache: dict[type, object] = {}

    def interleave(self, inter, f, seq):
        seq = iter(seq)
        try:
            f(next(seq))
        except StopIteration:
            pass
        else:
            for x in seq:
                inter()
                f(x)

    def _write_comma_space(self):
        self._source.append(", ")

    def items_view(self, traverser, items, *, single: bool = False):
        if len(items) == 1:
            traverser(items[0])
            if single:
                self._source.append(",")
        else:
            self.interleave(self._write_comma_space, traverser, items)

    def maybe_newline(self):
        if self._source:
            self._source.append("\n")

    def fill(self, text=""):
        src = self._source
        if src:
            src.append("\n")
        ind = self._indent
        prefix = _INDENT_CACHE[ind] if ind < len(_INDENT_CACHE) else "    " * ind
        if text:
            src.append(prefix + text)
        else:
            src.append(prefix)

    def write(self, *text):
        src = self._source
        n = len(text)
        if n == 1:
            src.append(text[0])
        elif n == 0:
            return
        else:
            # Multi-arg path (hot call sites mostly use 1 arg / direct append).
            src.extend(text)

    def buffered(self, buffer=None):
        # Kept for API compatibility; rarely used. Manual enter/exit pair.
        if buffer is None:
            buffer = []
        return _BufferedCM(self, buffer)

    def block(self, *, extra=None):
        return _BlockCM(self, extra)

    def delimit(self, start, end):
        return _DelimitCM(self._source, start, end)

    def delimit_if(self, start, end, condition):
        if condition:
            return _DelimitCM(self._source, start, end)
        return _NULL_CM

    def require_parens(self, precedence, node):
        if self._precedences.get(node, Precedence.TEST) > precedence:
            return _DelimitCM(self._source, "(", ")")
        return _NULL_CM

    def get_precedence(self, node):
        return self._precedences.get(node, Precedence.TEST)

    def set_precedence(self, precedence, *nodes):
        prec = self._precedences
        for node in nodes:
            prec[node] = precedence

    def traverse(self, node):
        # Lists are statement/arg containers; exact type check avoids ABC overhead.
        if node.__class__ is list:
            for item in node:
                self.traverse(item)
            return
        # Inline type-keyed visitor dispatch (avoids name-string cache + super()).
        cache = self._type_visitor_cache
        cls = node.__class__
        visitor = cache.get(cls)
        if visitor is None:
            visitor = getattr(self, "visit_" + cls.__name__, self.generic_visit)
            cache[cls] = visitor
        visitor(node)  # type: ignore[operator]

    def visit(self, node):
        # Full reset so a single NodeUnparser instance can be reused safely.
        self._source = []
        self._precedences = {}
        self._indent = 0
        self.traverse(node)
        return "".join(self._source)

    def visit_Script(self, node: ast.Script):
        if node.annotations:
            for annotation in node.annotations:
                self.fill(annotation)
        self.traverse(node.body)

    def visit_Expression(self, node: ast.Expression):
        self.traverse(node.body)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.fill()
        if node.annotations:
            for annotation in node.annotations:
                self.fill(annotation)
            self.fill()
        if node.export:
            self._source.append("export ")
        if node.method:
            self._source.append("method ")
        self._source.append(node.name)
        with self.delimit("(", ")"):
            if node.args:
                self.items_view(self.traverse, node.args)
        self._source.append(" => ")
        if len(node.body) == 1 and isinstance(node.body[0], ast.Expr):
            self.traverse(node.body[0].value)
        else:
            with self.block():
                self.traverse(node.body)

    def visit_TypeDef(self, node: ast.TypeDef):
        self.fill()
        if node.annotations:
            for annotation in node.annotations:
                self.fill(annotation)
            self.fill()
        if node.export:
            self._source.append("export ")
        self._source.append("type ")
        self._source.append(node.name)
        with self.block():
            # Split body into fields and methods for better organization
            fields = []
            methods = []
            for stmt in node.body:
                if isinstance(stmt, ast.FunctionDef) and stmt.method:
                    methods.append(stmt)
                else:
                    fields.append(stmt)

            # Unparse fields first, then methods
            for field in fields:
                self.traverse(field)
            for method in methods:
                self.traverse(method)

    def visit_EnumDef(self, node: ast.EnumDef):
        self.fill()
        if node.annotations:
            for annotation in node.annotations:
                self.fill(annotation)
            self.fill()
        if node.export:
            self._source.append("export ")
        self._source.append("enum ")
        self._source.append(node.name)
        with self.block():
            self.traverse(node.body)

    def visit_Assign(self, node: ast.Assign):
        self.fill()
        if node.annotations:
            for annotation in node.annotations:
                self.fill(annotation)
            self.fill()
        if getattr(node, "export", None):
            self._source.append("export ")
        if node.mode:
            self.traverse(node.mode)
            self._source.append(" ")
        if node.type:
            self.traverse(node.type)
            self._source.append(" ")
        self.traverse(node.target)
        if node.value:
            self._source.append(" = ")
            self.traverse(node.value)

    def visit_ReAssign(self, node: ast.ReAssign):
        self.fill()
        self.traverse(node.target)
        self._source.append(" := ")
        self.traverse(node.value)

    def visit_AugAssign(self, node: ast.AugAssign):
        self.fill()
        self.traverse(node.target)
        self._source.append(" ")
        self.traverse(node.op)
        self._source.append("= ")
        self.traverse(node.value)

    def visit_ForTo(self, node: ast.ForTo):
        self._source.append("for ")
        self.traverse(node.target)
        self._source.append(" = ")
        self.traverse(node.start)
        self._source.append(" to ")
        self.traverse(node.end)
        if node.step:
            self._source.append(" by ")
            self.traverse(node.step)
        with self.block():
            self.traverse(node.body)

    def visit_ForIn(self, node: ast.ForIn):
        self._source.append("for ")
        self.traverse(node.target)
        self._source.append(" in ")
        self.traverse(node.iter)
        with self.block():
            self.traverse(node.body)

    def visit_While(self, node: ast.While):
        self._source.append("while ")
        self.traverse(node.test)
        with self.block():
            self.traverse(node.body)

    def visit_If(self, node: ast.If):
        self._source.append("if ")
        self.traverse(node.test)
        with self.block():
            self.traverse(node.body)
        while (
            node.orelse
            and len(node.orelse) == 1
            and isinstance(node.orelse[0], ast.Expr)
            and isinstance(node.orelse[0].value, ast.If)
        ):
            node = node.orelse[0].value
            self.fill("else if ")
            self.traverse(node.test)
            with self.block():
                self.traverse(node.body)
        if node.orelse:
            self.fill("else")
            with self.block():
                self.traverse(node.orelse)

    def visit_Switch(self, node: ast.Switch):
        self._source.append("switch")
        if node.subject:
            self._source.append(" ")
            self.traverse(node.subject)
        with self.block():
            self.traverse(node.cases)

    def visit_Import(self, node: ast.Import):
        self.fill()
        src = self._source
        src.append("import ")
        src.append(node.namespace)
        src.append("/")
        src.append(node.name)
        src.append("/")
        src.append(str(node.version))
        if node.alias:
            src.append(" as ")
            src.append(node.alias)

    def visit_Expr(self, node: ast.Expr):
        self.fill()
        self.traverse(node.value)

    def visit_Break(self, node: ast.Break):
        self.fill("break")

    def visit_Continue(self, node: ast.Continue):
        self.fill("continue")

    # Type-keyed operator tables (avoid per-node __class__.__name__ strings).
    boolops: ClassVar = {
        ast.And: "and",
        ast.Or: "or",
    }

    boolop_precedence: ClassVar = {
        "and": Precedence.AND,
        "or": Precedence.OR,
    }

    # Spaced forms for hot binary/bool ops.
    _BOOLOP_SPACED: ClassVar = {
        ast.And: " and ",
        ast.Or: " or ",
    }

    def visit_BoolOp(self, node: ast.BoolOp):
        op_type = type(node.op)
        operator = self.boolops[op_type]
        operator_precedence = self.boolop_precedence[operator]
        spaced = self._BOOLOP_SPACED[op_type]

        def increasing_level_traverse(child):
            nonlocal operator_precedence
            operator_precedence = operator_precedence.next()
            self._precedences[child] = operator_precedence
            self.traverse(child)

        with self.require_parens(operator_precedence, node):
            self.interleave(lambda: self._source.append(spaced), increasing_level_traverse, node.values)

    binop: ClassVar = {
        ast.Add: "+",
        ast.Sub: "-",
        ast.Mult: "*",
        ast.Div: "/",
        ast.Mod: "%",
        ast.BitAnd: "&",
        ast.BitOr: "|",
        ast.BitXor: "^",
        ast.LShift: "<<",
        ast.RShift: ">>",
    }

    binop_precedence: ClassVar = {
        "+": Precedence.ARITH,
        "-": Precedence.ARITH,
        "*": Precedence.TERM,
        "/": Precedence.TERM,
        "%": Precedence.TERM,
        "&": Precedence.BITAND,
        "|": Precedence.BITOR,
        "^": Precedence.BITXOR,
        "<<": Precedence.SHIFT,
        ">>": Precedence.SHIFT,
    }

    _BINOP_SPACED: ClassVar = {
        ast.Add: " + ",
        ast.Sub: " - ",
        ast.Mult: " * ",
        ast.Div: " / ",
        ast.Mod: " % ",
        ast.BitAnd: " & ",
        ast.BitOr: " | ",
        ast.BitXor: " ^ ",
        ast.LShift: " << ",
        ast.RShift: " >> ",
    }

    def visit_BinOp(self, node: ast.BinOp):
        op_type = type(node.op)
        operator = self.binop[op_type]
        operator_precedence = self.binop_precedence[operator]
        with self.require_parens(operator_precedence, node):
            left_precedence = operator_precedence
            right_precedence = operator_precedence.next()
            self._precedences[node.left] = left_precedence
            self.traverse(node.left)
            self._source.append(self._BINOP_SPACED[op_type])
            self._precedences[node.right] = right_precedence
            self.traverse(node.right)

    unop: ClassVar = {
        ast.Not: "not",
        ast.UAdd: "+",
        ast.USub: "-",
        ast.Invert: "~",
    }

    unop_precedence: ClassVar = {
        "not": Precedence.NOT,
        "+": Precedence.FACTOR,
        "-": Precedence.FACTOR,
        "~": Precedence.FACTOR,
    }

    def visit_UnaryOp(self, node: ast.UnaryOp):
        operator = self.unop[type(node.op)]
        operator_precedence = self.unop_precedence[operator]
        with self.require_parens(operator_precedence, node):
            self._source.append(operator)
            if isinstance(node.op, ast.Not):
                self._source.append(" ")
            self._precedences[node.operand] = operator_precedence
            self.traverse(node.operand)

    def visit_Conditional(self, node: ast.Conditional):
        with self.require_parens(Precedence.TEST, node):
            next_prec = Precedence.TEST.next()
            prec = self._precedences
            prec[node.test] = next_prec
            prec[node.body] = next_prec
            self.traverse(node.test)
            self._source.append(" ? ")
            self.traverse(node.body)
            self._source.append(" : ")
            prec[node.orelse] = Precedence.TEST
            self.traverse(node.orelse)

    cmpops: ClassVar = {
        ast.Eq: "==",
        ast.NotEq: "!=",
        ast.Lt: "<",
        ast.LtE: "<=",
        ast.Gt: ">",
        ast.GtE: ">=",
    }

    cmpop_precedence: ClassVar = {
        "==": Precedence.EQ,
        "!=": Precedence.EQ,
        "<": Precedence.INEQ,
        "<=": Precedence.INEQ,
        ">": Precedence.INEQ,
        ">=": Precedence.INEQ,
    }

    _CMPOP_SPACED: ClassVar = {
        ast.Eq: " == ",
        ast.NotEq: " != ",
        ast.Lt: " < ",
        ast.LtE: " <= ",
        ast.Gt: " > ",
        ast.GtE: " >= ",
    }

    def visit_Compare(self, node: ast.Compare):
        with self.require_parens(Precedence.CMP, node):
            next_prec = Precedence.CMP.next()
            prec = self._precedences
            prec[node.left] = next_prec
            for c in node.comparators:
                prec[c] = next_prec
            self.traverse(node.left)
            src = self._source
            spaced = self._CMPOP_SPACED
            for o, e in zip(node.ops, node.comparators, strict=True):
                src.append(spaced[type(o)])
                self.traverse(e)

    def visit_Call(self, node: ast.Call):
        self._precedences[node.func] = Precedence.ATOM
        self.traverse(node.func)
        with self.delimit("(", ")"):
            if node.args:
                self.items_view(self.traverse, node.args)

    def visit_Constant(self, node: ast.Constant):
        src = self._source
        if node.kind:
            src.append(node.value)
            return
        value = node.value
        # Identity checks for bools (bool is int subclass; must precede numeric paths).
        if value is True:
            src.append("true")
        elif value is False:
            src.append("false")
        elif isinstance(value, str):
            # Prefer Pine v6 triple-quoted form when the value contains newlines so
            # unparse preserves readable multiline literals. Fall back to escaped
            # single-line form otherwise (and always when the value itself contains
            # both quote styles that would break triple delimiters).
            if "\n" in value or "\r" in value:
                if '"""' not in value:
                    src.append('"""')
                    src.append(value)
                    src.append('"""')
                elif "'''" not in value:
                    src.append("'''")
                    src.append(value)
                    src.append("'''")
                else:
                    # Both triple delimiters appear in content — escape as JSON.
                    src.append(json.dumps(value, ensure_ascii=False))
            elif '"' in value and "'" not in value:
                src.append(repr(value))
            else:
                src.append(json.dumps(value, ensure_ascii=False))
        else:
            src.append(repr(value))

    def visit_Attribute(self, node: ast.Attribute):
        self._precedences[node.value] = Precedence.ATOM
        self.traverse(node.value)
        src = self._source
        src.append(".")
        src.append(node.attr)

    def visit_Subscript(self, node: ast.Subscript):
        self.traverse(node.value)
        with self.delimit("[", "]"):
            if node.slice:
                if isinstance(node.slice, ast.Tuple):
                    self.items_view(self.traverse, node.slice.elts)
                else:
                    self.traverse(node.slice)

    def visit_Name(self, node: ast.Name):
        self._source.append(node.id)

    def visit_Tuple(self, node: ast.Tuple):
        with self.delimit("[", "]"):
            if node.elts:
                self.items_view(self.traverse, node.elts)

    def visit_Qualify(self, node: ast.Qualify):
        self.traverse(node.qualifier)
        self._source.append(" ")
        self.traverse(node.value)

    def visit_Specialize(self, node: ast.Specialize):
        self.traverse(node.value)
        with self.delimit("<", ">"):
            if node.args:
                if isinstance(node.args, ast.Tuple):
                    self.items_view(self.traverse, node.args.elts)
                else:
                    self.traverse(node.args)

    def visit_Var(self, node: ast.Var):
        self._source.append("var")

    def visit_VarIp(self, node: ast.VarIp):
        self._source.append("varip")

    def visit_Const(self, node: ast.Const):
        self._source.append("const")

    def visit_Input(self, node: ast.Input):
        self._source.append("input")

    def visit_Sipmle(self, node: ast.Simple):
        self._source.append("simple")

    def visit_Series(self, node: ast.Series):
        self._source.append("series")

    def visit_And(self, node: ast.And):
        self._source.append("and")

    def visit_Or(self, node: ast.Or):
        self._source.append("or")

    def visit_Add(self, node: ast.Add):
        self._source.append("+")

    def visit_Sub(self, node: ast.Sub):
        self._source.append("-")

    def visit_Mult(self, node: ast.Mult):
        self._source.append("*")

    def visit_Div(self, node: ast.Div):
        self._source.append("/")

    def visit_Mod(self, node: ast.Mod):
        self._source.append("%")

    def visit_Not(self, node: ast.Not):
        self._source.append("not")

    def visit_UAdd(self, node: ast.UAdd):
        self._source.append("+")

    def visit_USub(self, node: ast.USub):
        self._source.append("-")

    def visit_Eq(self, node: ast.Eq):
        self._source.append("==")

    def visit_NotEq(self, node: ast.NotEq):
        self._source.append("!=")

    def visit_Lt(self, node: ast.Lt):
        self._source.append("<")

    def visit_LtE(self, node: ast.LtE):
        self._source.append("<=")

    def visit_Gt(self, node: ast.Gt):
        self._source.append(">")

    def visit_GtE(self, node: ast.GtE):
        self._source.append(">=")

    def visit_Param(self, node: ast.Param):
        if node.type:
            self.traverse(node.type)
            self._source.append(" ")
        self._source.append(node.name)
        if node.default:
            self._source.append("=")
            self.traverse(node.default)

    def visit_Arg(self, node: ast.Arg):
        if node.name:
            src = self._source
            src.append(node.name)
            src.append("=")
        self.traverse(node.value)

    def visit_Case(self, node: ast.Case):
        self.fill()
        if node.pattern:
            self.traverse(node.pattern)
            self._source.append(" ")
        self._source.append("=> ")
        if len(node.body) == 1 and isinstance(node.body[0], ast.Expr):
            self.traverse(node.body[0].value)
        else:
            with self.block():
                self.traverse(node.body)

    def visit_Comment(self, node: ast.Comment):
        self.fill(node.value)


class _BufferedCM:
    """Swap the active source buffer for the duration of the context."""

    __slots__ = ("_buf", "_orig", "_u")

    def __init__(self, unparser: NodeUnparser, buffer: list):
        self._u = unparser
        self._buf = buffer
        self._orig = None

    def __enter__(self):
        self._orig = self._u._source
        self._u._source = self._buf
        return self._buf

    def __exit__(self, *exc):
        self._u._source = self._orig
        return False


# Thread-local reused unparser: keeps type-visitor cache warm across calls.
_tls = threading.local()


def unparse_node(node: ast.AST) -> str:
    """Unparse *node* to Pine source, reusing a per-thread NodeUnparser."""
    u = getattr(_tls, "unparser", None)
    if u is None:
        u = NodeUnparser()
        _tls.unparser = u
    return u.visit(node)
