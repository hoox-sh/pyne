# Build Pipeline

## Standard Flow

```
Source → ruff check → mypy → pytest → Nuitka compile → dist/pynescript-lsp
                                                    ↓
                                              VS Code .vsix bundle
```

## LSP Binary Build

```bash
# Full build (onefile binary)
python scripts/build/compile.py --jobs=4

# Check imports without compiling (fast, ~30s)
python scripts/build/compile.py --check

# Standalone build (faster, no self-extracting)
python scripts/build/compile.py --standalone
```

Build times: `--check` ~30s, `--standalone` 5-15min, `--onefile` 10-30min.

Requires: Python 3.10+, `nuitka>=2.0`, `cryptography`, C compiler.

## Metadata Encryption

- `builtin_metadata.json` is encrypted with Fernet during build
- Encryption key: `scripts/build/.metadata.key` (gitignored)
- CI uses `CRYPTO_KEY` / `METADATA_KEY` secret
- Decryption: `src/pynescript/langserver/providers/metadata_decrypt.py`

## Release

- Triggered by `v*` tags on GitHub
- Publishes to GitHub Releases + VS Code Marketplace
- Requires `VSCE_PAT` secret for marketplace publishing
