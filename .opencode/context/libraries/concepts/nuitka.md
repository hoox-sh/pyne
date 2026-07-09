<!-- Context: libraries/concepts/nuitka | Priority: high | Version: 1.0 | Updated: 2026-07-05 -->

# Nuitka (Python → binary compiler)

Nuitka compiles the LSP server into a single-file or standalone-directory
executable. This is how the closed-source-style distribution works.

**context7 source**: `/websites/nuitka_net_user-documentation` (225 snippets) and
`/nuitka/nuitka-action` (475). Verify against the Nuitka version you install
(`pip install nuitka` — no version pinned in this repo's `pyproject.toml`).

## Used in This Repo

```bash
python -m nuitka \
  --output-dir=dist/lsp \
  --python-flag=no_site,no_docstrings \
  --static-libpython=no \
  --follow-imports \
  --include-data-dir=src/pynescript/langserver/providers=pynescript/langserver/providers \
  --lto=auto \
  --product-name=pynescript-lsp \
  --jobs=4 \
  --onefile \
  --remove-output \
  src/pynescript/langserver
```

Driven by `scripts/build/compile.py`.

## Key Flags

| Flag | Effect |
| --- | --- |
| `--onefile` | Produce a single self-extracting binary. |
| `--standalone` | Directory with binary + dependencies. Faster build, no self-extract. |
| `--include-data-dir=SRC=DST` | Recursively bundle `SRC/` into the binary as `DST/`. |
| `--include-data-files=PATTERN=DST` | Single-file inclusion. |
| `--include-onefile-external-data=PATTERN` | Keep data **outside** the onefile blob. |
| `--follow-imports` | Recursively compile imports. |
| `--lto=auto` | Link-time optimization. |
| `--static-libpython=no` | Use shared libpython (avoids needing a static build). |
| `--python-flag=no_site` | Don't prepend site-packages. |
| `--python-flag=no_docstrings` | Strip docstrings. |
| `--remove-output` | Clean intermediate build artifacts (release only). |
| `--unstripped` | Keep symbols (for `--check` mode). |
| `--product-name=NAME` | Output binary name. |
| `--jobs=N` | Parallel compile jobs. |

## Build Modes in This Repo

| Mode | Time | Notes |
| --- | --- | --- |
| `--check` | ~30s | `compile.py --check` — import resolution only, no compile. |
| `--standalone` | 5–15 min | `compile.py --standalone` — dir layout, no onefile. |
| `--onefile` (default) | 10–30 min | Full self-extracting binary. |
| CI (`ci_build.py`) | 5–15 min | Higher parallelism + cache-friendly layout. |

## Embedding Data Files

To ship the encrypted metadata inside the binary:

```
--include-data-dir=src/pynescript/langserver/providers=pynescript/langserver/providers
```

This bundles the entire `providers/` directory. At runtime,
`metadata_decrypt.py` reads `Path(__file__).parent / "builtin_metadata.json.enc"`.

## Prerequisites

- C compiler: `gcc`, `clang`, or `msvc`.
- Anaconda: `conda install libpython-static` (or use `--static-libpython=no`).
- `cryptography` for the Fernet step (separate from Nuitka).

## Common Gotchas

- `--onefile` first run is slow (extraction happens at runtime on each launch
  into a temp dir). Use `--standalone` for repeated dev runs.
- `--include-data-dir` paths are **relative to the build root**, not to where
  you run `python -m nuitka`.
- Without `--remove-output`, the build dir is huge; CI sets this flag.
- Nuitka doesn't see dynamic imports via `importlib.import_module` — declare them
  via `--include-module=...` or use static imports.

## 📂 Codebase References

- **Implementation**: `scripts/build/compile.py` — local build (this flag set).
- **Implementation**: `scripts/build/ci_build.py` — CI build.
- **Reference**: `scripts/build/README.md` — build documentation.
