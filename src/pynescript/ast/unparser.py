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

"""AST → Pine Script source code generator (pretty-printer / unparser).

Turns :class:`~pynescript.ast.node.AST` trees into syntactically valid Pine
Script text. Used for formatting (LSP), CLI round-trips, tests, and debugging.

Public entry points
-------------------
* **Preferred API:** :func:`pynescript.ast.helper.unparse` (also re-exported as
  ``pynescript.unparse`` / ``pynescript.ast.unparse``). That thin wrapper calls
  :func:`unparse_node` in this module.
* **This module:** :func:`unparse_node` and :class:`NodeUnparser` for callers
  that already depend on the unparser package (e.g. LSP formatting).

``helper.unparse`` / ``unparse_node`` reuse a **per-thread**
:class:`NodeUnparser` so the type→visitor cache stays warm. Prefer those over
constructing a fresh unparser on every call unless you need a dedicated
instance.

Round-trip notes
----------------
* **Goal:** ``unparse(parse(source))`` yields readable, re-parsable Pine that
  preserves program structure (statements, expressions, operator association).
* **Not a byte-identical pretty-printer:** whitespace, comment placement, and
  some surface forms are normalized (indent is 4 spaces; operators are spaced).
* **Precedence:** binary / unary / boolean / comparison / ternary nodes record
  child precedence so parentheses appear only when needed to keep evaluation
  order. Binary ops assign ``precedence.next()`` on the RHS so chains stay
  left-associative without redundant parens on the left.
* **Multiline strings (v6):** string constants containing newlines prefer
  Pine triple-quoted forms (double or single) so output stays readable;
  otherwise escaped single-line forms are used.
* **Version / annotation lines:** script- and declaration-level ``annotations``
  (e.g. ``//@version=6``) are emitted as full lines before the body—not as
  free-floating comments elsewhere.
* **Known structural limits** live outside this file (e.g. AST fields the
  parser/builder does not populate cannot reappear on unparse). Corpus tests
  in ``tests/test_parse_and_unparse.py`` guard re-parse stability.

Main types
----------
* :class:`Precedence` — operator binding levels for parenthesization.
* :class:`NodeUnparser` — :class:`~pynescript.ast.visitor.NodeVisitor` that
  appends source fragments and implements ``visit_*`` for each AST node kind.
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

# Characters that force the slow json.dumps / repr path for string constants.
# Plain strings without these are emitted as "..." without encoding overhead.
_STR_SPECIAL: frozenset[str] = frozenset('\\"\n\r\t\x08\x0c')


def _is_plain_string(value: str) -> bool:
    """True when *value* needs no escapes inside double quotes."""
    special = _STR_SPECIAL
    for ch in value:
        if ch in special:
            return False
    return True


def _quote_plain_string(value: str) -> str:
    """Double-quote a string known to need no escapes (matches json.dumps form)."""
    return '"' + value + '"'


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
    """Operator precedence levels for parenthesization decisions.

    Higher enum values bind **tighter**. A child is wrapped in ``(...)`` when
    its assigned precedence is **strictly greater** than the parent context
    (see :meth:`NodeUnparser.require_parens` / :meth:`NodeUnparser._needs_parens`).
    Default for unset nodes is :attr:`TEST` (loosest), so bare roots need no
    outer parens.

    :meth:`next` returns the next tighter level (or self at the top). Binary
    operators use the current level for the left operand and ``next()`` for
    the right so chains associate left-to-right without extra parens on the
    left; boolean chains raise the level per value for the same reason.
    """

    TEST = auto()  # '?', ':' - ternary conditional (lowest / loosest)
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
    ATOM = auto()  # Highest / tightest — literals, names, attr, calls

    def next(self) -> Precedence:
        """Return the next tighter precedence, or *self* if already :attr:`ATOM`."""
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
    """Pretty-print a Pine Script AST by appending fragments to an internal buffer.

    Subclass of :class:`~pynescript.ast.visitor.NodeVisitor`. Most callers should
    use :func:`unparse_node` or :func:`pynescript.ast.helper.unparse` rather than
    constructing this class; those entry points reuse a thread-local instance.

    Lifecycle
    ---------
    :meth:`visit` is the full-document API: it **resets** ``_source``,
    ``_precedences``, and ``_indent``, walks the tree via :meth:`traverse`, and
    returns ``"".join(_source)``. Nested walkers should call :meth:`traverse`
    (or a ``visit_*`` method) so they do not wipe the buffer mid-render.

    Formatting model
    ----------------
    * **Indent:** 4 spaces per :meth:`block` level; new statements usually start
      with :meth:`fill` (newline + indent), then tokens via :meth:`write` /
      direct ``_source.append``.
    * **Precedence:** :meth:`set_precedence` / tables on expression nodes drive
      :meth:`require_parens` so output keeps the same binding as the AST.
    * **visit_* methods:** one per AST node class name; they encode Pine surface
      syntax (``=>`` bodies, ``else if`` chains, ``var``/``varip``, etc.). Only
      non-obvious ones carry extra docstrings below.

    Attributes (instance)
    ---------------------
    ``_source``
        List of string chunks assembled by :meth:`visit`.
    ``_precedences``
        Map of AST node → :class:`Precedence` for parenthesization.
    ``_indent``
        Current block depth (integer).
    ``_type_visitor_cache``
        ``type`` → ``visit_*`` callable (avoids string-based dispatch).
    """

    # ruff: noqa: N802

    def __init__(self) -> None:
        """Create an empty unparser (empty buffer, zero indent, cold type cache)."""
        super().__init__()  # Initialize visitor cache
        self._source: list[str] = []
        self._precedences: dict = {}
        self._indent = 0
        # Type-object keyed dispatch (faster than class-name strings).
        self._type_visitor_cache: dict[type, object] = {}
        # Scratch for BoolOp interleave (avoids per-call lambda).
        self._boolop_spaced: str = " and "

    def interleave(self, inter, f, seq) -> None:
        """Call *f* on each item of *seq*, invoking *inter* between items.

        Empty *seq* is a no-op. Used for comma-separated lists and boolean
        chains where the separator is a callback (not a fixed string).
        """
        seq = iter(seq)
        try:
            f(next(seq))
        except StopIteration:
            pass
        else:
            for x in seq:
                inter()
                f(x)

    def _write_comma_space(self) -> None:
        """Append comma+space — bound method used as :meth:`interleave` separator."""
        self._source.append(", ")

    def _write_boolop_spaced(self) -> None:
        """Append the current bool-op token (`` and `` / `` or ``) from ``_boolop_spaced``."""
        self._source.append(self._boolop_spaced)

    def items_view(self, traverser, items, *, single: bool = False) -> None:
        """Emit a comma-separated sequence of *items* via *traverser*.

        Fast-paths zero/one/two elements to avoid iterator overhead on hot
        call/tuple sites. If *single* is true and there is exactly one item,
        append a trailing comma (Python-style singleton tuple form; unused for
        typical Pine lists but kept for API flexibility).
        """
        n = len(items)
        if n == 1:
            traverser(items[0])
            if single:
                self._source.append(",")
        elif n == 0:
            return
        elif n == 2:  # noqa: PLR2004  # hot arity fast-path for Call/tuple
            # Common Call/tuple arity: avoid interleave iterator overhead.
            traverser(items[0])
            self._source.append(", ")
            traverser(items[1])
        else:
            self.interleave(self._write_comma_space, traverser, items)

    def maybe_newline(self) -> None:
        """Append a newline only if the buffer is non-empty (avoid leading blank)."""
        if self._source:
            self._source.append("\n")

    def fill(self, text: str = "") -> None:
        """Start a new indented line, optionally writing *text* after the indent.

        If the buffer already has content, inserts ``\\n`` first, then the
        current indent prefix (4 spaces × ``_indent``), then *text* when given.
        Statement-level visitors use this so each stmt begins at column 0 of its
        block (including bare indent when *text* is empty).
        """
        src = self._source
        if src:
            src.append("\n")
        ind = self._indent
        cache = _INDENT_CACHE
        prefix = cache[ind] if ind < len(cache) else "    " * ind
        if text:
            src.append(prefix + text)
        else:
            src.append(prefix)

    def write(self, *text: str) -> None:
        """Append one or more string fragments to the source buffer (no newline)."""
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
        """Temporarily redirect ``_source`` into *buffer* (context manager).

        Rarely used; kept for API compatibility. On exit, restores the previous
        buffer so nested capture does not leak.
        """
        # Kept for API compatibility; rarely used. Manual enter/exit pair.
        if buffer is None:
            buffer = []
        return _BufferedCM(self, buffer)

    def block(self, *, extra=None):
        """Context manager: increase indent by one for a statement body.

        If *extra* is set, it is appended before indenting (legacy hook). Body
        visitors typically open a :meth:`block` after a header line such as
        ``if cond`` or ``name(args) =>``.
        """
        return _BlockCM(self, extra)

    def delimit(self, start, end):
        """Context manager: write *start* on enter and *end* on exit (e.g. parens)."""
        return _DelimitCM(self._source, start, end)

    def delimit_if(self, start, end, condition):
        """Like :meth:`delimit` when *condition* is true; otherwise a no-op CM."""
        if condition:
            return _DelimitCM(self._source, start, end)
        return _NULL_CM

    def require_parens(self, precedence, node):
        """Return a paren-delimiting CM when *node* binds looser than *precedence*.

        Uses ``_precedences[node]`` (default :attr:`Precedence.TEST`). Compare
        is **strict greater than** parent level: equal precedence does not
        parenthesize, matching left-associative chaining rules set by callers.
        """
        if self._precedences.get(node, Precedence.TEST) > precedence:
            return _DelimitCM(self._source, "(", ")")
        return _NULL_CM

    def _needs_parens(self, precedence, node) -> bool:
        """Same test as :meth:`require_parens` without allocating a context manager.

        Hot expression paths (``BoolOp``, ``BinOp``, …) branch on this and append
        ``(`` / ``)`` manually to avoid ``_DelimitCM`` allocation.
        """
        return self._precedences.get(node, Precedence.TEST) > precedence

    def get_precedence(self, node) -> Precedence:
        """Return the precedence assigned to *node*, or :attr:`Precedence.TEST`."""
        return self._precedences.get(node, Precedence.TEST)

    def set_precedence(self, precedence, *nodes) -> None:
        """Assign *precedence* to each of *nodes* before they are traversed."""
        prec = self._precedences
        for node in nodes:
            prec[node] = precedence

    def traverse(self, node) -> None:
        """Walk *node* (or each element if *node* is a ``list``) without resetting.

        Unlike :meth:`visit`, does **not** clear the buffer—safe for nested
        calls. Dispatches via ``_type_visitor_cache`` to ``visit_<ClassName>``.
        """
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

    def visit(self, node) -> str:
        """Unparse *node* to a full source string (public instance entry point).

        Resets buffer, precedence map, and indent so a single instance can be
        reused safely across documents. Prefer :func:`unparse_node` for the
        shared thread-local instance used by ``helper.unparse``.
        """
        # Full reset so a single NodeUnparser instance can be reused safely.
        # clear() reuses list/dict capacity across calls (less allocator churn).
        src = self._source
        src.clear()
        self._precedences.clear()
        self._indent = 0
        self.traverse(node)
        return "".join(src)

    def visit_Script(self, node: ast.Script) -> None:
        """Emit top-level annotations (e.g. ``//@version=6``) then the body.

        Each annotation string is written as its own filled line so version and
        other directive comments stay above the first statement—matching how the
        parser attaches them to :class:`~pynescript.ast.node.Script`.
        """
        if node.annotations:
            for annotation in node.annotations:
                self.fill(annotation)
        self.traverse(node.body)

    def visit_Expression(self, node: ast.Expression) -> None:
        """Unparse a single expression root (no script wrapper or trailing newline)."""
        self.traverse(node.body)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Emit ``export``/``method`` *name* ``(args) =>`` body.

        Single-statement bodies that are :class:`~pynescript.ast.node.Expr` are
        inlined after ``=>`` (expression form). Multi-statement bodies open a
        :meth:`block` (indented multi-line form). Leading *annotations* are
        emitted as filled lines before the signature.
        """
        self.fill()
        if node.annotations:
            for annotation in node.annotations:
                self.fill(annotation)
            self.fill()
        src = self._source
        if node.export:
            src.append("export ")
        if node.method:
            src.append("method ")
        src.append(node.name)
        src.append("(")
        if node.args:
            self.items_view(self.traverse, node.args)
        src.append(") => ")
        body = node.body
        if len(body) == 1 and body[0].__class__ is ast.Expr:
            self.traverse(body[0].value)
        else:
            with self.block():
                self.traverse(body)

    def visit_TypeDef(self, node: ast.TypeDef) -> None:
        """Emit ``export type Name`` with fields first, then ``method`` members.

        Reorders the type body so non-method statements (fields) appear before
        method :class:`~pynescript.ast.node.FunctionDef` nodes for stable,
        readable output regardless of original AST order.
        """
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

    def visit_Assign(self, node: ast.Assign) -> None:
        """Emit declaration/assignment: annotations, optional ``export``, mode, type, ``=``.

        *annotations* (compiler/version-style lines attached to the declaration)
        are filled before the statement. *mode* is ``var`` / ``varip`` / ``const``
        / etc.; *export* supports library ``export`` bindings when present.
        """
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

    def visit_If(self, node: ast.If) -> None:
        """Emit ``if`` / ``else if`` / ``else`` with indented bodies.

        Nested ``else`` branches that are a single expression-wrapped ``If`` are
        flattened to ``else if`` chains so round-tripped source matches idiomatic
        Pine rather than nested ``else`` + ``if`` blocks.
        """
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

    # Type → precedence (skip string intermediate lookup on hot path).
    _BOOLOP_PREC: ClassVar = {
        ast.And: Precedence.AND,
        ast.Or: Precedence.OR,
    }

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        """Emit ``and`` / ``or`` chains with left-associative parenthesization.

        Each successive operand gets a **tighter** precedence via
        :meth:`Precedence.next` so same-operator chains do not re-parenthesize
        needlessly while mixed nesting still wraps correctly. Saves/restores
        ``_boolop_spaced`` so nested bool-ops do not clobber the interleave token.
        """
        op_type = type(node.op)
        operator_precedence = self._BOOLOP_PREC[op_type]
        # Save/restore so nested BoolOps don't clobber the interleave token.
        prev_spaced = self._boolop_spaced
        self._boolop_spaced = self._BOOLOP_SPACED[op_type]
        prec_level = operator_precedence
        needs = self._needs_parens(operator_precedence, node)
        src = self._source
        if needs:
            src.append("(")

        def increasing_level_traverse(child):
            nonlocal prec_level
            prec_level = prec_level.next()
            self._precedences[child] = prec_level
            self.traverse(child)

        try:
            self.interleave(self._write_boolop_spaced, increasing_level_traverse, node.values)
        finally:
            self._boolop_spaced = prev_spaced
        if needs:
            src.append(")")

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

    _BINOP_PREC: ClassVar = {
        ast.Add: Precedence.ARITH,
        ast.Sub: Precedence.ARITH,
        ast.Mult: Precedence.TERM,
        ast.Div: Precedence.TERM,
        ast.Mod: Precedence.TERM,
        ast.BitAnd: Precedence.BITAND,
        ast.BitOr: Precedence.BITOR,
        ast.BitXor: Precedence.BITXOR,
        ast.LShift: Precedence.SHIFT,
        ast.RShift: Precedence.SHIFT,
    }

    def visit_BinOp(self, node: ast.BinOp) -> None:
        """Emit spaced binary operators with left-associative precedence rules.

        Left child keeps the operator's precedence; right child uses
        :meth:`Precedence.next` so ``a - b - c`` prints without parens while
        ``a - (b - c)`` still parenthesizes the right subtree when required.
        """
        op_type = type(node.op)
        operator_precedence = self._BINOP_PREC[op_type]
        needs = self._needs_parens(operator_precedence, node)
        src = self._source
        if needs:
            src.append("(")
        left_precedence = operator_precedence
        right_precedence = operator_precedence.next()
        prec = self._precedences
        prec[node.left] = left_precedence
        self.traverse(node.left)
        src.append(self._BINOP_SPACED[op_type])
        prec[node.right] = right_precedence
        self.traverse(node.right)
        if needs:
            src.append(")")

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

    _UNOP_TOKEN: ClassVar = {
        ast.Not: "not ",
        ast.UAdd: "+",
        ast.USub: "-",
        ast.Invert: "~",
    }

    _UNOP_PREC: ClassVar = {
        ast.Not: Precedence.NOT,
        ast.UAdd: Precedence.FACTOR,
        ast.USub: Precedence.FACTOR,
        ast.Invert: Precedence.FACTOR,
    }

    def visit_UnaryOp(self, node: ast.UnaryOp) -> None:
        """Emit unary ``not`` / ``+`` / ``-`` / ``~``; ``not`` includes a trailing space."""
        op_type = type(node.op)
        operator_precedence = self._UNOP_PREC[op_type]
        needs = self._needs_parens(operator_precedence, node)
        src = self._source
        if needs:
            src.append("(")
        src.append(self._UNOP_TOKEN[op_type])
        self._precedences[node.operand] = operator_precedence
        self.traverse(node.operand)
        if needs:
            src.append(")")

    def visit_Conditional(self, node: ast.Conditional) -> None:
        """Emit ternary ``test ? body : orelse`` (loosest :attr:`Precedence.TEST`).

        *test* and *body* use a tighter level so nested ternaries in those arms
        parenthesize; *orelse* stays at :attr:`~Precedence.TEST` so
        ``a ? b : c ? d : e`` associates rightward without extra parens on the
        trailing conditional.
        """
        needs = self._needs_parens(Precedence.TEST, node)
        src = self._source
        if needs:
            src.append("(")
        next_prec = Precedence.TEST.next()
        prec = self._precedences
        prec[node.test] = next_prec
        prec[node.body] = next_prec
        self.traverse(node.test)
        src.append(" ? ")
        self.traverse(node.body)
        src.append(" : ")
        prec[node.orelse] = Precedence.TEST
        self.traverse(node.orelse)
        if needs:
            src.append(")")

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

    def visit_Compare(self, node: ast.Compare) -> None:
        """Emit chained comparisons (``a < b <= c``) with spaced operators."""
        needs = self._needs_parens(Precedence.CMP, node)
        src = self._source
        if needs:
            src.append("(")
        next_prec = Precedence.CMP.next()
        prec = self._precedences
        prec[node.left] = next_prec
        for c in node.comparators:
            prec[c] = next_prec
        self.traverse(node.left)
        spaced = self._CMPOP_SPACED
        for o, e in zip(node.ops, node.comparators, strict=True):
            src.append(spaced[type(o)])
            self.traverse(e)
        if needs:
            src.append(")")

    def visit_Call(self, node: ast.Call) -> None:
        """Emit ``func(args)``; *func* is forced to :attr:`Precedence.ATOM`."""
        self._precedences[node.func] = Precedence.ATOM
        self.traverse(node.func)
        # Manual delimit — Call is the hottest paren site; skip _DelimitCM alloc.
        src = self._source
        src.append("(")
        args = node.args
        if args:
            self.items_view(self.traverse, args)
        src.append(")")

    def visit_Constant(self, node: ast.Constant) -> None:
        """Emit literals: bools as ``true``/``false``, numbers via ``repr``, strings.

        **String formatting rules (v6-aware):**

        * If ``node.kind`` is set, *value* is emitted raw (pre-formatted token).
        * Multiline values (newline / CR) prefer Pine triple-quoted forms
          (triple double-quotes first, then triple single-quotes) so
          round-trips stay readable. When the content contains both triple
          delimiters, fall back to :func:`json.dumps` escapes on one line.
        * Single-line plain strings (no escapes needed) use double quotes via
          the fast path; strings with only double quotes use :func:`repr`
          (single-quoted); otherwise JSON double-quoted escaping.
        * Booleans use identity checks (``is True`` / ``is False``) before
          numeric ``repr`` because ``bool`` subclasses ``int``.
        """
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
        elif value.__class__ is str:
            # Prefer Pine v6 triple-quoted form when the value contains newlines so
            # unparse preserves readable multiline literals. Fall back to escaped
            # single-line form otherwise (and always when the value itself contains
            # both quote styles that would break triple delimiters).
            if "\n" in value or "\r" in value:
                if '"""' not in value:
                    src.append('"""' + value + '"""')
                elif "'''" not in value:
                    src.append("'''" + value + "'''")
                else:
                    # Both triple delimiters appear in content — escape as JSON.
                    src.append(json.dumps(value, ensure_ascii=False))
            elif _is_plain_string(value):
                # Fast path: plain string → "..." (byte-identical to json.dumps).
                src.append(_quote_plain_string(value))
            elif '"' in value and "'" not in value:
                src.append(repr(value))
            else:
                src.append(json.dumps(value, ensure_ascii=False))
        else:
            src.append(repr(value))

    def visit_Attribute(self, node: ast.Attribute):
        self._precedences[node.value] = Precedence.ATOM
        self.traverse(node.value)
        self._source.append("." + node.attr)

    def visit_Subscript(self, node: ast.Subscript):
        self.traverse(node.value)
        src = self._source
        src.append("[")
        sl = node.slice
        if sl:
            if sl.__class__ is ast.Tuple:
                self.items_view(self.traverse, sl.elts)
            else:
                self.traverse(sl)
        src.append("]")

    def visit_Name(self, node: ast.Name):
        self._source.append(node.id)

    def visit_Tuple(self, node: ast.Tuple):
        src = self._source
        src.append("[")
        elts = node.elts
        if elts:
            self.items_view(self.traverse, elts)
        src.append("]")

    def visit_Qualify(self, node: ast.Qualify):
        self.traverse(node.qualifier)
        self._source.append(" ")
        self.traverse(node.value)

    def visit_Specialize(self, node: ast.Specialize):
        self.traverse(node.value)
        src = self._source
        src.append("<")
        args = node.args
        if args:
            if args.__class__ is ast.Tuple:
                self.items_view(self.traverse, args.elts)
            else:
                self.traverse(args)
        src.append(">")

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
        name = node.name
        if name:
            self._source.append(name + "=")
        self.traverse(node.value)

    def visit_Case(self, node: ast.Case) -> None:
        """Emit a switch arm: optional *pattern*, then ``=>`` expression or block.

        Same single-:class:`~pynescript.ast.node.Expr` inlining rule as
        :meth:`visit_FunctionDef` (expression form vs indented multi-statement).
        """
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

    def visit_Comment(self, node: ast.Comment) -> None:
        """Emit a full-line comment at the current indent (``node.value`` as stored)."""
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
    """Convert *node* to Pine Script source, reusing a per-thread :class:`NodeUnparser`.

    This is the implementation behind :func:`pynescript.ast.helper.unparse`.
    Thread-local reuse keeps ``_type_visitor_cache`` warm without sharing
    mutable buffer state across threads (:meth:`NodeUnparser.visit` still
    resets the buffer each call).

    Args:
        node: Any AST root (typically :class:`~pynescript.ast.node.Script` or
            :class:`~pynescript.ast.node.Expression`).

    Returns:
        Syntactically valid Pine Script source string for *node*.
    """
    u = getattr(_tls, "unparser", None)
    if u is None:
        u = NodeUnparser()
        _tls.unparser = u
    return u.visit(node)
