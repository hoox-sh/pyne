<!-- Context: project-intelligence/lookup/commands | Priority: high | Version: 1.0 | Updated: 2026-07-05 -->

# Commands Cheat-Sheet

Every command a developer (or CI) might want. Run from the repo root unless noted.

## Make Targets (`Makefile`)

| Target | Command | Purpose |
| --- | --- | --- |
| `make install` | `pip install -e ".[lsp]"` | Core + LSP editable install |
| `make test` | `pytest tests/ -v --tb=short` | Run all tests |
| `make test-lsp` | `pytest tests/test_langserver.py tests/test_lsp_features.py -v` | LSP-only tests |
| `make test-backend` | `pytest tests/test_backend.py -v` | Backend tests |
| `make lint` | `ruff check src/ tests/ backend/` | Lint |
| `make fmt` | `ruff format src/ tests/ backend/` | Format |
| `make build` | `python scripts/build/compile.py --jobs=4` | Compile LSP onefile + VSIX |
| `make build-check` | `python scripts/build/compile.py --check` | Fast import check |
| `make build-vscode` | `cd vscode-extension && npm ci && npm run compile && npx vsce package` | VS Code ext |
| `make run` | `python -m backend.app` | Run Flask Pro API |
| `make run-lsp` | `python -m pynescript.langserver` | Run LSP server |
| `make docker-build` | `docker build -f Dockerfile.api -t pynescript-api .` | Build API image |
| `make docker-run` | `docker compose up api --build` | Run API in Docker |
| `make clean` | `rm -rf dist/ vscode-extension/out/ vscode-extension/node_modules/ ...` | Clean artifacts |

## Hatch Env Shortcuts (`pyproject.toml`)

| Command | Purpose |
| --- | --- |
| `hatch run test:test` | Run tests |
| `hatch run test:test-cov` | Tests with coverage (lcov) |
| `hatch run test:cov` | Coverage via `coverage` CLI |
| `hatch run lint:style` | `ruff check` |
| `hatch run lint:typing` | `mypy --install-types` on src/ and tests/ |
| `hatch run lint:format` | `ruff format` |
| `hatch run lint:gen-parser` | `antlr4` (rebuild generated parser) |
| `hatch run docs:build` | `sphinx-build docs docs/_build` |

## CLI (after `pip install -e .`)

```bash
pynescript --version
pynescript parse-and-dump file.pine
pynescript parse-and-unparse file.pine
pynescript lint file.pine --fail-on warnings
pynescript data AAPL --provider yahoo --period 6mo
pynescript lsp
pynescript-lsp --stdio
```

## Coverage

```bash
hatch run test:test-cov                       # generates lcov + term report
# CI uploads to codecov from Python 3.13:
#   file: ./coverage.xml
#   see .github/workflows/ci.yml "Upload coverage" step
```

## 📂 Codebase References

- **Reference**: `Makefile` — all `make *` targets.
- **Reference**: `pyproject.toml` — `[tool.hatch.envs.*.scripts]`.
- **Reference**: `.github/workflows/ci.yml` — CI matrix commands.
