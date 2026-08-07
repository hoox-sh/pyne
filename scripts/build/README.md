# Build Scripts

This directory contains scripts for compiling the Pynescript **LSP** and **CLI**
binaries with Nuitka.

## Quick Start

```bash
# Install prerequisites
pip install nuitka cryptography

# Full LSP build (onefile binary + VSIX bundle) — default
python scripts/build/compile.py
# ≡ make build

# CLI onefile binary (pynescript)
python scripts/build/compile.py --target cli
# ≡ make build-cli

# Both
python scripts/build/compile.py --target all

# Check imports without compiling (fast)
python scripts/build/compile.py --target all --check
# ≡ make build-check

# Standalone build (faster, no self-extracting binary)
python scripts/build/compile.py --target cli --standalone
```

## Files

- `compile.py` — Main build script with options for dev/CI use (`--target lsp|cli|all`)
- `ci_build.py` — Optimized CI build script (GitHub Actions, Cloud Build)

## What Gets Built

```
dist/
├── lsp/
│   └── pynescript-lsp          # LSP onefile binary (self-extracting)
├── cli/
│   └── pynescript              # CLI onefile binary
├── vsix/
│   └── pynescript-lsp.vsix     # VS Code extension bundle
├── pynescript-lsp              # LSP binary (CI moves to dist/)
└── pynescript                  # CLI binary (CI moves to dist/)
```

### Target differences

| Target | Entry | Includes | Excludes |
| --- | --- | --- | --- |
| `lsp` | `langserver/__main__.py` | pygls + providers metadata | evaluator, compiler, numba |
| `cli` | `pynescript/__main__.py` | Click CLI + evaluator (interpret) | langserver, flask, numba |

Portable Nuitka builds intentionally **do not** embed Numba; `compile` / Numba
paths work in the Docker CLI image (`pip install ".[compile,data]"`) and from
the PyPI package with the `compile` extra.

## Encrypted Metadata

The `builtin_metadata.json` is encrypted with Fernet during the build so Nuitka
binaries can ship metadata without plaintext on disk.

```
src/pynescript/langserver/providers/
├── builtin_metadata.json          # Plaintext (git-tracked, open; preferred in dev)
├── builtin_metadata.json.enc      # Encrypted (git-tracked)
├── builtin_metadata.json.sha256   # Integrity hash (16-char SHA-256 prefix)
scripts/build/.metadata.key         # Fernet key (gitignored — never commit)
```

### Key resolution (stable / reproducible)

`compile.py` and `ci_build.py` resolve the key in this order:

1. `CRYPTO_KEY` env  
2. `PYNESCRIPT_METADATA_KEY` env  
3. `METADATA_KEY` env  
4. Existing `scripts/build/.metadata.key`  
5. Generate a new key and write `.metadata.key` (local first-time only)

Use the **same** key in every CI run so `.enc` blobs stay reproducible across
rebuilds of the same JSON.

### Local first-time setup

```bash
pip install cryptography

# Option A — force encrypt without a full Nuitka compile (Fernet IV still changes .enc)
python scripts/build/compile.py --check --encrypt   # generates .metadata.key + encrypts

# Option B — generate key explicitly
python -c "from cryptography.fernet import Fernet; from pathlib import Path; \
  p=Path('scripts/build/.metadata.key'); p.write_bytes(Fernet.generate_key()); p.chmod(0o600); print(p.read_text())"

# Re-encrypt after regenerating JSON
python scripts/generate_builtin_metadata.py
python -c "from scripts.build.compile import encrypt_metadata; encrypt_metadata()"
```

**Note:** plain `--check` (e.g. `make build-check`) does **not** re-encrypt metadata, so Fernet
IV churn does not dirty `builtin_metadata.json.enc` / `.sha256` in git. Use `--encrypt` or a full
LSP build when you intentionally want a new ciphertext.

### GitHub Actions secret

Store the **same** key bytes as repository secrets:

| Secret name | Used as |
|-------------|---------|
| `METADATA_KEY` | `CRYPTO_KEY: ${{ secrets.METADATA_KEY }}` in release/CI |
| `CRYPTO_KEY` | optional alias (same value) |

```bash
# After scripts/build/.metadata.key exists:
gh secret set METADATA_KEY -R hoox-sh/pyne < scripts/build/.metadata.key
gh secret set CRYPTO_KEY -R hoox-sh/pyne < scripts/build/.metadata.key
```

### Google Cloud Build

Set substitution `_METADATA_KEY` to the same Fernet key string (see `cloudbuild.yaml`:
`CRYPTO_KEY=${_METADATA_KEY}`).

## CI/CD

### GitHub Actions

```yaml
- name: Build LSP binary
  run: python scripts/build/ci_build.py --target lsp --jobs 4
  env:
    CRYPTO_KEY: ${{ secrets.METADATA_KEY }}

- name: Build CLI binary
  run: python scripts/build/ci_build.py --target cli --jobs 4 --skip-metadata --skip-vsix
```

### Google Cloud Build

```yaml
steps:
  - name: python
    args: [python, scripts/build/ci_build.py, --jobs=4]
    env:
      - 'CRYPTO_KEY=${_METADATA_KEY}'
```

## Build Time

| Mode | Time | Notes |
|------|------|-------|
| `--check` | ~30s | Import resolution only |
| `--standalone` | 5–15min | Faster, no onefile packaging |
| `--onefile` | 10–30min | Full self-extracting binary |
| CI (8 cores) | 5–15min | High parallelism, cached builds |

## Dependencies

- Python 3.10+ (3.12 recommended)
- `nuitka>=2.0`
- `cryptography` (for metadata encryption)
- C compiler (gcc/clang/msvc)
- Anaconda: `conda install libpython-static` (or use `--static-libpython=no`)
