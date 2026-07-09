# Code Quality Standards

## Mandatory Header

Every Python file must start with:

```python
from __future__ import annotations
```

Enforced by ruff isort (`required-imports`). Do not add this manually — ruff handles it.

## Import Style

Enforced by `[tool.ruff.lint.isort]`:

- `force-single-line = true` — one import per line
- `lines-between-types = 1` — blank line between stdlib, third-party, first-party
- `lines-after-imports = 2` — two blank lines after the import block

```python
from __future__ import annotations

import os

from pathlib import Path

from pynescript.ast.helper import parse
from pynescript.ast.linter import lint_script


def foo():
    ...
```

## Ruff Rules

- Line length: 120
- Target: Python 3.10
- Rule set is extensive (see `pyproject.toml [tool.ruff.lint]`)
- `generated/` directories are excluded from ruff — never edit those files
- Tests allow: `S101` (assert), `PLR2004` (magic numbers), `T201` (print), `TID252`

## Per-File Ignores

| Path | Suppressed Rules | Reason |
|------|-----------------|--------|
| `tests/**/*` | `ARG001`, `C901`, `F841`, `PLR0912`, `PLR2004`, `S101`, `T201`, `TID252` | Test ergonomics |
| `src/pynescript/__main__.py` | `ARG001`, `EM101`, `PLR0913`, `B904`, `PLC0415` | CLI entry point |
| `src/pynescript/util/data.py` | `DTZ005`, `B904`, `PLC0415` | Data provider |
| `src/pynescript/ast/helper.py` | `C901`, `PLC0415`, `PLR1704` | Complex helper |
| `src/pynescript/ast/type_system.py` | `FBT001`, `FBT002` | Type system |

## Mypy Configuration

- Python 3.10 target
- `disallow_untyped_defs = false`, `disallow_incomplete_defs = false`
- `check_untyped_defs = true` (except tests)
- ANTLR/ASDL generated modules — errors ignored entirely
- `pynescript.ast.evaluator.builtins.*` — broad suppressions (dynamic dispatch)
- `pynescript.ast.helper`, `pynescript.ast.builder` — `no-any-return` disabled
- Tests — `check_untyped_defs = false`, errors ignored

## Generated Code

**Never edit** files in these directories — they are regenerated from grammar definitions:

- `src/pynescript/ast/grammar/antlr4/generated/` — ANTLR4 output
- `src/pynescript/ast/grammar/asdl/generated/` — ASDL output

To regenerate ANTLR parser:

```bash
hatch run lint:gen-parser
# or: antlr4 -lib resource/ -o generated/ -Dlanguage=Python3 resource/*.g4
```

## Naming Conventions

- Follow standard Python naming: `snake_case` for functions/variables, `PascalCase` for classes
- AST node names follow ASDL conventions (defined in `resource/` grammar files)
- Evaluator builtin modules mirror Pine Script namespaces: `technical.py`, `strategy.py`, `arrays.py`, etc.

## File Organization

- `src/pynescript/` — Core library (src layout)
- `backend/` — Pro API (Flask), separate from core
- `vscode-extension/` — VS Code extension (TypeScript)
- `clients/` — Editor configs (Neovim, Zed, Emacs, Helix)
- `scripts/` — Build scripts, metadata generation
- `tests/data/builtin_scripts/` — `.pine` test fixtures