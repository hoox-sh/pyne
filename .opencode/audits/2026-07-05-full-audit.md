# pynescript — Full Audit Report

**Date:** 2026-07-05
**Scope:** Code quality, security, dependencies, architecture
**Codebase:** `pynescript` v0.2.0 (Python toolchain for TradingView Pine Script)
**Auditor:** automated static review (ruff, mypy, manual inspection)
**Files covered:** `src/`, `backend/`, `vscode-extension/`, `scripts/`, root configs
**Files NOT covered:** `scripts/build/*` (Nuitka pipeline), `examples/`, `docs/`, `frontend/`, `clients/*`, `vscode-extension/node_modules/`, deep LSP test review

**Headline numbers:**
- ~25.2k LOC source (`src/` + `backend/` + `scripts/`, excluding generated)
- ~12.3k LOC tests across 27 test files
- **1 critical**, **6 high**, **9 medium**, **8 low** findings + 14 process/minor items
- 464 ruff issues (10 auto-fixable)
- 9 mypy errors (all missing-type-stub for optional deps; no logic bugs)

---

## 1. Architecture Audit

### Module structure (the good)

The codebase follows a clean, intentional structure matching the AGENTS.md entry-point table:

```
src/pynescript/
├── __main__.py                 # Click CLI (pynescript)
├── __init__.py                 # public re-exports
├── ast/                        # parser, AST, evaluator, linter
│   ├── helper.py               # parse() / unparse() / dump() — public API
│   ├── grammar/                # ANTLR4 .g4 + ASDL generators
│   └── evaluator/builtins/     # ta.*, math.*, request.*, etc.
├── langserver/                 # pygls server (pynescript-lsp)
│   ├── server.py               # @self.feature handlers
│   ├── features/               # one file per LSP method
│   ├── providers/              # metadata_decrypt.py (Fernet), builtin_metadata.json
│   └── workspace.py            # in-memory doc store
├── ext/                        # optional: jupyter, pygments, nautilus_trader
└── util/                       # data.py (data providers)

backend/
├── app.py                      # Flask app (pynescript Pro API)
├── runtime.py                  # Pine Script execution wrapper
├── middleware/auth.py          # API key + rate limit
├── services/                   # backtest, chart_renderer
└── api/                        # preview, backtest blueprints
```

**What works well:**
- Console scripts properly separated: `pynescript` (Click) vs `pynescript-lsp` (pygls).
- ANTLR4/ASDL grammar live in `resource/`; generated files gitignored-adjacent.
- LSP server uses idiomatic pygls `@self.feature()` decorators.
- Backend `Runtime` is separate from in-process `BuiltinEvaluator` — different execution contexts.
- Per-file-ignores in `pyproject.toml` acknowledge test-style exemptions (PLR2004 magic numbers etc.).

### Architecture findings

| # | Severity | Finding | Location |
|---|----------|---------|----------|
| **A1** | **High** | **Dead method due to MRO shadowing** — `_builtin_ta_intelligent_strategy_synthesizer` is defined in **both** `technical_submodules/advanced.py:1589` and `technical_submodules/synthesizer.py:18`. `AdvancedIndicators` is listed before `SynthesizerIndicators` in the `TechnicalAnalysisMixin` MRO (`technical.py:23-36`), so the `synthesizer.py` version is **never called**. The entire 188-line `synthesizer.py` (containing a single function) is effectively dead code. Confirmed via `inspect.getmro()`. | `src/pynescript/ast/evaluator/builtins/technical_submodules/synthesizer.py`, `advanced.py:1589-1685`, `technical.py:23-36` |
| A2 | Medium | **Unused parse in backtest** — `run_backtest` does `tree = parse(script); _ = tree` then discards the AST (`backtest.py:115-119`). The "MVP" comment says the full evaluator is future work, but the dead call + swallowed `except` makes the file look like it does something it doesn't. | `backend/services/backtest.py:115-119` |
| A3 | Medium | **`from .module import *` in `ast/__init__.py`** — broad star imports masked by `noqa: F403` (`ast/__init__.py:25-30`). Relied on by `from pynescript.ast import FunctionDef, Assign, ...` in LSP code. Intentional, but means new symbols silently leak into the public API. Worth a deliberate re-export list. | `src/pynescript/ast/__init__.py:25-30` |
| A4 | Low | **`_collect_workspace_symbols` is a private helper inside `setup_method_handlers`** — `server.py:280-341` is a 60-line helper doing a hand-rolled AST walk inside a method that's already 103 statements (high complexity). Only place `FunctionDef`/`TypeDef`/`Assign` are inspected from LSP. Should move to `features/symbols.py` for symmetry. | `src/pynescript/langserver/server.py:52, 280-341` |
| A5 | Low | **`_collect_workspace_symbols` does AST traversal with `hasattr(child_node, "_fields")` checks** — `server.py:331-338` is fragile; ASDL-generated nodes do have `_fields` but the recursion logic is ad-hoc. The codebase has a `pynescript.ast.visitor` and `pynescript.ast.transformer` that could be reused. | `src/pynescript/langserver/server.py:280-341` |
| A6 | Low | **LSP parses/lints on every keystroke** — `Workspace._parse_and_lint` called in `put_document` and `update_document` (`workspace.py:73, 97`) with no debouncing or incremental linting. Fine for small files; O(file size) per keystroke for large `.pine` strategies. | `src/pynescript/langserver/workspace.py:100-114` |

