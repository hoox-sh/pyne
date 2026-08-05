# Agent 09 — Collections / strings

| Field | Value |
| --- | --- |
| **Role / ID** | 09 — collections / strings |
| **Verdict** | **win** (goldens landed; soft-na expanded) |
| **Date** | 2026-08-04 |

## Files

| Path | Role |
| --- | --- |
| `builtins/arrays.py` | Negative indices, soft paths |
| `builtins/matrix_evaluator.py` | Region / soft semantics |
| `builtins/map.py` + `map_evaluator.py` | Soft map ops |
| `builtins/strings.py` | match / pos / soft-na |
| `tests/test_corpus_collections_r8.py` | Runtime goldens |
| `tests/test_collections.py` | Expanded unit cases |

## Intentional non-goals

Do **not** soft-suppress library `runtime.error` validation demos (R7 residual 6).

## Tests

`tests/test_corpus_collections_r8.py` + `tests/test_collections.py` (included in
R8 focused suite).
