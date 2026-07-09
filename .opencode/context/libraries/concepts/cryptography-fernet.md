<!-- Context: libraries/concepts/cryptography-fernet | Priority: medium | Version: 1.0 | Updated: 2026-07-05 -->

# cryptography / Fernet

`Fernet` is the symmetric encryption used to encrypt the LSP `builtin_metadata.json`
so the compiled binary doesn't ship plaintext docs.

**context7 source**: `/pyca/cryptography` and
`/websites/cryptography_io_en`. Verify against the installed `cryptography`
version.

## Used in This Repo

```python
from cryptography.fernet import Fernet

# Build time — scripts/build/compile.py
key = Fernet.generate_key()
fernet = Fernet(key)
encrypted = fernet.encrypt(plaintext_bytes)
(encrypted_path).write_bytes(encrypted)
# Write `key` to scripts/build/.metadata.key (gitignored)

# Runtime — src/pynescript/langserver/providers/metadata_decrypt.py
key = _load_embedded_key()      # may come from the compiled .pyc or env
fernet = Fernet(key)
plaintext = fernet.decrypt(encrypted_bytes)
```

## Properties

- **Authenticated** — Fernet uses AES-128-CBC + HMAC-SHA256; tampering is
  detected and raises `InvalidToken`.
- **Versioned** — Format is `Version || Timestamp(8) || IV(16) || Ciphertext ||
  HMAC(32)`. Older keys still decrypt older payloads.
- **URL-safe base64** — the output is text-safe.

## Key Generation

```python
Fernet.generate_key()  # → bytes (44 chars, url-safe-base64)
```

Output is safe to put in a file, env var, or secret store.

## CI Key Persistence

To produce a byte-stable encrypted bundle across CI runs, the key must be
reused:

- GitHub Actions: `env: CRYPTO_KEY: ${{ secrets.METADATA_KEY }}`.
- Cloud Build: `env: CRYPTO_KEY=${_METADATA_KEY}`.

`scripts/build/ci_build.py` reads `CRYPTO_KEY` and uses it as the Fernet key
when set; otherwise it generates a new one.

## Gotchas

- Don't `print()` a Fernet key — it's a secret.
- `Fernet.decrypt` raises `InvalidToken` on tamper or wrong key — wrap in
  `try/except` if you need to fall back to plaintext.
- `os.chmod(key_file, 0o600)` is what `compile.py` does; preserve that mode in
  CI artifacts.

## 📂 Codebase References

- **Implementation**: `scripts/build/compile.py` — `encrypt_metadata()`.
- **Implementation**: `scripts/build/ci_build.py` — reads `CRYPTO_KEY`.
- **Implementation**: `src/pynescript/langserver/providers/metadata_decrypt.py`
  — runtime decrypt.
- **Reference**: `pyproject.toml` — `cryptography` is **not** in
  `[project.dependencies]`; it's a build-time tool, install with
  `pip install cryptography`.
