<!-- Context: project-intelligence/concepts/pine-script-language | Priority: high | Version: 1.1 | Updated: 2026-07-12 (v6 section added) -->

# Pine Script (the source language)

High-level reference to the **Pine Script** language pynescript parses. Read
this when you need to know what an AST shape, an evaluator method, or a
linter rule *means*. Authoritative sources: the ANTLR grammar and ASDL
(`PinescriptParser.g4`, `Pinescript.asdl`); worked examples in
`tests/data/builtin_scripts/*.pine`.

## What It Is

TradingView's indicator/strategy DSL. v5 is the current target; v6 in the
corpus (and increasingly the default for new scripts). **Not Python** — syntax, types, and semantics differ.

### v6 Additions (as of 2026-07)
- Multiline strings (`"""..."""` / `'''...'''`) with literal newlines and indentation.
- `sort_field` (int or string) on `array.sort`, `array.sort_indices`, `matrix.sort` for UDT collections.
- `request.footprint()` + `footprint` / `volume_row` types (with many methods).
- Default dynamic requests, stricter booleans, removal of several legacy parameters.
- Many of these are now supported in pynescript (see `docs/missing_features.md` for current matrix).

## File Shape

1. **Annotations** — `//@version=5`, `//@description "…"` (promoted to script
   or nearest statement by `helper._add_annotations`).
2. **Declaration** — `indicator(…)`, `strategy(…)`, or `library(…)`.
3. **Statements** — function/method/type/enum defs, imports, assignments,
   control flow, expression statements.

## Annotations → Targets

`//@version=N` → `Script.annotations`. `//@description`, `//@type`,
`//@field`, `//@enum`, `//@var` → appropriate def or statement.

## Declarations (grammar ↔ AST)

| Form | Grammar | ASDL |
| --- | --- | --- |
| `indicator/strategy/library(...)` | top-level call | `Expr(Call(...))` |
| `f(x) => body` | `function_declaration` | `FunctionDef(args, body, method=0, export, annotations)` |
| `method f(self, x) => body` | `method_declaration` | `FunctionDef(..., method=1, ...)` |
| `type Name\n  field…` | `type_declaration` | `TypeDef(body, export, annotations)` |
| `enum Name\n  A\n  B` | `enum_declaration` | `EnumDef(body, export, annotations)` |

`EXPORT?` makes a def public (for `library`).

## Types

Built-ins: `int`, `float`, `bool`, `string`, `color`, `line`, `label`, `box`,
`table`, `polyline`, `array`, `matrix`, `map`, plus UDTs from `type`.

Type qualifiers (AST: `Qualify(type_qual, expr)`): `series` (default, varies
per bar), `simple` (known at bar compile time), `const` (compile-time
constant), `input` (declared by `input.int`, `input.float`, etc.).

## Statements

`statement` is a **compound_statement** (function/method/type/enum/structure)
or a **simple_statements** block (comma-separated, single line — Python-style).
Simple kinds: `expression_statement`, `import_statement`, `break_statement`,
`continue_statement`.

## Control Flow → AST

`if … else …` → `If(test, body, orelse)`. `for i = a to b [by s]` →
`ForTo(target, start, end, body, step)`. `for x in arr` → `ForIn(target, iter,
body)`. `while cond` → `While(test, body)`. `switch expr\n  a => …` →
`Switch(cases, subject)`. `for` runs a fixed count of iterations in older
Pine; `for … in` is the iterator form in v6.

## Expressions

Precedence: ternary → or → and → equality → inequality → additive →
multiplicative → unary → primary.

- `Call(func, args)` — positional or `name=value`.
- `Attribute(value, attr, ctx)` — `ta.sma`, `math.max`.
- `Subscript(value, slice, ctx)` — `a[i]`, `a[i,j]`, `a[start:end]`.
- `Conditional(test, body, orelse)` — ternary.
- `Compare(left, ops, comparators)` — chains: `a < b < c` is one Compare.
- `Tuple(elts, ctx)` — `(a,b)`; bare `a,b` on RHS is a Tuple (destructure).
- **No list/array literals** — use `array.new<T>(size)` + `array.push`.

## Imports & Built-ins

`import namespace/name/version` → `Import(namespace, name, version, alias?)`,
e.g. `import TradingView/ta/5 as tvta`.

Always-in-scope: OHLCV `open/high/low/close/volume/hl2/hlc3/ohlc4`; time
`time/time_close/bar_index/last_bar_index`; state `na`; namespaces
`syminfo.*`, `timeframe.*`, `ticker.*`, `session.*`. Resolved in the
evaluator's `Name` mixin via namespace dispatch.

## Gotchas vs Python

- No list literals; no OOP (`type` is a record-like UDT; methods via
  `method foo(self, x) => …`).
- Series semantics: most expressions evaluate per bar; `close` differs per
  bar; `na` is the "not available" sentinel. Type qualifiers `const`/`input`
  change how the linter and runtime treat a value.
- Strings are double-quoted only. Comments are `//` only. Annotations start
  with `//@`. Indentation is significant (Python-like).

## 📂 Codebase References

- `src/pynescript/ast/grammar/antlr4/resource/PinescriptParser.g4` — syntax.
- `src/pynescript/ast/grammar/asdl/resource/Pinescript.asdl` — AST shape.
- `tests/data/builtin_scripts/*.pine` — 500+ real Pine scripts.
- `parser-ast.md` — how the parser+AST pipeline consumes Pine.
