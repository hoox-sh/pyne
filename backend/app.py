# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

"""Pynescript Pro API Server.

Flask server for live chart previews, backtests, and API key management.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from flask import Flask, g, jsonify, request
from flask_cors import CORS

from backend.api.preview import backtest_bp, preview_bp
from backend.middleware.auth import get_key_store, require_api_key, track_usage
from backend.runtime import Runtime

app = Flask(__name__)
CORS(app)


@app.route("/", methods=["GET"])
def health_check():
    return jsonify(
        {
            "status": "healthy",
            "service": "pynescript-pro-api",
            "version": "1.0.0",
            "timestamp": int(time.time()),
            "endpoints": {
                "GET /": "This health check",
                "POST /run": "Run Pine Script (free)",
                "POST /preview/chart": "Chart thumbnail (Pro)",
                "POST /preview/indicator": "Indicator preview (Pro)",
                "POST /backtest/quick": "Quick backtest (Pro)",
                "POST /auth/create_key": "Create API key (requires admin)",
                "GET /auth/usage": "Get usage stats (Pro)",
            },
        }
    )


@app.route("/run", methods=["POST"])
def run_pine_script():
    """Execute Pine Script with provided data. Free tier endpoint."""
    data = request.get_json() or {}
    script = data.get("script", "")
    ohlcv = data.get("data", [])

    if not script:
        return jsonify(
            {
                "status": "error",
                "code": "NO_SCRIPT",
                "message": "No 'script' provided.",
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

    runtime = Runtime()
    result = runtime.run(script, ohlcv)

    if "error" in result:
        return jsonify(
            {
                "status": "error",
                "code": "EXECUTION_ERROR",
                "message": result["error"],
            }
        ), 500

    return jsonify(
        {
            "status": "success",
            "plots": result.get("plots", []),
            "count": result.get("count", 0),
        }
    )


@app.route("/auth/create_key", methods=["POST"])
def create_api_key():
    """Create a new API key. In production, this requires admin auth."""
    data = request.get_json() or {}
    tier = data.get("tier", "hobby")
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
    data = request.get_json() or {}
    raw_key = data.get("api_key", "")

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
    app.run(host="0.0.0.0", port=5002, debug=False)
