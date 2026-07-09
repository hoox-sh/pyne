<!-- Context: project-intelligence/errors/test-gotchas | Priority: medium | Version: 1.0 | Updated: 2026-07-05 -->

# Test Gotchas

What trips people up when running or writing tests.

## `pinescript_filepath` fixture is slow

`tests/conftest.py` parametrizes any test using `pinescript_filepath` over
**every** `*.pine` in `tests/data/builtin_scripts/`. That's 500+ files. If you
add a new test using this fixture, expect several minutes of runtime.

Override for a focused run:
```bash
pytest --example-scripts-dir=./one_script_dir tests/test_evaluator.py
```

## LSP tests need extras

Direct-handler tests in `tests/test_lsp_features.py` need `.[lsp]` only.
E2E tests in `tests/test_langserver.py` need:
```bash
pip install -e ".[dev-lsp]"   # adds pytest-lsp
pip install pytest-asyncio     # CI installs this explicitly
```

Without `pytest-asyncio`, the e2e async tests will be skipped or error with
"async def functions not natively supported".

## Backend tests need extra deps

`tests/test_backend.py` imports `flask`, `flask_cors`, and uses numpy/matplotlib
internally. CI installs them; locally you need:
```bash
pip install -r backend/requirements.txt
```

## Coverage parallel mode

`[tool.coverage.run]` has `parallel = true`. Running `coverage run` directly
emits `.coverage.<host>.<pid>` files; you need `coverage combine` to merge:
```bash
hatch run test:cov     # does run + combine + lcov + report
```

CI uploads via codecov only on Python 3.13 (see `.github/workflows/ci.yml`).

## Flaky Parametrize from New Files

If you drop a `.pine` file into `tests/data/builtin_scripts/`, every test using
`pinescript_filepath` gets a new case. A failing test will look like
`test_runs[<your_new_file>.pine]`. Move it elsewhere or pass
`--example-scripts-dir` to exclude.

## Module-level Test Files

Many `tests/test_phase*.py` are snapshot-style rollout tests. They run
many literal_eval / parse / unparse cases. Don't add new top-level modules —
extend the existing phase file matching the feature tier (1-8).

## Builder Mismatch

If you edit `src/pynescript/ast/builder.py` and tests fail with missing
`visit_*` methods, regenerate the ANTLR parser first (see
`guides/grammar-changes.md`) — the visitor base class may have new methods.

## `builder.py.bak` Confusion

There is a stale `src/pynescript/ast/builder.py.bak` file. It is **not** used.
Do not edit it; do not delete it without explicit user approval (it may be a
rollback target).

## 📂 Codebase References

- **Implementation**: `tests/conftest.py` — `pytest_generate_tests` hook.
- **Implementation**: `tests/test_lsp_features.py` — handler tests.
- **Implementation**: `tests/test_langserver.py` — e2e tests.
- **Reference**: `pyproject.toml` — `[tool.coverage.*]`, optional deps.