---

## 2. Code Quality Audit

### Tooling baseline

| Tool | Result | Comment |
|------|--------|---------|
| `ruff check src/ tests/ backend/` | **464 errors** (10 auto-fixable) | See breakdown below |
| `mypy src/pynescript` | **9 errors** | All missing-type-stub for optional deps; no logic bugs |
| `ruff format --check` | not run in audit | run `make fmt` to verify |
| `pytest` | not run in audit | run `make test` to verify |

### Ruff findings by rule (top 10)

```
280  PLR2004  magic-value-comparison       (mostly tests per-file-ignored)
 49  N802    invalid-function-name         (snake_case violations)
 24  PLC0415 import-outside-top-level      (intentional in some, but flagged)
 21  F841    unused-variable
 12  ARG001  unused-function-argument
  8  RUF059  unused-unpacked-variable
  7  PLW0603 global-statement
  6  C901    complex-structure             (5 real offenders, see below)
  6  I001    unsorted-imports              (auto-fixable)
  6  FBT001/2/3  boolean-positional-arg   (matplotlib calls, harmless)
```

**Real complexity hotspots (`C901`):**
- `_builtin_ta_intelligent_strategy_synthesizer` in `technical_submodules/advanced.py:1589` — **cyclomatic 28, 97 statements, 37 branches** (PLR0912 + PLR0915 also fire).
- `_builtin_ta_intelligent_strategy_synthesizer` in `technical_submodules/synthesizer.py:18` — **cyclomatic 36, 108 statements, 39 branches**. **Plus this is the dead code from A1.**
- `setup_method_handlers` in `langserver/server.py:52` — **cyclomatic 31, 103 statements**. Should be split per-feature.
- `visit_TypeDef` in `ast/evaluator/statements.py:104` — cyclomatic 13, borderline.
- `_collect_workspace_symbols` in `langserver/server.py:280` — cyclomatic 12.

### Code-quality findings

