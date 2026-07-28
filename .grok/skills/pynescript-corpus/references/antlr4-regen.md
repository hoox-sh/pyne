# ANTLR4 regen notes (pynescript)

## Why temp dir

Running `antlr4 -o generated resource/PinescriptLexer.g4` while the grammar
lives under `src/...` can emit a nested `src/...` tree inside the output dir.
Copy both `.g4` files into a flat temp directory and generate there.

## Order

1. Generate **Lexer** first (writes `PinescriptLexer.tokens`).
2. Generate **Parser** second (`tokenVocab=PinescriptLexer`).

## Bases

`PinescriptLexerBase.py` / `PinescriptParserBase.py` are **hand-written**.
Copy from `resource/` into `generated/` after every regen (antlr does not emit them).

## Builder coupling

Full parser regen changes context class method names. After regen, run a quick
`parse()` smoke on `indicator("t")\nplot(1)`. If builder AttributeErrors appear
(e.g. missing `template_spec_suffix()`), either:

- update `builder.py` to the new accessors, or
- revert to the previous `PinescriptParser.py` and only ship lexer changes.

## ASDL

New operator classes (e.g. `BitAnd`) require ASDL resource edit + `asdlgen.py`.
Unparser precedence tables and evaluator `visit_BinOp` should learn the new ops
when evaluation matters; corpus parse+unparse only needs builder + unparser.
