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

"""Request body schema validation for the Pynescript Pro API.

Audit 2026-07-05 / S9: every ``request.get_json()`` is validated against an
explicit schema. Unknown fields are rejected (no silent type coercion).
The validator is hand-rolled (no pydantic/marshmallow dependency) because
the API surface is small (~6 endpoints) and the existing patterns are
simple.

A schema is a dict mapping field name → ``(type, required, default)``. The
``_validate`` helper returns either the validated dict or a Flask response
tuple for invalid input. Endpoints can do::

    data, err = validate(request.get_json() or {}, REQUIRED_SCRIPT_FIELD)
    if err:
        return err
"""

from __future__ import annotations

from typing import Any

from flask import jsonify


def _expect_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _expect_list(value: Any) -> list | None:
    return value if isinstance(value, list) else None


def _expect_dict(value: Any) -> dict | None:
    return value if isinstance(value, dict) else None


# Schema for the free /run endpoint. Pine script source + OHLCV bar data.
# We keep the bar-list check loose (length >= 1, no per-bar schema) to match
# existing behaviour; tightening that is its own audit item.
RUN_SCHEMA: dict[str, tuple[type, bool, Any]] = {
    "script": (str, True, ""),
    "data": (list, True, []),
    # Optional request.* data source wiring
    "symbol": (str, False, "CHART"),
    "data_source": (str, False, ""),  # ""|mock|ccxt|ccxtpro|yahoo|alphavantage
    "data_options": (dict, False, {}),  # exchange, api_key, seed, start_price, …
    "mode": (str, False, "auto"),  # interpret|compile|auto (default auto = compile+fallback)
    # Pine input.* overrides keyed by title (AXIS Script Settings)
    "inputs": (dict, False, {}),
}

# Shared OHLCV + many scripts (AXIS multi-indicator). Nested script objects
# are validated in the route (schema helper is flat only).
RUN_BATCH_SCHEMA: dict[str, tuple[type, bool, Any]] = {
    "scripts": (list, True, []),
    "data": (list, True, []),
    "symbol": (str, False, "CHART"),
    "data_source": (str, False, ""),
    "data_options": (dict, False, {}),
    "mode": (str, False, "auto"),
}

# Hard cap to keep free-tier /run/batch bounded.
RUN_BATCH_MAX_SCRIPTS = 8


# Schema for /preview/chart.
PREVIEW_CHART_SCHEMA: dict[str, tuple[type, bool, Any]] = {
    "script": (str, False, ""),
    "data": (dict, True, {}),
    "options": (dict, False, {}),
}


# Schema for /preview/indicator.
PREVIEW_INDICATOR_SCHEMA: dict[str, tuple[type, bool, Any]] = {
    "expression": (str, True, ""),
    "data": (dict, True, {}),
    "options": (dict, False, {}),
}


# Schema for /backtest/quick.
BACKTEST_QUICK_SCHEMA: dict[str, tuple[type, bool, Any]] = {
    "script": (str, True, ""),
    "data": (dict, False, {}),
    "initial_capital": (float, False, 10000.0),
    "mock_data": (bool, False, False),
    "mock_bars": (int, False, 252),
}


# Schema for /auth/create_key.
CREATE_KEY_SCHEMA: dict[str, tuple[type, bool, Any]] = {
    "tier": (str, False, "hobby"),
}


# Schema for /auth/validate.
VALIDATE_KEY_SCHEMA: dict[str, tuple[type, bool, Any]] = {
    "api_key": (str, True, ""),
}


def _coerce(value: Any, py_type: type) -> tuple[Any, str | None]:
    """Return ``(value, error_message)``. ``error_message`` is None on success."""
    # bool is a subclass of int in Python; treat it as a separate type.
    if py_type is bool:
        if not isinstance(value, bool):
            return value, "must be a boolean"
        return value, None
    if py_type is int:
        if isinstance(value, bool) or not isinstance(value, int):
            return value, "must be an integer"
        return value, None
    if py_type is float:
        if isinstance(value, bool):
            return value, "must be a number"
        if not isinstance(value, (int, float)):
            return value, "must be a number"
        return float(value), None
    if py_type is str:
        coerced = _expect_str(value)
        if coerced is None:
            return value, "must be a string"
        return coerced, None
    if py_type is list:
        coerced = _expect_list(value)
        if coerced is None:
            return value, "must be a list"
        return coerced, None
    if py_type is dict:
        coerced = _expect_dict(value)
        if coerced is None:
            return value, "must be an object"
        return coerced, None
    return value, None  # pragma: no cover - unknown type, accept as-is


def validate(body: Any, schema: dict[str, tuple[type, bool, Any]]) -> tuple[dict[str, Any] | None, tuple | None]:
    """Validate ``body`` against ``schema``.

    Returns ``(data, error_response)``. Exactly one is non-None. On success,
    ``data`` is a dict containing only the schema fields (no extras).
    """
    if not isinstance(body, dict):
        return None, (
            jsonify(
                {
                    "status": "error",
                    "code": "INVALID_BODY",
                    "message": "Request body must be a JSON object.",
                }
            ),
            400,
        )

    out: dict[str, Any] = {}
    for field_name, (py_type, required, default) in schema.items():
        if field_name not in body:
            if required:
                return None, (
                    jsonify(
                        {
                            "status": "error",
                            "code": "MISSING_FIELD",
                            "message": f"Missing required field: {field_name!r}.",
                        }
                    ),
                    400,
                )
            out[field_name] = default
            continue
        value = body[field_name]
        # Optional fields: null/empty treated as "use default" (common for WS
        # clients that send "symbol": null when unset).
        if value is None and not required:
            out[field_name] = default
            continue
        coerced, err = _coerce(value, py_type)
        if err is not None:
            return None, (
                jsonify(
                    {
                        "status": "error",
                        "code": "INVALID_FIELD",
                        "message": f"Field {field_name!r} {err}.",
                    }
                ),
                400,
            )
        out[field_name] = coerced

    # Reject unexpected fields. Stricter than pydantic's default but matches
    # the spirit of S9: don't silently accept unknown input.
    extras = set(body) - set(schema)
    if extras:
        return None, (
            jsonify(
                {
                    "status": "error",
                    "code": "UNKNOWN_FIELDS",
                    "message": f"Unexpected field(s): {sorted(extras)}.",
                }
            ),
            400,
        )

    return out, None
