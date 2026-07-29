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

Package name on PyPI: **`pynescript`** (repo product name: **pyne**).

1. Bump `__version__` in `src/pynescript/__about__.py` and update `CHANGELOG.md`.
2. Ensure CI is green on `main`.
3. Tag and push: `git tag vX.Y.Z && git push origin vX.Y.Z`.
4. GitHub Actions **Publish** builds sdist/wheel and uploads to PyPI via
   [Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
   (environment `pypi`, workflow `publish.yml`).

Dry-run (build only, no upload): Actions → Publish → Run workflow → `dry_run=true`.

Local check:

```bash
python -m build && twine check dist/*
```

AXIS charting UI releases are handled in
[jango-blockchained/axis](https://github.com/jango-blockchained/axis), not here.
