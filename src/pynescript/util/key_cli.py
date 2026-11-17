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

"""Click group ``pyne key`` — mint API keys against the configured key store.

The mint path is shared with ``POST /auth/create_key``: both call
``APIKeyStore.create_key`` from :mod:`backend.middleware.auth`, so key format,
hashing, and tier limits have exactly one implementation.

``backend`` is imported lazily. The published wheel ships only
``src/pynescript``, so a top-level import would break ``pyne info`` for pip
users; without the Pro backend the command exits with a clear message instead
of a traceback.
"""

from __future__ import annotations

import json
import os

from typing import Any

import click


# Keep in lockstep with the valid tiers in ``backend/app.py`` (CREATE_KEY_SCHEMA).
_TIERS: tuple[str, ...] = ("free", "hobby", "pro", "team", "enterprise")

_MINT_WARNING = "Store this API key securely. It will not be shown again."

_BACKEND_HINT = (
    "Key minting needs the Pro backend (backend.middleware.auth), which ships "
    "with the pyne source checkout, not the wheel. Run this command from a "
    "repo checkout with the [pro] extra installed: pip install 'hoox-pyne[pro]'."
)


def _echo_json(payload: dict[str, Any]) -> None:
    """Emit machine output with plain ``click.echo`` (Rich would wrap it)."""
    click.echo(json.dumps(payload, indent=2))


def _status(kind: str, msg: str) -> None:
    """Human output through the shared CLI status helper.

    Imported lazily: ``pynescript.__main__`` imports this module to register
    the group, so a module-level import would be circular.
    """
    from pynescript.__main__ import _echo_status

    _echo_status(kind, msg)


def _require_admin_token() -> None:
    """Fail closed when ``ADMIN_TOKEN`` is unset or blank.

    Mirrors :func:`backend.middleware.auth.require_admin_token`: the HTTP route
    treats an unset token as "admin access disabled", not "open access", and
    this command must not be a softer door to the same capability. There is no
    server here to compare the token against, so this is a presence gate.
    """
    if not (os.environ.get("ADMIN_TOKEN") or "").strip():
        msg = (
            "ADMIN_TOKEN is not set. Key minting is disabled without it "
            "(POST /auth/create_key fails closed the same way). "
            "Export ADMIN_TOKEN and retry."
        )
        raise click.ClickException(msg)


def _load_store() -> Any:
    """Return the configured key store, or fail with an actionable message."""
    try:
        from backend.middleware.auth import get_key_store
    except ImportError as exc:
        raise click.ClickException(_BACKEND_HINT) from exc
    return get_key_store()


@click.group("key", short_help="Mint Pro API keys against the configured key store.")
def key_group() -> None:
    """Manage API keys in the store selected by ``STORE_BACKEND``.

    Minting reuses the same store and the same generator as
    ``POST /auth/create_key``; ``STORE_BACKEND`` picks the backend
    (``json`` | ``sqlite`` | ``redis``).

    ``ADMIN_TOKEN`` must be set and non-empty. The HTTP endpoint treats an
    unset token as "admin access disabled", and this command does the same.

    \b
    Examples:
      export ADMIN_TOKEN=...
      pyne key create
      pyne key create --tier pro
      pyne key create --tier hobby --json
    """


@key_group.command("create", short_help="Mint one API key and print it once.")
@click.option(
    "--tier",
    type=click.Choice(_TIERS, case_sensitive=False),
    default="hobby",
    show_default=True,
    help="Usage tier recorded with the key.",
)
@click.option("--json", "as_json", is_flag=True, help="Machine-readable output.")
def create_cmd(tier: str, as_json: bool) -> None:
    """Create an API key and print the raw secret exactly once.

    The ``sqlite`` / ``redis`` backends store only a PBKDF2 hash of the secret;
    the raw key cannot be recovered later, so store it now.

    \b
    Examples:
      pyne key create --tier pro
      pyne key create --json
    """
    _require_admin_token()
    store = _load_store()
    raw_key, key_id = store.create_key(tier=tier)

    if as_json:
        _echo_json(
            {
                "status": "success",
                "api_key": raw_key,
                "key_id": key_id,
                "tier": tier,
            }
        )
        return

    _status("ok", f"API key created (tier: {tier}, key_id: {key_id})")
    click.echo()
    click.echo(f"  {raw_key}")
    click.echo()
    _status("warn", _MINT_WARNING)
