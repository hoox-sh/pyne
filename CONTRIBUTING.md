# Contributing to pyne

> Part of **[HOOX](https://hoox.sh)**: [pyne](https://hoox.sh/pyne) · [axis](https://hoox.sh/axis) · [hoox](https://hoox.sh)  
> Charting UI contributions go to **[axis](https://github.com/jango-blockchained/axis)**.

Thank you for your interest in contributing to pyne!

## Getting Started

Please refer to the documentation in the `docs/` directory for detailed instructions on setting up your development environment and understanding the project structure.

- [Developer Guide](docs/index.md)
- [Project Structure](docs/reference.md)

## Development Workflow

1.  **Fork the repository** and create your branch from `main`.
2.  **Install dependencies** using `hatch`.
3.  **Run tests** to ensure everything is working: `hatch run test:test`.
4.  **Make your changes**.
5.  **Run linting and formatting**: `hatch run lint:style` and `hatch run lint:typing`.
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
| **Console scripts** | `pynescript`, `pynescript-lsp` |
| **Product / repo** | **pyne** · [jango-blockchained/pyne](https://github.com/jango-blockchained/pyne) |

> The historical name `pynescript` on PyPI belongs to
> [elbakramer/pynescript](https://github.com/elbakramer/pynescript). This project
> publishes as **`hoox-pyne`** so installs do not collide:
> `pip install "hoox-pyne[lsp]"` → `import pynescript`.

### One-time PyPI setup (Trusted Publishing)

1. Create a PyPI account (or org) and enable 2FA.
2. On PyPI → **Publishing** → **Add a new pending publisher**:
   - **PyPI project name:** `hoox-pyne`
   - **Owner:** `jango-blockchained`
   - **Repository:** `pyne`
   - **Workflow name:** `publish.yml`
   - **Environment name:** `pypi`
3. GitHub → repo **Settings → Environments → `pypi`** (create if missing).
   Optional: required reviewers for production uploads.
4. First successful tag publish creates the project and attaches the publisher.

### Cut a release

1. Bump `__version__` in `src/pynescript/__about__.py` and update `CHANGELOG.md`.
2. Align `vscode-extension/package.json` version when shipping the VSIX together.
3. Ensure CI is green on `main`.
4. Tag and push: `git tag vX.Y.Z && git push origin vX.Y.Z`.
5. GitHub Actions **Publish** builds sdist/wheel and uploads via
   [Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
   (environment `pypi`, workflow `publish.yml`).

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
[jango-blockchained/axis](https://github.com/jango-blockchained/axis), not here.
