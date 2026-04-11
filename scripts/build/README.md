# Build Scripts

This directory contains scripts for compiling the Pynescript LSP binary with Nuitka.

## Quick Start

```bash
# Install prerequisites
pip install nuitka cryptography

# Full build (onefile binary + VSIX bundle)
python scripts/build/compile.py

# Check imports without compiling (fast)
python scripts/build/compile.py --check

# Standalone build (faster, no self-extracting binary)
python scripts/build/compile.py --standalone
```

## Files

- `compile.py` — Main build script with options for dev/CI use
- `ci_build.py` — Optimized CI build script (GitHub Actions, Cloud Build)

## What Gets Built

```
dist/
├── lsp/
│   └── pynescript-lsp          # Onefile binary (self-extracting)
├── vsix/
│   └── pynescript-lsp.vsix     # VS Code extension bundle
└── pynescript-lsp              # Standalone binary (if --standalone)
```

## Encrypted Metadata

The `builtin_metadata.json` is encrypted with Fernet during the build:

```
src/pynescript/langserver/providers/
├── builtin_metadata.json          # Plaintext (git-tracked, open)
├── builtin_metadata.json.enc      # Encrypted (git-tracked)
├── builtin_metadata.json.sha256   # Integrity hash
scripts/build/.metadata.key         # Fernet key (NOT git-tracked)
```

The key is generated at build time and stored locally. For CI/CD, store the key as a secret.

## CI/CD

### GitHub Actions

```yaml
- name: Build LSP binary
  run: python scripts/build/ci_build.py
  env:
    CRYPTO_KEY: ${{ secrets.METADATA_KEY }}
```

### Google Cloud Build

```yaml
steps:
  - name: python
    args: [python, scripts/build/ci_build.py, --jobs=4]
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
