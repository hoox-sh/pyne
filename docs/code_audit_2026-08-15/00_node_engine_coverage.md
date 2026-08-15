# Node → engine coverage matrix

**Date:** 2026-08-15  
**Phase:** 0 ingest (Lead Architect)  
**Schema:** `src/pynescript/ast/grammar/asdl/resource/Pinescript.asdl`  
**Dispatch:** `NodeVisitor.visit` is type-object keyed (`visitor.py`). Interpreter fail-closes in `BaseEvaluator.generic_visit`. Compiler inherits silent `NodeVisitor.generic_visit`.

Legend: **Y** = dedicated `visit_*` (or builder ANTLR `visit*`). **I** = inspected via parent (`isinstance` / field walk). **—** = not executed / not lowered. **D** = dead on composed MRO.

| ASDL node | Builder | Interpret | Compile | Unparse | Notes |
| --- | :---: | :---: | :---: | :---: | --- |
| `Script` | Y | Y | Y | Y | Compile/Runtime entry. |
| `Expression` | Y | I | — | Y | `literal_eval` unwraps `.body`. Compile expects a script. |
| `FunctionDef` | Y | Y | Y | Y | Grammar return type **dropped** (no ASDL field). |
| `TypeDef` | Y | Y | Y | Y | Compile → `object_mode`. |
| `EnumDef` | Y | Y | Y | Y | |
| `Assign` | Y | Y | Y | Y | `var`/`varip` via `mode`. |
| `ReAssign` | Y | Y | Y | Y | `:=` history + UDT fields. |
| `AugAssign` | Y | Y | Y | Y | Interpret rebinds via `_bind_series_name` (Wave B). |
| `Import` | Y | Y | Y | Y | Compile stubs + `object_mode`. |
| `Expr` | Y | Y | Y | Y | |
| `Break` / `Continue` | Y | Y | Y | Y | |
| `BoolOp` | Y | Y | Y | Y | |
| `BinOp` | Y | Y | Y | Y | |
| `UnaryOp` | Y | Y | Y | Y | |
| `Conditional` | Y | Y | Y | Y | Ternary. |
| `Compare` | Y | Y | Y | Y | |
| `Call` | Y | Y | Y | Y | Hottest node. Interpret ~850 LOC; compile ~2500. |
| `Constant` | Y | Y | Y | Y | |
| `Attribute` | Y | Y | Y | Y | |
| `Subscript` | Y | Y | Y | Y | History `close[n]`; type `float[]`. |
| `Name` | Y | Y | Y | Y | |
| `Tuple` | Y | Y | Y | Y | Unpack assign both engines. |
| `ForTo` / `ForIn` / `While` | Y | Y | Y | Y | |
| `If` | Y | Y / D | Y | Y | Interpret: `ExpressionEvaluator` wins MRO; `StatementEvaluator.visit_If` dead. |
| `Switch` | Y | Y / D | Y | Y | Same MRO as `If`. |
| `Qualify` | Y | I | — | Y | Type specs only. Value visit would fail-close interpret / silent-skip compile. |
| `Specialize` | Y | Y | Y | Y | Compile unwraps to callee. |
| `Var` / `VarIp` | Y | I | I | Y | `Assign.mode`. |
| `Const` / `Input` / `Simple` / `Series` | Y | I | I | Y | Type qualifiers, not runtime values. |
| `Load` / `Store` | Y | I | I | — | Builder singletons. |
| operators / compare / bool / unary | Y | I | I | Y | Interpret has `visit_Eq`…`visit_GtE`. |
| `Param` / `Arg` | Y | I | I | Y | Walked from `FunctionDef` / `Call`. |
| `Case` | Y | I | I | Y | Walked from `Switch`. |
| `Comment` | Y | — | — | Y | Annotations attached in `helper` post-pass. |

## Visitor architecture (do not recouple)

```
NodeVisitor (type-cache dispatch)
  ├─ NodeTransformer          rewrite
  ├─ NodeLiteralEvaluator     interpret (mixin MRO)
  │    Base → Literal → Expression → Builtin → Statement → Name
  └─ CompilerVisitor          lower to Python / Numba
```

- **Parse cache** (`helper.py`): sha256 LRU, default ON. Hits return **shared AST identity** after `_scrub_pine_call_sites`. Call-site TA/plot state keys `id(Call)`.
- **Builder** is a separate ANTLR visitor (`PinescriptASTBuilder`), reused as `_SHARED_BUILDER`. Operator/ctx nodes are module singletons (`_LOAD`, `_ADD`, …).
- **Compile fail-open vs interpret fail-closed** is the highest architectural hazard on this matrix.

## Coverage holes that can drive this sprint

1. **`Qualify` has no engine visitor.** Safe today because it only appears on `Assign.type` / param types (parent inspect). Do not start visiting type annotations with `self.visit(type_node)`.
2. **UDF/method return types parse and vanish.** `builder.py` `visitFunction_declaration` / `visitMethod_declaration` document the ASDL gap. Frontend-only unless we add an ASDL field — that would force both engines.
3. **`Expression` root is interpret-only.** Compile path is script/bar-loop. Keep it that way.
4. **God methods, not missing nodes.** Executable ASDL is essentially fully visited. Remaining work is `visit_Call` / `visit_Assign` cost and emit quality, not new node kinds.

## Merge-order implication

Grammar last. ASDL field additions are a **cross-engine contract change** (Frontend + Interpreter + JIT + QA in one PR). Prefer this sprint: no ASDL edits unless a top-3 audit proves a runtime hole.
