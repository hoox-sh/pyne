<!-- Context: project-intelligence/guides/grammar-changes | Priority: medium | Version: 1.1 | Updated: 2026-07-12 -->

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

## Case Study: Adding Pine Script v6 Multiline Strings (2026-07)

### The Feature
Pine v6 (April 2026) added triple-quoted multiline strings:
```pinescript
s = """
line one
  indented line
"""
```
Newlines and **all** source indentation must be preserved literally (no automatic dedent or `\n` escaping required).

### Problems Encountered
1. **Resource g4 already contained attempted triple rules** but they used quoting that the ANTLR tool rejected:
   - `fragment TRIPLE_SINGLE... : "'''" ... "'''" ;`
   - Error: `syntax error: '"' came as a complete surprise to me`
2. The **committed generated lexer** did not contain the `TRIPLE_*` fragments (even when resource had been edited). Old single/double rules caused the content after `"""` to be tokenized incorrectly (manifested as "mismatched input expecting for/if/switch/while" because the parser fell into `structure_expression`).
3. `PinescriptLexerBase._handle_STRING_token` already had special-case code for `startswith('"""')` or `startswith("'''")` — the intent was there, the compiled ATN was not.
4. Full regeneration via the project's `generate.py` + `antlr4-cli` produced a `PinescriptParser.py` whose context classes lacked methods the hand-written `builder.py` expected (e.g. `template_spec_suffix()`), breaking even simple parses.
5. Path issues: running antlr while the `.g4` lived under `src/...` caused it to emit files under a mirrored `src/` subdirectory inside the output dir.

### Solution
- **Resource only change** (per hard rule):
  ```g4
  fragment TRIPLE_SQ_START: '\'' '\'' '\'';
  fragment TRIPLE_SINGLE_QUOTED_STRING: TRIPLE_SQ_START (STRING_CHAR_NO_SINGLE_QUOTE | STRING_ESCAPE_SEQ | OS_INDEPENDENT_NL)*? TRIPLE_SQ_START;
  fragment TRIPLE_DOUBLE_QUOTED_STRING: '"""' (STRING_CHAR_NO_DOUBLE_QUOTE | STRING_ESCAPE_SEQ | OS_INDEPENDENT_NL)*? '"""';
  ```
- Generated only the **lexer** in a clean `/tmp` directory (avoids mirroring).
- Copied **only** `PinescriptLexer.py` + refreshed `LexerBase.py` into `generated/`. Left `PinescriptParser.py` and visitors at their committed versions.
- Verified immediately with:
  ```python
  from pynescript.ast.helper import parse, unparse
  ast = parse('''indicator("x")\ns = """\nfoo\n  bar\n"""\n''')
  assert "foo" in unparse(ast)
  ```
- Updated `docs/missing_features.md`.

### Outcome
Multiline strings now parse, round-trip, and preserve content + indentation exactly. The same pattern (resource edit + targeted lexer refresh) is the recommended practical workflow when full regen would require simultaneous builder surgery.

### Related Work in Same Session
- Matrix `sort_field` support (evaluator side, no grammar change) was implemented in parallel by extending `Matrix` class + `matrix_evaluator.py` (mirroring the UDT logic already present in `arrays.py` using `ObjectInstance.get_field` / `.fields`).

See also `AGENTS.md` (Pine v6 grammar notes) and the 2026-07 updates in `docs/missing_features.md`.
