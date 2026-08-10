# Agent 01 — AST / Parser / Unparser Audit

**Scope:** `src/pynescript/ast/` (core: builder, helper, unparser, visitor, transformer, collector, linter, type_system, error; grammar wrappers/tools; not evaluator internals)  
**Date:** 2026-08-10  
**Mode:** Read-only audit  

---

## Executive summary (severity-ranked)

| Severity | Count | Headline |
|----------|-------|----------|
| **Critical** | 1 | Linter `C004` always fires (`str.strip()` removes trailing newline before check) |
| **High** | 6 | Unparser typo drops `simple` qualifier; linter rules W002/C001/C003 broken; silent drop of function return types; exception-swallowing scrub on parse cache; `SyntaxError.__str__` assumes `details` always set |
| **Medium** | 10 | Multi-line end-column formula; shared mutable parse cache; incomplete type system equality/compat; annotation attachment gaps; dual visitor caches; generated tree junk; ASDL defaults hide incomplete nodes; bare `except Exception` in linter; import version typing; collector/annotation enum gap |
| **Low** | 8 | Dead ClassVar maps; misspelled method name; god-object builder; inconsistent return annotations; no slots; bare `pass` subclasses |

**Overall quality of this stack:** solid **staff-level infrastructure** for parse → AST → unparse (architecture, SLL/LL two-phase parse, precedence unparser, ASDL pipeline), dragged down by a **toy/heuristic linter**, a **shallow type_system**, and several **correctness nits** that slip past otherwise careful docs.

---

## Critical / High findings (with file:line where possible)

### C1 — Critical: linter `C004` always reports missing trailing newline

```204:208:src/pynescript/ast/linter.py
        if not source.strip().endswith("\n"):
            self._add_warning(
                code="C004",
                message="File should end with a newline",
            )
```

`str.strip()` strips **all** trailing whitespace including `\n`, so `endswith("\n")` is **never** true for any non-empty script body. Every linted file gets `C004`.

**Fix:** `if source and not source.endswith("\n"):` (optionally allow `\r\n`).

---

### H1 — High: unparser typo `visit_Sipmle` drops `simple` type qualifier

```1006:1007:src/pynescript/ast/unparser.py
    def visit_Sipmle(self, node: ast.Simple):
        self._source.append("simple")
```

Dispatch is by class name (`visit_` + `type(node).__name__` → `visit_Simple`). The misspelled method is **never called**. Unparsing `simple int x = 1` falls through to `generic_visit` (empty op node → emits nothing) → **semantic round-trip loss** of the `simple` qualifier.

**Evidence:** repo-wide only this one `Sipmle` spelling; no `visit_Simple`.

**Fix:** rename to `visit_Simple`. Add a round-trip test for each `type_qual` (`const`/`input`/`simple`/`series`).

---

### H2 — High: linter `W002` line number is a character offset

```151:158:src/pynescript/ast/linter.py
        else:
            version = int(version_match.group(1))
            if version < 5:
                self._add_warning(
                    code="W002",
                    message=f"Pine Script v{version} is deprecated. Consider upgrading to v5 or v6.",
                    line=version_match.start(),
                )
```

`Match.start()` is a **byte/character index**, not a 1-based line. IDEs/LSP will jump to the wrong line.

**Fix:** `line = source[: version_match.start()].count("\n") + 1` (same pattern as `_check_deprecated`).

---

### H3 — High: linter `C001` naming rule is inverted / noise

```177:184:src/pynescript/ast/linter.py
            if match := re.search(r"(\w+)\s*=\s*ta\.", line):
                var_name = match.group(1)
                if re.match(r"^[a-z]", var_name):
                    self._add_warning(
                        code="C001",
                        message=f"Variable '{var_name}' should use camelCase (e.g., '{_to_camel(var_name)}')",
                        line=i,
                    )
```

Pine idiomatic style is **lowerCamelCase**. This flags **every** lowercase-starting name (including `rsi`, `fastMa`, `myLength`). Only PascalCase escapes. `_to_camel` only helps snake_case.

**Fix:** warn on snake_case (`_ in name`) or non-camelCase patterns; do not warn on `^[a-z][a-zA-Z0-9]*$`.

---

### H4 — High: linter `C003` is wrong for Pine (no braces)

```197:202:src/pynescript/ast/linter.py
            if re.match(r"^\s+if\s+", line):
                self._add_warning(
                    code="C003",
                    message="Avoid single-line if statements without braces",
                    line=i,
                )
```

Any indented `if` (normal Pine control flow) is warned. Pine uses indentation, not braces. Rule is a Python-style false positive generator.

