# Copyright (C) 2025 jango-blockchained
#
# This file is part of pynescript.
#
# pynescript is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pynescript is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: LGPL-3.0-or-later

"""Pynescript Pro API Server.

Flask server for live chart previews, backtests, and API key management.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from flask import Flask
from flask import g
from flask import jsonify
from flask import request
from flask_cors import CORS

from backend.api.preview import backtest_bp
from backend.api.preview import preview_bp
from backend.middleware.auth import get_key_store
from backend.middleware.auth import require_admin_token
from backend.middleware.auth import require_api_key
from backend.middleware.schemas import CREATE_KEY_SCHEMA
from backend.middleware.schemas import RUN_SCHEMA
from backend.middleware.schemas import VALIDATE_KEY_SCHEMA
from backend.middleware.schemas import validate
from backend.runtime import Runtime

try:
    from flask_sock import Sock

    _SOCK_AVAILABLE = True
except ImportError:  # optional dep until pip install flask-sock
    Sock = None  # type: ignore[misc, assignment]
    _SOCK_AVAILABLE = False


app = Flask(__name__)
# Reject request bodies larger than 5MB to prevent memory-exhaustion DoS.
# Without this, an attacker can POST multi-GB JSON and OOM the worker before
# gunicorn's --timeout fires. See audit 2026-07-05, finding S1.
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB
# Audit 2026-07-05 / S7+S8: restrict CORS instead of the default `*`. Origins
# and headers are read from env vars so a deployment can override without code
# changes. The same-origin case (no Origin header, e.g. server-to-server or
# curl) is always allowed.
# flask-cors supports regex origins; use a pattern that covers any localhost port.
LOCALHOST_RE = r"^https?://(?:localhost|127\.0\.0\.1)(?::\d+)?$"
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("ALLOWED_ORIGINS", "https://pynescript.ai,https://app.pynescript.ai," + LOCALHOST_RE).split(
        ","
    )
    if o.strip()
]
CORS(
    app,
    origins=ALLOWED_ORIGINS,
    methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization", "X-Admin-Token"],
    supports_credentials=False,
)

sock = Sock(app) if _SOCK_AVAILABLE and Sock is not None else None


def execute_run_payload(data: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Shared run logic for POST /run and WS /ws/run.

    Returns (body_dict, http_status). Body always includes ``status``.
    """
    validated, err = validate(data or {}, RUN_SCHEMA)
    if err is not None:
        # validate() returns (flask.Response, status_code) on error
        resp, code = err
        try:
            payload = resp.get_json(silent=True) or {
                "status": "error",
                "code": "VALIDATION_ERROR",
                "message": "Invalid request body",
            }
        except Exception:  # noqa: BLE001
            payload = {
                "status": "error",
                "code": "VALIDATION_ERROR",
                "message": "Invalid request body",
            }
        return payload, int(code or 400)

    assert validated is not None
    script = validated["script"]
    ohlcv = validated["data"]
    symbol = validated.get("symbol") or "CHART"
    data_source = validated.get("data_source") or None
    data_options = validated.get("data_options") or {}
    mode = validated.get("mode") or "interpret"
    if isinstance(data_source, str) and not data_source.strip():
        data_source = None

    if not script:
        return {
            "status": "error",
            "code": "NO_SCRIPT",
            "message": "No 'script' provided.",
        }, 400

    if not ohlcv:
        return {
            "status": "error",
            "code": "NO_DATA",
            "message": "No 'data' provided.",
        }, 400

    data_feed = None
    data_provider = None
    try:
        from pynescript.util.data import resolve_request_sources

        data_feed, data_provider = resolve_request_sources(
            chart_bars=ohlcv,
            symbol=str(symbol),
            data_source=data_source,
            source_options=data_options if isinstance(data_options, dict) else {},
        )
    except Exception as e:  # noqa: BLE001 — surface config errors cleanly
        return {
            "status": "error",
            "code": "DATA_SOURCE_ERROR",
            "message": f"Failed to configure data source: {e}",
        }, 400

    runtime = Runtime(symbol=str(symbol))
    result = runtime.run(
        script,
        ohlcv,
        data_feed=data_feed,
        data_provider=data_provider,
        mode=str(mode),
    )

    if "error" in result:
        return {
            "status": "error",
            "code": "EXECUTION_ERROR",
            "message": result["error"],
        }, 500

    return {
        "status": "success",
        "plots": result.get("plots", []),
        "series": result.get("series", {}),
        "plot_meta": result.get("plot_meta", {}),
        "events": result.get("events", []),
        "drawings": result.get("drawings", []),
        "script_id": result.get("script_id", ""),
        "run_id": result.get("run_id", ""),
        "count": result.get("count", 0),
        "mode": result.get("mode", mode),
        "data_source": data_source or "chart",
    }, 200


