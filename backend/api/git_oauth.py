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

"""GitHub / GitLab device OAuth proxy for AXIS (VPS / Flask Pro API).

Browser SPAs cannot call ``github.com/login/*`` or ``gitlab.com/oauth/*``
(no CORS). The AXIS Cloudflare Worker already exposes:

* ``POST /api/git/oauth/device/start``
* ``POST /api/git/oauth/device/poll``

This blueprint mirrors those routes on the Pro API so AXIS Connect works when
``store.endpoint`` points at Flask (``:5002``) instead of the Worker.

Env (optional — body may supply ``clientId`` for self-hosted OAuth apps):

* ``GITHUB_OAUTH_CLIENT_ID``
* ``GITLAB_OAUTH_CLIENT_ID``
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from flask import Blueprint
from flask import jsonify
from flask import request

logger = logging.getLogger(__name__)

bp = Blueprint("git_oauth", __name__)

GITHUB_SCOPE = "repo read:user"
GITLAB_SCOPE = "api"


def _form_body(params: dict[str, str]) -> bytes:
    return urllib.parse.urlencode(params).encode("utf-8")


def _post_form(url: str, params: dict[str, str]) -> tuple[int, dict[str, Any]]:
    req = urllib.request.Request(
        url,
        data=_form_body(params),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "pynescript-pro-api/git-oauth",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            status = int(getattr(resp, "status", 200) or 200)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        status = int(e.code)
    except urllib.error.URLError as e:
        raise RuntimeError(f"Upstream OAuth unreachable: {e}") from e

    try:
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        data = {"error": "invalid_json", "error_description": raw[:200]}
    if not isinstance(data, dict):
        data = {"error": "invalid_json", "error_description": "expected object"}
    return status, data


def _resolve_client_id(provider: str, body: dict[str, Any]) -> str:
    from_body = str(body.get("clientId") or body.get("client_id") or "").strip()
    if from_body:
        return from_body
    if provider == "github":
        return str(os.environ.get("GITHUB_OAUTH_CLIENT_ID") or "").strip()
    return str(os.environ.get("GITLAB_OAUTH_CLIENT_ID") or "").strip()


def _start_device(provider: str, client_id: str, scope: str) -> dict[str, Any]:
    if provider == "github":
        status, data = _post_form(
            "https://github.com/login/device/code",
            {"client_id": client_id, "scope": scope},
        )
        if status >= 400 or data.get("error"):
            msg = str(data.get("error_description") or data.get("error") or f"HTTP {status}")
            raise RuntimeError(f"GitHub device start failed: {msg}")
        return {
            "provider": "github",
            "device_code": data.get("device_code"),
            "user_code": data.get("user_code"),
            "verification_uri": data.get("verification_uri") or "https://github.com/login/device",
            "verification_uri_complete": data.get("verification_uri_complete"),
            "expires_in": data.get("expires_in") or 900,
            "interval": data.get("interval") or 5,
        }

    status, data = _post_form(
        "https://gitlab.com/oauth/authorize_device",
        {"client_id": client_id, "scope": scope},
    )
    if status >= 400 or data.get("error"):
        msg = str(data.get("error_description") or data.get("error") or f"HTTP {status}")
        raise RuntimeError(f"GitLab device start failed: {msg}")
    return {
        "provider": "gitlab",
        "device_code": data.get("device_code"),
        "user_code": data.get("user_code"),
        "verification_uri": data.get("verification_uri") or "https://gitlab.com/-/profile/device",
        "verification_uri_complete": data.get("verification_uri_complete"),
        "expires_in": data.get("expires_in") or 300,
        "interval": data.get("interval") or 5,
    }


def _poll_device(provider: str, client_id: str, device_code: str) -> dict[str, Any]:
    grant = "urn:ietf:params:oauth:grant-type:device_code"
    if provider == "github":
        _status, data = _post_form(
            "https://github.com/login/oauth/access_token",
            {
                "client_id": client_id,
                "device_code": device_code,
                "grant_type": grant,
            },
        )
        if data.get("error"):
            return {
                "status": "pending",
                "error": str(data.get("error")),
                "error_description": (str(data["error_description"]) if data.get("error_description") else None),
                "interval": data.get("interval"),
            }
        if not data.get("access_token"):
            raise RuntimeError("GitHub token poll failed: no access_token")
        return {
            "status": "success",
            "access_token": data.get("access_token"),
            "token_type": data.get("token_type") or "bearer",
            "scope": data.get("scope"),
            "provider": "github",
        }

    status, data = _post_form(
        "https://gitlab.com/oauth/token",
        {
            "client_id": client_id,
            "device_code": device_code,
            "grant_type": grant,
        },
    )
    if data.get("error"):
        return {
            "status": "pending",
            "error": str(data.get("error")),
            "error_description": (str(data["error_description"]) if data.get("error_description") else None),
        }
    if status >= 400 or not data.get("access_token"):
        raise RuntimeError(f"GitLab token poll failed: {data.get('error_description') or data.get('error') or status}")
    return {
        "status": "success",
        "access_token": data.get("access_token"),
        "token_type": data.get("token_type") or "bearer",
        "scope": data.get("scope"),
        "refresh_token": data.get("refresh_token"),
        "provider": "gitlab",
    }


def _body() -> dict[str, Any]:
    raw = request.get_json(silent=True)
    return raw if isinstance(raw, dict) else {}


@bp.route("/api/git/oauth/device/start", methods=["POST"])
def device_start():
    """Begin GitHub/GitLab device authorization (AXIS Connect)."""
    body = _body()
    provider_raw = str(body.get("provider") or "github").lower()
    provider = "gitlab" if provider_raw == "gitlab" else "github"
    client_id = _resolve_client_id(provider, body)
    if not client_id:
        msg = (
            "GitHub OAuth client id missing. Set env GITHUB_OAUTH_CLIENT_ID or pass clientId "
            "(public OAuth App id with Device Flow enabled)."
            if provider == "github"
            else "GitLab OAuth application id missing. Set env GITLAB_OAUTH_CLIENT_ID or pass clientId."
        )
        return jsonify({"status": "error", "code": "NO_CLIENT_ID", "message": msg}), 400

    scope = str(body.get("scope") or "").strip() or (GITLAB_SCOPE if provider == "gitlab" else GITHUB_SCOPE)
    try:
        started = _start_device(provider, client_id, scope)
        return jsonify({"status": "success", **started}), 200
    except Exception as e:  # noqa: BLE001 — surface upstream OAuth errors cleanly
        logger.warning("oauth start: %s", e)
        return (
            jsonify(
                {
                    "status": "error",
                    "code": "OAUTH_UPSTREAM",
                    "message": "OAuth start failed",
                }
            ),
            502,
        )


@bp.route("/api/git/oauth/device/poll", methods=["POST"])
def device_poll():
    """Poll device authorization until approved / denied / expired."""
    body = _body()
    provider_raw = str(body.get("provider") or "github").lower()
    provider = "gitlab" if provider_raw == "gitlab" else "github"
    client_id = _resolve_client_id(provider, body)
    if not client_id:
        msg = (
            "GitHub OAuth client id missing. Set env GITHUB_OAUTH_CLIENT_ID or pass clientId."
            if provider == "github"
            else "GitLab OAuth application id missing. Set env GITLAB_OAUTH_CLIENT_ID or pass clientId."
        )
        return jsonify({"status": "error", "code": "NO_CLIENT_ID", "message": msg}), 400

    device_code = str(body.get("device_code") or body.get("deviceCode") or "").strip()
    if not device_code:
        return (
            jsonify(
                {
                    "status": "error",
                    "code": "BAD_REQUEST",
                    "message": "device_code required",
                }
            ),
            400,
        )

    try:
        polled = _poll_device(provider, client_id, device_code)
        return jsonify(polled), 200
    except Exception as e:  # noqa: BLE001
        logger.warning("oauth poll: %s", e)
        return (
            jsonify(
                {
                    "status": "error",
                    "code": "OAUTH_UPSTREAM",
                    "message": "OAuth poll failed",
                }
            ),
            502,
        )
