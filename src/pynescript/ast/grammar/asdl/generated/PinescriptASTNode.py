from __future__ import annotations
import builtins as _builtins
import dataclasses as _dataclasses
import typing as _typing

identifier = str
int = int
string = str | bytes
constant = str | bytes | int | float | complex | bool | tuple | frozenset | None | type(...)


class AST:
    __slots__ = ("_pine_call_site", "_pine_site_id")
    _fields: _typing.ClassVar[_builtins.list[_builtins.str]] = []
    _attributes: _typing.ClassVar[_builtins.list[_builtins.str]] = []


@_dataclasses.dataclass(slots=True)
class mod(AST):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Script(mod):
    body: _builtins.list[stmt] = _dataclasses.field(default_factory=_builtins.list)
    annotations: _builtins.list[string] = _dataclasses.field(default_factory=_builtins.list)
    _fields: _typing.ClassVar[_builtins.list[_builtins.str]] = ["body", "annotations"]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Expression(mod):
    body: expr = _dataclasses.field(default=None)
    _fields: _typing.ClassVar[_builtins.list[_builtins.str]] = ["body"]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class stmt(AST):
    lineno: int = _dataclasses.field(default=None, repr=False, compare=False, kw_only=True)
    col_offset: int = _dataclasses.field(default=None, repr=False, compare=False, kw_only=True)
    end_lineno: int | None = _dataclasses.field(default=None, repr=False, compare=False, kw_only=True)
    end_col_offset: int | None = _dataclasses.field(default=None, repr=False, compare=False, kw_only=True)
    _attributes: _typing.ClassVar[_builtins.list[_builtins.str]] = [
        "lineno",
        "col_offset",
        "end_lineno",
        "end_col_offset",
    ]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class FunctionDef(stmt):
    name: identifier = _dataclasses.field(default=None)
    args: _builtins.list[param] = _dataclasses.field(default_factory=_builtins.list)
    body: _builtins.list[stmt] = _dataclasses.field(default_factory=_builtins.list)
    returns: expr | None = _dataclasses.field(default=None)
    method: int | None = _dataclasses.field(default=None)
    export: int | None = _dataclasses.field(default=None)
    annotations: _builtins.list[string] = _dataclasses.field(default_factory=_builtins.list)
    _fields: _typing.ClassVar[_builtins.list[_builtins.str]] = [
        "name",
        "args",
        "body",
        "returns",
        "method",
        "export",
        "annotations",
    ]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class TypeDef(stmt):
    name: identifier = _dataclasses.field(default=None)
    body: _builtins.list[stmt] = _dataclasses.field(default_factory=_builtins.list)
    export: int | None = _dataclasses.field(default=None)
    annotations: _builtins.list[string] = _dataclasses.field(default_factory=_builtins.list)
    _fields: _typing.ClassVar[_builtins.list[_builtins.str]] = ["name", "body", "export", "annotations"]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class EnumDef(stmt):
    name: identifier = _dataclasses.field(default=None)
    body: _builtins.list[stmt] = _dataclasses.field(default_factory=_builtins.list)
    export: int | None = _dataclasses.field(default=None)
    annotations: _builtins.list[string] = _dataclasses.field(default_factory=_builtins.list)
    _fields: _typing.ClassVar[_builtins.list[_builtins.str]] = ["name", "body", "export", "annotations"]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Assign(stmt):
    target: expr = _dataclasses.field(default=None)
    value: expr | None = _dataclasses.field(default=None)
    type: expr | None = _dataclasses.field(default=None)
    mode: decl_mode | None = _dataclasses.field(default=None)
    export: int | None = _dataclasses.field(default=None)
    annotations: _builtins.list[string] = _dataclasses.field(default_factory=_builtins.list)
    _fields: _typing.ClassVar[_builtins.list[_builtins.str]] = [
        "target",
        "value",
        "type",
        "mode",
        "export",
        "annotations",
    ]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class ReAssign(stmt):
    target: expr = _dataclasses.field(default=None)
    value: expr = _dataclasses.field(default=None)
    _fields: _typing.ClassVar[_builtins.list[_builtins.str]] = ["target", "value"]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class AugAssign(stmt):
    target: expr = _dataclasses.field(default=None)
    op: operator = _dataclasses.field(default=None)
    value: expr = _dataclasses.field(default=None)
    _fields: _typing.ClassVar[_builtins.list[_builtins.str]] = ["target", "op", "value"]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Import(stmt):
    namespace: identifier = _dataclasses.field(default=None)
    name: identifier = _dataclasses.field(default=None)
    version: int = _dataclasses.field(default=None)
    alias: identifier | None = _dataclasses.field(default=None)
    _fields: _typing.ClassVar[_builtins.list[_builtins.str]] = ["namespace", "name", "version", "alias"]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Expr(stmt):
    value: expr = _dataclasses.field(default=None)
    _fields: _typing.ClassVar[_builtins.list[_builtins.str]] = ["value"]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Break(stmt):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Continue(stmt):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class expr(AST):
    lineno: int = _dataclasses.field(default=None, repr=False, compare=False, kw_only=True)
    col_offset: int = _dataclasses.field(default=None, repr=False, compare=False, kw_only=True)
    end_lineno: int | None = _dataclasses.field(default=None, repr=False, compare=False, kw_only=True)
    end_col_offset: int | None = _dataclasses.field(default=None, repr=False, compare=False, kw_only=True)
    _attributes: _typing.ClassVar[_builtins.list[_builtins.str]] = [
        "lineno",
        "col_offset",
        "end_lineno",
        "end_col_offset",
    ]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class BoolOp(expr):
    op: bool_op = _dataclasses.field(default=None)
    values: _builtins.list[expr] = _dataclasses.field(default_factory=_builtins.list)
    _fields: _typing.ClassVar[_builtins.list[_builtins.str]] = ["op", "values"]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class BinOp(expr):
    left: expr = _dataclasses.field(default=None)
    op: operator = _dataclasses.field(default=None)
    right: expr = _dataclasses.field(default=None)
    _fields: _typing.ClassVar[_builtins.list[_builtins.str]] = ["left", "op", "right"]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class UnaryOp(expr):
    op: unary_op = _dataclasses.field(default=None)
    operand: expr = _dataclasses.field(default=None)
    _fields: _typing.ClassVar[_builtins.list[_builtins.str]] = ["op", "operand"]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Conditional(expr):
    test: expr = _dataclasses.field(default=None)
    body: expr = _dataclasses.field(default=None)
    orelse: expr = _dataclasses.field(default=None)
    _fields: _typing.ClassVar[_builtins.list[_builtins.str]] = ["test", "body", "orelse"]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Compare(expr):
    left: expr = _dataclasses.field(default=None)
    ops: _builtins.list[compare_op] = _dataclasses.field(default_factory=_builtins.list)
    comparators: _builtins.list[expr] = _dataclasses.field(default_factory=_builtins.list)
    _fields: _typing.ClassVar[_builtins.list[_builtins.str]] = ["left", "ops", "comparators"]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Call(expr):
    func: expr = _dataclasses.field(default=None)
    args: _builtins.list[arg] = _dataclasses.field(default_factory=_builtins.list)
    _fields: _typing.ClassVar[_builtins.list[_builtins.str]] = ["func", "args"]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Constant(expr):
    value: constant = _dataclasses.field(default=None)
    kind: string | None = _dataclasses.field(default=None)
    _fields: _typing.ClassVar[_builtins.list[_builtins.str]] = ["value", "kind"]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Attribute(expr):
    value: expr = _dataclasses.field(default=None)
    attr: identifier = _dataclasses.field(default=None)
    ctx: expr_context = _dataclasses.field(default=None)
    _fields: _typing.ClassVar[_builtins.list[_builtins.str]] = ["value", "attr", "ctx"]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Subscript(expr):
    value: expr = _dataclasses.field(default=None)
    slice: expr | None = _dataclasses.field(default=None)
    ctx: expr_context = _dataclasses.field(default=None)
    _fields: _typing.ClassVar[_builtins.list[_builtins.str]] = ["value", "slice", "ctx"]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Name(expr):
    id: identifier = _dataclasses.field(default=None)
    ctx: expr_context = _dataclasses.field(default=None)
    _fields: _typing.ClassVar[_builtins.list[_builtins.str]] = ["id", "ctx"]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Tuple(expr):
    elts: _builtins.list[expr] = _dataclasses.field(default_factory=_builtins.list)
    ctx: expr_context = _dataclasses.field(default=None)
    _fields: _typing.ClassVar[_builtins.list[_builtins.str]] = ["elts", "ctx"]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class ForTo(expr):
    target: expr = _dataclasses.field(default=None)
    start: expr = _dataclasses.field(default=None)
    end: expr = _dataclasses.field(default=None)
    body: _builtins.list[stmt] = _dataclasses.field(default_factory=_builtins.list)
    step: expr | None = _dataclasses.field(default=None)
    _fields: _typing.ClassVar[_builtins.list[_builtins.str]] = ["target", "start", "end", "body", "step"]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class ForIn(expr):
    target: expr = _dataclasses.field(default=None)
    iter: expr = _dataclasses.field(default=None)
    body: _builtins.list[stmt] = _dataclasses.field(default_factory=_builtins.list)
    _fields: _typing.ClassVar[_builtins.list[_builtins.str]] = ["target", "iter", "body"]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class While(expr):
    test: expr = _dataclasses.field(default=None)
    body: _builtins.list[stmt] = _dataclasses.field(default_factory=_builtins.list)
    _fields: _typing.ClassVar[_builtins.list[_builtins.str]] = ["test", "body"]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class If(expr):
    test: expr = _dataclasses.field(default=None)
    body: _builtins.list[stmt] = _dataclasses.field(default_factory=_builtins.list)
    orelse: _builtins.list[stmt] = _dataclasses.field(default_factory=_builtins.list)
    _fields: _typing.ClassVar[_builtins.list[_builtins.str]] = ["test", "body", "orelse"]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Switch(expr):
    cases: _builtins.list[case] = _dataclasses.field(default_factory=_builtins.list)
    subject: expr | None = _dataclasses.field(default=None)
    _fields: _typing.ClassVar[_builtins.list[_builtins.str]] = ["cases", "subject"]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Once(expr):
    test: expr | None = _dataclasses.field(default=None)
    body: _builtins.list[stmt] = _dataclasses.field(default_factory=_builtins.list)
    _fields: _typing.ClassVar[_builtins.list[_builtins.str]] = ["test", "body"]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Qualify(expr):
    qualifier: type_qual = _dataclasses.field(default=None)
    value: expr = _dataclasses.field(default=None)
    _fields: _typing.ClassVar[_builtins.list[_builtins.str]] = ["qualifier", "value"]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Specialize(expr):
    value: expr = _dataclasses.field(default=None)
    args: expr = _dataclasses.field(default=None)
    _fields: _typing.ClassVar[_builtins.list[_builtins.str]] = ["value", "args"]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class decl_mode(AST):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Var(decl_mode):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class VarIp(decl_mode):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class type_qual(AST):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Const(type_qual):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Input(type_qual):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Simple(type_qual):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Series(type_qual):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class expr_context(AST):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Load(expr_context):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Store(expr_context):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class bool_op(AST):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class And(bool_op):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Or(bool_op):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class operator(AST):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Add(operator):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Sub(operator):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Mult(operator):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Div(operator):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Mod(operator):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class BitAnd(operator):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class BitOr(operator):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class BitXor(operator):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class LShift(operator):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class RShift(operator):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class unary_op(AST):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Not(unary_op):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class UAdd(unary_op):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class USub(unary_op):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Invert(unary_op):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class compare_op(AST):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Eq(compare_op):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class NotEq(compare_op):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Lt(compare_op):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class LtE(compare_op):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Gt(compare_op):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class GtE(compare_op):
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class param(AST):
    lineno: int = _dataclasses.field(default=None, repr=False, compare=False, kw_only=True)
    col_offset: int = _dataclasses.field(default=None, repr=False, compare=False, kw_only=True)
    end_lineno: int | None = _dataclasses.field(default=None, repr=False, compare=False, kw_only=True)
    end_col_offset: int | None = _dataclasses.field(default=None, repr=False, compare=False, kw_only=True)
    _attributes: _typing.ClassVar[_builtins.list[_builtins.str]] = [
        "lineno",
        "col_offset",
        "end_lineno",
        "end_col_offset",
    ]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Param(param):
    name: identifier = _dataclasses.field(default=None)
    default: expr | None = _dataclasses.field(default=None)
    type: expr | None = _dataclasses.field(default=None)
    _fields: _typing.ClassVar[_builtins.list[_builtins.str]] = ["name", "default", "type"]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class arg(AST):
    lineno: int = _dataclasses.field(default=None, repr=False, compare=False, kw_only=True)
    col_offset: int = _dataclasses.field(default=None, repr=False, compare=False, kw_only=True)
    end_lineno: int | None = _dataclasses.field(default=None, repr=False, compare=False, kw_only=True)
    end_col_offset: int | None = _dataclasses.field(default=None, repr=False, compare=False, kw_only=True)
    _attributes: _typing.ClassVar[_builtins.list[_builtins.str]] = [
        "lineno",
        "col_offset",
        "end_lineno",
        "end_col_offset",
    ]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Arg(arg):
    value: expr = _dataclasses.field(default=None)
    name: identifier | None = _dataclasses.field(default=None)
    _fields: _typing.ClassVar[_builtins.list[_builtins.str]] = ["value", "name"]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class case(AST):
    lineno: int = _dataclasses.field(default=None, repr=False, compare=False, kw_only=True)
    col_offset: int = _dataclasses.field(default=None, repr=False, compare=False, kw_only=True)
    end_lineno: int | None = _dataclasses.field(default=None, repr=False, compare=False, kw_only=True)
    end_col_offset: int | None = _dataclasses.field(default=None, repr=False, compare=False, kw_only=True)
    _attributes: _typing.ClassVar[_builtins.list[_builtins.str]] = [
        "lineno",
        "col_offset",
        "end_lineno",
        "end_col_offset",
    ]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Case(case):
    body: _builtins.list[stmt] = _dataclasses.field(default_factory=_builtins.list)
    pattern: expr | None = _dataclasses.field(default=None)
    _fields: _typing.ClassVar[_builtins.list[_builtins.str]] = ["body", "pattern"]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class cmnt(AST):
    lineno: int = _dataclasses.field(default=None, repr=False, compare=False, kw_only=True)
    col_offset: int = _dataclasses.field(default=None, repr=False, compare=False, kw_only=True)
    end_lineno: int | None = _dataclasses.field(default=None, repr=False, compare=False, kw_only=True)
    end_col_offset: int | None = _dataclasses.field(default=None, repr=False, compare=False, kw_only=True)
    _attributes: _typing.ClassVar[_builtins.list[_builtins.str]] = [
        "lineno",
        "col_offset",
        "end_lineno",
        "end_col_offset",
    ]
    __hash__ = _builtins.object.__hash__


