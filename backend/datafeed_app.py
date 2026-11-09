# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Standalone CCXT datafeed gateway (compose service ``datafeed``).

Same blueprint as the Pro API (``GET /datafeed/*``, ``WS /datafeed/watch``)
so AXIS can talk to a dedicated process. RAM sessions live in this process
only — do not split ``/datafeed/session`` and ``/datafeed/watch`` across hosts.
"""

from __future__ import annotations

import os

from flask import Flask
from flask import make_response
from flask import request

from backend.api.datafeed import datafeed_bp
from backend.api.datafeed import gateway_health


def create_app() -> Flask:
    """Flask app with only the datafeed blueprint + optional watch WS."""
    application = Flask(__name__)
    # Same 5 MB body cap as backend.app — a huge POST can OOM this process
    # before gunicorn --timeout fires (audit 2026-07-05, S1).
    application.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
    application.register_blueprint(datafeed_bp)
    try:
        from flask_sock import Sock

        from backend.api.datafeed import register_watch_route

        register_watch_route(Sock(application))
    except ImportError:
        pass

    @application.get("/")
    def root():  # type: ignore[no-untyped-def]
        return gateway_health()

    @application.after_request
    def _cors(resp):  # type: ignore[no-untyped-def]
        origin = request.headers.get("Origin")
        if origin:
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Vary"] = "Origin"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS, HEAD"
            resp.headers["Access-Control-Allow-Headers"] = (
                "Content-Type, Authorization, X-Admin-Token, X-Api-Key, X-AXIS-Client, Accept"
            )
            resp.headers["Access-Control-Max-Age"] = "86400"
        return resp

    @application.before_request
    def _preflight():  # type: ignore[no-untyped-def]
        if request.method != "OPTIONS":
            return None
        return _cors(make_response("", 204))

    return application


app = create_app()


def main() -> None:
    host = os.environ.get("HOST", "0.0.0.0")  # noqa: S104 — container must listen on all ifaces
    port = int(os.environ.get("PORT", "8080"))
    app.run(host=host, port=port)


if __name__ == "__main__":
    main()
