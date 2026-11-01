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
import logging
import os
import re
import time

from collections.abc import Callable
from typing import Any


# Explicit name (not ``__name__``): under ``python -m backend.app`` the module
# is ``__main__``, which logging_setup.configure_logging does NOT manage (its
# prefixes are ``pynescript``/``backend``), so the PYNE_DEBUG access log was
# silently dropped. Under gunicorn ``__name__`` is ``backend.app`` anyway.
logger = logging.getLogger("backend.app")


def _dbg(msg: str, *args: Any) -> None:
    """Emit one backend debug line when ``PYNE_DEBUG`` is enabled."""
    if _debug_on():
        logger.debug(msg, *args)


_INTERNAL_PATH_RE = re.compile(r'(?:File ")?[\\/](?:[\w.-]+[\\/])*[\w.-]+\.py(?:", line \d+)?')
_MAX_ERROR_MSG_LEN = 500
_TRACE_PREFIXES = (
    "Traceback ",
    "File ",
    "During handling of",
    "The above exception",
)


def _sanitize_error_for_response(msg: str) -> str:
    """One-line client error: drop traceback frames and source paths."""
    last = ""
    for line in str(msg).splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith(_TRACE_PREFIXES) or _INTERNAL_PATH_RE.search(s):
            continue
        last = s
    if len(last) > _MAX_ERROR_MSG_LEN:
        last = last[:_MAX_ERROR_MSG_LEN] + "..."
    return last or "An error occurred"


def _public_exc_message(exc: BaseException) -> str:
    """Client-facing exception text. Full ``str(exc)`` stays in the server log."""
    cleaned = _sanitize_error_for_response(str(exc))
    if cleaned == "An error occurred":
        return type(exc).__name__
    return cleaned


def _load_env_file() -> bool:
    """Load ``.env`` into the process environment (python-dotenv optional).

    Flask's own CLI does this for ``flask run``; ``python -m backend.app`` and
    gunicorn do not. Existing environment variables always win. Without
    python-dotenv installed this is a quiet no-op (``pip install -r
    backend/requirements.txt`` installs it).
    """
    try:
        from dotenv import find_dotenv
        from dotenv import load_dotenv
    except ImportError:
        logger.debug("python-dotenv not installed; .env is ignored")
        return False
    # Prefer the process working directory (how ``flask run`` and
    # ``python -m backend.app`` are launched), then fall back to the
    # module-relative search so a launch from a subdirectory still finds the
    # repository ``.env``. Existing environment variables always win.
    dotenv_path = find_dotenv(usecwd=True) or find_dotenv()
    if not dotenv_path:
        logger.debug("no .env file found; skipping environment load")
        return False
    return bool(load_dotenv(dotenv_path))


# Read .env before any env-dependent module-level configuration below
# (logging policy, key store, runner scheduler).
_load_env_file()


from flask import Flask
from flask import g
from flask import jsonify
from flask import request
from flask_cors import CORS

from backend.api import data_series as data_api
from backend.api.git_oauth import bp as git_oauth_bp
from backend.api.lsp_http import bp as lsp_bp
from backend.api.preview import backtest_bp
from backend.api.preview import preview_bp
from backend.api.runner import bp as runner_bp
from backend.datastore import live as data_live
from backend.datastore import series as series_store


try:
    from backend.api.datafeed import datafeed_bp
except ImportError:
    datafeed_bp = None  # type: ignore[assignment]
