<!-- Context: project-intelligence/examples/parse-and-unparse | Priority: high | Version: 1.0 | Updated: 2026-07-05 -->

# Parse & Unparse (Round-Trip)

The core public API lives in `pynescript.ast`. The simplest workflow is parse →
inspect → unparse.

## Minimal Example

```python
from pynescript.ast import parse, unparse, dump

source = """
//@version=5
indicator("My RSI")
rsi(close, 14)
"""

tree = parse(source, filename="<demo>")
print(dump(tree))                # human-readable AST
print(unparse(tree))             # regenerate source
```

## CLI Equivalent

```bash
pynescript parse-and-dump examples/rsi_strategy.pine
pynescript parse-and-unparse messy.pine > clean.pine
```

## Evaluating Expressions

```python
from pynescript.ast import literal_eval

literal_eval("1 + 2 * 3")                       # → 7
literal_eval("ta.sma([100, 102, 101], 3)")       # → 101.0
literal_eval("math.max(close, open)")
```

`literal_eval` uses `NodeLiteralEvaluator` — safe subset (no side effects), covers
all `ta.*`, `math.*`, `str.*`, etc.

## AST Visitor / Transformer

```python
from pynescript.ast import parse
from pynescript.ast.transformer import NodeTransformer

class Renamer(NodeTransformer):
    def visit_Name(self, node):
        if node.id == "close":
            node.id = "price"
        return node

tree = parse(source)
new_tree = Renamer().visit(tree)
```

## Gotchas

- `parse(source, filename)` — `filename` is used for error messages; pass `"<stdin>"`
  or a real path.
- Comments like `//@version=5` are turned into script-level annotations on the root
  `Script` node; not lost on round-trip.
- `dump(indent=2)` (default) prints the AST; use `dump(tree, indent=None)` for a
  single line.

## 📂 Codebase References

- **Implementation**: `src/pynescript/ast/helper.py` — `parse`, `unparse`,
  `dump`, `literal_eval`.
- **Implementation**: `src/pynescript/ast/transformer.py` — `NodeTransformer`.
- **Implementation**: `src/pynescript/__main__.py` — `parse-and-dump`,
  `parse-and-unparse` Click commands.
