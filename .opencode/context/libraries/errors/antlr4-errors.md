<!-- Context: libraries/errors/antlr4-errors | Priority: medium | Version: 1.0 | Updated: 2026-07-05 -->

# ANTLR4 Errors

What goes wrong when the grammar or runtime misbehaves. All entries verified
against this repo's `error_listener.py` and builder usage.

## "no viable alternative at input '...'"

Lexer/parser couldn't match a token. Two common causes:
1. **Missing keyword in `PinescriptLexer.g4`** — add the keyword as a `KEYWORD`
   rule and regenerate.
2. **Builder doesn't know the new context** — `visit<X>` method missing on
   `PinescriptASTBuilder` (or the visitor class wasn't regenerated).

Fix: re-run `hatch run lint:gen-parser`, then check `builder.py` for
`visit<NewRuleName>`.

## "missing token at '...'" / "extraneous input '...'"

Parser recovered but the AST shape won't match what the builder expects. The
`PinescriptErrorListener` records these in
`Linter.lint()`-like fashion and surfaces them as `LintWarning`s.

## "ClassCastException" / "AttributeError: 'NoneType' object has no attribute '...'"

A `ctx.<field>()` returned `None` for a required field. Either:
- The grammar accepts an empty alternative and the builder doesn't guard for
  it — add a `None` check.
- The parser rule is wrong — re-check the rule's alternatives.

## "Could not invoke visitor for rule '...'" (pygls side, not ANTLR)

Means the registered handler raised before returning. Check the LSP server
logs (`logging.basicConfig(level=logging.DEBUG)`); pygls prints the traceback.

## Token Stream IndexError

`CommonTokenStream` raises if you try to read past the end before `parser.fill()`
runs. Always let the parser drive the stream; don't index into the stream
before `parser.start_()` returns.

## "antlr4" CLI Not Found

```bash
hatch run lint:gen-parser   # uses the lint env which has antlr4-cli
# or:
pip install antlr4-cli      # requires Java 11+
java -version
```

## Generated Code Out of Sync

If you edit a `.g4` and forget to regenerate, the builder will crash on
`AttributeError` when calling the old generated visitor method. Always regen
before debugging.

## UTF-8 in Pine Scripts

`FileStream` defaults to encoding. If you see garbage in error messages or
`UnicodeDecodeError`, pass `encoding="utf-8"` explicitly:

```python
FileStream(path, encoding="utf-8")
```

## 📂 Codebase References

- **Implementation**: `src/pynescript/ast/grammar/antlr4/error_listener.py`.
- **Implementation**: `src/pynescript/ast/helper.py` — driver.
- **Implementation**: `src/pynescript/ast/builder.py` — visitor.
- **Reference**: `libraries/concepts/antlr4-python3.md`.
