# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Coverage for AST error, visitor, collector, transformer, and type_system."""

from __future__ import annotations

import pytest

from pynescript.ast import parse
from pynescript.ast.collector import StatementCollector
from pynescript.ast.error import IndentationError as PineIndentationError
from pynescript.ast.error import SyntaxError as PineSyntaxError
from pynescript.ast.error import SyntaxErrorDetails
from pynescript.ast.transformer import NodeTransformer
from pynescript.ast.type_system import ArrayType
from pynescript.ast.type_system import BuiltinTypeKind
from pynescript.ast.type_system import Field
from pynescript.ast.type_system import MapType
from pynescript.ast.type_system import MatrixType
from pynescript.ast.type_system import MethodResolver
from pynescript.ast.type_system import MethodSignature
from pynescript.ast.type_system import ObjectInstance
from pynescript.ast.type_system import Type
from pynescript.ast.type_system import TypeQualifier
from pynescript.ast.type_system import TypeRegistry
from pynescript.ast.type_system import UserDefinedType
from pynescript.ast.type_system import bool_type
from pynescript.ast.type_system import color_type
from pynescript.ast.type_system import float_type
from pynescript.ast.type_system import int_type
from pynescript.ast.type_system import string_type
from pynescript.ast.visitor import NodeVisitor


MINI = '//@version=6\nindicator("t")\nx = 1\nif x > 0\n    y = 2\nplot(x)\n'


class TestSyntaxError:
    def test_details_namedtuple(self) -> None:
        d = SyntaxErrorDetails("<src>", 3, 2, "  foo =", end_lineno=3, end_offset=5)
        assert d.filename == "<src>"
        assert d.lineno == 3
        assert d.offset == 2

    def test_from_details_object(self) -> None:
        d = SyntaxErrorDetails("f.pine", 1, 0, "bad")
        err = PineSyntaxError("oops", d)
        text = str(err)
        assert "oops" in text
        assert 'File "f.pine"' in text
        assert "^" in text

    def test_from_unpacked_fields(self) -> None:
        err = PineSyntaxError("nope", "a.pine", 2, 4, "    x = ?")
        assert err.details.lineno == 2
        assert err.details.offset == 4
        assert "nope" in str(err)

    def test_indentation_subclass(self) -> None:
        err = PineIndentationError("bad indent", "t.pine", 1, 0, "x")
        assert isinstance(err, PineSyntaxError)
        assert "bad indent" in str(err)


class TestVisitorAndCollector:
    def test_visitor_cache_and_generic(self) -> None:
        seen: list[str] = []

        class V(NodeVisitor):
            def visit_Name(self, node):
                seen.append(node.id)
                return node.id

        tree = parse(MINI)
        v = V()
        v.visit(tree)
        assert "x" in seen
        # second walk hits cache
        seen.clear()
        v.visit(tree)
        assert "x" in seen

    def test_statement_collector_yields_nested(self) -> None:
        tree = parse(MINI)
        nodes = list(StatementCollector().visit(tree))
        kinds = {type(n).__name__ for n in nodes}
        assert "Assign" in kinds
        assert "If" in kinds or "Expr" in kinds


class TestTransformer:
    def test_rename_identifiers(self) -> None:
        tree = parse('//@version=6\nindicator("t")\nx = close\nplot(x)\n')

        class Rename(NodeTransformer):
            def visit_Name(self, node):
                if node.id == "x":
                    node.id = "y"
                return node

        out = Rename().visit(tree)
        from pynescript.ast import unparse

        src = unparse(out)
        assert "y =" in src or "y=" in src.replace(" ", "")


class TestTypeSystem:
    def test_qualifiers_and_str(self) -> None:
        t = Type("foo", TypeQualifier.SERIES)
        assert str(t) == "series foo"
        assert str(Type("bar")) == "bar"

    def test_builtin_factories(self) -> None:
        assert int_type().kind == BuiltinTypeKind.INT
        assert float_type().kind == BuiltinTypeKind.FLOAT
        assert bool_type().kind == BuiltinTypeKind.BOOL
        assert string_type().kind == BuiltinTypeKind.STRING
        assert color_type().kind == BuiltinTypeKind.COLOR

    def test_collection_types(self) -> None:
        elem = int_type()
        assert ArrayType(elem).name == "array<int>"
        assert MatrixType(elem).name == "matrix<int>"
        assert MapType(string_type(), elem).name == "map<string, int>"

    def test_compatibility_default(self) -> None:
        a = int_type()
        # BuiltinType uses identity equality (no custom __eq__), so distinct
        # instances of the same kind are not assignment-compatible via ==.
        assert a.is_compatible_with(a) is True
        assert a.is_compatible_with(int_type()) is False
        assert a.is_compatible_with(float_type()) is False
        assert Type("x").is_compatible_with(Type("y")) is False

    def test_field_and_method_repr(self) -> None:
        f = Field("x", float_type(), default_value=1.5, varip=True)
        assert "varip" in repr(f)
        assert "x" in repr(f)
        m = MethodSignature("move", [("dx", float_type())], return_type=bool_type())
        assert "method move" in repr(m)
        assert "dx" in repr(m)

    def test_registry_udt_and_instance(self) -> None:
        reg = TypeRegistry()
        udt = UserDefinedType("Point")
        udt.add_field(Field("x", float_type(), default_value=0.0))
        udt.add_field(Field("y", float_type(), default_value=0.0))
        udt.add_method(MethodSignature("len", [], return_type=float_type()))
        reg.register_type(udt)
        assert reg.get_type("Point") is udt
        assert reg.get_type("int").kind == BuiltinTypeKind.INT  # type: ignore[union-attr]
        assert reg.is_builtin_type("float") is True
        assert reg.is_user_defined_type("Point") is True
        assert "1 user types" in repr(reg)
        assert "type Point" in repr(udt)
        assert udt.get_field("x") is not None
        assert udt.get_method("len") is not None

        inst = ObjectInstance(udt)
        assert inst.get_field("x") == 0.0
        inst.set_field("y", 3.0)
        assert inst.get_field("y") == 3.0
        assert "Point(" in repr(inst)
        with pytest.raises(AttributeError):
            inst.get_field("missing")
        with pytest.raises(AttributeError):
            inst.set_field("missing", 1)
        clone = inst.copy()
        assert clone.get_field("y") == 3.0
        assert clone is not inst

    def test_method_resolver_new_copy_and_user(self) -> None:
        reg = TypeRegistry()
        udt = UserDefinedType("Point")
        udt.add_field(Field("x", float_type(), default_value=0.0))
        udt.add_field(Field("y", float_type(), default_value=0.0))
        sig = MethodSignature("len", [], return_type=float_type())
        udt.add_method(sig)
        reg.register_type(udt)
        resolver = MethodResolver(reg)
        seed = ObjectInstance(udt)
        created = resolver.resolve_method(seed, "new", [1.0, 2.0])
        assert isinstance(created, ObjectInstance)
        assert created.get_field("x") == 1.0
        assert created.get_field("y") == 2.0
        copied = resolver.resolve_method(created, "copy", [])
        assert copied.get_field("x") == 1.0
        assert resolver.resolve_method(created, "len", []) is sig
        with pytest.raises(AttributeError):
            resolver.resolve_method(created, "nope", [])
