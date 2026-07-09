<!-- Context: libraries/errors/nuitka-errors | Priority: medium | Version: 1.0 | Updated: 2026-07-05 -->

# Nuitka Errors

Pitfalls when building the LSP binary with `scripts/build/compile.py` or
`scripts/build/ci_build.py`.

## "static libpython not available"

```
Error, static libpython is not available for use.
```

Conda without `libpython-static`, or a slim Docker image. Fixes:
- `conda install libpython-static`
- Pass `--static-libpython=no` (already the default in this repo's
  `compile.py`).

## "No module named nuitka"

```
pip install nuitka
```

Add `nuitka` to your dev env. There is no `pyproject.toml` entry — it's a
build-time tool.

## Binary Is Huge (>100 MB)

Causes:
- `--follow-imports` pulls in everything; some packages are huge
  (`pandas`, `matplotlib`, etc.).
- Test deps leaking in — make sure you run the build with the **production**
  venv, not the dev one.

Fix: use `--standalone` to see what gets pulled, then drop unused heavy
imports. For the backend, that's a separate concern (see `Dockerfile.api`).

## Data File Not Found at Runtime

```
FileNotFoundError: .../builtin_metadata.json.enc
```

The data file was not included. Check the
`--include-data-dir=src/pynescript/langserver/providers=pynescript/langserver/providers`
flag is set with **absolute** paths and that the destination is what
`metadata_decrypt.py` looks up (`Path(__file__).parent / "..."`).

## "ImportError" at Runtime in Compiled Binary

The compiled binary can't find a dynamic import. Two common cases:
- `importlib.import_module("foo")` — Nuitka doesn't see this. Add
  `--include-module=foo` or convert to a static import.
- Plugin discovery via entry points — needs `--include-package` or
  `--include-module` for each discovered plugin.

## Onefile First-Launch Slowness

`--onefile` extracts to a temp dir on every launch. The first run is slow
because of the extraction. This is normal. Use `--standalone` for dev.

## Key Re-rolls Between CI Runs

`Fernet.generate_key()` is called every time when `CRYPTO_KEY` is unset.
Symptom: the committed `builtin_metadata.json.enc` differs by a few bytes
between runs even when inputs are identical.

Fix: set `CRYPTO_KEY` in CI (see `libraries/concepts/cryptography-fernet.md`).

## Build Times Out (Cloud Build)

`cloudbuild.yaml` sets `timeout: 1200s` (20 min). If you bump parallelism or
add heavy packages, you may need to extend this. `--onefile` builds on 8
cores typically take 10–20 min.

## C Compiler Missing

```
Nuitka will now use gcc but it is not installed.
```

Install `gcc` (Linux), `clang` (macOS), or `msvc` (Windows, with Build Tools).

## 📂 Codebase References

- **Implementation**: `scripts/build/compile.py` — local build.
- **Implementation**: `scripts/build/ci_build.py` — CI build.
- **Reference**: `scripts/build/README.md` — build docs.
- **Reference**: `libraries/concepts/nuitka.md`.
