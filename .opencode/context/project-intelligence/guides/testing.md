<!-- Context: project-intelligence/guides/testing | Priority: high | Version: 1.0 | Updated: 2026-07-05 -->

# Testing

`tests/` is pytest-based with a heavy parametrize over real `.pine` corpus files.
Run subsets via the Makefile or pytest directly.

## Layout

```
tests/
├── conftest.py                    # pinescript_filepath fixture
├── data/
│   ├── builtin_scripts/*.pine     # ~500+ official pine scripts (parametrized)
│   └── library/                   # community-pulled library scripts
├── test_alerts.py
├── test_backend.py                # requires flask, flask-cors, numpy, matplotlib
├── test_collections_phase4.py
├── test_evaluator.py
├── test_langserver.py             # e2e pygls tests (async)
├── test_linter.py
├── test_lsp_features.py           # direct handler tests (unit)
├── test_map_collections.py
├── test_matrix_collections.py
├── test_parse_and_unparse.py
├── test_phase*.py                 # phase rollout snapshots
├── test_real_world_compatibility.py
├── test_udt_*.py                  # user-defined-type tests
```

## Commands

```bash
make test              # all tests
make test-lsp          # test_langserver.py + test_lsp_features.py
make test-backend      # test_backend.py
pytest tests/test_evaluator.py -v
pytest tests/test_lsp_features.py::TestBuiltinMetadata -v
```

The CI matrix runs all tests on Python 3.10, 3.11, 3.12, 3.13
(`.github/workflows/ci.yml`).

## The `pinescript_filepath` Fixture

`tests/conftest.py` parametrizes any test taking `pinescript_filepath` over
**every** `*.pine` file in `tests/data/builtin_scripts/`:

```python
def test_runs(pinescript_filepath):
    src = pinescript_filepath.read_text()
    tree = parse(src, str(pinescript_filepath))
    assert tree is not None
```

Override the source dir with `--example-scripts-dir=...`:
```bash
pytest --example-scripts-dir=./my_dir tests/
```

## Backend Tests

Need extra deps: `pip install flask flask-cors numpy matplotlib`. They hit the
Flask app's endpoints via `app.test_client()` — no live network.

## LSP Tests

Need `pip install -e ".[dev-lsp]"` for `pytest-lsp`. CI installs
`pytest-asyncio` separately for the e2e suite.

## Coverage

```bash
hatch run test:cov     # pytest -n auto -d --cov=src/pynescript --cov=tests --cov-report=lcov
# or:
coverage run -m pytest tests && coverage combine && coverage lcov && coverage report
```

Coverage is configured for parallel mode (`parallel = true`) and omits
`src/pynescript/__about__.py`. CI uploads via codecov on Python 3.13.

## 📂 Codebase References

- **Implementation**: `tests/conftest.py` — `pinescript_filepath` fixture.
- **Reference**: `Makefile` — `test`, `test-lsp`, `test-backend` targets.
- **Reference**: `.github/workflows/ci.yml` — matrix and commands.
- **Reference**: `pyproject.toml` — `[tool.coverage.*]`, `[tool.hatch.envs.test]`.