| # | Severity | Finding | Location |
|---|----------|---------|----------|
| Q1 | **High** | **Duplicate method (same as A1)** — `SynthesizerIndicators` class is dead because MRO always resolves to `AdvancedIndicators` first. Either delete `synthesizer.py` or swap MRO order. | `synthesizer.py` (whole file) |
| Q2 | Medium | **Duplicate import** — `data.py:28` and `data.py:30` both `from datetime import timedelta` (F811). | `src/pynescript/util/data.py:28-30` |
| Q3 | Medium | **Mid-file import** — `config.py:65` does `from typing import Any` after a function definition (E402). The function doesn't use `Any` in its body. Move to top. | `src/pynescript/langserver/config.py:65` |
| Q4 | Medium | **Unused imports** — `evaluator/builtins/__init__.py:32, 48, 49` imports `typing.Any`, `VolumeRow`, `Footprint` but doesn't use them (F401). | `src/pynescript/ast/evaluator/builtins/__init__.py:32, 48, 49` |
| Q5 | Medium | **Global state in middleware** — `_key_store: APIKeyStore | None` is module-level mutable state (`auth.py:130-137`) with a `get_key_store()` lazy init. Fine for a single-process dev server, but combined with gunicorn `--workers 2 --threads 4` (`Dockerfile.api`) **each worker has its own key store** — a key created in worker A is invisible in worker B. This is a correctness bug, not just style. | `backend/middleware/auth.py:130-137`; `Dockerfile.api` CMD |
| Q6 | Low | **`try: ... except: pass`** (S110) — all in `backend/services/backtest.py:118, 262` and various evaluator mock sites. Silent failures hide bugs. Add `logger.debug` or `# noqa: S110` with comment. | `backend/services/backtest.py:118, 262` |
| Q7 | Low | **`cast(Any, ...)` on `ndarray` masks types** — `chart_renderer.py:127-128` uses `cast(Any, positive)` to silence mypy on matplotlib patterns. Could use `numpy.typing.NDArray[np.bool_]` annotations. | `backend/services/chart_renderer.py:127, 128` |
| Q8 | Low | **`E501 line-too-long`** at 2 sites — minor. | — |
| Q9 | Low | **Magic numbers everywhere** (`PLR2004`) — 280 hits, mostly in tests (already per-file-ignored) but the remaining ~50 in `src/pynescript/ast/evaluator/builtins/{alerts,arrays,drawing}.py` should be named constants for maintainability. | various |

### Mypy analysis

Mypy is configured **strict-ish** (per `pyproject.toml`) with exemptions for generated grammar modules, `evaluator.builtins.*`, and `tests.*`. The 9 errors are all **legitimate missing-stub issues for optional dependencies**, not bugs:

```
src/pynescript/util/data.py:202: import-not-found yfinance
src/pynescript/util/data.py:291-292: import-not-found alpha_vantage
src/pynescript/util/data.py:399: import-not-found ccxt
src/pynescript/ext/jupyter.py:36: import-not-found IPython.core.magic
src/pynescript/ext/jupyter.py:177: import-untyped pandas
src/pynescript/ext/pygments/lexers.py:12-13: import-untyped pygments
src/pynescript/langserver/features/inlay_hints.py:199: no-any-return
```

The `inlay_hints.py:199` is the only real `Any`-leak in the LSP layer — worth fixing.

---

## 3. Security Audit

The most findings-heavy area. The backend is small (~600 LOC) and works for a dev server, but it has several issues that need to be addressed before any production exposure.

### 3.1 Critical

| # | Issue | Detail | Recommendation |
|---|-------|--------|----------------|
| **S1** | **No `MAX_CONTENT_LENGTH` on Flask** | `app.py:28` creates the Flask app without `app.config["MAX_CONTENT_LENGTH"]`. An attacker can POST multi-GB JSON to `/run` or `/preview/chart` and exhaust memory before gunicorn's `--timeout 60` kills the worker. | Add `app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024` (5MB) to `app.py:28`. |

### 3.2 High

| # | Issue | Detail | Recommendation |
|---|-------|--------|----------------|
| **S2** | **API key accepted as URL query parameter** | `auth.py:152` falls back to `request.args.get("api_key", "")` if no `Authorization` header is present. This puts the secret in nginx/gunicorn access logs, browser history, and `Referer` headers. | Remove the query-param fallback; only accept `Authorization: Bearer …` and `Authorization: ApiKey …`. |
| **S3** | **`/auth/create_key` is unauthenticated** | `app.py:99-126` lets **anyone** mint a Pro-tier API key with no auth. The docstring says "In production, this requires admin auth" but no such check exists. Combined with S5 below, the public Cloud Run deployment can be used to flood the tier system. | Gate with an `X-Admin-Token` env-var check, or disable the endpoint in prod. |
| **S4** | **Cloud Run deploys with `--allow-unauthenticated`** | `cloudbuild.yaml:55` makes the API public. The same image also has S1, S2, S3 active. | Add `--no-allow-unauthenticated` and put the API behind IAP / an internal LB, or at minimum require `Authorization: Bearer …` on every route. |
| **S5** | **In-memory API key store per gunicorn worker** | (See Q5.) `gunicorn --workers 2 --threads 4` in `Dockerfile.api` means up to 8 isolated key stores. A user creating a key hits one worker; their next request may hit another and get 401. The store is also lost on every restart. | Replace with a shared store (Redis, SQLite, Postgres) before any production use. TODO comment is already at `auth.py:77`. |
| **S6** | **Truncated SHA-256 integrity check (64 bits)** | `metadata_decrypt.py:75` does `hashlib.sha256(plaintext).hexdigest()[:16]` — that's 64 bits, half the security of even MD5's collision space. An attacker who can flip 16 bytes in `builtin_metadata.json.enc` has a 1-in-2⁶⁴ chance of a forgery. | Use the full 64 hex chars. Or better, switch from `Fernet.decrypt(plaintext)` + manual SHA to `Fernet` only (Fernet already includes an HMAC). The current scheme is double-hashing for no benefit. |

