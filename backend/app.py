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

"""Pynescript Pro API Server.

Flask application entry for live chart previews, Pine ``/run`` execution,
compile prewarm, free LSP-HTTP/git OAuth bridges, and API key management.

Start with ``python -m backend.app`` (dev) or gunicorn in production.
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

from backend.api.git_oauth import bp as git_oauth_bp
from backend.api.lsp_http import bp as lsp_bp
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
#
# IMPORTANT: env ALLOWED_ORIGINS=* must be the string "*", not the list ["*"].
# A list containing the single string "*" only matches Origin: * literally and
# breaks AXIS on VPS/local cross-port setups (completion/hover/run preflight).
LOCALHOST_RE = r"^https?://(?:localhost|127\.0\.0\.1)(?::\d+)?$"
# Private LAN / demo VPS HTTP origins (any port) — safe enough for Pro API demos
PRIVATE_HTTP_RE = (
    r"^https?://(?:"
    r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"192\.168\.\d{1,3}\.\d{1,3}|"
    r"172\.(?:1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}|"
    r"162\.254\.38\.194"  # AXIS/pyne public demo host
    r")(?::\d+)?$"
)


def _parse_allowed_origins() -> list[str] | str:
    raw = os.environ.get(
        "ALLOWED_ORIGINS",
        "https://pynescript.ai,https://app.pynescript.ai," + LOCALHOST_RE,
    ).strip()
    if raw == "*" or raw.lower() == "any":
        return "*"
    parts = [o.strip() for o in raw.split(",") if o.strip()]
    # Always keep local-dev regex even when an explicit list is provided
    if LOCALHOST_RE not in parts:
        parts.append(LOCALHOST_RE)
    if PRIVATE_HTTP_RE not in parts and raw != "*":
        parts.append(PRIVATE_HTTP_RE)
    return parts


ALLOWED_ORIGINS = _parse_allowed_origins()
# Free browser surface used by AXIS (VPS UI → local pyne is a first-class setup).
# Always reflect Origin on these paths so OPTIONS preflight never fails CORS.
_FREE_CORS_PATH_PREFIXES = (
    "/",
    "/run",
    "/compile",
    "/lsp/",
    "/ws/",
)

# Once-per-worker host prewarm (builtins + disk cache dir). Soft-fail without Numba.
_HOST_COMPILE_PREWARMED = False


def _path_is_free_cors(path: str) -> bool:
    if path == "/" or path == "":
        return True
    for p in _FREE_CORS_PATH_PREFIXES:
        if p != "/" and path.startswith(p.rstrip("/") if p.endswith("/") else p):
            # /run, /run/batch, /lsp/*, /ws/*
            if p.endswith("/"):
                return path.startswith(p) or path == p.rstrip("/")
            return path == p or path.startswith(p + "/")
    return False


def _origin_allowed(origin: str) -> bool:
    if not origin:
        return False
    allowed = ALLOWED_ORIGINS
    if allowed == "*":
        return True
    if not isinstance(allowed, list):
        return False
    import re

    for pat in allowed:
        if pat == "*" or pat == origin:
            return True
        try:
            if re.match(pat + ("" if pat.endswith("$") else "$"), origin) or re.match(
                pat, origin
            ):
                return True
        except re.error:
            continue
    return False


def _apply_cors_headers(resp, origin: str | None = None):  # type: ignore[no-untyped-def]
    origin = origin or request.headers.get("Origin")
    if not origin:
        return resp
    path = request.path or "/"
    # Free AXIS endpoints: always allow any browser Origin (local compile from VPS UI)
    if _path_is_free_cors(path) or _origin_allowed(origin):
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Vary"] = "Origin"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, HEAD"
        resp.headers["Access-Control-Allow-Headers"] = (
            "Content-Type, Authorization, X-Admin-Token, Accept"
        )
        resp.headers["Access-Control-Max-Age"] = "86400"
    return resp


CORS(
    app,
    origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS != "*" else "*",
    methods=["GET", "POST", "OPTIONS", "HEAD"],
    allow_headers=["Content-Type", "Authorization", "X-Admin-Token", "Accept"],
    expose_headers=["Content-Type"],
    supports_credentials=False,
    max_age=86400,
)


@app.before_request
def _cors_preflight():  # type: ignore[no-untyped-def]
    """Answer OPTIONS early with full CORS headers (browser preflight)."""
    if request.method != "OPTIONS":
        return None
    from flask import make_response

    resp = make_response("", 204)
    return _apply_cors_headers(resp)


@app.after_request
def _ensure_cors_headers(resp):  # type: ignore[no-untyped-def]
    """Echo ACAO on every response for free paths / allowlisted Origins."""
    return _apply_cors_headers(resp)


sock = Sock(app) if _SOCK_AVAILABLE and Sock is not None else None
if sock is None:
    import logging as _logging

    _logging.getLogger(__name__).warning(
        "flask-sock not installed — WS /ws/run disabled (AXIS falls back to POST /run). "
        "Install: pip install 'pyne[pro]'  or  pip install flask-sock simple-websocket"
    )


def _maybe_host_compile_prewarm(*, force: bool = False) -> dict[str, Any] | None:
    """Pay Numba builtin cold cost once per worker when deploy prewarm is on.

    Controlled by ``PYNE_COMPILE_PREWARM`` (default **on**). Skipped when the
    flag is off or when Flask ``TESTING`` is set (unit tests use explicit
    ``POST /compile/prewarm``). Never raises — correctness of later runs is
    independent of prewarm success. Returns prewarm result dict when work ran,
    else ``None``.
    """
    global _HOST_COMPILE_PREWARMED
    if not force and _HOST_COMPILE_PREWARMED:
        return None
    # Avoid multi-second Numba cold cost on every backend pytest suite.
    if not force and app.config.get("TESTING"):
        return None
    try:
        from pynescript.compiler.engine import prewarm_enabled
        from pynescript.compiler.engine import prewarm_scripts

        if not force and not prewarm_enabled():
            _HOST_COMPILE_PREWARMED = True
            return None
        # Builtins only here; explicit POST /compile/prewarm may pass scripts.
        result = prewarm_scripts(None, force_builtins=force)
        _HOST_COMPILE_PREWARMED = True
        return result
    except Exception as exc:  # noqa: BLE001 — never block /run on prewarm
        import logging as _logging

        _logging.getLogger(__name__).debug("host compile prewarm failed: %s", exc, exc_info=True)
        _HOST_COMPILE_PREWARMED = True
        return {"error": str(exc), "has_numba": False}


def _err_to_dict(err: tuple) -> tuple[dict[str, Any], int]:
    """Normalize validate/free_limits errors to ``(body_dict, status)``.

    Accepts either a plain ``(dict, status)`` (free_limits) or a Flask
    ``(Response, status)`` pair from :func:`validate`.
    """
    resp, code = err
    if isinstance(resp, dict):
        return resp, int(code or 400)
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


def execute_run_payload(data: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Shared run logic for POST /run and WS /ws/run.

    Returns (body_dict, http_status). Body always includes ``status``.
    Default ``mode`` is ``auto`` (prefer warm compile; interpret on fallback).

    Free-tier abuse guards (audit 2026-08-10): bar/script caps, IP rate limit,
    concurrency gate, chart/mock-only data sources. See
    :mod:`backend.middleware.free_limits`.
    """
    from backend.middleware.free_limits import acquire_free_slot
    from backend.middleware.free_limits import check_free_rate_limit
    from backend.middleware.free_limits import release_free_slot
    from backend.middleware.free_limits import validate_free_run_bounds

    rate_err = check_free_rate_limit()
    if rate_err is not None:
        return _err_to_dict(rate_err)

    slot_err = acquire_free_slot()
    if slot_err is not None:
        return _err_to_dict(slot_err)

    try:
        return _execute_run_payload_inner(data, validate_free_run_bounds)
    finally:
        release_free_slot()


