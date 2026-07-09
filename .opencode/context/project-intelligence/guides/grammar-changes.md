<!-- Context: project-intelligence/guides/grammar-changes | Priority: medium | Version: 1.0 | Updated: 2026-07-05 -->

# Grammar Changes (ANTLR `.g4`)

The Pine Script grammar lives in
`src/pynescript/ast/grammar/antlr4/resource/`. The matching `generated/` directory
holds Python lexer/parser classes that **must be regenerated** after any edit.

## Source Files (edit these)

- `src/pynescript/ast/grammar/antlr4/resource/PinescriptLexer.g4`
- `src/pynescript/ast/grammar/antlr4/resource/PinescriptParser.g4`
- `src/pynescript/ast/grammar/antlr4/resource/PinescriptLexerBase.py` — hand-written
  base class for the lexer (channel/EOF logic).
- `src/pynescript/ast/grammar/antlr4/resource/PinescriptParserBase.py` — hand-written
  base class for the parser.

## Generated (do not edit)

- `src/pynescript/ast/grammar/antlr4/generated/`
  - `PinescriptLexer.py`, `PinescriptParser.py`
  - `PinescriptParserVisitor.py`, `PinescriptParserListener.py`
  - `PinescriptLexerBase.py`, `PinescriptParserBase.py`
  - `.tokens`, `.interp` files

These are produced by the ANTLR4 generator. They are committed so users don't
need Java at install time.

## Regenerate

The `lint` hatch env pulls in `antlr4-cli`:

```bash
hatch run lint:gen-parser
# or directly:
antlr4 -Dlanguage=Python3 -visitor -listener \
  -o src/pynescript/ast/grammar/antlr4/generated \
  src/pynescript/ast/grammar/antlr4/resource/PinescriptLexer.g4 \
  src/pynescript/ast/grammar/antlr4/resource/PinescriptParser.g4
```

Requires **Java + ANTLR4 jar** (the `antlr4-cli` PyPI wrapper handles this).

## Downstream Effects

After regenerating, `src/pynescript/ast/builder.py` will need new `visit_*` methods
for any added parser rules. The `PinescriptParserVisitor` is generated; the
builder subclass in `builder.py` is hand-written.

If you add a new AST shape (statement / expression), also update the ASDL schema
and regenerate nodes (see `pyasdl` usage in `libraries/concepts/pyasdl.md`):

```bash
pyasdl src/pynescript/ast/grammar/asdl/resource/Pinescript.asdl \
  -o src/pynescript/ast/grammar/asdl/generated
```

## Mypy/Ruff Excludes (already configured)

Generated modules are excluded from mypy and ruff in `pyproject.toml`:

```toml
[[tool.mypy.overrides]]
module = [
  "pynescript.ast.grammar.antlr4.generated.*",
  "pynescript.ast.grammar.asdl.generated.*",
  "pynescript.ast.grammar.antlr4.resource.*",
  ...
]
ignore_errors = true
```

Do not add lint fixes inside `generated/` — they will be overwritten on the next
regen.

## 📂 Codebase References

- **Implementation**: `src/pynescript/ast/grammar/antlr4/resource/*.g4`
- **Implementation**: `src/pynescript/ast/grammar/antlr4/resource/*Base.py`
- **Implementation**: `src/pynescript/ast/builder.py` — visitor subclass.
- **Reference**: `pyproject.toml` — `[tool.mypy.overrides]` for generated modules.