### 3.3 Medium

| # | Issue | Detail | Location |
|---|-------|--------|----------|
| S7 | **`CORS(app)` with default `*` origin** | `app.py:29` enables CORS for all origins. Mostly OK with cookie-less Bearer tokens, but a misconfigured client could leak keys to attacker-controlled origins. | `CORS(app, origins=["https://pynescript.ai"])` etc. |
| S8 | **CORS allows `methods=["*"], allow_headers=["*"]`** | `flask-cors` defaults are wide-open. | Restrict to `["GET", "POST"]` and explicit headers. |
| S9 | **No schema validation on `request.get_json()`** | All 6 endpoints do `data = request.get_json() or {}` then access keys directly. A missing key returns `None` and downstream code may crash or use defaults silently. | Use `pydantic` or `marshmallow`; reject unexpected fields. |
| S10 | **No sandboxing of Pine Script execution** | `runtime.py:195` does `evaluator.visit(tree)` on user-supplied AST. The evaluator is custom, not `eval()`, but a bug in any builtin (e.g. `request.security`) could read arbitrary files or make network calls. No resource cap, no timeout, no seccomp. | Add per-request timeouts (`signal.alarm` or worker pool), limit memory via `resource.setrlimit`. Document threat model. |
| S11 | **`S104: app.run(host="0.0.0.0", ...)` in `__main__` guard** | `app.py:207` is OK in dev (gunicorn in prod), but scanners will flag it. | `os.environ.get("HOST", "127.0.0.1")`. |
| S12 | **No bound on `request.args` / `request.headers` size** | Flask's default `MAX_CONTENT_LENGTH` is `None`. Combined with S1, a request with 10MB of query string + headers can be parsed fully before any handler runs. | Set the global `MAX_CONTENT_LENGTH` and rely on reverse proxy for header caps. |
| S13 | **`auth.py:55-60` `_get_reset_time` math is magic** | `time.mktime(time.struct_time((now // (32 * 86400) + 1, …)))` constructs a `struct_time` from scratch. Correct-ish for monthly reset semantics but obscure. | Use `datetime.replace(day=1) + relativedelta(months=1)` or add comment. |
| S14 | **`app.py:184-203` 404/500 error handlers leak `request.path`** | 404 echoes user-supplied path back in JSON message. Not real XSS in JSON API, but a small info-leak. | `message: "Endpoint not found"`. |

### 3.4 Low

| # | Issue | Location |
|---|-------|----------|
| S15 | **LSP server processes any untrusted source** | Acceptable: LSP runs as child of editor. The `pynescript.lsp.command` setting in `vscode-extension/src/extension.ts:16-19` lets user point at any binary, but that's their own editor. |
| S16 | **`matplotlib` imported at module top in `chart_renderer.py`** | Heavy import per Flask worker; per-chart CPU/IO cost. OK for low-traffic dev. |
| S17 | **8 `S311 random` usages** | All in mock-data paths (`request.py:490-493`, `jupyter.py:106-109`, `backtest.py:313-315`, `data.py:89`). Not security-sensitive (no tokens, no IDs). Add `# noqa: S311` with comment, or switch to `numpy.random.default_rng`. |
| S18 | **VS Code extension trusts `pynescript.lsp.command` user setting** | See S15. |
| S19 | **`backend/api/preview.py:194-207` `_compute_indicator` parses a string with `str.split` on commas** | Not user-reachable (called only with `expression` from JSON), but fragile. Real parser would be safer. |
| S20 | **`charts_renderer.py:1-18` imports `matplotlib` but doesn't lock backend in `pyproject.toml`** | OK because `matplotlib.use("Agg")` set explicitly. |
| S21 | **No `.env.example`, no `python-dotenv` in deps** | Standard for Flask apps. No accidental env loading. |
| S22 | **No `SECURITY.md`, no responsible disclosure process** | AGENTS.md is the closest thing. |