**Fix:** remove rule or rewrite against real AST shape (e.g. empty body / suspicious patterns).

---

### H5 — High: function/method return types parsed by grammar, dropped by builder

```569:575:src/pynescript/ast/builder.py
    def visitFunction_declaration(self, ctx: PinescriptParser.Function_declarationContext):
        """UDF: ``export? [return_type] name(params) => body``.

        Grammar allows a leading ``type_specification`` as the return type
        (Pine v5+/v6). ASDL ``FunctionDef`` has no returns field yet, so that
        context is intentionally not mapped — parse succeeds; type is dropped.
        """
```

Same for `visitMethod_declaration` (lines 594–598). ASDL:

```5:5:src/pynescript/ast/grammar/asdl/resource/Pinescript.asdl
     stmt = FunctionDef(identifier name, param* args, stmt* body, int? method, int? export, string* annotations)
```

**Impact:** parse succeeds; round-trip and any type-aware tooling lose return annotations. Documented intentional gap, but still a **correctness / Pine-parity** hole at the AST boundary.

**Fix:** add `expr? returns` (or similar) to ASDL `FunctionDef`, map in builder, emit in unparser.

---

### H6 — High: parse-cache scrub swallows all exceptions

```165:185:src/pynescript/ast/helper.py
def _scrub_pine_call_sites(tree: AST) -> AST:
    ...
    try:
        for node in walk(tree):
            if getattr(node, "_pine_call_site", None) is not None:
                try:
                    delattr(node, "_pine_call_site")
                except Exception:
                    try:
                        object.__setattr__(node, "_pine_call_site", None)
                    except Exception:
                        pass
    except Exception:
        pass
    return tree
```

Triple-nested bare `except Exception` means failed scrub still returns a tree that may retain **evaluator-bound call sites** → wrong handlers on multi-run hosts (the exact bug this scrub was meant to prevent). Failures become silent.

**Fix:** narrow exceptions (`AttributeError`, `TypeError`); log or re-raise in debug; never swallow walk failures.

---

### H7 — High: `SyntaxError.__str__` assumes `details` always present

```65:90:src/pynescript/ast/error.py
    def __init__(self, message: str, *details: SyntaxErrorDetails | object) -> None:
        self.message = message
        if details:
            if len(details) == 1 and isinstance(details[0], SyntaxErrorDetails):
                self.details = details[0]
            else:
                self.details = SyntaxErrorDetails(*details)

    def __str__(self) -> str:
        f = StringIO()
        code = self.details.text.lstrip()
        ...
```

`PinescriptLexerBase._reportLexerError` constructs `errcls(message)` **without** details first, then relies on the error listener to fill them in. Any code path that raises `SyntaxError("msg")` alone (or fails before details attach) will **crash in `__str__`** with `AttributeError: details`.

Also: no `self.details = None` default; subclass `IndentationError` inherits the same.

**Fix:** default `self.details = None`; branch `__str__` to return `self.message` only when unset.

---

## Medium findings

### M1 — Multi-line `end_col_offset` formula looks off-by-two

```193:201:src/pynescript/ast/builder.py
        if stop_text is not None and "\n" in stop_text:
            stop_nls = stop_text.count("\n")
            stop_nlpos = stop_text.rfind("\n")
            node.end_lineno = stop.line + stop_nls  # type: ignore[attr-defined]
            node.end_col_offset = stop_len - stop_nlpos + 1  # type: ignore[attr-defined]
```

For token text `"a\nb"`: `stop_len=3`, `stop_nlpos=1` → `end_col_offset=3`. Last line content is `"b"` (length 1). Python-style exclusive end column on the last line should be **1**, i.e. roughly `stop_len - stop_nlpos - 1`. Same formula in `error_listener.py` lines 121–125. Breaks `get_source_segment` for multi-line tokens (strings, etc.).

---

### M2 — Shared parse-cache returns mutable identity

Documented in `helper.py` (lines 105–110, 535–539), but still a design hazard: `NodeTransformer`, `increment_lineno`, or any in-place rewrite mutates the cache for all subsequent `parse()` hits. `_scrub_pine_call_sites` only strips one attr; it does not deep-copy.

**Mitigations already present:** env kill-switch, `clear_parse_cache()`. Missing: optional copy-on-write, or freeze nodes, or return `copy.deepcopy` when a flag is set.

---

### M3 — Type system compatibility is identity-based / incomplete

```72:79:src/pynescript/ast/type_system.py
    def is_compatible_with(self, other: Type) -> bool:
        if isinstance(other, BuiltinType):
            return self == other
        return False
```

