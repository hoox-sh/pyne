<!-- Context: project-intelligence/guides/dev-setup | Priority: high | Version: 1.0 | Updated: 2026-07-05 -->

# Dev Setup

Python 3.10+ is required. The project ships with both a `Makefile` and a `hatch`
env layout — pick one.

## Option A — Make + pip

```bash
# Core + LSP:
make install         # → pip install -e ".[lsp]"

# Run the API locally:
pip install -r backend/requirements.txt   # flask, flask-cors, numpy, matplotlib
make run                                    # → python -m backend.app

# Run the LSP server:
make run-lsp                                 # → python -m pynescript.langserver
```

## Option B — Hatch (per `CONTRIBUTING.md`)

```bash
# 1. Install hatch (https://hatch.pypa.io):
pip install hatch

# 2. Run tests / lint inside isolated envs:
hatch run test:test
hatch run lint:style    # ruff check
hatch run lint:typing   # mypy
hatch run docs:build    # sphinx-build docs docs/_build
```

Hatch envs (from `pyproject.toml`):
- `test` — pytest, pytest-cov, pytest-xdist, flask, lsprotocol, pygls, pytest-lsp,
  flask-cors.
- `lint` — `detached: true`; installs antlr4-cli, black, mypy, pyasdl, ruff.
- `docs` — `detached: true`; furo, myst-parser, sphinx, sphinx-click.

## VS Code Extension (separate node project)

```bash
make build-vscode
# → cd vscode-extension && npm install && npm run compile && npx vsce package
```

Node 22 (per `ci.yml` cache). The TypeScript build emits to `vscode-extension/out/`.

## Optional Deps

| Extra | Installs |
| --- | --- |
| `.[lsp]` | `pygls`, `lsprotocol` |
| `.[dev-lsp]` | `pygls`, `lsprotocol`, `pytest-lsp` |
| `.[dev]` (via hatch `test` env) | pytest, coverage, xdist, flask, flask-cors |

## Editor Wiring (client side)

- VS Code: install the `pynescript` extension from the marketplace — auto-activates
  on `.pine` files.
- Neovim (nvim-lspconfig):
  ```lua
  require('lspconfig').pynescript.setup({})
  ```
- Zed: `settings.json` → `language_servers.pynescript` with `command: "pynescript-lsp"`.
- Emacs (lsp-mode): see `clients/emacs/`.

See `clients/` for the canonical config snippets and full guides.

## 📂 Codebase References

- **Reference**: `pyproject.toml` — `[project.optional-dependencies]`, hatch envs.
- **Reference**: `Makefile` — `install`, `run`, `run-lsp`, `build-vscode`.
- **Reference**: `CONTRIBUTING.md` — official hatch-based workflow.
- **Reference**: `clients/` — editor config snippets.