from backend.middleware.auth import get_key_store
from backend.middleware.auth import require_admin_token
from backend.middleware.auth import require_api_key
from backend.middleware.schemas import CREATE_KEY_SCHEMA
from backend.middleware.schemas import DATA_SESSION_CREATE_SCHEMA
from backend.middleware.schemas import DATA_SESSION_TICK_SCHEMA
from backend.middleware.schemas import OPTIMIZE_SCHEMA
from backend.middleware.schemas import RUN_SCHEMA
from backend.middleware.schemas import SESSION_APPEND_SCHEMA
from backend.middleware.schemas import SESSION_CREATE_SCHEMA
from backend.middleware.schemas import SESSION_TICK_SCHEMA
from backend.middleware.schemas import VALIDATE_KEY_SCHEMA
from backend.middleware.schemas import validate
from backend.middleware.sessions import SESSIONS
from backend.runtime import Runtime
from pynescript import stats as _stats
from pynescript.debug import debug_enabled as _debug_on


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
# Same product set as AXIS Worker pickOrigin — not open `*.pages.dev`.
# Apex + preview hosts under the pynescript-axis Pages project, plus hoox/pyne.
PRODUCT_ORIGIN_RE = (
    r"^https://(?:"
    r"(?:[\w-]+\.)*(?:hoox\.sh|pynescript\.ai|pynescript\.online)|"
    r"(?:[\w-]+\.)*pynescript-axis\.pages\.dev"
    r")$"
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
    if PRODUCT_ORIGIN_RE not in parts and raw != "*":
        parts.append(PRODUCT_ORIGIN_RE)
    return parts


ALLOWED_ORIGINS = _parse_allowed_origins()
# Free browser surface used by AXIS (VPS UI → local pyne is a first-class setup).
# Always reflect Origin on these paths so OPTIONS preflight never fails CORS.
# /health is the AXIS Settings probe (Pages preview → axis.hoox.sh).
_FREE_CORS_PATH_PREFIXES = (
    "/",
    "/health",
    "/run",
    "/optimize",
    "/compile",
    "/lsp/",
    "/ws/",
    "/datafeed",
)

# Once-per-worker host prewarm (builtins + disk cache dir). Soft-fail without Numba.
_HOST_COMPILE_PREWARMED = False


def _path_is_free_cors(path: str) -> bool:
    if path in {"/", ""}:
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
        if pat in {"*", origin}:
            return True
        try:
            if re.match(pat + ("" if pat.endswith("$") else "$"), origin) or re.match(pat, origin):
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
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS, HEAD"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Admin-Token, X-Api-Key, Accept"
        resp.headers["Access-Control-Max-Age"] = "86400"
    return resp


CORS(
    app,
    origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS != "*" else "*",
    methods=["GET", "POST", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=["Content-Type", "Authorization", "X-Admin-Token", "X-Api-Key", "Accept"],
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


@app.before_request
def _request_stats_start():  # type: ignore[no-untyped-def]
    """Stamp the request start so ``_request_stats_end`` can record latency."""
    g._pyne_req_t0 = time.perf_counter()
    # Proper in-flight gauge: raised here, lowered in the after_request hook.
    _stats.inc_gauge("http.in_flight")


@app.after_request
def _request_stats_end(resp):  # type: ignore[no-untyped-def]
    """Fold one request into ``pynescript.stats`` and log it under PYNE_DEBUG.

    Cheap when debug is off: counters are a few dict updates behind one lock.
    """
    try:
        t0 = getattr(g, "_pyne_req_t0", None)
        duration = (time.perf_counter() - t0) if t0 else 0.0
        rule = getattr(request, "url_rule", None)
        endpoint = rule.rule if rule is not None else request.path
        status = resp.status_code
        _stats.count("http.requests")
        _stats.count("http.by_endpoint", dim=f"{request.method} {endpoint}")
        _stats.count("http.by_status_class", dim=f"{status // 100}xx")
        _stats.latency("http.request", duration)
        _stats.dec_gauge("http.in_flight")
        if status >= 500:
            _stats.count("http.server_errors")
        elif status >= 400:
            _stats.count("http.client_errors")
        if duration > 1.0:
            _stats.count("http.slow_requests")
        _dbg(
            "%s %s -> %d in %.1fms (%s)",
            request.method,
            endpoint,
            status,
            duration * 1000.0,
            _describe_source(),
        )
        if _debug_on() and duration > 0.5:
            logger.debug("slow request %s %s took %.1fms", request.method, endpoint, duration * 1000.0)
    except Exception:  # stats must never break a response
        pass
    return resp


def _describe_source() -> str:
    """Compact caller label for the debug access log (no PII, no secrets)."""
    api_key = getattr(g, "api_key", None)
    if api_key is not None:
        return f"key={getattr(api_key, 'tier', 'unknown')}"
    remote = request.remote_addr
    return f"ip={remote}" if remote else "ip=?"


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
else:
    try:
        from backend.api.datafeed import register_watch_route

        register_watch_route(sock)
    except ImportError:
        pass
    try:
        from backend.api.live_ws import register_live_route

        register_live_route(sock)
    except ImportError:
        pass


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
        _dbg("host compile prewarm starting force=%s", force)
        _t_pw0 = time.perf_counter()
        result = prewarm_scripts(None, force_builtins=force)
        _HOST_COMPILE_PREWARMED = True
        _dbg("host compile prewarm done in %.1fms: %s", (time.perf_counter() - _t_pw0) * 1000.0, result)
        return result
    except Exception as exc:  # never block /run on prewarm
        import logging as _logging

        _logging.getLogger(__name__).debug("host compile prewarm failed: %s", exc, exc_info=True)
        _dbg("host compile prewarm failed: %s", exc)
        _HOST_COMPILE_PREWARMED = True
        logger.warning("host compile prewarm failed: %s", exc)
        return {"error": "Internal server error", "has_numba": False}


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
    except Exception:
        payload = {
            "status": "error",
            "code": "VALIDATION_ERROR",
            "message": "Invalid request body",
        }
    return payload, int(code or 400)


def _parse_run_libraries(raw_libs: Any) -> list[dict[str, Any]]:
    """Normalize AXIS git-publish library objects (max 32)."""
    libraries: list[dict[str, Any]] = []
    if not isinstance(raw_libs, list):
        return libraries
    for item in raw_libs[:32]:
        if not isinstance(item, dict):
            continue
        ns = str(item.get("namespace") or "").strip()
        name = str(item.get("name") or "").strip()
        src = str(item.get("source") or "")
        try:
            ver = int(item.get("version") or 1)
        except (TypeError, ValueError):
            ver = 1
        if ns and name and src:
            libraries.append({"namespace": ns, "name": name, "version": ver, "source": src})
    return libraries


_RUN_TIMEOUT_DEFAULT = 30.0

# Degraded tail-poll cap (F-14): a dropped socket polls bars, never history.
TAIL_MAX_BARS = 5000
# Matches docker/entrypoint-api.sh GUNICORN_TIMEOUT default.
_RUN_TIMEOUT_MAX_DEFAULT = 120.0


def _default_run_timeout() -> float:
    """Server-side default execution timeout (``PYNE_RUN_TIMEOUT``, seconds)."""
    raw = os.environ.get("PYNE_RUN_TIMEOUT", "").strip()
    if raw:
        try:
            value = float(raw)
            if value > 0:
                return value
        except ValueError:
            pass
    return _RUN_TIMEOUT_DEFAULT


def _max_run_timeout() -> float:
    """Cap for client-supplied ``timeout_seconds`` (``PYNE_RUN_TIMEOUT_MAX``)."""
    raw = os.environ.get("PYNE_RUN_TIMEOUT_MAX", "").strip()
    if raw:
        try:
            value = float(raw)
            if value > 0:
                return value
        except ValueError:
            pass
    return _RUN_TIMEOUT_MAX_DEFAULT


def _timeout_seconds_kwarg(raw: Any) -> dict[str, float]:
    """Return ``timeout_seconds=`` — client value, else a server-side default.

    Without this, a pathological script runs until gunicorn's ``--timeout``
    SIGKILLs the worker, dropping every in-flight request on it. Client values
    are capped so a huge ``timeout_seconds`` cannot hold a worker indefinitely.
    """
    cap = _max_run_timeout()
    if isinstance(raw, (int, float)) and not isinstance(raw, bool) and raw > 0:
        return {"timeout_seconds": min(float(raw), cap)}
    return {"timeout_seconds": _default_run_timeout()}


def _blocked_webhook_error(wh_raw: Any) -> tuple[dict[str, Any], int] | None:
    """Return a 400 body when *wh_raw* is a non-empty blocked webhook URL."""
    if not isinstance(wh_raw, str) or not wh_raw.strip():
        return None
    from .alert_forwarder import normalize_webhook_url

    if normalize_webhook_url(wh_raw) is not None:
        return None
    return {
        "status": "error",
        "code": "WEBHOOK_URL_BLOCKED",
        "message": (
            "webhook_url is invalid or blocked (private/loopback/"
            "metadata hosts are not allowed). Use a public https URL "
            "or set ALERT_WEBHOOK_ALLOW_PRIVATE=1 for private demos."
        ),
    }, 400


def execute_run_payload(data: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Shared run logic for POST /run and WS /ws/run.

    Returns (body_dict, http_status). Body always includes ``status``.
    Default ``mode`` is ``auto`` (prefer warm compile; interpret on fallback).

    Optional free-tier abuse guards (audit 2026-08-10; off unless
    ``FREE_TIER_LIMITS`` is truthy): bar/script caps, IP rate limit,
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

    assert validated is not None  # noqa: S101 - validator invariant
    script = validated["script"]
    ohlcv = validated["data"]
    symbol = validated.get("symbol") or "CHART"
    data_source = validated.get("data_source") or None
    data_options = validated.get("data_options") or {}
    # Prefer compile with interpret fallback for production throughput.
    mode = validated.get("mode") or "auto"
    if isinstance(data_source, str) and not data_source.strip():
        data_source = None

    # Refuse inline API keys unless explicitly allowed (datafeed security).
    # Credentials should flow through /datafeed/session, not /run body.
    if os.environ.get("DATAFEED_ALLOW_INLINE_KEYS", "0") != "1":
        if "api_key" in data_options or "secret" in data_options:
            return {
                "status": "error",
                "code": "INLINE_KEYS_NOT_ALLOWED",
                "message": "Inline API keys are not allowed. Use /datafeed/session instead.",
            }, 400

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
    blocked = _blocked_webhook_error(validated.get("webhook_url") or "")
    if blocked is not None:
        return blocked

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
    except Exception as e:  # surface config errors cleanly
        logger.warning("data source config: %s", e)
        return {
            "status": "error",
            "code": "DATA_SOURCE_ERROR",
            "message": "Failed to configure data source",
        }, 400

    inputs = validated.get("inputs") or {}
    if not isinstance(inputs, dict):
        inputs = {}
    profiler = bool(validated.get("profiler"))
    libraries = _parse_run_libraries(validated.get("libraries"))
    timeout_kw = _timeout_seconds_kwarg(validated.get("timeout_seconds"))

    runtime = Runtime(symbol=str(symbol))
    _dbg(
        "POST /run symbol=%s mode=%s bars=%d script_chars=%d inputs=%d libraries=%d profiler=%s "
        "data_source=%s timeout=%s",
        symbol,
        mode,
        len(ohlcv),
        len(script),
        len(inputs),
        len(libraries),
        profiler,
        data_source,
        timeout_kw.get("timeout_seconds"),
    )
    _t_run0 = time.perf_counter()
    result = runtime.run(
        script,
        ohlcv,
        data_feed=data_feed,
        data_provider=data_provider,
        mode=str(mode),
        inputs=inputs if inputs else None,
        profiler=profiler,
        libraries=libraries or None,
        **timeout_kw,
    )
    _dbg(
        "POST /run returned in %.1fms mode=%s backend=%s error=%s",
        (time.perf_counter() - _t_run0) * 1000.0,
        result.get("mode"),
        result.get("auto_backend"),
        bool(result.get("error")),
    )

    # Response windowing — serialize only the requested bar range. Must run
    # AFTER the full result is built (the bar loop is untouched) and is a no-op
    # when the client sends no window, so the default path is byte-identical.
    if validated.get("from_bar") is not None or validated.get("to_bar") is not None:
        try:
            from backend.middleware.window import apply_window

            result = apply_window(
                result,
                validated.get("from_bar"),
                validated.get("to_bar"),
            )
        except Exception:  # never fail a run over a trim
            logger.warning("window trim failed; returning full envelope", exc_info=True)

    if "error" in result:
        err_body: dict[str, Any] = {
            "status": "error",
            "code": "EXECUTION_ERROR",
            "message": _sanitize_error_for_response(str(result["error"])),
        }
        # Pass through Runtime classification when present (parse/compile/runtime/…).
        if result.get("error_kind"):
            err_body["error_kind"] = result["error_kind"]
        if result.get("error_type"):
            err_body["error_type"] = _sanitize_error_for_response(str(result["error_type"]))
        if result.get("error_bar") is not None:
            err_body["error_bar"] = result["error_bar"]
        if result.get("timed_out"):
            err_body["timed_out"] = True
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
    if result.get("timed_out"):
        resp["timed_out"] = True
    # `count` stays the number of bars EVALUATED, so a client that sees
    # count=20000 with a 500-long series needs this to know it got a window
    # rather than a short history.
    if result.get("window") is not None:
        resp["window"] = result["window"]

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
    except Exception as e:  # never fail the run on webhook errors
        logger.warning("alert forward: %s", e)
        resp["alert_forward_error"] = "Alert forwarding failed"

    return resp, 200


def _free_tier_limits_flag() -> bool:
    """Whether unauthenticated /run guards are opted in (off by default)."""
    from backend.middleware.free_limits import free_tier_limits_enabled

    return free_tier_limits_enabled()


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
    except Exception as exc:  # health must stay up
        logger.warning("compile health: %s", exc)
        return {
            "has_numba": False,
            "error": "Internal server error",
            "default_mode": "auto",
            "host_prewarmed": _HOST_COMPILE_PREWARMED,
        }


def _health_payload() -> dict[str, Any]:
    endpoints = {
        "GET /": "This health check",
        "GET /health": "Alias of GET /",
        "POST /run": "Run Pine Script (free; mode default auto = warm compile)",
        "POST /run/batch": "Run multiple Pine scripts on shared OHLCV (free)",
        "POST /optimize": "Strategy hyperparameter search (free; interpret + inputs)",
        "POST /compile/prewarm": "Warm Numba builtins / optional scripts (free)",
        "GET /stats": "Process runtime stats (engine, deltas, datafeed, http)",
        # Live sessions. Process-local, so these only resolve on the single
        # gunicorn worker — advertised here because /health is the discovery
        # surface agents and AXIS read to learn what this API can do.
        "POST /session": "Create a live session (interpret only; O(1) re-tick)",
        "GET /session/<session_id>": "Live session status (bars, idle, TTL)",
        "GET /session/<session_id>/tail": "Bars after a cursor (degraded WS fallback)",
        "POST /session/<session_id>/tick": "Re-tick the forming bar — O(1)",
        "POST /session/<session_id>/append": "Append closed bars — O(delta)",
        "DELETE /session/<session_id>": "Release a session (else idle TTL)",
        # Engine-owned data plane: bars live in the PYNE store, not the request.
        "GET /data/series": "Stored OHLCV series bounds (engine-owned data)",
        "DELETE /data/series": "Drop one stored series (client dataset flush)",
        "GET /data/series/bars": "Newest stored bars for a series (chart paint)",
        "POST /data/series/provide": "Upload closed bars into the series store (max 5000)",
        "POST /data/series/fetch": "Fetch history via CCXT into the series store",
        "POST /data/session": "Create a live session bound to a stored series (DATA_MISS 409)",
        "POST /data/session/<session_id>/tick": "Advance a bound session from the engine feed",
        "POST /lsp/completion": "Pine completion (free, AXIS editor)",
        "POST /lsp/hover": "Pine hover docs (free, AXIS editor)",
        "POST /lsp/diagnostics": "Pine parse+lint pre-eval (free, AXIS editor)",
        "POST /lsp/preevaluate": "Alias of /lsp/diagnostics",
        "POST /lsp/convert": "Rewrite older Pine toward v6 (free, AXIS editor)",
        "POST /preview/chart": "Chart thumbnail (Pro)",
        "POST /preview/indicator": "Indicator preview (Pro)",
        "POST /backtest/quick": "Quick backtest (Pro)",
        "POST /auth/create_key": "Create API key (requires admin)",
        "GET /auth/usage": "Get usage stats (Pro)",
    }
    from backend.runner import runner_enabled
    from backend.runner import scheduler_enabled

    if runner_enabled():
        endpoints["POST /scripts"] = "Deploy a hosted script (optional runner)"
        endpoints["GET /scripts"] = "List hosted scripts"
        endpoints["GET /scripts/:id"] = "Get hosted script + cron state"
        endpoints["DELETE /scripts/:id"] = "Delete hosted script"
        endpoints["GET /cron/jobs"] = "List runner jobs"
        endpoints["PUT /cron/jobs"] = "Enable/disable runner jobs"
        endpoints["POST /cron/run"] = "Tick hosted scripts (bar-close)"
    if sock is not None:
        endpoints["WS /ws/run"] = "Run Pine Script over WebSocket (prefer WSS when available)"
        endpoints["WS /ws/live"] = "Engine-owned subscriptions: subscribe → status → full → delta → close"
        endpoints["WS /datafeed/watch"] = "CCXT Pro OHLCV stream (AXIS ccxt-ws)"
    endpoints["GET /datafeed/ohlcv"] = "CCXT historical OHLCV (AXIS ccxt-rest)"
    endpoints["GET /datafeed/markets"] = "CCXT markets for an exchange"
    endpoints["GET /datafeed/health"] = "Datafeed gateway + ccxt_exchanges"
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
            "optimize": True,
            "free_tier_limits": _free_tier_limits_flag(),
            "script_runner": runner_enabled(),
            "script_runner_scheduler": scheduler_enabled(),
            # Engine-owned data plane (AXIS D3): capabilities are read from here.
            "live_modes": ["every-tick", "bar-close"],
            "data_session": True,
            "session_delta": True,
            "live_stream": True,
        },
        "compile": _compile_health_section(),
        "endpoints": endpoints,
    }


@app.route("/stats", methods=["GET"])
def get_stats():
    """Process-wide runtime statistics (counters, latencies, gauges).

    Public like ``/health`` so ops can poll it without an API key. In-process
    only — counters reset when the worker restarts, which is honest for the
    single-worker gunicorn setup the live sessions require.

    Payload sections:

    - ``http`` — request count, per endpoint / status class, in-flight, slow
    - ``run`` / ``interpret`` / ``compile`` / ``prewarm`` — execution engine
    - ``delta`` — live-session ``append_bars`` (O(delta)) / forming-bar ticks
    - ``sessions`` — live session store size and lifecycle counters
    - ``datafeed`` / ``provider`` — CCXT realtime + historical fetches
    - ``compile_cache`` — live engine cache sizes (same source as /health)
    - ``debug`` — current ``PYNE_DEBUG`` configuration
    """
    from backend.logging_setup import debug_report

    snapshot = _stats.snapshot()
    return jsonify(
        {
            "status": "ok",
            "service": "pynescript-pro-api",
            "version": "1.0.0",
            "timestamp": int(time.time()),
            "debug": debug_report(),
            "counters": snapshot["counters"],
            "latencies": snapshot["latencies"],
            "gauges": snapshot["gauges"],
            "compile_cache": _compile_cache_snapshot(),
            "sessions": _sessions_snapshot(),
            "notes": "in-process counters; reset on worker restart",
        }
    )


def _compile_cache_snapshot() -> dict[str, Any]:
    """Live compile cache sizes, or ``{}`` when the engine cannot be imported."""
    try:
        from pynescript.compiler.engine import compile_cache_stats

        return compile_cache_stats()
    except Exception as exc:  # /stats must stay up
        logger.warning("stats compile cache: %s", exc)
        return {"error": "unavailable"}


def _sessions_snapshot() -> dict[str, Any]:
    """Live session store size plus derived gauges."""
    try:
        st = SESSIONS.stats()
        _stats.set_gauge("sessions.active", int(st.get("sessions", 0) or 0))
        return st
    except Exception as exc:  # /stats must stay up
        logger.warning("stats sessions: %s", exc)
        return {"error": "unavailable"}


@app.before_request
def _runner_scheduler_boot():
    """Start the optional poll loop in this process (gunicorn --preload fork)."""
    from backend.runner import scheduler_enabled
    from backend.runner.scheduler import maybe_start_background

    if scheduler_enabled():
        maybe_start_background()


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


def _opt_int(d: dict[str, Any], key: str, default: int) -> int:
    """Coerce ``d[key]`` to int; missing/None keep ``default`` (0 is valid)."""
    if key not in d or d[key] is None:
        return default
    return int(d[key])


def _opt_float(d: dict[str, Any], key: str, default: float) -> float:
    """Coerce ``d[key]`` to float; missing/None keep ``default`` (0.0 is valid)."""
    if key not in d or d[key] is None:
        return default
    return float(d[key])


def _optimize_error_http(err: str) -> tuple[str, int]:
    """Map ``StudyResult.error`` to a stable API code and HTTP status.

    Recognized user-input failures are 400. Unexpected engine crashes stay
    500 ``OPTIMIZE_ERROR``.
    """
    s = (err or "").strip()
    lower = s.lower()
    if s.startswith("NOT_A_STRATEGY"):
        return "NOT_A_STRATEGY", 400
    if s.startswith("TOO_MANY_RUNS"):
        return "TOO_MANY_RUNS", 400
    if s.startswith("GRID_TOO_LARGE") or lower.startswith("grid has"):
        return "GRID_TOO_LARGE", 400
    if s.startswith("EMPTY_SPACE"):
        return "EMPTY_SPACE", 400
    if s.startswith("NO_DATA"):
        return "NO_DATA", 400
    if s.startswith("INVALID_VALIDATION"):
        return "INVALID_VALIDATION", 400
    if s.startswith("INVALID_OBJECTIVE") or "unknown objective" in lower:
        return "INVALID_OBJECTIVE", 400
    if s.startswith("INVALID_SAMPLER") or "unknown sampler" in lower:
        return "INVALID_SAMPLER", 400
    if s.startswith("INVALID_SPACE"):
        return "INVALID_SPACE", 400
    if s.startswith("INVALID_"):
        return s.split(":", 1)[0].split()[0], 400
    return "OPTIMIZE_ERROR", 500


def execute_optimize_payload(data: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Shared body for ``POST /optimize`` (same free-tier gates as ``/run``)."""
    from backend.middleware.free_limits import acquire_free_slot
    from backend.middleware.free_limits import check_free_rate_limit
    from backend.middleware.free_limits import release_free_slot
    from backend.middleware.free_limits import validate_free_run_bounds
    from pynescript.optimize import run_study
    from pynescript.optimize import space_from_payload
    from pynescript.optimize.types import ValidationSpec

    rate_err = check_free_rate_limit()
    if rate_err is not None:
        return _err_to_dict(rate_err)

    slot_err = acquire_free_slot()
    if slot_err is not None:
        return _err_to_dict(slot_err)

    try:
        validated, err = validate(data or {}, OPTIMIZE_SCHEMA)
        if err is not None:
            return _err_to_dict(err)
        assert validated is not None  # noqa: S101 - validator invariant
        script = validated["script"]
        ohlcv = validated["data"]
        if not script:
            return {"status": "error", "code": "NO_SCRIPT", "message": "No 'script' provided."}, 400
        if not ohlcv:
            return {"status": "error", "code": "NO_DATA", "message": "No 'data' provided."}, 400
        bounds_err = validate_free_run_bounds(
            script=script if isinstance(script, str) else None,
            ohlcv=ohlcv if isinstance(ohlcv, list) else None,
        )
        if bounds_err is not None:
            return _err_to_dict(bounds_err)

        try:
            space = space_from_payload(validated.get("space"))
        except ValueError as exc:
            logger.warning("invalid space: %s", exc)
            return {"status": "error", "code": "INVALID_SPACE", "message": "Invalid space parameter"}, 400

        raw_val = validated.get("validation") or {}
        if not isinstance(raw_val, dict):
            raw_val = {}
        mode = str(raw_val.get("mode") or "holdout").strip().lower()
        if mode not in {"holdout", "walk-forward", "in-sample"}:
            return {
                "status": "error",
                "code": "INVALID_VALIDATION",
                "message": f"validation.mode must be holdout|walk-forward|in-sample, got {mode!r}",
            }, 400
        try:
            spec = ValidationSpec(
                mode=mode,  # type: ignore[arg-type]
                holdout_frac=_opt_float(raw_val, "holdout_frac", 0.3),
                train_bars=_opt_int(raw_val, "train_bars", 200),
                test_bars=_opt_int(raw_val, "test_bars", 50),
                step_bars=_opt_int(raw_val, "step_bars", 50),
                warmup_bars=_opt_int(raw_val, "warmup_bars", 0),
            )
            n_trials = _opt_int(validated, "n_trials", 30)
            min_trades = _opt_int(validated, "min_trades", 5)
            seed_raw = validated.get("seed")
            seed = int(seed_raw) if seed_raw is not None else None
        except (TypeError, ValueError) as exc:
            logger.warning("optimize validation: %s", exc)
            return {
                "status": "error",
                "code": "INVALID_VALIDATION",
                "message": "Invalid optimization parameters",
            }, 400
        libs = _parse_run_libraries(validated.get("libraries"))
        raw_fixed = validated.get("fixed_inputs")
        fixed_inputs = raw_fixed if isinstance(raw_fixed, dict) else None
        study = run_study(
            script,
            ohlcv if isinstance(ohlcv, list) else [],
            space,
            n_trials=n_trials,
            sampler=str(validated.get("sampler") or "auto"),
            objective=str(validated.get("objective") or "composite"),
            validation=spec,
            min_trades=min_trades,
            seed=seed,
            symbol=str(validated.get("symbol") or "CHART"),
            oos_every_trial=bool(validated.get("oos_every_trial", True)),
            libraries=libs or None,
            fixed_inputs=fixed_inputs,
        )
        body = study.to_dict()
        if study.status == "error" and study.error:
            code, http = _optimize_error_http(study.error)
            body["code"] = code
            body["message"] = study.error
            return body, http
        return body, 200
    finally:
        release_free_slot()


# ── Live evaluation sessions ──────────────────────────────────────────────────
#
# A session keeps a parsed script, its series, and its TA state alive so that
# re-ticking the forming bar is O(1) instead of re-evaluating every bar
# (1,087 ms → 0.13 ms on 20k bars). That state is per-process, which is why the
# Pro API runs a single gunicorn worker — see backend/middleware/sessions.py.
#
# Endpoints are intentionally a small, explicit surface:
#   POST   /session              create (runs the initial bars once)
#   GET    /session/<id>         status
#   POST   /session/<id>/append  add closed bars   — O(delta)
#   POST   /session/<id>/tick    re-tick last bar  — O(1)
#   DELETE /session/<id>         release


def _session_envelope(result: Any, session_id: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Shape a session result like ``/run`` so one client normalizer handles both."""
    if not isinstance(result, dict):
        return {
            "status": "error",
            "code": "SESSION_RESULT_INVALID",
            "session_id": session_id,
        }
    if "error" in result:
        return {
            "status": "error",
            "code": "SESSION_EXECUTION_ERROR",
            "message": _sanitize_error_for_response(str(result["error"])),
            "session_id": session_id,
        }
    out: dict[str, Any] = {
        "status": "success",
        "session_id": session_id,
        "plots": result.get("plots", []),
        "series": result.get("series", {}),
        "plot_meta": result.get("plot_meta", {}),
        "events": result.get("events", []),
        "drawings": result.get("drawings", []),
        "alerts": result.get("alerts", []),
        "inputs": result.get("inputs", []),
        "count": result.get("count", 0),
        "mode": result.get("mode", "interpret"),
        "overlay": result.get("overlay", True),
        "script_name": result.get("script_name", "plot"),
        "logs": result.get("logs", []),
        # Bar-time axis of the evaluated window — the client joins the series
        # to its chart by time (the engine's stored series can have gaps, so
        # an index join would displace the plot).
        "times": result.get("times") or [],
        "meta": {
            **(result.get("meta") or {}),
            "inputs": result.get("inputs", []),
            "plot_meta": result.get("plot_meta", {}),
        },
    }
    if result.get("alert_conditions") is not None:
        out["alert_conditions"] = result["alert_conditions"]
    if extra:
        out.update(extra)
    return out


def _delta_tail(values: Any, tail_len: int) -> list[Any] | None:
    """Last ``tail_len`` entries of a result column, or None when unusable.

    An empty column carries no length information and stays empty (the client
    treats empty-vs-non-empty as a mismatch and falls back to a full run).
    A shorter non-empty column cannot be expressed as a tail — the caller
    answers the full envelope instead.
    """
    if not isinstance(values, list):
        return None
    if not values:
        return []
    if tail_len <= 0 or len(values) < tail_len:
        return None
    return values[-tail_len:]


def _delta_envelope(
    result: dict[str, Any], session_id: str, extra: dict[str, Any], tail_len: int
) -> dict[str, Any] | None:
    """Tail-only variant of :func:`_session_envelope` for ``delta: true`` ticks.

    ``tail_len == 0`` answers flags only (unchanged ticks: no plots/series at
    all — the client reuses its cached result). Otherwise only the last
    ``tail_len`` cells of ``plots``/``series`` travel; small fields
    (events/drawings/alerts/meta/…) stay full, they are tiny next to 10k-bar
    series. The client merges positionally
    (``full = cached[:base_index] + tail``) after checking ``count``.

    Returns None when the result cannot be expressed as a tail — the caller
    then answers the full envelope instead of a corrupt delta.
    """
    count = result.get("count")
    plots = result.get("plots") or []
    series = result.get("series") or {}
    expressible = (
        isinstance(count, int)
        and count >= 0
        and isinstance(series, dict)
        and (
            tail_len <= 0
            or (
                count - tail_len >= 0
                and _delta_tail(plots, tail_len) is not None
                and all(_delta_tail(v, tail_len) is not None for v in series.values())
            )
        )
    )
    if not expressible:
        return None
    out = _session_envelope(result, session_id, extra)
    if not isinstance(out, dict) or out.get("status") != "success":
        return out
    if tail_len > 0:
        out["plots"] = _delta_tail(plots, tail_len)
        out["series"] = {k: _delta_tail(v, tail_len) for k, v in series.items()}
        # The bar-time axis travels with the tail (the client splices it the
        # same way it splices plots/series).
        out["times"] = _delta_tail(result.get("times") or [], tail_len)
        out["delta"] = {"base_index": count - tail_len, "count": count, "tail_len": tail_len}
    else:
        out["plots"] = []
        out["series"] = {}
        out["times"] = []
    return out


def _maybe_delta_envelope(
    result: Any,
    session_id: str,
    extra: dict[str, Any],
    validated: dict[str, Any],
    tail_len: int,
) -> dict[str, Any]:
    """Answer a delta envelope when the client opted in, else the full one.

    A requested window trim (``from_bar``/``to_bar``) always takes the full
    trimmed path — trims and tails do not compose.
    """
    if (
        validated.get("delta") is True
        and isinstance(result, dict)
        and "error" not in result
        and validated.get("from_bar") is None
        and validated.get("to_bar") is None
    ):
        delta = _delta_envelope(result, session_id, extra, tail_len)
        if delta is not None:
            return delta
    return _session_envelope(result, session_id, extra)


def _load_session(
    session_id: str,
) -> tuple[Any | None, tuple[dict[str, Any], int] | None]:
    session = SESSIONS.get(session_id)
    if session is None:
        return None, (
            {
                "status": "error",
                "code": "NO_SESSION",
                "message": (
                    "Unknown or expired session id. Sessions idle longer than"
                    " the TTL are evicted and cannot be recovered; recent ones"
                    " are rebuilt automatically after a restart. Create a new"
                    " one with POST /session."
                ),
            },
            404,
        )
    return session, None


def _session_window(result: Any, validated: dict[str, Any]) -> tuple[Any, dict[str, Any] | None]:
    """Apply the optional envelope trim, matching POST /run semantics."""
    if validated.get("from_bar") is None and validated.get("to_bar") is None:
        return result, None
    try:
        from backend.middleware.window import apply_window

        trimmed = apply_window(result, validated.get("from_bar"), validated.get("to_bar"))
        return trimmed, trimmed.get("window")
    except Exception as exc:  # never fail a tick over a trim
        logger.warning("session window trim failed: %s", exc)
        return result, None


@app.route("/session", methods=["POST"])
def create_session_route():
    """Create a live evaluation session over the supplied bars.

    Interpret only — ``compile`` has no resumable evaluator state. Callers then
    use ``/session/<id>/tick`` for the forming bar and ``/session/<id>/append``
    for new closed bars.
    """
    payload: dict[str, Any] = dict(request.get_json(silent=True) or {})
    validated, err = validate(payload, SESSION_CREATE_SCHEMA)
    if err is not None:
        return _err_to_dict(err)

    script = validated.get("script")
    ohlcv = validated.get("data") or []
    if not script:
        return jsonify({"status": "error", "code": "NO_SCRIPT", "message": "No 'script' provided."}), 400
    if not ohlcv:
        return jsonify({"status": "error", "code": "NO_DATA", "message": "No 'data' provided."}), 400

    mode = str(validated.get("mode") or "interpret").strip().lower()
    if mode not in ("interpret", ""):
        return jsonify(
            {
                "status": "error",
                "code": "MODE_UNSUPPORTED",
                "message": "Sessions support interpret only; compile has no resumable state.",
            }
        ), 400

    try:
        runtime = Runtime(symbol=str(validated.get("symbol") or "CHART"))
        libraries = _parse_run_libraries(validated.get("libraries")) or None
        session = runtime.create_session(
            script,
            ohlcv,
            inputs=validated.get("inputs") or None,
            libraries=libraries,
            profiler=bool(validated.get("profiler")),
            mode="interpret",
        )
    except Exception as exc:  # surface engine failures cleanly
        logger.warning("session create failed: %s", exc)
        return jsonify(
            {
                "status": "error",
                "code": "SESSION_CREATE_FAILED",
                "message": _public_exc_message(exc),
            }
        ), 400

    try:
        session_id = SESSIONS.put(session)
    except RuntimeError as exc:
        return jsonify(
            {
                "status": "error",
                "code": "SESSIONS_FULL",
                "message": _public_exc_message(exc),
            }
        ), 503

    # Journal the inputs so a worker recycle / container restart rebuilds the
    # session from identical bars instead of 404ing (best-effort).
    SESSIONS.track(
        session_id,
        script=script,
        symbol=str(validated.get("symbol") or "CHART"),
        inputs=validated.get("inputs") or {},
        libraries=libraries or [],
        profiler=bool(validated.get("profiler")),
        bars=list(ohlcv),
    )

    return jsonify(_session_envelope(session.result(), session_id, {"sessions": SESSIONS.stats()})), 200


@app.route("/session/<session_id>", methods=["GET"])
def session_status_route(session_id: str):
    """Status for a live session (bar count, idle time, TTL)."""
    described = SESSIONS.describe(session_id)
    if described is None:
        return jsonify(
            {
                "status": "error",
                "code": "NO_SESSION",
                "message": f"Unknown session {session_id!r}.",
            }
        ), 404
    return jsonify({"status": "success", **described}), 200


@app.route("/session/<session_id>/tail", methods=["GET"])
def session_tail_route(session_id: str):
    """Degraded live fallback (F-14): bars after a client cursor.

    Query: ``since_count`` — bars the client already holds. Answers
    ``{status, count, closed_upto, tail}`` with at most ``TAIL_MAX_BARS`` bars
    so a dropped socket degrades to polling the same shapes the WS pushes.
    ``closed_upto`` is null for sessions without a series binding (the client
    cannot treat the tip as closed without an interval).
    """
    from flask import request as flask_request

    from backend.datastore import live as live_mod

    try:
        since_count = max(0, int(flask_request.args.get("since_count", "0")))
    except (TypeError, ValueError):
        since_count = 0
    session = SESSIONS.get(session_id)
    if session is None:
        return jsonify(
            {
                "status": "error",
                "code": "NO_SESSION",
                "message": f"Unknown session {session_id!r}.",
            }
        ), 404
    bars = getattr(session, "_ohlcv_data", None) or []
    count = len(bars)
    tail = bars[max(0, min(since_count, count)) :][:TAIL_MAX_BARS]
    closed_upto = None
    binding = live_mod.binding_of(session)
    if binding is not None:
        try:
            import time as _time

            now_s = int(_time.time())
            interval_s = int(binding.key.interval_seconds)
            upto = 0
            for bar in bars:
                t = int(bar["time"])
                if t + interval_s <= now_s and t > upto:
                    upto = t
            closed_upto = upto
        except (KeyError, TypeError, ValueError):
            closed_upto = None
    return jsonify({"status": "success", "count": count, "closed_upto": closed_upto, "tail": tail}), 200


@app.route("/session/<session_id>/tick", methods=["POST"])
def session_tick_route(session_id: str):
    """Re-tick the forming bar with revised OHLCV — O(1) bars.

    Overwrites the last committed cell in place; the bar count does not advance.
    ``var`` scope and TA windows roll back to bar-open on each call, so repeated
    ticks behave like intermediate realtime ticks.
    """
    session, missing = _load_session(session_id)
    if missing is not None:
        return jsonify(missing[0]), missing[1]

    payload: dict[str, Any] = dict(request.get_json(silent=True) or {})
    bar = payload.get("bar")
    if not isinstance(bar, dict):
        return jsonify(
            {
                "status": "error",
                "code": "NO_BAR",
                "message": "'bar' must be an OHLCV object.",
            }
        ), 400

    validated, err = validate(payload, SESSION_TICK_SCHEMA)
    if err is not None:
        return _err_to_dict(err)

    try:
        result = session.update_last_bar(bar)
    except Exception as exc:  # a bad tick must not 500
        logger.warning("session tick failed: %s", exc)
        return jsonify(
            {
                "status": "error",
                "code": "SESSION_TICK_FAILED",
                "message": _public_exc_message(exc),
                "session_id": session_id,
            }
        ), 400

    SESSIONS.note_tick(session_id, bar)
    result, window = _session_window(result, validated)
    extra: dict[str, Any] = {"session_id": session_id}
    if window is not None:
        extra["window"] = window
        return jsonify(_session_envelope(result, session_id, extra)), 200
    # A tick only revises the tail cell: delta answers that one cell.
    return jsonify(_maybe_delta_envelope(result, session_id, extra, validated, 1)), 200


@app.route("/session/<session_id>/append", methods=["POST"])
def session_append_route(session_id: str):
    """Append newly closed bars — O(delta), not O(history).

    ``bars`` is a list of OHLCV objects for bars that have just closed.
    """
    session, missing = _load_session(session_id)
    if missing is not None:
        return jsonify(missing[0]), missing[1]

    payload: dict[str, Any] = dict(request.get_json(silent=True) or {})
    bars_in = payload.get("bars")
    if not isinstance(bars_in, list):
        return jsonify(
            {
                "status": "error",
                "code": "NO_BARS",
                "message": "'bars' must be a list of OHLCV objects.",
            }
        ), 400

    validated, err = validate(payload, SESSION_APPEND_SCHEMA)
    if err is not None:
        return _err_to_dict(err)

    try:
        result = session.append_bars(bars_in, realtime_ticks=int(validated.get("realtime_ticks") or 1))
    except Exception as exc:  # a bad append must not 500
        logger.warning("session append failed: %s", exc)
        return jsonify(
            {
                "status": "error",
                "code": "SESSION_APPEND_FAILED",
                "message": _public_exc_message(exc),
                "session_id": session_id,
            }
        ), 400

    SESSIONS.note_append(session_id, bars_in)
    result, window = _session_window(result, validated)
    extra: dict[str, Any] = {"session_id": session_id, "appended": len(bars_in)}
    if window is not None:
        extra["window"] = window
        return jsonify(_session_envelope(result, session_id, extra)), 200
    return jsonify(_maybe_delta_envelope(result, session_id, extra, validated, len(bars_in))), 200


@app.route("/session/<session_id>", methods=["DELETE"])
def session_delete_route(session_id: str):
    """Release a session immediately instead of waiting for the idle TTL."""
    if not SESSIONS.drop(session_id):
        return jsonify(
            {
                "status": "error",
                "code": "NO_SESSION",
                "message": f"Unknown session {session_id!r}.",
            }
        ), 404
    return jsonify({"status": "success", "session_id": session_id, "released": True}), 200


# ── Engine-owned data sessions ───────────────────────────────────────────────
#
# A data session is a /session whose bars come from the engine's series store
# (backend/datastore) instead of the request body. AXIS sends identity only.
#   POST   /data/session                create (200 hit, 409 DATA_MISS)
#   POST   /data/session/<id>/tick      fetch since stored newest, advance


def _data_session_refusal(validated: dict[str, Any]) -> tuple[dict[str, Any], int] | None:
    """Reject a data-session body that cannot run (no script, or a compile request)."""
    if not validated.get("script"):
        return {"status": "error", "code": "NO_SCRIPT", "message": "No 'script' provided."}, 400
    mode = str(validated.get("mode") or "interpret").strip().lower()
    if mode not in ("interpret", ""):
        return {
            "status": "error",
            "code": "MODE_UNSUPPORTED",
            "message": "Sessions support interpret only; compile has no resumable state.",
        }, 400
    return None


@app.route("/data/session", methods=["POST"])
@require_api_key
def create_data_session_route():
    """Create a live session over the stored series window for ``history_bars``.

    A miss (fewer stored bars than ``history_bars``) returns 409 ``DATA_MISS``
    with ``have``/``need`` so the client can provide or fetch, then retry.
    """
    payload: dict[str, Any] = dict(request.get_json(silent=True) or {})
    validated, err = validate(payload, DATA_SESSION_CREATE_SCHEMA)
    if err is not None:
        return _err_to_dict(err)

    key = series_store.make_key(
        validated["exchange"],
        validated["symbol"],
        validated["interval"],
        validated["market"],
    )
    history = series_store.check_history_bars(validated["history_bars"])
    refused = _data_session_refusal(validated)
    if refused is not None:
        return jsonify(refused[0]), refused[1]

    store = series_store.get_store()
    status = store.status(key)
    have = int(status["count"])
    if have < history:
        return jsonify({"status": "miss", "code": "DATA_MISS", "key": key.text, "have": have, "need": history}), 409
    bars = store.window(key, history)

    try:
        runtime = Runtime(symbol=str(validated["symbol"]))
        libraries = _parse_run_libraries(validated.get("libraries")) or None
        session = runtime.create_session(
            validated["script"],
            bars,
            inputs=validated.get("inputs") or None,
            libraries=libraries,
            profiler=bool(validated.get("profiler")),
            mode="interpret",
        )
    except Exception as exc:
        logger.warning("data session create failed: %s", exc)
        return jsonify(
            {
                "status": "error",
                "code": "SESSION_CREATE_FAILED",
                "message": _public_exc_message(exc),
            }
        ), 400

    try:
        session_id = SESSIONS.put(session)
    except RuntimeError as exc:
        return jsonify(
            {
                "status": "error",
                "code": "SESSIONS_FULL",
                "message": _public_exc_message(exc),
            }
        ), 503

    data_live.bind_session(session, key, bars[-1])
    binding = data_live.binding_of(session)
    SESSIONS.track(
        session_id,
        script=validated["script"],
        symbol=str(validated["symbol"]),
        inputs=validated.get("inputs") or {},
        libraries=libraries or [],
        profiler=bool(validated.get("profiler")),
        bars=list(bars),
        binding=(
            {"key": binding.key.text, "last_time": binding.last_time, "last_bar": dict(binding.last_bar)}
            if binding is not None
            else None
        ),
    )
    extra: dict[str, Any] = {
        "sessions": SESSIONS.stats(),
        "cache": "hit",
        "data": {"key": key.text, "count": have, "newest": status["newest"]},
    }
    return jsonify(_session_envelope(session.result(), session_id, extra)), 200


def _make_session_journal_recorder(session_id: str) -> Callable[[str, Any], None]:
    """Report ``live.sync_session`` mutations into the session journal.

    Mirrors the in-place ``update_last_bar`` / ``append_bars`` calls so a
    restart rebuilds from the same bars the object holds.
    """

    def _record_applied(kind: str, payload: Any) -> None:
        if kind == "tick" and isinstance(payload, dict):
            SESSIONS.note_tick(session_id, payload)
        elif kind == "append" and isinstance(payload, list):
            SESSIONS.note_append(session_id, payload)

    return _record_applied


@app.route("/data/session/<session_id>/tick", methods=["POST"])
@require_api_key
def data_session_tick_route(session_id: str):
    """Fetch candles since the stored newest and advance the bound session.

    Closed bars are persisted and appended; the forming bar is re-ticked in
    place. Body is ``{exchange, symbol}`` only and must name the bound series.
    """
    session, missing = _load_session(session_id)
    if missing is not None:
        return jsonify(missing[0]), missing[1]

    payload: dict[str, Any] = dict(request.get_json(silent=True) or {})
    validated, err = validate(payload, DATA_SESSION_TICK_SCHEMA)
    if err is not None:
        return _err_to_dict(err)

    # Re-read the binding from the (possibly just rebuilt) session: after a
    # restart the object is fresh and the persisted tail is the anchor.
    binding = data_live.binding_of(session)
    if binding is None or not binding.key.identity_matches(validated["exchange"], validated["symbol"]):
        return jsonify(
            {
                "status": "error",
                "code": "SESSION_KEY_MISMATCH",
                "message": "Session is bound to a different series key.",
                "session_id": session_id,
            }
        ), 409

    try:
        outcome = data_api.sync_data_session(
            session,
            binding,
            is_alive=lambda: SESSIONS.get(session_id) is session,
            on_apply=_make_session_journal_recorder(session_id),
        )
    except series_store.DataError as exc:
        return jsonify({**exc.body(), "session_id": session_id}), exc.status
    except Exception as exc:
        logger.warning("data session tick failed: %s", exc)
        return jsonify(
            {
                "status": "error",
                "code": "SESSION_TICK_FAILED",
                "message": _public_exc_message(exc),
                "session_id": session_id,
            }
        ), 400

    if not outcome.unchanged:
        fresh = data_live.binding_of(session)
        if fresh is not None:
            SESSIONS.note_binding(
                session_id,
                {"key": fresh.key.text, "last_time": fresh.last_time, "last_bar": dict(fresh.last_bar)},
            )

    extra: dict[str, Any] = {
        "session_id": session_id,
        "appended": outcome.appended,
        "forming": outcome.forming,
        "unchanged": outcome.unchanged,
        "stale": outcome.stale,
    }
    tail_len = 0 if outcome.unchanged else outcome.grown + (1 if outcome.reticked else 0)
    return jsonify(_maybe_delta_envelope(outcome.result, session_id, extra, validated, tail_len)), 200


@app.route("/optimize", methods=["POST"])
def optimize_strategy():
    """Search strategy ``input.*`` values over N interpret runs.

    Uses :func:`pynescript.optimize.run_study` (real Runtime, not
    ``/backtest/quick``). Free-tier bar/rate/concurrency helpers no-op
    unless ``FREE_TIER_LIMITS`` is truthy.
    """
    payload: dict[str, Any] = dict(request.get_json(silent=True) or {})
    body, status = execute_optimize_payload(payload)
    return jsonify(body), status


@app.route("/compile/prewarm", methods=["POST"])
def compile_prewarm():
    """Warm shared Numba kernels and optionally compile Pine sources (H2).

    Free readiness hook for deploy/probes. Body (all optional)::

        {
          "scripts": ["//@version=6\\nindicator(\\"x\\")\\nplot(close)"],
          "force": false
        }

    Without Numba, returns 200 with ``has_numba: false`` (object-mode compile
    still works; numeric JIT skip is expected). Does not execute scripts on
    OHLCV — only populates IR / disk caches.

    Rate/concurrency helpers no-op unless ``FREE_TIER_LIMITS`` is truthy
    (audit 2026-08-10 free-tier guards).
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
        _dbg("POST /compile/prewarm force=%s scripts=%d", force, len(sources))
        try:
            from pynescript.compiler.engine import prewarm_scripts

            result = prewarm_scripts(sources or None, force_builtins=force)
            _HOST_COMPILE_PREWARMED = True
        except Exception as exc:
            logger.warning("prewarm error: %s", exc)
            _dbg("POST /compile/prewarm failed: %s", exc)
            return jsonify(
                {
                    "status": "error",
                    "code": "PREWARM_ERROR",
                    "message": "Prewarm failed",
                }
            ), 500

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        _dbg(
            "POST /compile/prewarm done in %.1fms ok=%s failed=%s",
            elapsed_ms,
            result.get("scripts_ok"),
            result.get("scripts_failed"),
        )
        body = {
            "status": "success",
            "prewarm_ms": round(elapsed_ms, 2),
            **result,
        }
        return jsonify(body), 200
    finally:
        release_free_slot()


# Optional run fields a WS ``run`` frame may carry. Mirrors RUN_SCHEMA
# (backend/middleware/schemas.py) so the WS channel has the same surface as
# POST /run. ``libraries`` used to be missing here, so published-library
# imports (``import ns/Name/1``) resolved over REST but failed over WS.
_WS_RUN_OPTIONAL_FIELDS = (
    "symbol",
    "mode",
    "data_source",
    "data_options",
    "inputs",
    "profiler",
    "libraries",
    "timeout_seconds",
    "from_bar",
    "to_bar",
)


def _ws_envelope_to_payload(msg: dict[str, Any]) -> dict[str, Any]:
    """Map a WS ``run`` frame to the REST body shape.

    Null optionals are omitted — the schema rejects null for typed optional
    fields like ``symbol`` (it treats null as "use default", but keeping the
    frame faithful avoids surprising defaults).
    """
    payload: dict[str, Any] = {}
    if "script" in msg:
        payload["script"] = msg.get("script")
    if "data" in msg:
        payload["data"] = msg.get("data")
    for opt in _WS_RUN_OPTIONAL_FIELDS:
        if opt in msg and msg.get(opt) is not None:
            payload[opt] = msg[opt]
    return payload


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

        The run frame accepts the same optional fields as ``POST /run``
        (``symbol``, ``mode``, ``inputs``, ``profiler``, ``libraries``, …) —
        see {@link _WS_RUN_OPTIONAL_FIELDS}.
        """
        while True:
            raw = ws.receive()
            if raw is None:
                break
            try:
                msg = json.loads(raw) if isinstance(raw, str) else json.loads(raw.decode("utf-8"))
            except Exception:
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
            payload = _ws_envelope_to_payload(msg)
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
    from backend.middleware.schemas import RUN_BATCH_MAX_SCRIPTS
    from backend.middleware.schemas import RUN_BATCH_SCHEMA

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

    blocked = _blocked_webhook_error(data.get("webhook_url") or "")
    if blocked is not None:
        body, code = blocked
        return jsonify(body), code

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
    except Exception as e:
        logger.warning("batch data source: %s", e)
        return jsonify(
            {
                "status": "error",
                "code": "DATA_SOURCE_ERROR",
                "message": "Failed to configure data source",
            }
        ), 400

    libraries = _parse_run_libraries(data.get("libraries"))
    timeout_kw = _timeout_seconds_kwarg(data.get("timeout_seconds"))

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
                libraries=libraries or None,
                **timeout_kw,
            )
        except Exception as e:  # per-script isolation
            logger.warning("batch script error: %s", e)
            results.append(
                {
                    "id": sid,
                    "status": "error",
                    "code": "EXECUTION_ERROR",
                    "message": "Script execution failed",
                }
            )
            continue
        if "error" in result:
            err_item: dict[str, Any] = {
                "id": sid,
                "status": "error",
                "code": "EXECUTION_ERROR",
                "message": _sanitize_error_for_response(str(result["error"])),
            }
            if result.get("timed_out"):
                err_item["timed_out"] = True
            results.append(err_item)
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
        if result.get("timed_out"):
            item["timed_out"] = True
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
        except Exception as e:
            logger.warning("batch alert forward: %s", e)
            item["alert_forward_error"] = "Alert forwarding failed"
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
if datafeed_bp is not None:
    app.register_blueprint(datafeed_bp)
app.register_blueprint(data_api.bp)
app.register_error_handler(series_store.DataError, data_api.data_error_response)
app.register_blueprint(runner_bp)
try:
    from backend.runner.scheduler import maybe_start_background

    maybe_start_background()
except Exception:  # boot must not fail if runner misconfigured
    logger.exception("pyne runner scheduler failed to start")


# Apply the PYNE_DEBUG logging policy at import so gunicorn workers, `flask run`
# and `python -m backend.app` all get the same levels without extra flags.
try:
    from backend.logging_setup import configure_logging as _configure_logging

    _LOGGING_POLICY = _configure_logging()
    configure_logging = _configure_logging
except Exception:  # logging setup must never block boot
    _LOGGING_POLICY = {"enabled": False, "error": "configure_logging failed"}
    logger.warning("logging setup failed; using defaults", exc_info=True)


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


@app.errorhandler(413)
def payload_too_large(_e):
    """JSON 413 for bodies over ``MAX_CONTENT_LENGTH`` (no Werkzeug HTML)."""
    return jsonify(
        {
            "status": "error",
            "code": "PAYLOAD_TOO_LARGE",
            "message": "Request body exceeds the 5 MB limit.",
        }
    ), 413


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


def main() -> None:
    """Run the Flask dev server.

    Entry point for ``python -m backend.app``, ``python -m backend`` and the
    ``pyne-backend`` console script shipped by the ``hoox-pyne-backend`` wheel.
    """
    # Audit 2026-07-05 / S11: default to localhost for the dev runner. Use
    # HOST=0.0.0.0 to expose the dev server to other machines if needed.
    import logging

    _policy = configure_logging(force=True)
    if not _policy["handler_installed"]:
        logging.basicConfig(
            level=getattr(logging, _policy["level"], logging.INFO),
            format="%(levelname)s %(name)s: %(message)s",
        )
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5002"))
    logger.info(
        "Pro API on http://%s:%s  websocket=%s  debug=%s",
        host,
        port,
        sock is not None,
        _policy["enabled"],
    )
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