@app.route("/", methods=["GET"])
def health_check():
    endpoints = {
        "GET /": "This health check",
        "POST /run": "Run Pine Script (free)",
        "POST /run/batch": "Run multiple Pine scripts on shared OHLCV (free)",
        "POST /preview/chart": "Chart thumbnail (Pro)",
        "POST /preview/indicator": "Indicator preview (Pro)",
        "POST /backtest/quick": "Quick backtest (Pro)",
        "POST /auth/create_key": "Create API key (requires admin)",
        "GET /auth/usage": "Get usage stats (Pro)",
    }
    if sock is not None:
        endpoints["WS /ws/run"] = "Run Pine Script over WebSocket (prefer WSS when available)"
    return jsonify(
        {
            "status": "healthy",
            "service": "pynescript-pro-api",
            "version": "1.0.0",
            "timestamp": int(time.time()),
            "websocket": sock is not None,
            "endpoints": endpoints,
        }
    )


@app.route("/run", methods=["POST"])
def run_pine_script():
    """Execute Pine Script with provided data. Free tier endpoint."""
    body, status = execute_run_payload(request.get_json(silent=True) or {})
    return jsonify(body), status


if sock is not None:

    @sock.route("/ws/run")
    def ws_run(ws):  # type: ignore[no-untyped-def]
        """WebSocket run channel for AXIS (WSS-first when TLS terminates).

        Protocol (JSON text frames)::

            → { "type": "ping" }
            ← { "type": "pong" }

            → { "type": "run", "id": "…", "script": "…", "data": [bars…], "mode"?: "interpret" }
            ← { "type": "result", "id": "…", ...run payload fields... }
            ← { "type": "error", "id": "…", "message": "…", "code"?: "…" }
        """
        while True:
            raw = ws.receive()
            if raw is None:
                break
            try:
                msg = json.loads(raw) if isinstance(raw, str) else json.loads(raw.decode("utf-8"))
            except Exception:  # noqa: BLE001
                ws.send(
                    json.dumps(
                        {
                            "type": "error",
                            "message": "Invalid JSON frame",
                            "code": "BAD_JSON",
                        }
                    )
                )
                continue

            if not isinstance(msg, dict):
                ws.send(
                    json.dumps(
                        {
                            "type": "error",
                            "message": "Frame must be a JSON object",
                            "code": "BAD_FRAME",
                        }
                    )
                )
                continue

            mtype = str(msg.get("type") or "run")
            req_id = msg.get("id")

            if mtype == "ping":
                ws.send(json.dumps({"type": "pong", "id": req_id}))
                continue

            if mtype != "run":
                ws.send(
                    json.dumps(
                        {
                            "type": "error",
                            "id": req_id,
                            "message": f"Unknown type: {mtype}",
                            "code": "UNKNOWN_TYPE",
                        }
                    )
                )
                continue

            # Map WS envelope → REST body shape
            payload = {
                "script": msg.get("script"),
                "data": msg.get("data"),
                "symbol": msg.get("symbol"),
                "mode": msg.get("mode"),
                "data_source": msg.get("data_source"),
                "data_options": msg.get("data_options"),
            }
            body, _status = execute_run_payload(payload)
            if body.get("status") == "error":
                ws.send(
                    json.dumps(
                        {
                            "type": "error",
                            "id": req_id,
                            "message": body.get("message") or "Run failed",
                            "code": body.get("code"),
                            "status": "error",
                        }
                    )
                )
            else:
                out = dict(body)
                out["type"] = "result"
                out["id"] = req_id
                ws.send(json.dumps(out))