No `__eq__`/`__hash__` on `Type`/`BuiltinType` → object identity. Two `BuiltinType(BuiltinTypeKind.INT)` instances are incompatible. No int→float promotion, no series/simple lattice, no collection element checks. Qualifiers ignored. Fine as a sketch; **not** a type system for Pine parity.

`MethodResolver.resolve_method(..., method_name == "new")` expects an `ObjectInstance` but `.new` is typically invoked on the type name, not an instance (API smell).

---

### M4 — Annotation attachment incomplete

`_add_annotations` only attaches to `FunctionDef`, `TypeDef`, `Assign` (helper.py ~297–310). No `EnumDef`, no `ReAssign`. Script-level only uses the **first** comment group with kinds ending in `S`. Nested annotations depend on `StatementCollector` source order (generally OK) but enum docs are dropped.

---

### M5 — Dual visitor method caches on `NodeUnparser`

`NodeVisitor` maintains `_visitor_cache` (visitor.py:53–70). `NodeUnparser` adds `_type_visitor_cache` and **bypasses** `super().visit` in `traverse` (unparser.py:404–411). Calling `NodeVisitor.visit` on an unparser would use a different cache/path. Works for intended API (`unparse_node` → `visit` → `traverse`) but is inconsistent inheritance.

---

### M6 — Nested junk under `grammar/antlr4/generated/src/...`

`generated/src/pynescript/ast/grammar/antlr4/resource/` holds another copy of lexer/parser artifacts. Likely a mis-pointed ANTLR `-o` or packaging path at some point. Inflates tree, confuses imports/reviews, risk of stale dual sources.

`antlr4/tool/generate.py` copies resource `*.py` into `generated/` (correct for bases) but does not clean nested leftovers.

---

### M7 — ASDL generator defaults all fields to `None`

`asdlgen.py` with `defaults="all"` makes required fields optional at construction time (`name: identifier = None`, etc.). Enables incomplete ASTs that blow up later in unparser/evaluator instead of at construction. Tradeoff for builder ergonomics; weakens static guarantees.

Also: generated classes are mutable dataclasses **without** `slots=True` → higher memory for large scripts.

---

### M8 — Linter syntax check uses bare `except Exception`

```111:113:src/pynescript/ast/linter.py
        try:
            parse(source, filename)
        except Exception as e:
```

Catches programming errors (e.g. recursion, ImportError if graph broken) as `E001` “Syntax error”. Should catch `pynescript.ast.error.SyntaxError` (and maybe `ValueError` for mode).

---

### M9 — Import version may not be `int`

ASDL: `Import(..., int version, ...)`. Builder:

```1259:1259:src/pynescript/ast/builder.py
        version = self.visit(version)
```

`visitLiteral_number` can return `float` (e.g. `1.0`). Unparser does `str(node.version)` so round-trip might emit `1.0` instead of `1`.

---

### M10 — Typed `for` iterators / other intentional drops

```910:916:src/pynescript/ast/builder.py
    def visitFor_iterator(...):
        """Loop variable; optional type annotation is accepted but not stored on ForTo/ForIn."""
        ...
        return self.visit(ctx.name_store())
```

Same class of info-loss as return types. Grammar accepts more than ASDL stores.

---

### M11 — Error listener assumes non-null `offendingSymbol`

```121:125:src/pynescript/ast/grammar/antlr4/error_listener.py
        symbol_len = offendingSymbol.stop - offendingSymbol.start + 1
        symbol_nls = offendingSymbol.text.count("\n")
        ...
```

ANTLR can pass `None` for some recognition errors. Would raise `AttributeError` instead of a clean `SyntaxError`.

---

## Low / nits

| ID | Item | Location |
|----|------|----------|
| L1 | Dead string-keyed ClassVars (`binop_precedence`, `cmpop_precedence`, `boolops`, `unop`, …) coexist with type-keyed hot tables | `unparser.py` ~645–800 |
| L2 | `visit_Sipmle` typo (also High) | `unparser.py:1006` |
| L3 | `PinescriptASTBuilder` is a large multi-inheritance god visitor (~1400 lines); hard to unit-test in isolation | `builder.py` |
| L4 | Inconsistent return type hints on many `visit_*` (some annotated, most not) | builder/unparser |
| L5 | `IndentationError` body is bare `pass` | `error.py:96` |
| L6 | `NodeVisitor.generic_visit` return type effectively always `None`; not stated in signature beyond `Any` | `visitor.py` |
| L7 | `list` identity check `node.__class__ is list` in unparser rejects list subclasses (unlikely in practice) | `unparser.py:400` |
| L8 | Module-level `sys.setrecursionlimit` mutation during parse is process-global (restored in `finally`, still races with concurrent parsers in same process) | `helper.py:386–445` |
| L9 | Color literals store full text as `Constant.value` with `kind="#"`; slightly special-cased vs other constants | builder ~1203–1211 |
| L10 | `StatementCollector` + `Structure` tuple is brittle if new control forms are added | `collector.py:37–43` |

