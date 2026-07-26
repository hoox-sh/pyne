// Minimal static server for AXIS dist/
import { join, resolve } from "node:path";
const ROOT = resolve(import.meta.dir, "dist");
const PORT = Number(process.env.PORT || 8081);
const HOST = process.env.HOST || "0.0.0.0";

const MIME: Record<string, string> = {
  ".html": "text/html; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json",
  ".webmanifest": "application/manifest+json",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".woff2": "font/woff2",
  ".map": "application/json",
};

function contentType(path: string) {
  const i = path.lastIndexOf(".");
  return MIME[i >= 0 ? path.slice(i) : ""] || "application/octet-stream";
}

const server = Bun.serve({
  hostname: HOST,
  port: PORT,
  async fetch(req) {
    const url = new URL(req.url);
    let pathname = decodeURIComponent(url.pathname);
    if (pathname === "/") pathname = "/index.html";
    // SPA fallback for client routes
    let filePath = join(ROOT, pathname);
    let file = Bun.file(filePath);
    if (!(await file.exists())) {
      filePath = join(ROOT, "index.html");
      file = Bun.file(filePath);
    }
    if (!(await file.exists())) {
      return new Response("Not found", { status: 404 });
    }
    return new Response(file, {
      headers: {
        "Content-Type": contentType(filePath),
        "Cache-Control": pathname.startsWith("/assets/")
          ? "public, max-age=31536000, immutable"
          : "no-cache",
      },
    });
  },
});

console.log(`[axis-pwa] http://${server.hostname}:${server.port} → ${ROOT}`);
