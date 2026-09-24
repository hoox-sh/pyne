# docs/pyne/core

# Concepts

* [ASDL Schema](asdl-schema.md) - Algebraic AST definition in Pinescript.asdl, generated dataclasses, and how schema changes flow into the pipeline.
* [AST Builder](builder.md) - PinescriptASTBuilder: ANTLR parse-tree visitor that constructs ASDL nodes, locations, and comment kinds.
* [Error Model](error-model.md) - SyntaxError, IndentationError, SyntaxErrorDetails, and PinescriptErrorListener bridge from ANTLR to diagnostics.
* [Grammar (ANTLR4)](grammar-antlr4.md) - Resource .g4 grammars, generated artifacts, INDENT/DEDENT, regeneration, and the never-edit-generated rule.
* [Helper API](helper-api.md) - parse, sha256 LRU cache, unparse, dump, walk, literaleval, and location utilities — the public AST surface.
* [Language Core](index.md) - ANTLR4 grammar, ASDL AST, builder, visitors, unparser, type system, linter, and error model for PYNE.
* [Linter](linter.md) - PineLinter static rules: syntax via parse, version, deprecations, naming, style codes.
* [Type System](type-system.md) - Pine v6 type model: qualifiers, builtins, collections, UDTs, TypeRegistry, and MethodResolver.
* [Unparser](unparser.md) - NodeUnparser: precedence-aware AST → Pine Script source regeneration.
* [Visitor & Transformer](visitor-transformer.md) - NodeVisitor and NodeTransformer: read-only traversal vs in-place AST rewrite with caching dispatch.
