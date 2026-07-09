# AGENTS.md

Compact guide for AI agents working in the **pynescript** repo. Read this first
to avoid common mistakes; dive into `.opencode/context/project-intelligence/`
for deeper reference.

## What this is

Python toolchain for TradingView Pine Script: parser, AST, evaluator, linter,
LSP server, Flask Pro API, VS Code extension. Source under `src/pynescript/`
(src-layout package), ANTLR4 grammar, ASDL-generated AST nodes, Nuitka-compiled
LSP binary, optional cloud backend.

## Quick Commands

```bash
make install         # pip install -e ".[lsp]"
make test            # pytest tests/ -v --tb=short          (all tests)
make test-lsp        # tests/test_langserver.py + test_lsp_features.py
make test-backend    # tests/test_backend.py (needs pip install -r backend/requirements.txt)
make lint            # ruff check src/ tests/ backend/
make fmt             # ruff format
make run             # python -m backend.app                 (Flask Pro API)
make run-lsp         # python -m pynescript.langserver        (LSP)
make build-check     # python scripts/build/compile.py --check   (fast, no compile)
```

Hatch equivalents: `hatch run test:test`, `hatch run lint:style`,
`hatch run lint:typing`. See `.opencode/context/project-intelligence/lookup/commands.md`.

## Hard Constraints

- **Edit only `resource/` for the grammar**; never touch
  `src/pynescript/ast/grammar/antlr4/generated/` or
  `src/pynescript/ast/grammar/asdl/generated/` — both are regenerated artifacts.
  See `.opencode/context/project-intelligence/guides/grammar-changes.md`.
- **No stale backups in `src/`.** `builder.py.bak` and
  `evaluator/builtins/technical_refactored.py` were removed in 2026-07; do not
  recreate them — the live `builder.py` and `technical.py` are the only sources
  of truth.
- **`from __future__ import annotations` is required** on every new Python file
  (enforced by ruff isort `required-imports`).
- **Console scripts are separate**: `pynescript` (Click) and `pynescript-lsp`
  (pygls). Don't conflate them.
- **`tests/conftest.py` parametrizes `pinescript_filepath` over every `*.pine`
  in `tests/data/builtin_scripts/`** — a new test using this fixture runs ~500
  cases. Use `--example-scripts-dir=...` to narrow.
- **Generated `builtin_metadata.json` is built from code**, not hand-edited.
  Re-run `python scripts/generate_builtin_metadata.py` after adding builtins.

## Build / Release Quirks

- `scripts/build/.metadata.key` is **gitignored**; the symmetric Fernet key for
  encrypting `builtin_metadata.json.enc`. CI must supply it as `CRYPTO_KEY`:
  - GitHub Actions: `secrets.METADATA_KEY` (see `.github/workflows/ci.yml`).
  - Cloud Build: `${_METADATA_KEY}` (see `cloudbuild.yaml`).
  Without it, every CI run produces a different encrypted blob (not a bug, but
  hurts reproducibility).
- `make build` produces `dist/lsp/pynescript-lsp` (onefile Nuitka binary) and
  `dist/vsix/pynescript-*.vsix`. Use `make build-check` for a fast import check
  (~30s) without compiling.
- Anaconda envs need `conda install libpython-static` or `--static-libpython=no`
  (the default in `scripts/build/compile.py`).
- The VS Code extension is a separate Node 22 project under `vscode-extension/`.
  Build with `make build-vscode` (or `npm ci && npm run compile && npx vsce package`).
- `pine-worker/` is the colocated TypeScript port of the evaluator + a Python→TS converter tool. Treat it as an extra tool of the main repo (Bun + tests + parity with the Python oracle).

## Codebase Entry Points

| Want to ... | Look at |
| --- | --- |
| Parse / unparse Pine Script | `src/pynescript/ast/helper.py` |
| Add a new builtin (`ta.*`, `math.*`, …) | `src/pynescript/ast/evaluator/builtins/<ns>.py` + `scripts/generate_builtin_metadata.py` |
| Add an LSP feature | `src/pynescript/langserver/features/<name>.py` + `server.py` |
| Wire inlay hints / hover / etc. | `src/pynescript/langserver/features/inlay_hints.py` is a worked example |
| Add a CLI subcommand | `src/pynescript/__main__.py` (Click group) |
| Change the grammar | `src/pynescript/ast/grammar/antlr4/resource/*.g4`, then `hatch run lint:gen-parser` |
| Add a backend endpoint | `backend/api/preview.py` (Flask blueprints) |
| Work on the TS port (pine-worker) | `pine-worker/` (extra tool; see its README + the strategy-events plan) |

## Testing

- **Unit**: `tests/test_evaluator.py`, `tests/test_linter.py`,
  `tests/test_parse_and_unparse.py`.
- **LSP unit**: `tests/test_lsp_features.py` — calls handlers directly with
  fake `lsprotocol.types.*Params`.
- **LSP e2e**: `tests/test_langserver.py` — needs
  `pip install -e ".[dev-lsp]" pytest-asyncio`.
- **Backend**: `tests/test_backend.py` — needs `flask flask-cors numpy matplotlib`.
- **Corpus**: `tests/data/builtin_scripts/*.pine` powers the parametrize
  fixture; `tests/data/library/` is reference material only.
- Coverage: `hatch run test:test-cov` (parallel + lcov). CI uploads via codecov
  only on Python 3.13.

## Style

Ruff with line length 120 and a wide rule set (see `pyproject.toml`). Black
target-version `py310`. Mypy is strict-ish but exempts generated grammar
modules, `evaluator.builtins.*`, and `tests.*`. `from __future__ import
annotations` is mandatory (also via ruff isort `required-imports`).

## Sub-Skills

- **Brainstorm** before any non-trivial feature work (the
  `brainstorming` skill is recommended in `.opencode`).
- **TDD** when implementing features (see `test-driven-development` skill).
- **Verification before completion** — run `make test lint` and confirm output
  before claiming done.

## Where to Read More

- `.opencode/context/navigation.md` — full context tree map.
- `.opencode/context/project-intelligence/navigation.md` — internal docs.
- `.opencode/context/libraries/navigation.md` — pygls/antlr/click/Nuitka/lsprotocol references (sourced via context7).
- `.opencode/plans/pynescript-lsp-implementation.md` — 1000+ line LSP design doc (read for big-picture LSP work).
- `docs/` — Sphinx docs source (`hatch run docs:build`).
- `CONTRIBUTING.md` — official hatch-based dev workflow.
