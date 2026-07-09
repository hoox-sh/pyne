<!-- Context: project-intelligence/errors/build-issues | Priority: medium | Version: 1.0 | Updated: 2026-07-05 -->

# Build Issues

Common problems when running `make build` / `scripts/build/compile.py`.

## `nuitka` not installed

```
ERROR: No module named nuitka
```
Fix: `pip install nuitka cryptography`. C compiler also required
(`gcc`/`clang`/`msvc`). On Anaconda, the static libpython may be missing —
either `conda install libpython-static` or pass `--static-libpython=no`
(default in `compile.py`).

## `cryptography` missing → metadata not encrypted

```
cryptography not installed, skipping encryption
Run: pip install cryptography
```
The build continues and produces a binary, but the encrypted `.enc` is not
written. The plaintext `builtin_metadata.json` will still be in the binary,
which is fine for dev. For release builds, install `cryptography`.

## `.metadata.key` regenerates between CI runs

Symptom: `builtin_metadata.json.enc` differs across CI builds even with no
source changes. Cause: `ci_build.py` calls `Fernet.generate_key()` when
`CRYPTO_KEY` is unset.

Fix: store a Fernet key in the CI secret store:
- GitHub Actions: `secrets.METADATA_KEY` (consumed in `.github/workflows/ci.yml`).
- Cloud Build: substitution `_METADATA_KEY` (consumed in `cloudbuild.yaml`).

The key is in `scripts/build/.metadata.key` (gitignored). For local builds, do
**not** commit the key — let it regenerate; the encrypted blob is committed but
re-encrypted is fine because the dev plaintext is what matters.

## `antlr4` tool missing for `hatch run lint:gen-parser`

```
ERROR: antlr4 command not found
```
Fix: `hatch run lint:gen-parser` is only available inside the `lint` hatch env.
Either `hatch run lint:gen-parser` (uses the env) or install `antlr4-cli`
manually (requires Java).

## Onefile binary size or slow build

Use `--standalone` to skip the self-extracting wrapper (5–15 min vs 10–30 min).
`scripts/build/compile.py --standalone --jobs $(nproc)`.

## Build dir polluted

`make clean` removes `dist/`, `vscode-extension/out/`, `vscode-extension/node_modules/`,
`__pycache__/`, `*.pyc`, `*.pyo`. Run before switching Python version.

## 📂 Codebase References

- **Implementation**: `scripts/build/compile.py` — main build.
- **Implementation**: `scripts/build/ci_build.py` — CI build with `CRYPTO_KEY`.
- **Implementation**: `scripts/generate_builtin_metadata.py` — metadata regen.
- **Reference**: `scripts/build/README.md` — full build docs.
- **Reference**: `.gitignore` — `scripts/build/.metadata.key` is ignored.
