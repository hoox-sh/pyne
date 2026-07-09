<!-- Context: project-intelligence/technical | Priority: critical | Version: 1.0 | Updated: 2026-06-03 -->

# Technical Domain

**Core concept**: Python library for parsing, inspecting, and regenerating TradingView Pine Script. CLI tools + LSP server + Flask API backend.

## Quick Reference
| Layer | Technology | Version | Rationale |
|-------|-----------|---------|-----------|
| Language | Python | >=3.10 | Type hints, pattern matching |
| Build | Hatchling | — | Modern PEP 517/518 build |
| CLI | Click | >=8.1 | Declarative commands |
| Parser | ANTLR4 | >=4.13 | Robust parsing, multi-target |
| Backend | Flask + gunicorn | >=3.0 | Lightweight REST API |
| LSP | pygls + lsprotocol | >=2.0 | Language Server Protocol |
| Linter | ruff + mypy | — | Fast, comprehensive checks |
| Compiler | Nuitka | >=2.0 | Standalone binary builds |
| Testing | pytest + coverage | — | Parametrized fixtures |
| Frontend | VS Code (TypeScript) | ^5.3 | Editor integration |

## Code Patterns

### Flask API Endpoint
```python
@app.route("/endpoint", methods=["POST"])
def endpoint():
    data = request.get_json() or {}
    if not data.get("field"):
        return jsonify(status="error", code="ERROR_CODE", message="..."), 400
    result = process(data)
    return jsonify(status="success", **result)
```

### Mixin Dispatch (Builtin Evaluators)
```python
class NumericBuiltinsMixin(BuiltinDispatchMixin):
    def _numeric_builtin_map(self) -> dict[str, BuiltinHandler]:
        return {
            "abs": self._builtin_abs,
            "math.max": self._builtin_math_max,
        }

class BuiltinEvaluator(AlertsMixin, NumericBuiltinsMixin, ...):
    def _build_builtin_map(self) -> dict[str, BuiltinHandler]:
        dispatch = super()._build_builtin_map()
        dispatch.update(self._numeric_builtin_map())
        return dispatch
```

### Click CLI Command
```python
@cli.command(short_help="Description.")
@click.argument("path", type=click.Path(exists=True))
@click.option("--flag", is_flag=True, help="Flag description")
def command(path, flag):
    from module import function
    result = function(path)
    click.echo(result)
```

## Naming Conventions

| Type | Convention | Example |
|------|-----------|---------|
| Python files | snake_case | `technical.py`, `base.py` |
| Classes | PascalCase | `BuiltinEvaluator`, `PinescriptLanguageServer` |
| Methods | snake_case | `_build_builtin_map()`, `validate_series()` |
| Private | _leading underscore | `_error()`, `_numeric_builtin_map()` |
| Builtin modules | Pine Script namespaces | `technical.py`, `strategy.py` |
| Constants | UPPER_CASE | `_MATH_CONSTANTS` |

## Code Standards
- `from __future__ import annotations` mandatory first line of every Python file
- Ruff: line-length 120, target Python 3.10, force-single-line imports
- Type hints throughout (mypy strict-ish with per-module overrides)
- Generated code (ANTLR/ASDL) never edited — regenerate from `.g4`/`.asdl`
- LGPL-3.0 license header on all source files
- Tests: `assert` allowed, magic numbers allowed, `print()` allowed

## Security Requirements
- Validate all API input with explicit field checks before processing
- Fernet-encrypt `builtin_metadata.json` during build (key gitignored)
- API key authentication via `@require_api_key` middleware
- Rate limiting per API tier (free/hobby/pro/team/enterprise)
- CORS enabled on Flask backend, HTTPS-only in production
- Docker health checks for production services

## 📂 Codebase References
- CLI: `src/pynescript/__main__.py` — Click command definitions
- Evaluator: `src/pynescript/ast/evaluator/builtins/__init__.py` — Mixin composition
- API: `backend/app.py` — Flask routes and error handling
- LSP: `src/pynescript/langserver/server.py` — pygls implementation
- Config: `pyproject.toml` — ruff, mypy, hatch settings
- Build: `scripts/build/compile.py` — Nuitka compilation

## Related Files
- `standards/code-quality.md` — Ruff, mypy, import style details
- `standards/testing.md` — Test commands, fixtures, CI pipeline
