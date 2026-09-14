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

"""Optional hosted runner HTTP surface (``/scripts``, ``/cron/*``).

Registered always; handlers 404 with ``RUNNER_DISABLED`` unless
``PYNE_RUNNER`` is on. When ``ADMIN_TOKEN`` is set, mutating routes require it.
"""

from __future__ import annotations

import hmac
import os

from functools import wraps
from typing import Any

from flask import Blueprint
from flask import jsonify
from flask import request

from backend.alert_forwarder import normalize_webhook_url
from backend.middleware.auth import _provided_admin_token
from backend.middleware.schemas import validate
from backend.runner import runner_enabled
from backend.runner import store
from backend.runner.scheduler import tick


bp = Blueprint("runner", __name__)

SCRIPT_PUT_SCHEMA: dict[str, tuple[type, bool, Any]] = {
    "id": (str, True, ""),
    "script": (str, True, ""),
    "name": (str, False, ""),
    "symbol": (str, False, "BTCUSDT"),
    "timeframe": (str, False, "1d"),
    "mode": (str, False, "auto"),
    "enabled": (bool, False, True),
    "data_source": (str, False, "mock"),
    "data_options": (dict, False, {}),
    "period": (str, False, "6mo"),
    "max_bars": (int, False, 5000),
    "webhook_url": (str, False, ""),
    "forward_alerts": (bool, False, True),
    "alert_last_bar": (bool, False, True),
    "alert_batch": (bool, False, True),
    "inputs": (dict, False, {}),
    "libraries": (list, False, []),
}

CRON_JOBS_SCHEMA: dict[str, tuple[type, bool, Any]] = {
    "jobs": (list, True, []),
}

CRON_RUN_SCHEMA: dict[str, tuple[type, bool, Any]] = {
    "force": (bool, False, False),
    "script_id": (str, False, ""),
}


def _disabled():
    return (
        jsonify(
            {
                "status": "error",
                "code": "RUNNER_DISABLED",
                "message": "Set PYNE_RUNNER=1 to enable the hosted script runner.",
            }
        ),
        404,
    )


def _require_runner(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not runner_enabled():
            return _disabled()
        return f(*args, **kwargs)

    return decorated


def _require_runner_write(f):
    """Admin token when configured; open in local/dev (same as free /run)."""

    @wraps(f)
    @_require_runner
    def decorated(*args, **kwargs):
        expected = (os.environ.get("ADMIN_TOKEN") or "").strip()
        if expected:
            provided = _provided_admin_token()
            if not provided or not hmac.compare_digest(provided, expected):
                return (
                    jsonify(
                        {
                            "status": "error",
                            "code": "FORBIDDEN",
                            "message": "Admin token required for runner writes.",
                        }
                    ),
                    403,
                )
        return f(*args, **kwargs)

    return decorated


@bp.route("/scripts", methods=["GET"])
@_require_runner
def list_scripts():
    rows = store.list_scripts(include_source=False)
    return jsonify({"status": "success", "scripts": rows, "count": len(rows)})


@bp.route("/scripts", methods=["POST"])
@_require_runner_write
def put_script():
    data, err = validate(request.get_json(silent=True) or {}, SCRIPT_PUT_SCHEMA)
    if err is not None:
        return err
    wh = data.get("webhook_url") or ""
    if isinstance(wh, str) and wh.strip():
        if normalize_webhook_url(wh) is None:
            return (
                jsonify(
                    {
                        "status": "error",
                        "code": "WEBHOOK_URL_BLOCKED",
                        "message": "webhook_url is invalid or blocked.",
                    }
                ),
                400,
            )
    try:
        rec = store.put_script(data)
    except ValueError as exc:
        return jsonify({"status": "error", "code": "INVALID_SCRIPT", "message": str(exc)}), 400
    return jsonify({"status": "success", "script": rec}), 201


@bp.route("/scripts/<script_id>", methods=["GET"])
@_require_runner
def get_script(script_id: str):
    rec = store.get_script(script_id, include_source=True)
    if rec is None:
        return jsonify({"status": "error", "code": "NOT_FOUND", "message": "Unknown script."}), 404
    state = store.get_cron_state(script_id)
    rec["cron"] = state
    return jsonify({"status": "success", "script": rec})


@bp.route("/scripts/<script_id>", methods=["DELETE"])
@_require_runner_write
def delete_script(script_id: str):
    if not store.delete_script(script_id):
        return jsonify({"status": "error", "code": "NOT_FOUND", "message": "Unknown script."}), 404
    return jsonify({"status": "success", "deleted": script_id})


@bp.route("/cron/jobs", methods=["GET"])
@_require_runner
def get_cron_jobs():
    jobs = []
    for rec in store.list_scripts(include_source=False):
        state = store.get_cron_state(str(rec["id"]))
        jobs.append({**rec, "cron": state})
    return jsonify({"status": "success", "jobs": jobs, "count": len(jobs)})


@bp.route("/cron/jobs", methods=["PUT"])
@_require_runner_write
def put_cron_jobs():
    data, err = validate(request.get_json(silent=True) or {}, CRON_JOBS_SCHEMA)
    if err is not None:
        return err
    updated = []
    for job in data.get("jobs") or []:
        if not isinstance(job, dict):
            continue
        sid = str(job.get("script_id") or job.get("id") or "").strip()
        if not sid:
            continue
        enabled = bool(job.get("enabled", True))
        if store.set_enabled(sid, enabled=enabled):
            updated.append({"script_id": sid, "enabled": enabled})
    return jsonify({"status": "success", "updated": updated, "count": len(updated)})


@bp.route("/cron/run", methods=["POST"])
@_require_runner_write
def cron_run():
    data, err = validate(request.get_json(silent=True) or {}, CRON_RUN_SCHEMA)
    if err is not None:
        return err
    force = bool(data.get("force"))
    sid = str(data.get("script_id") or "").strip() or None
    result = tick(force=force, script_id=sid)
    return jsonify(result)
