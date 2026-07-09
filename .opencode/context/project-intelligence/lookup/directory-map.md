<!-- Context: project-intelligence/lookup/directory-map | Priority: high | Version: 1.0 | Updated: 2026-07-05 -->

# Directory Map

What lives where. Read this once to avoid hunting for files.

## Top Level

| Path | Role |
| --- | --- |
| `src/pynescript/` | Python package (src-layout) |
| `backend/` | Closed-source-style Flask Pro API |
| `vscode-extension/` | TypeScript VS Code extension |
| `clients/` | Editor config snippets (Neovim, Zed, Emacs, Helix) |
| `scripts/` | Build + utility scripts (Nuitka, metadata gen, copyright) |
| `tests/` | pytest test suite (with `data/` corpus) |
| `docs/` | Sphinx docs (`index.md` includes the README) |
| `examples/` | Sample Pine scripts |
| `dist/` | Build output (gitignored) |
| `reports/` | Generated compatibility reports (json) |
| `logs/` | Runtime logs (gitignored except for committed samples) |
| `Dockerfile`, `Dockerfile.api` | Container images |
| `cloudbuild.yaml` | GCP Cloud Build / Cloud Run deploy |
| `.github/workflows/` | GitHub Actions: `ci.yml`, `release.yml` |
| `pyproject.toml` | Build, deps, hatch envs, ruff/mypy/pytest config |
| `Makefile` | Developer shortcuts |
| `CHANGELOG.md` | Release notes |
| `CONTRIBUTING.md` | Hatch-based dev workflow |
| `CODE_OF_CONDUCT.md`, `LICENSE` | Repo meta |

## `src/pynescript/`

```
src/pynescript/
├── __about__.py                  # version string (hatch reads from here)
├── __init__.py
├── __main__.py                   # `pynescript` Click CLI
├── py.typed                      # PEP 561 marker
├── ast/
│   ├── __init__.py               # re-exports parse/unparse/dump/walk/...
│   ├── builder.py                # ANTLR parse tree → AST (LIVE)
│   ├── builder.py.bak            # stale backup — DO NOT EDIT
│   ├── collector.py
│   ├── error.py
│   ├── helper.py                 # parse, unparse, dump, literal_eval
│   ├── linter.py                 # PineLinter + LintWarning
│   ├── node.py                   # AST node re-exports
│   ├── transformer.py            # NodeTransformer
│   ├── type_system.py            # typed signatures (lax ruff)
│   ├── unparser.py               # AST → source
│   ├── visitor.py                # NodeVisitor
│   ├── evaluator/                # Builtin + literal evaluators (mixins)
│   └── grammar/
│       ├── antlr4/
│       │   ├── resource/         # *.g4 + *Base.py (HAND-EDITED)
│       │   └── generated/        # ANTLR output (REGENERATED)
│       └── asdl/
│           ├── resource/Pinescript.asdl
│           └── generated/PinescriptASTNode.py
├── ext/                          # Pygments lexer entry-point module
├── langserver/
│   ├── __init__.py
│   ├── __main__.py               # `pynescript-lsp` entry
│   ├── server.py                 # PynescriptLanguageServer
│   ├── config.py
│   ├── workspace.py
│   ├── features/                 # completion, hover, formatting, ...
│   ├── protocol/                 # constants, utils
│   └── providers/                # builtin_metadata + completion_items
└── util/
    ├── data.py                   # market data providers (yahoo, ccxt, ...)
    ├── pine_facade.py            # builtin script downloader
    └── itertools.py              # grouper helper
```

## `backend/`

```
backend/
├── app.py                        # Flask app + middleware
├── evaluator.py                  # script exec glue
├── runtime.py                    # Runtime sandbox
├── series.py                     # OHLC helpers
├── requirements.txt              # flask, flask-cors, numpy, matplotlib
├── api/preview.py                # preview_bp, backtest_bp
├── middleware/auth.py            # require_api_key, get_key_store
└── services/                     # chart_renderer.py, backtest.py
```

## `tests/`

See `guides/testing.md` for the full listing.

## 📂 Codebase References

- **Reference**: `pyproject.toml` — `src` layout declared by hatchling defaults.
- **Reference**: `.gitignore` — confirms `dist/`, `vscode-extension/out/`,
  `scripts/build/.metadata.key` are ignored.