---

## Documentation audit

### Strengths (good examples)

- **Module-level contracts** are excellent on `helper.py`, `builder.py`, `unparser.py`, `node.py`, `__init__.py`: pipeline stages, hand-edit rules, cache mutability risk, round-trip non-goals.
- **Non-obvious methods** get real docstrings: SLL/LL two-stage parse, comment kind encoding (`@=S`, `@0F`), ternary association, store-ctx fixup, Specialize span stitching.
- **Public API surface** is clearly split: star-export vs import-directly (`linter`, `type_system`, `collector`).

### Gaps

| Area | Gap |
|------|-----|
| `type_system.py` | Module docstring OK; no doc on compatibility lattice, Pine promotion rules, or that this is **not** used by the parser/linter |
| `linter.py` | Claims “static checks” but rules are regex heuristics; no rule catalog beyond scattered codes |
| `error.py` | Does not document that `details` may be missing / construction patterns |
| `visitor.py` / `transformer.py` | Good short docs; no note on dual-cache unparser subclass |
| Generated `PinescriptASTNode.py` | No header warning “DO NOT EDIT” inside the file body (only mentioned from `node.py`) |
| Grammar resource bases | `PinescriptLexerBase` has a solid bullet list of indent/string behavior; `PinescriptParserBase` is minimal |
| `asdlgen.py` | Thin; no explanation of `defaults` modes for maintainers |

### Type hints completeness

- Modern `from __future__ import annotations`, `|` unions, `list[str]` used widely in hand-written modules.
- Builder `visit_*` largely untyped (ANTLR context types available but omitted for size).
- Unparser many methods missing `-> None`.
- `type: ignore[attr-defined]` on location attrs is pervasive because generated dataclasses use dynamic location fields — understandable, not ideal.

---

## Modernization opportunities

Without breaking Pine parity:

1. **`dataclasses.dataclass(slots=True)`** in ASDL codegen (Python 3.10+) — large win for AST memory/GC on big scripts.
2. **`match`/`case`** in builder for token/op dispatch (augassign, unary, type_qualifier) — readability; keep hot path micro-optimizations where measured.
3. **`Protocol` / `TypedDict`** for location attributes instead of sprawling `type: ignore[attr-defined]`.
4. **`enum.StrEnum`** (3.11) for linter severity / comment kinds / TypeQualifier already Enum — good; could use `StrEnum` for wire/JSON.
5. **`functools.lru_cache` / `cache`** for pure helpers (`_parse_number_literal` patterns, comment regexes already compiled).
6. **`typing.Self`** on fluent helpers (`copy_location`, `fix_missing_locations`).
7. **Unify visitor dispatch** — single type-keyed cache on `NodeVisitor`; unparser should not fork.
8. **Replace custom type hierarchy** with a small algebraic type model + frozen dataclasses / `NamedTuple` for builtins.
9. **Linter**: either delete regex rules or reimplement as `NodeVisitor` passes over the real AST (only reliable approach).
10. **Parse cache**: optional `copy.deepcopy` on hit, or mark nodes with a generation id; consider `weakref` + content hash for debug.

---

## Quality scorecard

| Dimension | Score (1–10) | Notes |
|-----------|--------------|-------|
| Correctness (core parse/build) | **8** | Solid ANTLR pipeline, store-ctx, bitwise/shift, v6 strings; return-type drop & Simple unparse typo hurt |
| Correctness (unparser) | **7.5** | Precedence model is careful; `visit_Sipmle` is a footgun; dead maps |
| Correctness (linter) | **3** | Multiple broken rules; not production-grade |
| Correctness (type_system) | **4** | Sketch quality; identity equality; no lattice |
| Design / architecture | **8** | Clear layering (g4 → builder → ASDL → helper API); SLL/LL; thread-local unparser |
| Performance awareness | **8.5** | Shared builder, op singletons, indent cache, type-keyed dispatch, SLL first — senior-level |
| Docs | **8** | Above average for open source compilers |
| Consistency | **6.5** | Dual caches, uneven typing, linter vs rest quality gap |
| Testability | **7** | Stateless builder helps; god-file size hurts; intentional ASDL gaps need corpus tests |
| **Overall (this scope)** | **7.0** | **Senior** for parser/AST/unparser infrastructure; **not** staff-level end-to-end (linter/types lag) |

