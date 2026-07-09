# Data Flow

```
.pine source → ANTLR4 Lexer → ANTLR4 Parser → Parse Tree → AST (ASDL nodes)
                                                                    ↓
                                                            Visitor / Transformer
                                                                    ↓
                                                        Evaluator / Linter / Unparser
```

## Stages

1. **Lexing**: ANTLR4 lexer tokenizes `.pine` source
2. **Parsing**: ANTLR4 parser produces a parse tree
3. **AST Construction**: Parse tree → ASDL-based AST nodes
4. **Traversal**: `NodeVisitor` (read-only) or `NodeTransformer` (mutation)
5. **Output**: Evaluation, lint warnings, or formatted source code

## Reference

- Parser wrappers: `src/pynescript/ast/grammar/antlr4/`
- AST nodes: `src/pynescript/ast/node.py` (ASDL-generated)
- Tree traversal: `src/pynescript/ast/visitor.py`, `transformer.py`
