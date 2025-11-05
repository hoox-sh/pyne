# Documentation Development

This directory contains the PyneScript documentation built with Sphinx.

## Building Documentation Locally

### Prerequisites

Install the documentation dependencies:

```bash
pip install hatch
```

### Build the Docs

```bash
hatch run docs:build
```

The generated HTML documentation will be in `docs/_build/`.

### View the Docs

Open `docs/_build/index.html` in your browser, or use a local web server:

```bash
python -m http.server -d docs/_build 8000
```

Then visit http://localhost:8000

### Auto-rebuild During Development

For live reloading during documentation development:

```bash
hatch run sphinx-autobuild docs docs/_build --open-browser
```

## Documentation Structure

- `index.md` - Main landing page
- `usage.md` - Installation and quickstart guide
- `features.md` - Complete feature list and examples
- `api.md` - API overview organized by functionality
- `reference.md` - Complete API reference (auto-generated)
- `pinescript_implementation_status.md` - Feature coverage status
- `license.md` - License information
- `conf.py` - Sphinx configuration
- `apidoc/` - Auto-generated API documentation

## Auto-generated Documentation

The documentation automatically includes:

- All public APIs via `sphinx.ext.autodoc`
- All modules via `sphinx-apidoc`
- CLI documentation via `sphinx-click`
- Type hints via `sphinx.ext.napoleon`

Documentation is regenerated on every build to ensure 100% coverage.

## GitHub Pages Deployment

Documentation is automatically deployed to GitHub Pages when changes are pushed to the main branch. The workflow is defined in `.github/workflows/docs.yml`.

### Workflow Triggers

- Push to `main` or `master` branch with changes to:
  - `src/**`
  - `docs/**`
  - `.github/workflows/docs.yml`
  - `pyproject.toml`
- Manual trigger via workflow_dispatch

### GitHub Pages Configuration

To enable GitHub Pages deployment:

1. Go to repository Settings > Pages
2. Under "Source", select "GitHub Actions"
3. The workflow will automatically deploy on the next push

## Documentation Coverage

The documentation aims for 100% coverage of all project features:

- ✅ Core parsing and unparsing API
- ✅ AST manipulation and transformation
- ✅ Expression evaluation
- ✅ 149+ built-in functions
- ✅ Extensions (Pygments, Nautilus Trader)
- ✅ Command-line interface
- ✅ All public modules and classes
- ✅ Usage examples and code samples

## Contributing to Documentation

When adding new features:

1. Add docstrings to all public functions and classes
2. Include usage examples in docstrings
3. Add type hints for all parameters and returns
4. Update `features.md` if adding major functionality
5. Test the documentation build locally

## Style Guide

- Use Google-style docstrings (compatible with Napoleon)
- Include examples in docstrings when helpful
- Use Markdown for narrative documentation
- Use MyST syntax for advanced Markdown features
- Keep code examples simple and runnable