@app.route("/run/batch", methods=["POST"])
def run_pine_script_batch():
    """Run multiple Pine scripts on the same OHLCV bars (AXIS multi-indicator).

    Body::
        {
          "scripts": [ {"id": "rsi", "script": "..."}, ... ],  # max 8
          "data": [ {time, open, high, low, close, volume}, ... ],
          "symbol"?, "mode"?, "data_source"?, "data_options"?
        }

    Returns one result object per script (success or per-script error); HTTP 200
    unless the request envelope is invalid.
    """
    from backend.middleware.schemas import RUN_BATCH_MAX_SCRIPTS, RUN_BATCH_SCHEMA

    data, err = validate(request.get_json(silent=True) or {}, RUN_BATCH_SCHEMA)
    if err is not None:
        return err

    scripts = data["scripts"]
    ohlcv = data["data"]
    symbol = data.get("symbol") or "CHART"
    data_source = data.get("data_source") or None
    data_options = data.get("data_options") or {}
    mode = data.get("mode") or "interpret"
    if isinstance(data_source, str) and not data_source.strip():
        data_source = None

    if not isinstance(scripts, list) or not scripts:
        return jsonify(
            {
                "status": "error",
                "code": "NO_SCRIPTS",
                "message": "Provide a non-empty 'scripts' array.",
            }
        ), 400
    if len(scripts) > RUN_BATCH_MAX_SCRIPTS:
        return jsonify(
            {
                "status": "error",
                "code": "TOO_MANY_SCRIPTS",
                "message": f"At most {RUN_BATCH_MAX_SCRIPTS} scripts per batch.",
            }
        ), 400
    if not ohlcv:
        return jsonify(
            {
                "status": "error",
                "code": "NO_DATA",
                "message": "No 'data' provided.",
            }
        ), 400

    # Normalize script entries
    jobs: list[tuple[str, str]] = []
    for i, item in enumerate(scripts):
        if isinstance(item, str):
            jobs.append((f"script_{i}", item))
            continue
        if not isinstance(item, dict):
            return jsonify(
                {
                    "status": "error",
                    "code": "INVALID_SCRIPT",
                    "message": f"scripts[{i}] must be a string or object with 'script'.",
                }
            ), 400
        src = item.get("script")
        if not isinstance(src, str) or not src.strip():
            return jsonify(
                {
                    "status": "error",
                    "code": "INVALID_SCRIPT",
                    "message": f"scripts[{i}].script must be a non-empty string.",
                }
            ), 400
        sid = item.get("id")
        if not isinstance(sid, str) or not sid.strip():
            sid = f"script_{i}"
        jobs.append((sid, src))

    data_feed = None
    data_provider = None
    try:
        from pynescript.util.data import resolve_request_sources

        data_feed, data_provider = resolve_request_sources(
            chart_bars=ohlcv,
            symbol=str(symbol),
            data_source=data_source,
            source_options=data_options if isinstance(data_options, dict) else {},
        )
    except Exception as e:  # noqa: BLE001
        return jsonify(
            {
                "status": "error",
                "code": "DATA_SOURCE_ERROR",
                "message": f"Failed to configure data source: {e}",
            }
        ), 400

    results = []
    for sid, script in jobs:
        runtime = Runtime(symbol=str(symbol))
        try:
            result = runtime.run(
                script,
                ohlcv,
                data_feed=data_feed,
                data_provider=data_provider,
                mode=str(mode),
            )
        except Exception as e:  # noqa: BLE001 — per-script isolation
            results.append(
                {
                    "id": sid,
                    "status": "error",
                    "code": "EXECUTION_ERROR",
                    "message": str(e),
                }
            )
            continue
        if "error" in result:
            results.append(
                {
                    "id": sid,
                    "status": "error",
                    "code": "EXECUTION_ERROR",
                    "message": result["error"],
                }
            )
            continue
        results.append(
            {
                "id": sid,
                "status": "success",
                "plots": result.get("plots", []),
                "series": result.get("series", {}),
                "plot_meta": result.get("plot_meta", {}),
                "events": result.get("events", []),
                "drawings": result.get("drawings", []),
                "script_id": result.get("script_id", ""),
                "run_id": result.get("run_id", ""),
                "count": result.get("count", 0),
                "mode": result.get("mode", mode),
            }
        )

    ok = sum(1 for r in results if r.get("status") == "success")
    return jsonify(
        {
            "status": "success" if ok == len(results) else "partial",
            "results": results,
            "count": len(results),
            "ok": ok,
            "data_source": data_source or "chart",
        }
    )


