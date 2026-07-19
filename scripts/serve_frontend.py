#!/usr/bin/env python3
# Copyright (C) 2025 jango-blockchained
# SPDX-License-Identifier: LGPL-3.0-or-later
"""Serve frontend/ with no-cache headers so SuperChart JS edits always load.

Plain ``python -m http.server`` lets browsers cache script.js forever, which
makes frontend fixes appear to "do nothing" after a refresh.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import os
import socketserver
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "frontend"


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        # Force revalidation on every load for HTML/JS/CSS during development.
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, format: str, *args) -> None:  # noqa: A003 - stdlib signature
        # Quieter logs; still print errors
        if args and str(args[1]).startswith("4"):
            super().log_message(format, *args)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve SuperChart Lite frontend with no-cache headers")
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    if not ROOT.is_dir():
        raise SystemExit(f"frontend dir not found: {ROOT}")

    os.chdir(ROOT)
    handler = functools.partial(NoCacheHandler, directory=str(ROOT))
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer((args.host, args.port), handler) as httpd:
        print(f"SuperChart Lite → http://127.0.0.1:{args.port}/  (dir={ROOT}, Cache-Control: no-store)", flush=True)
        print("API expected at http://127.0.0.1:5002  (make run)", flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped", flush=True)


if __name__ == "__main__":
    main()
