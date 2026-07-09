<!-- Context: project-intelligence/guides/adding-builtin | Priority: medium | Version: 1.0 | Updated: 2026-07-05 -->

# Adding a Builtin Function

Builtins (`ta.sma`, `math.max`, `str.tostring`, …) are implemented inside
`src/pynescript/ast/evaluator/builtins/` and exposed via `BuiltinEvaluator`. The
LSP completion/hover set is built from those — the metadata is auto-generated.

## Where to Add Code

- `src/pynescript/ast/evaluator/builtins/` — one Python file per namespace:
  `ta.py`, `math.py`, `str.py`, `array.py`, `matrix.py`, `map.py`, `strategy.py`,
  `request.py`, `input.py`, `color.py`, `plot*.py`, `line.py`, `label.py`, `box.py`,
  `table.py`, `polyline.py`, `alert.py`, `ticker.py`, `timeframe.py`, `chart.py`.

A builtin method is just a method on a mixin class in one of these modules.

## Pattern

```python
# in src/pynescript/ast/evaluator/builtins/ta.py
class TechnicalAnalysisMixin:
    def _eval_ta_sma(self, source, length):
        # `source` is a list, `length` is an int — implement TradingView semantics
        return sum(source[-length:]) / length
```

The visitor dispatches `ta.sma(...)` to `_eval_ta_sma`. Method naming convention:
the leading namespace becomes the leading underscore:
`ta.sma` → `_eval_ta_sma`, `math.max` → `_eval_math_max`.

## Regenerate LSP Metadata

After adding builtins, regenerate the metadata bundle so the LSP picks them up:

```bash
python scripts/generate_builtin_metadata.py
# or, for a release:
make build-check         # fast import check, no compile
```

The script introspects `BuiltinEvaluator` and writes
`src/pynescript/langserver/providers/builtin_metadata.json`. The category is
inferred from the namespace prefix (see `_infer_category()` in the script).

## Type System

If the builtin needs typed parameters (e.g. for LSP signature help), add overloads
in `src/pynescript/ast/type_system.py`. This module is intentionally excluded from
strict ruff rules (`FBT001`, `FBT002` ignored) because it has many boolean params.

## Tests

Add cases to the relevant `tests/test_phase*.py` or a namespace-specific file:

```python
def test_ta_sma_three_bar_average():
    r = literal_eval("ta.sma([100, 102, 101], 3)")
    assert r == 101.0
```

## Gotchas

- Do not edit `builtin_metadata.json` by hand — always regenerate.
- The encrypted `.enc` and `.sha256` files are derived; the build pipeline
  regenerates them. Locally, only the plaintext JSON is needed.
- Mypy is lax on `evaluator.builtins.*` (see `pyproject.toml` override) — most
  `arg-type` / `assignment` / `union-attr` errors are suppressed there.

## 📂 Codebase References

- **Implementation**: `src/pynescript/ast/evaluator/builtins/` — per-namespace mixins.
- **Implementation**: `src/pynescript/ast/evaluator/__init__.py` — combined
  `NodeLiteralEvaluator`, `NodeEvaluator`.
- **Implementation**: `src/pynescript/ast/type_system.py` — typed signatures.
- **Implementation**: `scripts/generate_builtin_metadata.py` — LSP metadata regen.
- **Reference**: `pyproject.toml` — `evaluator.builtins.*` mypy override.