@app.route("/auth/create_key", methods=["POST"])
@require_admin_token
def create_api_key():
    """Create a new API key. Requires the ``X-Admin-Token`` header.

    The admin token is configured via the ``ADMIN_TOKEN`` environment
    variable. If unset, the endpoint returns 403 (the env is treated as
    "no admin access at all", not "open access"). Audit 2026-07-05 / S3.
    """
    data, err = validate(request.get_json(silent=True) or {}, CREATE_KEY_SCHEMA)
    if err is not None:
        return err
    tier = data["tier"]
    valid_tiers = ["free", "hobby", "pro", "team", "enterprise"]

    if tier not in valid_tiers:
        return jsonify(
            {
                "status": "error",
                "code": "INVALID_TIER",
                "message": f"Invalid tier. Must be one of: {valid_tiers}",
            }
        ), 400

    store = get_key_store()
    raw_key, key_id = store.create_key(tier=tier)

    return jsonify(
        {
            "status": "success",
            "api_key": raw_key,
            "key_id": key_id,
            "tier": tier,
            "message": "Store this API key securely. It will not be shown again.",
        }
    )


@app.route("/auth/usage", methods=["GET"])
@require_api_key
def get_usage():
    """Get current usage stats for the authenticated API key."""
    api_key = g.api_key
    return jsonify(
        {
            "status": "success",
            "key_id": api_key.key_id,
            "tier": api_key.tier,
            "usage": {
                "calls_used": api_key.calls_used,
                "calls_limit": api_key.calls_limit,
                "calls_remaining": api_key.calls_remaining(),
                "last_used": api_key.last_used,
                "created_at": api_key.created_at,
            },
        }
    )


@app.route("/auth/validate", methods=["POST"])
def validate_api_key():
    """Validate an API key without consuming a call."""
    data, err = validate(request.get_json(silent=True) or {}, VALIDATE_KEY_SCHEMA)
    if err is not None:
        return err
    raw_key = data["api_key"]

    store = get_key_store()
    api_key = store.validate_key(raw_key)

    if api_key is None:
        return jsonify(
            {
                "status": "error",
                "code": "INVALID_KEY",
                "message": "Invalid API key.",
            }
        ), 401

    return jsonify(
        {
            "status": "success",
            "key_id": api_key.key_id,
            "tier": api_key.tier,
            "active": api_key.is_active(),
            "rate_limited": api_key.is_rate_limited(),
            "tier_info": api_key.get_tier_info(),
        }
    )


app.register_blueprint(preview_bp)
app.register_blueprint(backtest_bp)


@app.errorhandler(404)
def not_found(e):
    return jsonify(
        {
            "status": "error",
            "code": "NOT_FOUND",
            "message": f"Endpoint {request.path} not found.",
        }
    ), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify(
        {
            "status": "error",
            "code": "INTERNAL_ERROR",
            "message": "Internal server error.",
        }
    ), 500


if __name__ == "__main__":
    # Audit 2026-07-05 / S11: default to localhost for the dev runner. Use
    # HOST=0.0.0.0 to expose the dev server to other machines if needed.
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5002"))
    app.run(host=host, port=port, debug=False)
