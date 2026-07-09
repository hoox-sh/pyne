<!-- Context: libraries/concepts/pyasdl | Priority: medium | Version: 1.0 | Updated: 2026-07-05 -->

# pyasdl

`pyasdl` is a small tool that turns an ASDL schema (`.asdl`) into Python
classes. This repo uses it to generate
`src/pynescript/ast/grammar/asdl/generated/PinescriptASTNode.py` from
`src/pynescript/ast/grammar/asdl/resource/Pinescript.asdl`.

ASDL (Abstract Syntax Description Language) is the same schema language
CPython uses for its own AST. The generated classes are simple dataclass-like
types with positional fields plus `lineno`/`col_offset` attributes.

## Schema Sketch

```asdl
module Pinescript
{
     mod = Script(stmt* body, string* annotations)
         | Expression(expr body)

     stmt = FunctionDef(identifier name, param* args, stmt* body, ...)
          | TypeDef(identifier name, stmt* body, int? export, string* annotations)
          | Assign(expr target, expr? value, ...)
          | ...

     expr = BoolOp(...)
          | BinOp(expr left, operator op, expr right)
          | Call(expr func, arg* args)
          | Name(identifier id, expr_context ctx)
          | ...
}
```

Types: `*` is sequence, `?` is optional, `identifier` is a string, `constant`
is any literal value.

## CLI

```bash
pyasdl src/pynescript/ast/grammar/asdl/resource/Pinescript.asdl \
  -o src/pynescript/ast/grammar/asdl/generated
```

Or via hatch:
```bash
hatch run lint:gen-parser    # also requires the antlr4-cli env
```

`pyasdl>=0.3.1` is in the `lint` hatch env (not in main deps).

## How the Generated Code Is Used

- `src/pynescript/ast/node.py` re-exports the classes so consumers see one
  namespace: `from pynescript.ast.node import Script, FunctionDef, Assign, ...`.
- `src/pynescript/ast/__init__.py` re-exports `node.py` (and the rest) as
  `from pynescript.ast import *`.
- The builder (`ast/builder.py`) instantiates these classes when visiting the
  ANTLR parse tree.
- Mypy and ruff ignore the `generated.*` module (see `pyproject.toml` overrides)
  because the code is machine-written and uses `Any`.

## Gotchas

- ASDL field order is significant — generated `__init__` is positional.
- Adding a new field to the schema means regenerating the module; existing
  builder call sites must be updated.
- The generated module is large (~1000+ lines); never import it directly
  outside `pynescript.ast.node`.

## 📂 Codebase References

- **Implementation**: `src/pynescript/ast/grammar/asdl/resource/Pinescript.asdl`.
- **Implementation**: `src/pynescript/ast/grammar/asdl/generated/PinescriptASTNode.py`.
- **Implementation**: `src/pynescript/ast/node.py` — re-exports.
- **Reference**: `pyproject.toml` — `[tool.hatch.envs.lint.dependencies]`
  has `pyasdl>=0.3.1`.
