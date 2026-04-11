"""Encrypted metadata loader for the compiled LSP binary.

When pynescript is compiled with Nuitka, the builtin_metadata.json is encrypted
with Fernet. This module handles decryption at runtime using an embedded key.

The key is generated during the build process (scripts/build/compile.py) and
stored as a Python bytecode file that gets compiled into the binary.

This module is only used in the compiled binary. For development, the plaintext
builtin_metadata.json is used directly.
"""

from __future__ import annotations

import base64
import hashlib
import os
import sys
from pathlib import Path
from typing import Any

_PROVIDERS_DIR = Path(__file__).parent
_METADATA_ENC = _PROVIDERS_DIR / "builtin_metadata.json.enc"
_METADATA_SHA = _PROVIDERS_DIR / "builtin_metadata.json.sha256"
_METADATA_PLAIN = _PROVIDERS_DIR / "builtin_metadata.json"

_fernet_key: bytes | None = None


def _get_fernet_key() -> bytes:
    global _fernet_key
    if _fernet_key is not None:
        return _fernet_key

    if getattr(sys, "_MEIPASS", None):
        _key_file = Path(sys._MEIPASS) / "pynescript" / "langserver" / "providers" / ".metadata.key"
    else:
        _key_file = _PROVIDERS_DIR / ".metadata.key"

    if _key_file.exists():
        _fernet_key = _key_file.read_bytes()
        return _fernet_key

    env_key = os.environ.get("PYNESCRIPT_METADATA_KEY", "")
    if env_key:
        _fernet_key = env_key.encode()
        return _fernet_key

    raise RuntimeError(
        "No metadata decryption key found. "
        "Set PYNESCRIPT_METADATA_KEY environment variable or ensure .metadata.key exists."
    )


def load_encrypted_metadata() -> dict[str, Any]:
    """Load and decrypt the encrypted builtin metadata."""
    from cryptography.fernet import Fernet

    key = _get_fernet_key()
    fernet = Fernet(key)

    if not _METADATA_ENC.exists():
        raise FileNotFoundError(
            f"Encrypted metadata not found at {_METADATA_ENC}. "
            "Make sure to run the build script before running the compiled binary."
        )

    encrypted = _METADATA_ENC.read_bytes()

    expected_sha = _METADATA_SHA.read_text().strip() if _METADATA_SHA.exists() else None
    plaintext = fernet.decrypt(encrypted)

    if expected_sha:
        actual_sha = hashlib.sha256(plaintext).hexdigest()[:16]
        if actual_sha != expected_sha:
            raise ValueError("Metadata integrity check failed (SHA256 mismatch)")

    import json

    return json.loads(plaintext.decode("utf-8"))


def get_metadata_cached() -> dict[str, Any]:
    """Load metadata, using plaintext if available, encrypted if not."""
    if _METADATA_PLAIN.exists():
        import json

        return json.loads(_METADATA_PLAIN.read_text(encoding="utf-8"))

    if _METADATA_ENC.exists():
        return load_encrypted_metadata()

    raise FileNotFoundError(
        f"No metadata found at {_METADATA_PLAIN} or {_METADATA_ENC}. Run: python scripts/build/compile.py"
    )