### 3.5 What's good (for completeness)

- **No `eval`/`exec` of user input** in production paths. `literal_eval` is the AST-safe version. Helper for `literal_eval` is a custom Pine AST evaluator, not Python's `eval`.
- **No `verify=False` on any HTTP call** (no SSL bypasses).
- **No `pickle` / `marshal` / `yaml.load`** in app code.
- **`subprocess` only in dev tools** (`scripts/build/*`, `asdl/tool/generate.py`, `antlr4/tool/generate.py`), all `noqa: S603` with reason.
- **Fernet used correctly** for `builtin_metadata.json.enc` (key bytes from file or env, both excluded by `.gitignore`).
- **API key generation uses `secrets.token_urlsafe(32)`** (`auth.py:86`) — correct.
- **No hardcoded secrets in source** (only SHA-256 hash of key for storage, not the key itself).
- **`.gitignore` correctly excludes `scripts/build/.metadata.key`** and `*.key` patterns.
- **Dockerfile.api runs as non-root** `appuser`.
- **gunicorn has `--timeout 60`** which mitigates some DoS.
- **CSP / X-Frame-Options** aren't set, but this is a JSON API not a browser app, so they're not needed.

---

## 4. Dependency Audit

### 4.1 Direct dependencies (pyproject.toml)

```toml
dependencies = [
  "antlr4-python3-runtime>=4.13.1",   # current latest 4.13.2 (OK)
  "click>=8.1.7",                      # OK
  "requests",                          # NO upper bound — OK for app, but any major bump is silent
  "tqdm",                              # NO version pin
]
```

### 4.2 Optional / extras

```toml
[project.optional-dependencies]
lsp = ["pygls>=2.0.0", "lsprotocol>=2024.0.0"]
dev-lsp = ["pygls>=2.0.0", "lsprotocol>=2024.0.0", "pytest-lsp>=0.1.0"]
```

### 4.3 Dependency findings

| # | Severity | Finding |
|---|----------|---------|
| D1 | Medium | **`requests` and `tqdm` have no minimum version constraint.** A future 5.0 release of `requests` or 99.0 of `tqdm` would break users silently. Pin at least to `>=2.31` and `>=4.66` to match what's in CI. |
| D2 | Medium | **All four deps are open-ended `>=`**. A full audit would run `pip-audit` or `safety check` against them (not run in this offline audit — see Limitations). |
| D3 | Medium | **Backend deps (Flask, flask-cors, gunicorn, numpy, matplotlib) are NOT in `pyproject.toml` at all** — they live only in `backend/requirements.txt`. `pip install pynescript` won't give a user a working backend. Either move them to an `[pro]` extra or document this clearly. |
| D4 | Medium | **`pygments` is used by shipped code but missing from runtime deps**. The Pygments entry-point in `pyproject.toml:49-50` will register a broken lexer on import. |
| D5 | Low | `antlr4-python3-runtime>=4.13.1` is recent; OK. |
| D6 | Low | `dev-lsp` duplicates `lsp`'s pygls/lsprotocol. Normal pattern, but consider `dev-lsp = [..., "lsp"]` to DRY. |
| D7 | Low | `pytest-asyncio` is in the install step of `.github/workflows/ci.yml` but **not in any pyproject extras**. CI works because the test env is built ad-hoc, but `pip install -e ".[dev-lsp]"` won't include it for local dev. |
| D8 | Low | `hatch envs.lint` requires `antlr4-cli` (Java tool) and `pyasdl>=0.3.1` — fine for contributors, but a fresh user running `hatch run lint:gen-parser` will need Java installed with no warning. |
| D9 | Low | `Dockerfile.api` does `pip install --no-cache-dir -r backend/requirements.txt` then `pip install --no-cache-dir .` — if `pyproject.toml` and `backend/requirements.txt` disagree about a transitive dep, gunicorn wins. |

### 4.4 Phantom dependencies (imported but undeclared)

The biggest hidden risk. Both ruff and mypy surface these:

