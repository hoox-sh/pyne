<!-- Context: libraries/guides/grammar-workflow | Priority: medium | Version: 1.0 | Updated: 2026-07-05 -->

# Grammar Workflow (`.g4` → generated → builder)

The end-to-end loop for changing the Pine Script grammar. Skip a step and the
parser/builder will be out of sync.

## 1. Edit the Grammar

`src/pynescript/ast/grammar/antlr4/resource/PinescriptLexer.g4` or
`PinescriptParser.g4`.

Example: add a new keyword token.

```antlr
// In PinescriptLexer.g4
MY_NEW_KEYWORD : 'mykw' ;
```

## 2. Regenerate ANTLR Outputs

```bash
# Inside the lint hatch env (pulls in antlr4-cli):
hatch run lint:gen-parser

# Or directly (requires antlr4 CLI on PATH):
antlr4 -Dlanguage=Python3 -visitor -listener \
  -o src/pynescript/ast/grammar/antlr4/generated \
  src/pynescript/ast/grammar/antlr4/resource/PinescriptLexer.g4 \
  src/pynescript/ast/grammar/antlr4/resource/PinescriptParser.g4
```

This overwrites:
- `PinescriptLexer.py`
- `PinescriptParser.py`
- `PinescriptParserVisitor.py`
- `PinescriptParserListener.py`
- `PinescriptLexer.tokens`, `.interp` files

## 3. Update the Builder (if rule structure changed)

`PinescriptASTBuilder` in `src/pynescript/ast/builder.py` is a
`PinescriptParserVisitor` subclass. ANTLR regenerates the parent class with new
`visit_<RuleName>` methods; add overrides as needed.

```python
class PinescriptASTBuilder(PinescriptParserVisitor):
    def visitMyNewRule(self, ctx):
        # `ctx` is the generated MyNewRuleContext
        return MyNewNode(...)
```

`ctx.getText()` returns the raw matched text. To walk children, use
`ctx.<ruleName>()` (returns single) or `ctx.<ruleName>() ` list comprehension
for repeated alternatives.

## 4. (If AST Shape Changed) Regenerate ASDL Nodes

```bash
pyasdl src/pynescript/ast/grammar/asdl/resource/Pinescript.asdl \
  -o src/pynescript/ast/grammar/asdl/generated
```

This rewrites `PinescriptASTNode.py`. Any consumer that imports the new class
directly will keep working; positional constructor args will change.

## 5. Update the Node Re-export

`src/pynescript/ast/node.py` re-exports the new node class. Also confirm
`src/pynescript/ast/__init__.py` re-exports `node.py` so `from pynescript.ast
import MyNewNode` works.

## 6. Run the Tests

```bash
make test          # full suite — many tests parse real .pine files
make test-lsp      # only LSP tests if ANTLR regen was lexer-only
```

The `pinescript_filepath` fixture parses every `.pine` in
`tests/data/builtin_scripts/`. A bad regen will show up as
`SyntaxError` or `KeyError` in those tests.

## 7. Update the Unparser (if needed)

If a new statement/expression form is added, extend
`src/pynescript/ast/unparser.py` so round-trips work.

## Pitfalls

- Don't hand-edit anything in `grammar/antlr4/generated/` — it gets overwritten.
- Lexer rules use uppercase (`MY_TOKEN`); parser rules use lowercaseCamel
  (`myRule`).
- Reserved Python keywords in rule names get an underscore suffix in the
  generated visitor (`visitClass_`).
- The `PinescriptParser.g4` entry rule is named `start_` (because `start` is a
  Python keyword). The driver calls `parser.start_()`.

## 📂 Codebase References

- **Implementation**: `src/pynescript/ast/grammar/antlr4/resource/*.g4` — edit.
- **Implementation**: `src/pynescript/ast/builder.py` — visitor subclass.
- **Implementation**: `src/pynescript/ast/grammar/asdl/resource/Pinescript.asdl`.
- **Reference**: `pyproject.toml` — `[tool.hatch.envs.lint.dependencies]`
  installs `antlr4-cli` and `pyasdl`.
- **Reference**: `libraries/concepts/antlr4-python3.md`.