@_dataclasses.dataclass(slots=True)
class Comment(cmnt):
    value: string = _dataclasses.field(default=None)
    kind: string | None = _dataclasses.field(default=None)
    _fields: _typing.ClassVar[_builtins.list[_builtins.str]] = ["value", "kind"]
    __hash__ = _builtins.object.__hash__


__all__ = [
    "identifier",
    "int",
    "string",
    "constant",
    "AST",
    "mod",
    "Script",
    "Expression",
    "stmt",
    "FunctionDef",
    "TypeDef",
    "EnumDef",
    "Assign",
    "ReAssign",
    "AugAssign",
    "Import",
    "Expr",
    "Break",
    "Continue",
    "expr",
    "BoolOp",
    "BinOp",
    "UnaryOp",
    "Conditional",
    "Compare",
    "Call",
    "Constant",
    "Attribute",
    "Subscript",
    "Name",
    "Tuple",
    "ForTo",
    "ForIn",
    "While",
    "If",
    "Switch",
    "Once",
    "Qualify",
    "Specialize",
    "decl_mode",
    "Var",
    "VarIp",
    "type_qual",
    "Const",
    "Input",
    "Simple",
    "Series",
    "expr_context",
    "Load",
    "Store",
    "bool_op",
    "And",
    "Or",
    "operator",
    "Add",
    "Sub",
    "Mult",
    "Div",
    "Mod",
    "BitAnd",
    "BitOr",
    "BitXor",
    "LShift",
    "RShift",
    "unary_op",
    "Not",
    "UAdd",
    "USub",
    "Invert",
    "compare_op",
    "Eq",
    "NotEq",
    "Lt",
    "LtE",
    "Gt",
    "GtE",
    "param",
    "Param",
    "arg",
    "Arg",
    "case",
    "Case",
    "cmnt",
    "Comment",
]
