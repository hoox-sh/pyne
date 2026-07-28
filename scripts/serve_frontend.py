#!/usr/bin/env python3
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
