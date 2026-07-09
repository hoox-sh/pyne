<!-- Context: project-intelligence/concepts/parser-ast | Priority: high | Version: 1.0 | Updated: 2026-07-05 -->

# Parser & AST Pipeline

Pine Script is parsed with ANTLR4, then converted to a hand-written AST whose node
classes are generated from an ASDL schema. The two `generated/` directories are
build artifacts — never edit by hand.

## Stages

1. **Lex** — `PinescriptLexer` (Python class generated from `PinescriptLexer.g4`).
2. **Token stream** — `antlr4.CommonTokenStream`.
3. **Parse** — `PinescriptParser` (Python class generated from `PinescriptParser.g4`).
4. **Build AST** — `PinescriptASTBuilder` in `src/pynescript/ast/builder.py` walks the
   parse tree (via `PinescriptParserVisitor`) and emits ASDL-typed nodes.
5. **Annotate** — `helper._add_annotations()` attaches `@version`, `@description`,
   etc. comments to the nearest following statement.
6. **Unparse** — `src/pynescript/ast/unparser.py` walks the AST back to source.

## Key Files

- `src/pynescript/ast/builder.py` — ANTLR visitor → AST. *(There is also a stale
  `builder.py.bak` — do not edit; it is a backup, not the live builder.)*
- `src/pynescript/ast/helper.py` — `parse()`, `unparse()`, `dump()`, `literal_eval()`.
- `src/pynescript/ast/node.py` — AST node re-exports.
- `src/pynescript/ast/transformer.py` — `NodeTransformer` (rewrite AST).
- `src/pynescript/ast/visitor.py` — `NodeVisitor` (read AST).
- `src/pynescript/ast/linter.py` — `PineLinter`, `LintWarning`, `lint_script()`.

## Generated Artifacts (never edit)

- `src/pynescript/ast/grammar/antlr4/generated/` — ANTLR4-generated parser/lexer.
- `src/pynescript/ast/grammar/asdl/generated/PinescriptASTNode.py` — ASDL node classes.

## Source of Truth (edit these)

- `src/pynescript/ast/grammar/antlr4/resource/PinescriptLexer.g4`
- `src/pynescript/ast/grammar/antlr4/resource/PinescriptParser.g4`
- `src/pynescript/ast/grammar/asdl/resource/Pinescript.asdl`

For a high-level orientation to the Pine Script language itself (syntax, types,
UDTs, control flow, gotchas), see
[`pine-script-language.md`](./pine-script-language.md).

## ASDL Notes

ASDL defines the AST shape (modules, statements, expressions). The `Pinescript`
module's `Script` is the root. `expr` covers BinOp, UnaryOp, Call, Subscript, etc.
See `ast/grammar/asdl/resource/Pinescript.asdl` for the full schema.

## 📂 Codebase References

- **Implementation**: `src/pynescript/ast/builder.py` (live AST builder)
- **Implementation**: `src/pynescript/ast/helper.py` (parse/unparse/literal_eval)
- **Reference**: `src/pynescript/ast/grammar/antlr4/resource/PinescriptParser.g4`
- **Reference**: `src/pynescript/ast/grammar/asdl/resource/Pinescript.asdl`
