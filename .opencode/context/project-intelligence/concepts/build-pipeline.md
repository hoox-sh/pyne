<!-- Context: project-intelligence/concepts/build-pipeline | Priority: high | Version: 1.0 | Updated: 2026-07-05 -->

# Build Pipeline (LSP binary + VSIX)

The LSP server ships as a Nuitka onefile binary plus a VSIX bundle that the VS Code
extension wraps. The pipeline also encrypts the builtin's metadata with Fernet so
the compiled binary doesn't expose plaintext docs.

## Stages

1. **Generate metadata** — `scripts/generate_builtin_metadata.py` introspects
   `BuiltinEvaluator` and writes
   `src/pynescript/langserver/providers/builtin_metadata.json`.
2. **Encrypt metadata** — Fernet-encrypts the JSON to `.enc` and writes a `.sha256`.
   The symmetric key lands in `scripts/build/.metadata.key` (gitignored).
3. **Compile with Nuitka** — `python -m nuitka` against
   `src/pynescript/langserver/`, with `--include-data-dir=.../providers=.../providers`
   so the encrypted metadata ships inside the binary.
4. **Bundle VSIX** — `scripts/build/compile.py` zips `vscode-extension/` (minus
   `*.map` and `*.ts`) and embeds the binary at `vsix/lsp_bin/pynescript-lsp`.

## Scripts

- `scripts/build/compile.py` — main local build; supports `--check`, `--standalone`,
  `--no-encrypt`, `--no-metadata`, `--clean`, `--jobs`, `--verbose`, `--dry-run`.
- `scripts/build/ci_build.py` — CI-optimized variant; reads `CRYPTO_KEY` env var to
  keep the same key across builds (so the encrypted bundle is byte-stable).
- `scripts/generate_builtin_metadata.py` — metadata generator (run only when
  adding builtins).
- `scripts/update_copyright.py` — license header updater (utility, not part of build).

## On-disk Artifacts

| Path | Tracked? | Notes |
| --- | --- | --- |
| `src/pynescript/langserver/providers/builtin_metadata.json` | Yes | Plaintext, used in dev. |
| `.../builtin_metadata.json.enc` | Yes | Encrypted, bundled in binary. |
| `.../builtin_metadata.json.sha256` | Yes | Hash of plaintext. |
| `scripts/build/.metadata.key` | **No** (gitignored) | Symmetric Fernet key. |
| `dist/lsp/pynescript-lsp` | No (gitignored) | Onefile binary. |
| `dist/vsix/pynescript-*.vsix` | No (gitignored) | VS Code extension bundle. |

## CI Key Wiring

- **GitHub Actions**: `env: CRYPTO_KEY: ${{ secrets.METADATA_KEY }}`
- **Cloud Build**: `env: CRYPTO_KEY=${_METADATA_KEY}` (substitution variable).

If `CRYPTO_KEY` is unset, `ci_build.py` generates a new key on each run — fine for
artifacts but breaks reproducibility.

## 📂 Codebase References

- **Implementation**: `scripts/build/compile.py` — local build.
- **Implementation**: `scripts/build/ci_build.py` — CI build.
- **Implementation**: `scripts/generate_builtin_metadata.py` — metadata generation.
- **Reference**: `scripts/build/README.md` — build docs.
- **Reference**: `cloudbuild.yaml` — Cloud Build steps.
- **Reference**: `.github/workflows/ci.yml` — GitHub Actions.
