# AGENTS.md

Compact guide for AI agents working in the **pyne** repo (package name
`pynescript`). Read this first to avoid common mistakes; dive into
`.opencode/context/project-intelligence/` for deeper reference.

## What this is

Python toolchain for TradingView Pine Script: parser, AST, evaluator, linter,
LSP server, Flask Pro API, VS Code extension. Source under `src/pynescript/`
(src-layout package), ANTLR4 grammar, ASDL-generated AST nodes, Nuitka-compiled
LSP binary, optional cloud backend.

**AXIS** (charting PWA) is **not** in this repo — see
[jango-blockchained/axis](https://github.com/jango-blockchained/axis)
(`/home/jango/Git/axis`).

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
- **Do not recreate `frontend/`.** AXIS was extracted to the `axis` repo (2026-07).

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

## Pine v6 Grammar & Regeneration Notes (2026-07)

When adding v6 features that touch literals or syntax (multiline strings `"""..."""` / `'''...'''`, etc.):

- The resource `PinescriptLexer.g4` may require **non-obvious quoting** for triple-quoted fragments. Direct `"'''"` or `'"""'` literals inside fragment rules can trigger ANTLR "quote came as a complete surprise" errors even if single/double work. Use factored starters:
  ```g4
  fragment TRIPLE_SQ_START: '\'' '\'' '\'';
  fragment TRIPLE_SINGLE_QUOTED_STRING: TRIPLE_SQ_START ... TRIPLE_SQ_START;
  ```
- `generate.py` (and `hatch run lint:gen-parser`) hardcodes `$(python -c 'sys.executable')/antlr4`. The `antlr4-cli` pip package often lands in `~/.local/bin`. Use a temp dir + full path or `PATH` shim + manual copy of `*Base.py`.
- Full regeneration can produce parser context classes whose accessor methods (e.g. `template_spec_suffix()`) differ from what `builder.py` expects. **Safe pattern observed**: edit only resource + selectively copy the fresh `PinescriptLexer.py` (and update the copied `LexerBase.py`). Leave the committed `PinescriptParser.py` (and its visitors) untouched unless you are prepared to also patch the builder.
- Always test with direct `from pynescript.ast.helper import parse, unparse` on a minimal v6 snippet containing the new syntax **before** running the huge parametrized corpus.
- After success, update `docs/missing_features.md` and the grammar-changes guide.

See `.opencode/context/project-intelligence/guides/grammar-changes.md` (case study) and `docs/missing_features.md`.
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

---

## Sister Repos & websites

**Site:** [hoox.sh](https://hoox.sh) — marketing + product docs for the stack.

| Product | GitHub | Local path | Website |
|---|---|---|---|
| **HOOX** | [jango-blockchained/hoox](https://github.com/jango-blockchained/hoox) | `/home/jango/Git/hoox` | [hoox.sh](https://hoox.sh) · [docs.hoox.sh](https://docs.hoox.sh) |
| **PYNE** (this repo) | [jango-blockchained/pyne](https://github.com/jango-blockchained/pyne) | `/home/jango/Git/pynescript` | [hoox.sh/pyne](https://hoox.sh/pyne) · [docs](https://hoox.sh/pyne/docs) |
| **AXIS** | [jango-blockchained/axis](https://github.com/jango-blockchained/axis) | `/home/jango/Git/axis` | [hoox.sh/axis](https://hoox.sh/axis) · [docs](https://hoox.sh/axis/docs) |

Related:

| Repo | Path | Purpose |
|---|---|---|
| `hoox-landing-page` | `/home/jango/Git/hoox-landing-page` | Marketing site source for [hoox.sh](https://hoox.sh) |
| `pyne-worker` | `/home/jango/Git/pyne-worker` | Python CF Worker — edge eval (depends on `pynescript`) |
| `pine-worker` | `/home/jango/Git/pine-worker` | TypeScript CF Worker — Pine eval + trade events |

**Key dependency links:**
- AXIS UI → pyne Pro API (`make run` on `:5002`) or AXIS Worker
- `pyne-worker` → `pynescript` package (editable install)
- HOOX trade path can consume Pine signals from edge workers

```
                    https://hoox.sh
           ┌──────────────┼──────────────┐
           ▼              ▼              ▼
         HOOX            PYNE           AXIS
    (edge execution)  (this repo)   (charting UI)
           │              │              │
           └──────────────┴──────────────┘
```
