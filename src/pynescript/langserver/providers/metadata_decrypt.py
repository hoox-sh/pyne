# Copyright (C) 2024-2026 jango_blockchained
#
# This file is part of pynescript.
#
# pynescript is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pynescript is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Fernet decryption of ``builtin_metadata.json.enc`` (Nuitka / packaged LSP).

**When used:** :func:`pynescript.langserver.providers.builtin_metadata.get_metadata`
falls back here only when plaintext JSON is missing or unreadable. Day-to-day
dev keeps ``builtin_metadata.json`` next to this package and never decrypts.

**Key resolution** (``_get_fernet_key``):

1. Cached key from a previous successful resolve
2. ``.metadata.key`` beside this package, or under ``sys._MEIPASS`` when frozen
3. ``PYNESCRIPT_METADATA_KEY`` environment variable (Fernet key material)

Build-time encryption and key generation live in ``scripts/build/compile.py``
(also honors ``CRYPTO_KEY`` / ``METADATA_KEY`` when writing the key). Never
commit ``.metadata.key``.

**Integrity:** if ``builtin_metadata.json.sha256`` exists, decrypted plaintext
must match the 16-char SHA-256 prefix or load raises.

Public API:

- :func:`load_encrypted_metadata` — decrypt ``.enc`` → dict (raises on missing key/blob)
- :func:`get_metadata_cached` — plaintext first, else encrypted (raises if neither)
"""

from __future__ import annotations

import hashlib
import os
import sys

from pathlib import Path
from typing import Any, cast


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
        _key_file = Path(getattr(sys, "_MEIPASS")) / "pynescript" / "langserver" / "providers" / ".metadata.key"
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
    """Decrypt ``builtin_metadata.json.enc`` and return the JSON object.

    Validates optional ``builtin_metadata.json.sha256`` (16-char prefix).

    Raises:
        FileNotFoundError: Encrypted blob missing.
        RuntimeError: No decryption key available.
        ValueError: Integrity check failed.
    """
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

    return cast(dict[str, Any], json.loads(plaintext.decode("utf-8")))


def get_metadata_cached() -> dict[str, Any]:
    """Load metadata preferring plaintext JSON, else decrypt the ``.enc`` blob.

    Same plaintext-first contract as :func:`~pynescript.langserver.providers.builtin_metadata.get_metadata`,
    but raises if neither artifact is available (unlike ``get_metadata``, which
    returns ``{}``).
    """
    if _METADATA_PLAIN.exists():
        import json

        return cast(dict[str, Any], json.loads(_METADATA_PLAIN.read_text(encoding="utf-8")))

    if _METADATA_ENC.exists():
        return load_encrypted_metadata()

    raise FileNotFoundError(
        f"No metadata found at {_METADATA_PLAIN} or {_METADATA_ENC}. Run: python scripts/build/compile.py"
    )