def _execute_run_payload_inner(
    data: dict[str, Any],
    validate_free_run_bounds: Any,
) -> tuple[dict[str, Any], int]:
    """Inner run body after free-tier rate/concurrency gates are held."""
    # Prefer warm path: once-per-worker builtin JIT before first auto/compile run.
    _maybe_host_compile_prewarm()

    validated, err = validate(data or {}, RUN_SCHEMA)
    if err is not None:
        return _err_to_dict(err)

    assert validated is not None
    script = validated["script"]
    ohlcv = validated["data"]
    symbol = validated.get("symbol") or "CHART"
    data_source = validated.get("data_source") or None
    data_options = validated.get("data_options") or {}
    # Prefer compile with interpret fallback for production throughput.
    mode = validated.get("mode") or "auto"
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

    bounds_err = validate_free_run_bounds(
        script=script if isinstance(script, str) else None,
        ohlcv=ohlcv if isinstance(ohlcv, list) else None,
        data_source=data_source if isinstance(data_source, str) else None,
    )
    if bounds_err is not None:
        return _err_to_dict(bounds_err)

    # Reject blocked webhook URLs early (SSRF) so clients get a clear 400.
    wh_raw = validated.get("webhook_url") or ""
    if isinstance(wh_raw, str) and wh_raw.strip():
        from .alert_forwarder import normalize_webhook_url

        if normalize_webhook_url(wh_raw) is None:
            return {
                "status": "error",
                "code": "WEBHOOK_URL_BLOCKED",
                "message": (
                    "webhook_url is invalid or blocked (private/loopback/"
                    "metadata hosts are not allowed). Use a public https URL "
                    "or set ALERT_WEBHOOK_ALLOW_PRIVATE=1 for private demos."
                ),
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

    inputs = validated.get("inputs") or {}
    if not isinstance(inputs, dict):
        inputs = {}
    profiler = bool(validated.get("profiler"))

    runtime = Runtime(symbol=str(symbol))
    result = runtime.run(
        script,
        ohlcv,
        data_feed=data_feed,
        data_provider=data_provider,
        mode=str(mode),
        inputs=inputs if inputs else None,
        profiler=profiler,
    )

    if "error" in result:
        err_body: dict[str, Any] = {
            "status": "error",
            "code": "EXECUTION_ERROR",
            "message": result["error"],
        }
        # Pass through Runtime classification when present (parse/compile/runtime/…).
        if result.get("error_kind"):
            err_body["error_kind"] = result["error_kind"]
        if result.get("error_type"):
            err_body["error_type"] = result["error_type"]
        if result.get("error_bar") is not None:
            err_body["error_bar"] = result["error_bar"]
        if "logs" in result:
            err_body["logs"] = result["logs"]
        if "profile" in result:
            err_body["profile"] = result["profile"]
        if isinstance(result.get("meta"), dict):
            err_body["meta"] = result["meta"]
        return err_body, 500

    resp: dict[str, Any] = {
        "status": "success",
        "plots": result.get("plots", []),
        "series": result.get("series", {}),
        "plot_meta": result.get("plot_meta", {}),
        "events": result.get("events", []),
        "drawings": result.get("drawings", []),
        "alerts": result.get("alerts", []),
        "inputs": result.get("inputs", []),
        "script_id": result.get("script_id", ""),
        "run_id": result.get("run_id", ""),
        "count": result.get("count", 0),
        "mode": result.get("mode", mode),
        "data_source": data_source or "chart",
        "overlay": result.get("overlay", True),
        "script_name": result.get("script_name", "plot"),
        "logs": result.get("logs", []),
        "profile": result.get("profile"),
        "meta": {
            **(result.get("meta") or {}),
            "inputs": result.get("inputs", []),
            "plot_meta": result.get("plot_meta", {}),
        },
    }
    if result.get("alert_conditions") is not None:
        resp["alert_conditions"] = result["alert_conditions"]

    # Warm-compile / auto-route diagnostics (H2 product path)
    for key in (
        "auto_backend",
        "compile_fallback_reason",
        "compile_cached",
        "compile_ms",
        "nopython_fallback_reason",
        "object_mode",
    ):
        if key in result and result[key] is not None:
            resp[key] = result[key]

    # L2: optional outbound webhook for alert()/alertcondition() firings
    try:
        from .alert_forwarder import maybe_forward_run_alerts

        wh = validated.get("webhook_url") or ""
        alert_fwd = maybe_forward_run_alerts(
            alerts=resp.get("alerts"),
            ohlcv=ohlcv if isinstance(ohlcv, list) else None,
            webhook_url=wh if isinstance(wh, str) else None,
            enable_forward=bool(validated.get("forward_alerts", True)),
            alert_last_bar=bool(validated.get("alert_last_bar", True)),
            alert_batch=bool(validated.get("alert_batch", True)),
            symbol=str(symbol) if symbol else None,
        )
        if alert_fwd is not None:
            resp["alert_forward"] = alert_fwd
    except Exception as e:  # noqa: BLE001 — never fail the run on webhook errors
        resp["alert_forward_error"] = str(e)

    return resp, 200


def _compile_health_section() -> dict[str, Any]:
    """Compile capability + cache/prewarm flags for readiness probes (H2)."""
    try:
        from pynescript.compiler.engine import compile_cache_stats
        from pynescript.compiler.engine import compile_deploy_config

        stats = compile_cache_stats()
        deploy = compile_deploy_config()
        return {
            "has_numba": bool(stats.get("has_numba")),
            "builtins_warmed": bool(stats.get("builtins_warmed")),
            "disk_cache_enabled": bool(stats.get("disk_cache_enabled")),
            "disk_cache_dir": stats.get("disk_cache_dir"),
            "prewarm_enabled": bool(stats.get("prewarm_enabled")),
            "source_entries": stats.get("source_entries"),
            "ir_entries": stats.get("ir_entries"),
            "default_mode": deploy.get("default_runtime_mode", "auto"),
            "host_prewarmed": _HOST_COMPILE_PREWARMED,
        }
    except Exception as exc:  # noqa: BLE001 — health must stay up
        return {
            "has_numba": False,
            "error": str(exc),
            "default_mode": "auto",
            "host_prewarmed": _HOST_COMPILE_PREWARMED,
        }


def _health_payload() -> dict[str, Any]:
    endpoints = {
        "GET /": "This health check",
        "GET /health": "Alias of GET /",
        "POST /run": "Run Pine Script (free; mode default auto = warm compile)",
        "POST /run/batch": "Run multiple Pine scripts on shared OHLCV (free)",
        "POST /compile/prewarm": "Warm Numba builtins / optional scripts (free)",
        "POST /lsp/completion": "Pine completion (free, AXIS editor)",
        "POST /lsp/hover": "Pine hover docs (free, AXIS editor)",
        "POST /lsp/diagnostics": "Pine parse+lint pre-eval (free, AXIS editor)",
        "POST /lsp/preevaluate": "Alias of /lsp/diagnostics",
        "POST /preview/chart": "Chart thumbnail (Pro)",
        "POST /preview/indicator": "Indicator preview (Pro)",
        "POST /backtest/quick": "Quick backtest (Pro)",
        "POST /auth/create_key": "Create API key (requires admin)",
        "GET /auth/usage": "Get usage stats (Pro)",
    }
    if sock is not None:
        endpoints["WS /ws/run"] = "Run Pine Script over WebSocket (prefer WSS when available)"
    from .alert_forwarder import default_webhook_url

    return {
        "status": "healthy",
        "service": "pynescript-pro-api",
        "version": "1.0.0",
        "timestamp": int(time.time()),
        "websocket": sock is not None,
        "features": {
            "alerts": True,
            "alert_webhooks": True,
            "alert_webhook_default": bool(default_webhook_url()),
            "warm_compile": True,
            "default_run_mode": "auto",
        },
        "compile": _compile_health_section(),
        "endpoints": endpoints,
    }


@app.route("/", methods=["GET"])
@app.route("/health", methods=["GET"])
def health_check():
    """Liveness/readiness JSON (version, endpoints, optional compile status)."""
    return jsonify(_health_payload())


@app.route("/run", methods=["POST"])
def run_pine_script():
    """Execute Pine Script with provided data. Free tier endpoint.

    ``mode`` is read from the JSON body (preferred; default **``auto``** —
    try warm compile, fall back to interpret). Query-string ``?mode=compile``
    is accepted as a legacy fallback when the body omits ``mode`` (older AXIS
    clients only put mode on the URL).
    """
    payload: dict[str, Any] = dict(request.get_json(silent=True) or {})
    qmode = request.args.get("mode")
    if qmode and not payload.get("mode"):
        payload["mode"] = qmode
    body, status = execute_run_payload(payload)
    return jsonify(body), status


@app.route("/compile/prewarm", methods=["POST"])
def compile_prewarm():
    """Warm shared Numba kernels and optionally compile Pine sources (H2).

    Free readiness hook for deploy/probes. Body (all optional)::

        {
          "scripts": ["//@version=5\\nindicator(\\"x\\")\\nplot(close)"],
          "force": false
        }

    Without Numba, returns 200 with ``has_numba: false`` (object-mode compile
    still works; numeric JIT skip is expected). Does not execute scripts on
    OHLCV — only populates IR / disk caches.

    Rate-limited and concurrency-gated (audit 2026-08-10 free-tier guards).
    """
    from backend.middleware.free_limits import acquire_free_slot
    from backend.middleware.free_limits import check_free_rate_limit
    from backend.middleware.free_limits import release_free_slot
    from backend.middleware.free_limits import validate_free_run_bounds

    rate_err = check_free_rate_limit()
    if rate_err is not None:
        body, code = rate_err
        return jsonify(body), code
    slot_err = acquire_free_slot()
    if slot_err is not None:
        body, code = slot_err
        return jsonify(body), code
    try:
        payload: dict[str, Any] = dict(request.get_json(silent=True) or {})
        force = bool(payload.get("force", False))
        scripts_raw = payload.get("scripts")
        sources: list[str] = []
        if isinstance(scripts_raw, list):
            for item in scripts_raw[:16]:  # hard cap: avoid abuse on free endpoint
                if isinstance(item, str) and item.strip():
                    sources.append(item)
                elif isinstance(item, dict) and isinstance(item.get("script"), str):
                    src = item["script"]
                    if src.strip():
                        sources.append(src)

        bounds_err = validate_free_run_bounds(scripts=sources)
        if bounds_err is not None:
            body, code = bounds_err
            return jsonify(body), code

        global _HOST_COMPILE_PREWARMED
        t0 = time.perf_counter()
        try:
            from pynescript.compiler.engine import prewarm_scripts

            result = prewarm_scripts(sources or None, force_builtins=force)
            _HOST_COMPILE_PREWARMED = True
        except Exception as exc:  # noqa: BLE001
            return jsonify(
                {
                    "status": "error",
                    "code": "PREWARM_ERROR",
                    "message": str(exc),
                }
            ), 500

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        body = {
            "status": "success",
            "prewarm_ms": round(elapsed_ms, 2),
            **result,
        }
        return jsonify(body), 200
    finally:
        release_free_slot()


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

            # Map WS envelope → REST body shape (omit null optionals —
            # schema rejects null for typed optional fields like symbol)
            payload: dict[str, Any] = {}
            if "script" in msg:
                payload["script"] = msg.get("script")
            if "data" in msg:
                payload["data"] = msg.get("data")
            for opt in ("symbol", "mode", "data_source", "data_options", "inputs", "profiler"):
                if opt in msg and msg.get(opt) is not None:
                    payload[opt] = msg[opt]
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
    from backend.middleware.free_limits import acquire_free_slot
    from backend.middleware.free_limits import check_free_rate_limit
    from backend.middleware.free_limits import release_free_slot

    rate_err = check_free_rate_limit()
    if rate_err is not None:
        body, code = rate_err
        return jsonify(body), code
    slot_err = acquire_free_slot()
    if slot_err is not None:
        body, code = slot_err
        return jsonify(body), code
    try:
        return _run_pine_script_batch_inner()
    finally:
        release_free_slot()


def _run_pine_script_batch_inner():
    """Batch run body after free-tier gates (see :func:`run_pine_script_batch`)."""
    from backend.middleware.free_limits import validate_free_run_bounds
    from backend.middleware.schemas import RUN_BATCH_MAX_SCRIPTS, RUN_BATCH_SCHEMA

    data, err = validate(request.get_json(silent=True) or {}, RUN_BATCH_SCHEMA)
    if err is not None:
        return err

    scripts = data["scripts"]
    ohlcv = data["data"]
    symbol = data.get("symbol") or "CHART"
    data_source = data.get("data_source") or None
    data_options = data.get("data_options") or {}
    mode = data.get("mode") or "auto"
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

    bounds_err = validate_free_run_bounds(
        scripts=[src for _, src in jobs],
        ohlcv=ohlcv if isinstance(ohlcv, list) else None,
        data_source=data_source if isinstance(data_source, str) else None,
    )
    if bounds_err is not None:
        body, code = bounds_err
        return jsonify(body), code

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
        item: dict[str, Any] = {
            "id": sid,
            "status": "success",
            "plots": result.get("plots", []),
            "series": result.get("series", {}),
            "plot_meta": result.get("plot_meta", {}),
            "events": result.get("events", []),
            "drawings": result.get("drawings", []),
            "alerts": result.get("alerts", []),
            "script_id": result.get("script_id", ""),
            "run_id": result.get("run_id", ""),
            "count": result.get("count", 0),
            "mode": result.get("mode", mode),
        }
        if result.get("alert_conditions") is not None:
            item["alert_conditions"] = result["alert_conditions"]
        try:
            from .alert_forwarder import maybe_forward_run_alerts

            alert_fwd = maybe_forward_run_alerts(
                alerts=item.get("alerts"),
                ohlcv=ohlcv if isinstance(ohlcv, list) else None,
                webhook_url=data.get("webhook_url") or None,
                enable_forward=bool(data.get("forward_alerts", True)),
                alert_last_bar=bool(data.get("alert_last_bar", True)),
                alert_batch=bool(data.get("alert_batch", True)),
                symbol=str(symbol) if symbol else None,
            )
            if alert_fwd is not None:
                item["alert_forward"] = alert_fwd
        except Exception as e:  # noqa: BLE001
            item["alert_forward_error"] = str(e)
        results.append(item)

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
app.register_blueprint(lsp_bp)
# AXIS Connect with GitHub/GitLab (device flow) — same paths as CF Worker
app.register_blueprint(git_oauth_bp)


@app.errorhandler(404)
def not_found(e):
    """JSON 404 for unknown paths."""
    return jsonify(
        {
            "status": "error",
            "code": "NOT_FOUND",
            "message": f"Endpoint {request.path} not found.",
        }
    ), 404


@app.errorhandler(500)
def server_error(e):
    """JSON 500 without leaking exception details to clients."""
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
    import logging

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5002"))
    logging.getLogger(__name__).info(
        "Pro API on http://%s:%s  websocket=%s",
        host,
        port,
        sock is not None,
    )
    app.run(host=host, port=port, debug=False)
