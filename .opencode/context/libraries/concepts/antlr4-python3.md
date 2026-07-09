<!-- Context: libraries/concepts/antlr4-python3 | Priority: high | Version: 1.0 | Updated: 2026-07-05 -->

# ANTLR4 Python Runtime

Python target for ANTLR4-generated parsers. Used by `src/pynescript/ast/helper.py`
and the builder in `src/pynescript/ast/builder.py`.

**context7 source**: `/antlr/antlr4` — `doc/python-target.md`,
`doc/listeners.md`. Verify at runtime; this is a distilled summary.

## Key Imports

```python
from antlr4 import (
    InputStream, FileStream, CommonTokenStream, ParseTreeWalker,
)
```

- `InputStream` — wraps a Python `str` for the lexer.
- `FileStream` — reads a file with optional encoding.
- `CommonTokenStream` — buffer between lexer and parser.
- `ParseTreeWalker` — walks a parse tree firing listener events.

## Typical Driver (this repo's pattern)

```python
from antlr4 import FileStream, CommonTokenStream
from pynescript.ast.grammar.antlr4.lexer import PinescriptLexer
from pynescript.ast.grammar.antlr4.parser import PinescriptParser
from pynescript.ast.builder import PinescriptASTBuilder

input_stream = FileStream(path, encoding="utf-8")
lexer = PinescriptLexer(input_stream)
stream = CommonTokenStream(lexer)
parser = PinescriptParser(stream)
tree = parser.start_()       # entry rule (named for grammar; often ends with `_`)

if parser.getNumberOfSyntaxErrors() > 0:
    raise SyntaxError(...)

builder = PinescriptASTBuilder()
ast_root = builder.visit(tree)   # PinescriptParserVisitor.visit() is generated
```

## Visitor vs Listener

- **Visitor** (`PinescriptParserVisitor`) — explicit tree walk via
  `visit_<RuleName>` methods; returns sub-results. **Used here.**
- **Listener** (`PinescriptParserListener`) — event-driven
  (`enter_<Rule>`, `exit_<Rule>`); uses `ParseTreeWalker.DEFAULT.walk(...)`.

## Error Listener Pattern (this repo)

`src/pynescript/ast/grammar/antlr4/error_listener.py` overrides ANTLR's
`BaseErrorListener` to collect `line`, `column`, and `msg` for the
`PineLinter`.

## PyPI Install

```bash
pip install antlr4-python3-runtime>=4.13.1
```

## Gotchas

- Python reserved words in grammar get a trailing underscore: `start_`, `class_`.
- The generated parser/lexer classes are in `grammar/antlr4/generated/` —
  do not edit; regenerate via `hatch run lint:gen-parser` (requires Java + ANTLR4).
- `FileStream` defaults to `utf-8`; pass `encoding="utf-8"` explicitly when
  reading non-ASCII Pine scripts.

## 📂 Codebase References

- **Implementation**: `src/pynescript/ast/helper.py` — driver.
- **Implementation**: `src/pynescript/ast/grammar/antlr4/error_listener.py`.
- **Reference**: `pyproject.toml` — `antlr4-python3-runtime>=4.13.1`.
- **Reference**: `src/pynescript/ast/grammar/antlr4/resource/PinescriptParser.g4`.