| # | Imported in | Package | Effect on user |
|---|-------------|---------|---------------|
| D10 | `src/pynescript/util/data.py:202` | `yfinance` | `YahooFinanceProvider()` raises `DataProviderError` with friendly msg, but it's a runtime surprise. |
| D11 | `src/pynescript/util/data.py:291, 292` | `alpha-vantage` | Same pattern. |
| D12 | `src/pynescript/util/data.py:399` | `ccxt` | Same pattern. |
| D13 | `src/pynescript/ext/jupyter.py:36` | `IPython` | Jupyter extension raises on import. |
| D14 | `src/pynescript/ext/jupyter.py:177` | `pandas` | Same. |
| D15 | `src/pynescript/ext/pygments/lexers.py:12, 13` | `pygments` | Lexer import fails (see D4). |

**Recommendation:** add a `[data]` extra: `data = ["yfinance", "alpha-vantage", "ccxt"]` and a `[jupyter]` extra. Update docstrings to reference these.

### 4.5 VS Code extension deps (separate Node project)

```json
"dependencies": { "vscode-languageclient": "^9.0.1" }
"devDependencies": { "@types/node": "^20.10.0", "@types/vscode": "^1.85.0",
                     "@vscode/test-electron": "^2.3.0", "typescript": "^5.3.0" }
```

| # | Finding |
|---|---------|
| D16 | All ^ ranges — OK for a separate project, but `engines.node` is missing (only `engines.vscode` is set to `^1.85.0`). |
| D17 | No `npm ci` lockfile in `vscode-extension/` (only `package-lock.json` listed by ls but not committed in diff context). Confirm `vscode-extension/package-lock.json` is committed and not gitignored. |

### 4.6 CVE lookups

**Not performed in this audit** — no `pip-audit`, `safety`, or `osv.dev` access was available. Recommend running:

```bash
pip install pip-audit
pip-audit -r pyproject.toml
pip-audit -r backend/requirements.txt
cd vscode-extension && npm audit --production
```

as a follow-up.

---

## 5. Cross-cutting & process findings

