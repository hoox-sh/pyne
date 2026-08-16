# Contributing to pyne

> Part of **[HOOX](https://hoox.sh)**: [pyne](https://hoox.sh/pyne) · [axis](https://hoox.sh/axis) · [hoox](https://hoox.sh)  
> Charting UI contributions go to **[hoox-sh/axis](https://github.com/hoox-sh/axis)** (sister repo; historical `jango-blockchained/axis`).

Thank you for your interest in contributing to pyne!

## Getting Started

```bash
git clone --recurse-submodules https://github.com/hoox-sh/pyne.git
# or after a plain clone:
git submodule update --init --recursive
```

`pynets/` is the only git submodule ([hoox-sh/pynets](https://github.com/hoox-sh/pynets)). Do not add in-tree copies. Work on PyneTS in the standalone repo and bump the submodule pointer here. **`pyne-lsp` is in-tree** (`src/pynescript/langserver/`), not a submodule.

Please refer to the documentation in the `docs/` directory for detailed instructions on setting up your development environment and understanding the project structure.

- Product docs: [hoox.sh/pyne/docs](https://hoox.sh/pyne/docs) · [Contributing (Mintlify)](docs/pyne/contributing.mdx)
- Everyday commands: `make install` / `make test` / `make lint` (Hatch envs still work: `hatch run test:test`)

## Development Workflow

1.  **Fork the repository** and create your branch from `main`.
2.  **Install**: `make install` (editable + LSP) or `pip install -e ".[lsp,pro]"`. Hatch envs are optional.
3.  **Run tests**: `make test` / `hatch run test:test`.
4.  **Make your changes**.
5.  **Lint / format**: `make lint` / `make fmt`, or `hatch run lint:style` and `hatch run lint:typing`.
6.  **Submit a Pull Request**.

## Code Style

We use `ruff` and `black` for code formatting. Please ensure your code passes the linting checks before submitting.

## Reporting Issues

If you find a bug or have a feature request, please open an issue on GitHub.

## Release / PyPI publication

| | |
|---|---|
| **PyPI distribution name** | [`hoox-pyne`](https://pypi.org/project/hoox-pyne/) |
| **Import package** | `pynescript` (unchanged) |
| **Console scripts** | **`pyne`**, **`pyne-lsp`** (aliases: `pynescript`, `pynescript-lsp`) |
| **Product / repo** | **pyne** · [hoox-sh/pyne](https://github.com/hoox-sh/pyne) |
| **GitHub org** | [`hoox-sh`](https://github.com/hoox-sh) (hoox.sh) |

> Historical collisions on PyPI: `pynescript` is
> [elbakramer/pynescript](https://github.com/elbakramer/pynescript); plain
> `pyne`/`PyNE` is an unrelated 0.1.0 process-networking library. This project
> publishes as **`hoox-pyne`**:
> `pip install "hoox-pyne[lsp]"` → `import pynescript` + CLIs `pyne` / `pyne-lsp`.

### One-time PyPI setup (personal account)

Package ownership is the **personal** PyPI user
[`jango-blockchained`](https://pypi.org/user/jango-blockchained/) — not a PyPI
org (no org approval required). GitHub Actions still run on **`hoox-sh/pyne`**.

#### Recommended: API token

1. pypi.org as **`jango-blockchained`** → Account settings → **API tokens** →
   Add token (entire account for first upload; project-scoped after
   `hoox-pyne` exists).
2. Store on GitHub (never commit):

```bash
gh api -X PUT repos/hoox-sh/pyne/environments/pypi
gh secret set PYPI_API_TOKEN -R hoox-sh/pyne   # paste pypi-… token
gh secret set METADATA_KEY -R hoox-sh/pyne < scripts/build/.metadata.key
gh secret set CRYPTO_KEY   -R hoox-sh/pyne < scripts/build/.metadata.key
```

#### Optional: Trusted Publishing (OIDC)

If `PYPI_API_TOKEN` is **unset**, the workflow uses OIDC. On PyPI (logged in as
`jango-blockchained`) → **Publishing** → pending publisher:

| Field | Value |
| --- | --- |
| PyPI project name | `hoox-pyne` |
| Owner | **`hoox-sh`** (GitHub **repo** owner — not your PyPI username) |
| Repository | `pyne` |
| Workflow name | `publish.yml` |
| Environment name | `pypi` |

See `docs/pyne/devops/pypi-publish.mdx` for failure modes.

### Cut a release

1. Bump `__version__` in `src/pynescript/__about__.py` and update `CHANGELOG.md`.
2. Align `vscode-extension/package.json` version when shipping the VSIX together.
3. Ensure CI is green on `main`.
4. Tag and push: `git tag vX.Y.Z && git push origin vX.Y.Z`.
5. GitHub Actions on `v*` tags:
   - **Publish** (`publish.yml`) — sdist/wheel → PyPI (`hoox_pyne-*.whl` / `hoox_pyne-*.tar.gz`) via `PYPI_API_TOKEN` or Trusted Publishing OIDC (environment `pypi`).
   - **Build & Release** (`release.yml`) — Nuitka CLI/LSP binaries + VSIX on the GitHub Release.
   - **GHCR** (`ghcr.yml`) — `ghcr.io/hoox-sh/pyne/{cli,lsp,api}:X.Y.Z`.

Dry-run (build only, no upload): Actions → **Publish** → Run workflow → `dry_run=true`.

Local check (no upload):

```bash
pip install build twine
rm -rf dist/
python -m build
twine check dist/*
# Expected artifacts: hoox_pyne-*.whl  hoox_pyne-*.tar.gz
```

AXIS charting UI releases are handled in
[hoox-sh/axis](https://github.com/hoox-sh/axis), not here.
