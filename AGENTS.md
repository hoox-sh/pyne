# AGENTS.md

Compact guide for AI agents working in the **pyne** repo (package name
`pynescript`). Read this first to avoid common mistakes; dive into
`.opencode/context/project-intelligence/` for deeper reference.

## What this is

Python toolchain for TradingView Pine Script: parser, AST, evaluator, linter,
LSP server, Flask Pro API, VS Code extension. Source under `src/pynescript/`
(src-layout package), ANTLR4 grammar, ASDL-generated AST nodes, Nuitka-compiled
LSP binary, optional cloud backend.

**AXIS** (charting PWA) is **not** in this repo — see
[jango-blockchained/axis](https://github.com/jango-blockchained/axis)
(`/home/jango/Git/axis`). **Do not recreate `frontend/`.**

## Quick Commands

```bash
make install         # pip install -e ".[lsp]"
make test            # pytest tests/ -v --tb=short          (all tests)
make test-lsp        # tests/test_langserver.py + test_lsp_features.py
make test-backend    # tests/test_backend.py (needs backend/requirements.txt)
make lint            # ruff check src/ tests/ backend/
make fmt             # ruff format
make run             # python -m backend.app                 (Flask Pro API :5002)
make run-lsp         # python -m pynescript.langserver        (LSP)
make build-check     # python scripts/build/compile.py --check   (fast, no compile)

# Docker (multi-target Dockerfile)
make docker-build      # buildx bake production api image
make docker-build-cli  # buildx bake CLI image (pynescript)
make docker-cli ARGS="check script.pine"  # compose profile cli
make docker-up         # compose api-dev on :5002 (source mounts)
make docker-up-full    # api + redis profile only (not LSP)
make docker-prod       # requires ADMIN_TOKEN; gunicorn, no source mounts
make docker-smoke      # curl health on :5002

# Packages / Nuitka
make package           # sdist + wheel (hoox-pyne)
make build             # Nuitka LSP binary
make build-cli         # Nuitka CLI binary
```

Hatch: `hatch run test:test`, `hatch run lint:style`, `hatch run lint:typing`.
See `.opencode/context/project-intelligence/lookup/commands.md`.

## Hard Constraints

- **Edit only `resource/` for the grammar**; never touch
  `src/pynescript/ast/grammar/antlr4/generated/` or
  `src/pynescript/ast/grammar/asdl/generated/` — both are regenerated artifacts.
  See `.opencode/context/project-intelligence/guides/grammar-changes.md`.
- **No stale backups in `src/`.** `builder.py.bak` and
  `evaluator/builtins/technical_refactored.py` were removed in 2026-07; do not
  recreate them — the live `builder.py` and `technical.py` are the only sources
  of truth.
- **`from __future__ import annotations` is required** on every new Python file
  (enforced by ruff isort `required-imports`).
- **Console scripts are separate**: `pynescript` (Click) and `pynescript-lsp`
  (pygls). Don't conflate them.
- **`tests/conftest.py` parametrizes `pinescript_filepath` over every `*.pine`
  in `tests/data/builtin_scripts/`** — a new test using this fixture runs ~500
  cases. Use `--example-scripts-dir=...` to narrow. Prefer unit tests that do
  **not** use this fixture in CI-critical paths.
- **Generated `builtin_metadata.json` is built from code**, not hand-edited.
  Re-run `python scripts/generate_builtin_metadata.py` after adding builtins,
  then re-encrypt (see CRYPTO_KEY below).

## CRYPTO_KEY / encrypted LSP metadata (important)

Nuitka LSP binaries ship `builtin_metadata.json.enc` (Fernet). The plaintext
JSON stays git-tracked for dev; the loader prefers plaintext when present.

| Artifact | Path | Tracked? |
| --- | --- | --- |
| Plaintext metadata | `src/pynescript/langserver/providers/builtin_metadata.json` | yes |
| Encrypted blob | `…/builtin_metadata.json.enc` | yes |
| Integrity (16-char SHA-256 prefix) | `…/builtin_metadata.json.sha256` | yes |
| Fernet key | `scripts/build/.metadata.key` | **no** (gitignored) |

### Key resolution (stable / reproducible)

`scripts/build/compile.py` and `ci_build.py` resolve the key in this order:

1. `CRYPTO_KEY` env
2. `PYNESCRIPT_METADATA_KEY` env (same material; also used at runtime decrypt)
3. `METADATA_KEY` env
4. Existing `scripts/build/.metadata.key`
5. Generate once and write `.metadata.key` (local first-time only)

**Always use the same key in CI** so rebuilds of the same JSON produce a
reproducible `.enc` (Fernet ciphertext still varies with IV, but the *key* must
not rotate accidentally).

### Local setup

```bash
pip install cryptography

# If no key yet: encrypt once (writes scripts/build/.metadata.key)
python -c "from scripts.build.compile import encrypt_metadata; encrypt_metadata()"

# After changing builtins:
python scripts/generate_builtin_metadata.py
python -c "from scripts.build.compile import encrypt_metadata; encrypt_metadata()"
```

### GitHub / Cloud Build secrets

| Store | Name | Used as |
| --- | --- | --- |
| GitHub Actions | `secrets.METADATA_KEY` | `CRYPTO_KEY: ${{ secrets.METADATA_KEY }}` in `release.yml` |
| GitHub Actions | `secrets.CRYPTO_KEY` | optional alias (same value) |
| Cloud Build | substitution `_METADATA_KEY` | `CRYPTO_KEY=${_METADATA_KEY}` in `cloudbuild.yaml` |

```bash
# After local .metadata.key exists:
gh secret set METADATA_KEY -R hoox-sh/pyne < scripts/build/.metadata.key
gh secret set CRYPTO_KEY   -R hoox-sh/pyne < scripts/build/.metadata.key
```

Never commit `.metadata.key`. If lost: generate a new Fernet key, update both
GitHub secrets + Cloud Build substitution, re-encrypt, commit new `.enc` +
`.sha256`.

Full detail: `scripts/build/README.md`.

## Docker / Pro API (ops)

Multi-target `Dockerfile` (default Cloud Run / bake target = **`api`**):

| Target | Process | Use |
| --- | --- | --- |
| `api` | gunicorn via `docker/entrypoint-api.sh` | production / Cloud Run |
| `api-dev` | `python -m backend.app` | local compose (source mounts) |
| `lsp` | stdio language server | `docker compose run --rm lsp` only |

Supporting files: `docker-bake.hcl`, `docker-compose.yml`,
`docker-compose.prod.yml`, `.dockerignore`, `.env.example`.

### Critical compose footguns

- **Prod volume merge:** Compose merges volumes by mount *target*. Prod overlay
  **must** use `volumes: !override` (only `api_data:/data`) or host
  `./src` + `./backend` binds survive and `PYTHONPATH` prefers host code.
- **`make docker-up-full`** starts **redis only** (not detached stdio LSP).
  Use `docker compose --profile lsp run --rm lsp` for LSP.
- **Host port** default `5002` → container `8080` (`API_PORT`).

### Auth & key store

- `POST /auth/create_key` is **fail-closed**: requires non-empty `ADMIN_TOKEN`
  env **and** matching `X-Admin-Token` (or Bearer / AdminToken). Unset token →
  403. `make docker-prod` refuses to start without `ADMIN_TOKEN`.
- `STORE_BACKEND`: `json` (default, single-process) | `sqlite` (multi-worker
  shared volume) | `redis` (multi-replica; needs `REDIS_URL`).
  Prod compose defaults to **`sqlite`** on `/data/api_keys.db`.
- JSON store may hold raw keys (dev only). SQLite/Redis stores are **hash-only**.

Tests set `ADMIN_TOKEN` via monkeypatch; local `make run` needs
`export ADMIN_TOKEN=…` to mint keys.

## Build / Release / CI

### Package

- PyPI **distribution** name: **`pyne`** (import / console scripts stay
  **`pynescript`** / `pynescript-lsp`). Upstream PyPI `pynescript` is elbakramer.
- Product/repo: **pyne** · install: `pip install "hoox-pyne[lsp]"`.
- Version: `src/pynescript/__about__.py` (exported as `pynescript.__version__`).
- Optional extras: `[lsp]`, `[pro]`, `[compile]`, `[data]` / `[datafeed]`.
- Publish: tag `vX.Y.Z` → `.github/workflows/publish.yml` (Trusted Publishing
  env `pypi`). Dry-run via workflow_dispatch. See `CONTRIBUTING.md`.

### Nuitka / VSIX

- `make build` → `dist/lsp/pynescript-lsp` + `dist/vsix/…`.
- `make build-check` → import check only (~30s).
- Anaconda: `conda install libpython-static` or keep `--static-libpython=no`.
- VS Code extension: `vscode-extension/` (Node 22). Version should track package
  when shipping together. `make build-vscode`.

### GitHub Actions (`.github/workflows/`)

| Workflow | Role |
| --- | --- |
| `ci.yml` | lint, test matrix 3.10–3.13, package build, Docker `api` smoke, VSIX |
| `release.yml` | Nuitka LSP binaries + VSIX on `v*` tags (`CRYPTO_KEY`) |
| `publish.yml` | PyPI upload on `v*` tags |

**No AXIS/frontend jobs in this repo.** PWA/e2e live in the `axis` repo.

CI unit path intentionally skips huge corpus-parametrized tests
(`test_parse_and_unparse`); run those locally with `make test`.

### Cloud Build

`cloudbuild.yaml` builds `--target=api` and deploys by `$COMMIT_SHA`. Pass
`_METADATA_KEY` for LSP binary encryption. Cloud Run defaults (memory/workers)
are tight for numpy/numba/matplotlib — raise memory / lower workers before
assuming OOM is an app bug.

## Codebase Entry Points

| Want to ... | Look at |
| --- | --- |
| Parse / unparse Pine Script | `src/pynescript/ast/helper.py` |
| Add a new builtin (`ta.*`, `math.*`, …) | `src/pynescript/ast/evaluator/builtins/<ns>.py` + `scripts/generate_builtin_metadata.py` |
| Add an LSP feature | `src/pynescript/langserver/features/<name>.py` + `server.py` |
| Wire inlay hints / hover / etc. | `src/pynescript/langserver/features/inlay_hints.py` is a worked example |
| Semantic tokens | `features/semantic_tokens.py` + legend in `langserver/config.py` |
| Add a CLI subcommand | `src/pynescript/__main__.py` (Click group) |
| Change the grammar | `src/pynescript/ast/grammar/antlr4/resource/*.g4`, then `hatch run lint:gen-parser` |
| Add a backend endpoint | `backend/api/` blueprints + `backend/app.py` |
| Auth / key store | `backend/middleware/auth.py` (+ `key_store_sqlite.py` / `key_store_redis.py`) |
| Work on the TS port | `pine-worker/` (extra tool; README + strategy-events plan) |

## LSP notes

- Server version comes from `pynescript.__about__.__version__` (not a hardcode).
- Advertise only **implemented** capabilities in `langserver/config.py`
  (no signatureHelp/codeAction until handlers exist).
- Builtin metadata: ~870 entries after regenerate; load order prefers
  plaintext over `.enc` in dev.
- Clients: VS Code extension (`vscode-extension/`), stdio `pynescript-lsp`,
  AXIS may use HTTP LSP bridge endpoints on the Pro API.

## Pine v6 Grammar & Regeneration Notes (2026-07)

When adding v6 features that touch literals or syntax (multiline strings
`"""..."""` / `'''...'''`, etc.):

- The resource `PinescriptLexer.g4` may require **non-obvious quoting** for
  triple-quoted fragments. Direct `"'''"` or `'"""'` literals inside fragment
  rules can trigger ANTLR "quote came as a complete surprise" errors. Use
  factored starters:
  ```g4
  fragment TRIPLE_SQ_START: '\'' '\'' '\'';
  fragment TRIPLE_SINGLE_QUOTED_STRING: TRIPLE_SQ_START ... TRIPLE_SQ_START;
  ```
- `generate.py` (and `hatch run lint:gen-parser`) hardcodes
  `$(python -c 'sys.executable')/antlr4`. The `antlr4-cli` pip package often
  lands in `~/.local/bin`. Use a temp dir + full path or `PATH` shim + manual
  copy of `*Base.py`.
- Full regeneration can produce parser context classes whose accessor methods
  differ from what `builder.py` expects. **Safe pattern**: edit only resource +
  selectively copy the fresh `PinescriptLexer.py` (and update the copied
  `LexerBase.py`). Leave the committed `PinescriptParser.py` (and visitors)
  untouched unless you are prepared to also patch the builder.
- Always test with `from pynescript.ast.helper import parse, unparse` on a
  minimal v6 snippet **before** the huge parametrized corpus.
- After success, update `docs/missing_features.md` and the grammar-changes guide.

See `.opencode/context/project-intelligence/guides/grammar-changes.md` and
`docs/missing_features.md`.

## Testing

- **Unit**: `tests/test_evaluator.py`, `tests/test_linter.py`,
  `tests/test_parse_and_unparse.py` (latter is corpus-parametrized).
- **LSP unit**: `tests/test_lsp_features.py` — handlers + fake
  `lsprotocol.types.*Params`.
- **LSP e2e**: `tests/test_langserver.py` — needs
  `pip install -e ".[dev-lsp]" pytest-asyncio`.
- **Backend**: `tests/test_backend.py` — needs
  `pip install -r backend/requirements.txt` (or `.[pro]`). Sets `ADMIN_TOKEN`
  in fixtures.
- **Corpus**: `tests/data/builtin_scripts/*.pine`; `tests/data/library/` is
  reference only.
- Coverage: `hatch run test:test-cov`. CI uploads codecov only on Python 3.13.

## Style

Ruff line length 120 (see `pyproject.toml`). Black target-version `py310`.
Mypy is strict-ish but exempts generated grammar modules,
`evaluator.builtins.*`, and `tests.*`. `from __future__ import annotations`
is mandatory.

`/build/` in `.gitignore` is **root-only** so `scripts/build/` stays trackable;
only `scripts/build/.metadata.key` is ignored.

## Sub-Skills

- **Brainstorm** before any non-trivial feature work.
- **TDD** when implementing features.
- **Verification before completion** — run `make test lint` (or the relevant
  subset) and confirm output before claiming done.

## Where to Read More

- `.opencode/context/navigation.md` — full context tree map.
- `.opencode/context/project-intelligence/navigation.md` — internal docs.
- `.opencode/context/libraries/navigation.md` — pygls/antlr/click/Nuitka/lsprotocol.
- `.opencode/plans/pynescript-lsp-implementation.md` — LSP design doc.
- `scripts/build/README.md` — Nuitka + CRYPTO_KEY.
- `docs/pyne/devops/` — Docker / GCP / security (Mintlify product docs).
- `CONTRIBUTING.md` — hatch workflow + PyPI release steps.
- `CHANGELOG.md` — Keep a Changelog.

---

## Sister Repos & websites

**Site:** [hoox.sh](https://hoox.sh) — marketing + product docs for the stack.

| Product | GitHub | Local path | Website |
|---|---|---|---|
| **HOOX** | [jango-blockchained/hoox](https://github.com/jango-blockchained/hoox) | `/home/jango/Git/hoox` | [hoox.sh](https://hoox.sh) · [docs.hoox.sh](https://docs.hoox.sh) |
| **PYNE** (this repo) | [hoox-sh/pyne](https://github.com/hoox-sh/pyne) | `/home/jango/Git/pynescript` | [hoox.sh/pyne](https://hoox.sh/pyne) · [docs](https://hoox.sh/pyne/docs) |
| **AXIS** | [jango-blockchained/axis](https://github.com/jango-blockchained/axis) | `/home/jango/Git/axis` | [hoox.sh/axis](https://hoox.sh/axis) · [docs](https://hoox.sh/axis/docs) |

Related:

| Repo | Path | Purpose |
|---|---|---|
| `hoox-landing-page` | `/home/jango/Git/hoox-landing-page` | Marketing site source for [hoox.sh](https://hoox.sh) |
| `pyne-worker` | `/home/jango/Git/pyne-worker` | Python CF Worker — edge eval (depends on `pynescript`) |
| `pine-worker` | `/home/jango/Git/pine-worker` | TypeScript CF Worker — Pine eval + trade events |

**Key dependency links:**
- AXIS UI → pyne Pro API (`make run` on `:5002`) or AXIS Worker
- `pyne-worker` → `pynescript` package (editable install)
- HOOX trade path can consume Pine signals from edge workers

```
                    https://hoox.sh
           ┌──────────────┼──────────────┐
           ▼              ▼              ▼
         HOOX            PYNE           AXIS
    (edge execution)  (this repo)   (charting UI)
           │              │              │
           └──────────────┴──────────────┘
```