**Honesty note:** Docs and perf commentary are strong enough that a casual review overrates the package. The linter and type_system would fail a serious design review; the parse/unparse core would pass.

---

## Concrete recommendations (prioritized, actionable)

### P0 — Fix now (bugs users hit)

1. **Rename** `visit_Sipmle` → `visit_Simple`; add tests for `const`/`input`/`simple`/`series` round-trip.  
   File: `src/pynescript/ast/unparser.py:1006`
2. **Fix C004** trailing-newline check (`endswith` on raw `source`).  
   File: `src/pynescript/ast/linter.py:204`
3. **Fix W002** line number; **disable or rewrite C001/C003**.  
   File: `src/pynescript/ast/linter.py`
4. **Harden** `SyntaxError.__str__` when `details` is missing.  
   File: `src/pynescript/ast/error.py`
5. **Narrow** `_scrub_pine_call_sites` exception handling; fail visible if scrub fails.  
   File: `src/pynescript/ast/helper.py:165-185`

### P1 — Semantic / tooling parity

6. Add `returns` (or `type`) field to ASDL `FunctionDef`; map in builder; unparse.  
   Files: `Pinescript.asdl`, `builder.py`, `unparser.py`
7. Store typed `for` targets if grammar allows (ASDL + builder).
8. Guard `offendingSymbol is None` in error listener; fix multi-line `end_col_offset` and share one helper with builder.
9. Linter: catch only `pynescript.ast.error.SyntaxError`; prefer AST-based rules.

### P2 — Design cleanup

10. Deep-copy or freeze cached parse trees; document API: “parse results are immutable”.
11. Implement real `Type.__eq__` and qualifier lattice **or** mark module experimental in docs and keep evaluator-local.
12. Delete nested `generated/src/...` tree; make `generate.py` clean output dir.
13. Merge unparser into single visitor cache; delete dead ClassVar string maps.
14. ASDL codegen: optional `slots=True`; consider `defaults="none"` for required fields in a major version.

### P3 — Polish

15. Annotate builder entry points and public unparser methods with return types.  
16. Add “DO NOT EDIT” banner to generated AST module via `asdlgen`.  
17. EnumDef annotation attachment in `_add_annotations`.  
18. Coerce import version with `int(...)` when literal is integral float.

---

## Evidence index (key files read)

| Path | Role |
|------|------|
| `/mnt/data/home/jango/Git/pynescript/src/pynescript/ast/helper.py` | parse cache, SLL/LL, annotations, walk/dump |
| `/mnt/data/home/jango/Git/pynescript/src/pynescript/ast/builder.py` | ANTLR → ASDL; location; comment kinds; return-type drop |
| `/mnt/data/home/jango/Git/pynescript/src/pynescript/ast/unparser.py` | precedence unparse; **Sipmle** typo; thread-local reuse |
| `/mnt/data/home/jango/Git/pynescript/src/pynescript/ast/visitor.py` | type-keyed visitor cache |
| `/mnt/data/home/jango/Git/pynescript/src/pynescript/ast/transformer.py` | in-place rewrite |
| `/mnt/data/home/jango/Git/pynescript/src/pynescript/ast/collector.py` | statement walk for annotations |
| `/mnt/data/home/jango/Git/pynescript/src/pynescript/ast/linter.py` | broken C004/C001/C003/W002 |
| `/mnt/data/home/jango/Git/pynescript/src/pynescript/ast/type_system.py` | shallow type model |
| `/mnt/data/home/jango/Git/pynescript/src/pynescript/ast/error.py` | SyntaxError formatting |
| `/mnt/data/home/jango/Git/pynescript/src/pynescript/ast/grammar/antlr4/error_listener.py` | ANTLR → SyntaxError |
| `/mnt/data/home/jango/Git/pynescript/src/pynescript/ast/grammar/antlr4/resource/PinescriptLexerBase.py` | indent / string wrap |
| `/mnt/data/home/jango/Git/pynescript/src/pynescript/ast/grammar/asdl/resource/Pinescript.asdl` | node schema |
| `/mnt/data/home/jango/Git/pynescript/src/pynescript/ast/grammar/asdl/tool/asdlgen.py` | codegen |
| `/mnt/data/home/jango/Git/pynescript/src/pynescript/ast/grammar/asdl/generated/PinescriptASTNode.py` | generated nodes |

---

*End of Agent 01 audit.*
