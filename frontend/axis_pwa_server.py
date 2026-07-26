from __future__ import annotations
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "dist"
PORT = int(os.environ.get("PORT", "8081"))
HOST = os.environ.get("HOST", "0.0.0.0")

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        if self.path.startswith("/assets/"):
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        else:
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def do_GET(self):
        # SPA fallback — never rewrite real static assets (plugins, assets, pyodide wheels)
        path = self.translate_path(self.path)
        req = self.path.split("?", 1)[0]
        is_static = (
            req.startswith("/assets/")
            or req.startswith("/plugins/")
            or req.startswith("/vendor/")
            or req.startswith("/pyodide/")
            or req.endswith(
                (
                    ".js",
                    ".css",
                    ".png",
                    ".webmanifest",
                    ".json",
                    ".map",
                    ".svg",
                    ".ico",
                    ".whl",
                    ".py",
                    ".wasm",
                    ".data",
                    ".zip",
                )
            )
        )
        if not is_static and (
            not os.path.exists(path)
            or (os.path.isdir(path) and not os.path.exists(os.path.join(path, "index.html")))
        ):
            self.path = "/index.html"
        return super().do_GET()

if __name__ == "__main__":
    os.chdir(ROOT)
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[axis-pwa] http://{HOST}:{PORT} -> {ROOT}", flush=True)
    httpd.serve_forever()
