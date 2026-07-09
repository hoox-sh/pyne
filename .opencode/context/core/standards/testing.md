# Testing Standards

## Running Tests

```bash
# All tests
make test
# or: python -m pytest tests/ -v --tb=short

# Single test file
python -m pytest tests/test_evaluator.py -v

# LSP tests only
make test-lsp
# or: python -m pytest tests/test_langserver.py tests/test_lsp_features.py -v

# Backend tests only
make test-backend
# or: python -m pytest tests/test_backend.py -v

# With coverage
python -m pytest -n auto -d --cov=src/pynescript --cov=tests --cov-report=term {args:tests}

# Via hatch
hatch run test:test
hatch run test:test-cov
```

## Test Dependencies

- LSP tests require: `pip install ".[dev-lsp]"` (installs `pygls`, `lsprotocol`, `pytest-lsp`)
- Backend tests require: `pip install flask flask-cors numpy matplotlib pytest`
- Parallel test runs: `pytest -n auto -d`

## Test Fixtures

- `tests/data/builtin_scripts/*.pine` — Real TradingView scripts used as parametrized test fixtures
- `conftest.py` auto-parametrizes any test with a `pinescript_filepath` fixture against all `.pine` files in that directory
- Use `--example-scripts-dir` flag to override the fixture directory

## Test File Conventions

- Test files: `tests/test_*.py`
- Tests can use `assert` statements (`S101` suppressed)
- Magic numbers allowed in tests (`PLR2004` suppressed)
- `print()` allowed in tests (`T201` suppressed)
- Relative imports within tests are allowed (`TID252` suppressed)

## Lint Before Commit

```bash
make lint    # ruff check src/ tests/ backend/
make fmt     # ruff format src/ tests/ backend/
```

## CI Pipeline

CI runs on push/PR to `main`:

1. **Lint**: `ruff check src/ tests/ --output-format=github`
2. **Type check**: `mypy src/ --ignore-missing-imports`
3. **Test**: Python 3.10, 3.11, 3.12, 3.13 matrix
4. **Backend test**: Separate job
5. **VS Code extension build**: `npm ci && npm run compile && npx vsce package`