| # | Severity | Finding |
|---|----------|---------|
| P1 | Medium | **No CI step for `backend/`** — `.github/workflows/ci.yml` runs `ruff check src/ tests/ --output-format=github`, but `make lint` includes `backend/`. Backend code is currently **not lint-checked in CI**. |
| P2 | Medium | **No mypy on `backend/`** — mypy only runs over `src/`, but `backend/` has type annotations and would benefit from the same strictness. |
| P3 | Low | **The 12 test files named `test_phase{5-8}_tier{1-8}*`** suggest an old "tier"-based development process. These are still in `tests/` and presumably still in pytest's default discovery. Combined with the ~500-file corpus parametrize in `conftest.py`, a full test run is slow. Consider tagging `@pytest.mark.slow` or moving to `tests/legacy/`. |
| P4 | Low | **`src/pynescript/ast/evaluator/builtins/technical_submodules/REFACTORING_GUIDE.md` and `REFACTORING_PROGRESS.md` and `COMPLETION_SUMMARY.md`** — development-process notes that were checked in. They document the refactoring that led to A1. Either move to `docs/internal/` or `.opencode/`, or link from a single ADR. |
| P5 | Low | **No `CHANGELOG.md` updates for 2026-07-05 edits** even though files in `src/pynescript/ast/evaluator/builtins/` were last touched then. The CHANGELOG only has 4 entries. |
| P6 | Low | **`.ruff_cache` and `.mypy_cache` exist on disk** — normal, they're in `.gitignore`. |
| P7 | Low | **`scripts/build/ci_build.py` and `scripts/build/compile.py`** are referenced in AGENTS.md and Dockerfile but were not audited in depth (build pipeline out of scope; AGENTS.md's "Build / Release Quirks" covers the Fernet key). |

---

## 6. Priority Matrix

| # | Severity | Area | One-line |
|---|----------|------|----------|
| **S1** | **CRITICAL** | Security | Set `MAX_CONTENT_LENGTH` on Flask app |
| **S2** | **High** | Security | Remove `?api_key=` query-string fallback in `auth.py:152` |
| **S3** | **High** | Security | Gate `/auth/create_key` behind admin auth (couples with S4) |
| **S4** | **High** | Security | Remove `--allow-unauthenticated` from Cloud Run deploy |
| **S5** | **High** | Security | Per-worker in-memory key store is broken — move to shared store |
| **S6** | **High** | Security | Truncated SHA-256 in `metadata_decrypt.py:75` — use full hash or HMAC |
| **A1 / Q1** | **High** | Architecture | Delete `synthesizer.py` or fix MRO order — it's dead code |
| S7 | Medium | Security | Restrict CORS to an allow-list |
| S8 | Medium | Security | Restrict CORS methods/headers |
| S9 | Medium | Security | Schema-validate every `request.get_json()` |
| S10 | Medium | Security | Add timeout & memory cap for Pine Script execution |
| S11 | Medium | Security | Use `127.0.0.1` default in dev `app.run` |
| Q2 | Medium | Quality | Remove duplicate `from datetime import timedelta` in `data.py:30` |
| Q3 | Medium | Quality | Move `from typing import Any` to top of `config.py:65` |
| Q4 | Medium | Quality | Remove 3 unused imports in `evaluator/builtins/__init__.py` |
| Q5 | Medium | Quality | Per-worker in-memory key store (couples with S5) |
| A2 | Medium | Architecture | Remove dead `parse()` call in `backtest.py:115-119` |
| A3 | Medium | Architecture | Replace `import *` in `ast/__init__.py` with explicit re-exports |
| D1 | Medium | Deps | Pin `requests>=2.31` and `tqdm>=4.66` |
| D2 | Medium | Deps | Run `pip-audit` / `npm audit` (deferred) |
| D3 | Medium | Deps | Move backend deps into `pyproject.toml` `[pro]` extra |
| D4 / D15 | Medium | Deps | Declare `pygments` as runtime dep (used in shipped code) |
| D10–D14 | Medium | Deps | Add `[data]` and `[jupyter]` extras for phantom imports |
| P1 | Medium | Process | Add `backend/` to CI lint scope |
| P2 | Medium | Process | Add mypy to `backend/` |
| S12–S22, A4–A6, D5–D9, D16–D17, P3–P7, Q6–Q9 | Low | various | Nice-to-haves and minor cleanups |

---

## 7. Recommended Remediation Order

1. **Security triage (this week):** S1, S2, S3, S4, S5, S6. These are the only items that would block a real production deploy.
2. **One PR for the easy stuff:** Q2 (duplicate import, 1 line), Q3 (E402, 3 lines), Q4 (3 unused imports), S11 (1-line env-var change), A2 (4-line dead-code removal), the `noqa: S311` additions. Mechanical, low risk.
3. **Resolve the dead-code landmine (A1):** decide between deleting `synthesizer.py` or reordering the MRO. The MRO reordering is a one-line change but needs a test that confirms `synthesizer.py` was the intended source.
4. **Dependency cleanup (D1, D3, D4, D10–D14):** one PR to `pyproject.toml`, one release note.
5. **CI hardening (P1, P2):** add `backend/` to ruff + mypy.
6. **Then a full re-audit after the above PRs land.**

---

## 8. Limitations of this audit

- **No CVE / vulnerability database lookups were performed** (no offline access to pip-audit, osv.dev, or GitHub Advisory DB). D2 is a placeholder for that work.
- **No tests were run** (`make test`, `make test-lsp`, `make test-backend`). All findings are static.
- **`scripts/build/*` and `Nuitka build pipeline` not audited in depth** (referenced in AGENTS.md as a known area; would need a separate review).
- **VS Code extension TypeScript code not deeply audited** (only `src/extension.ts` read in full; `node_modules` excluded).
- **LSP integration tests not audited** — `tests/test_langserver.py`, `test_lsp_features.py` not read.
- **Mypy wasn't run on `backend/`** (CI doesn't either). Manual review only.
- **No review of `examples/`, `docs/`, `frontend/`, or `clients/`** (out of scope for code audit).
- **`charts/` and other rendering/UI deps** only reviewed via `chart_renderer.py`; no end-to-end execution.

---

## 9. Task Tracking

This audit's findings have been converted into actionable tasks in `.opencode/tmp/tasks/audit-fixes/`. See `task.json` for the feature-level summary and `subtask_NN.json` for individual items. Run `bash ~/.opencode/skills/task-management/router.sh status audit-fixes` to see live status.
