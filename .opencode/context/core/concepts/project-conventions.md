# Project Conventions

## Build System

- **Backend**: Hatchling (`pyproject.toml` `[build-system]`)
- **Version**: Dynamic, read from `src/pynescript/__about__.py`
- **Python**: >= 3.10

## Dependency Groups

| Extra | Install | Purpose |
|-------|---------|---------|
| `[lsp]` | `pip install "pynescript[lsp]"` | LSP server (pygls, lsprotocol) |
| `[dev-lsp]` | `pip install -e ".[dev-lsp]"` | LSP + test deps (pytest-lsp) |

## Editor Config

- 4-space indent for Python, 2-space for JSON/YAML/Markdown, tab for Makefiles
- LF line endings, UTF-8, trim trailing whitespace, insert final newline

## Git Conventions

- Release tags: `v*` (triggers CI build + GitHub Release + VS Code Marketplace)
- CI runs on push/PR to `main`
- `scripts/build/.metadata.key` is gitignored (Fernet key)
- `dist/`, `vscode-extension/out/`, `vscode-extension/node_modules/` are gitignored

## Backend (Flask)

- Entry: `python -m backend.app` or `make run`
- Docker: `docker compose up api --build` or `make docker-run`
- Dependencies in `backend/requirements.txt` (separate from core)

## VS Code Extension

- Build: `npm ci && npm run compile && npx vsce package --allow-missing-repository`
- Published on `v*` tag push via CI (requires `VSCE_PAT` secret)
