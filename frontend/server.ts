// Bun static file server for the SuperChart Lite PWA.
// `bun run frontend/server.ts` — serves frontend/ on http://localhost:8081.
//
// Features:
//   • Zero dependencies.
//   • SPA-style fallback: paths without a file extension are served
//     index.html so deep links work after the SW caches the shell.
//   • Sets sane Content-Type + Cache-Control per asset class.
//   • Permissive CORS so the served origin can be hit from a backend on
//     another port (e.g. Flask on :5002).
//   • Graceful shutdown on SIGINT.

import { extname, join, normalize, resolve, sep } from 'node:path';
import { existsSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(fileURLToPath(new URL('.', import.meta.url)));
const PORT = Number(process.env.PORT || 8081);
const HOST = process.env.HOST || '127.0.0.1';

const MIME: Record<string, string> = {
    '.html': 'text/html; charset=utf-8',
    '.js':   'application/javascript; charset=utf-8',
    '.mjs':  'application/javascript; charset=utf-8',
    '.css':  'text/css; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.webmanifest': 'application/manifest+json; charset=utf-8',
    '.png':  'image/png',
    '.jpg':  'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif':  'image/gif',
    '.svg':  'image/svg+xml',
    '.ico':  'image/x-icon',
    '.txt':  'text/plain; charset=utf-8',
    '.map':  'application/json; charset=utf-8',
    '.woff': 'font/woff',
    '.woff2':'font/woff2',
    '.wasm': 'application/wasm',
};

function contentTypeFor(path: string): string {
    const ct = MIME[extname(path).toLowerCase()];
    return ct ?? 'application/octet-stream';
}

function safeJoin(root: string, urlPath: string): string | null {
    // Strip query string + hash + decode
    const noQuery = urlPath.split('?')[0] ?? urlPath;
    const noHash = noQuery.split('#')[0] ?? noQuery;
    let p = decodeURIComponent(noHash);
    if (p === '/') p = '/index.html';
    // Block path traversal
    const full = normalize(join(root, p));
    if (!full.startsWith(root + sep) && full !== root) return null;
    return full;
}

const CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Admin-Token',
};

const server = Bun.serve({
    port: PORT,
    hostname: HOST,
    development: process.env.NODE_ENV !== 'production',

    async fetch(req: Request): Promise<Response> {
        if (req.method === 'OPTIONS') {
            return new Response(null, { status: 204, headers: CORS_HEADERS });
        }
        if (req.method !== 'GET' && req.method !== 'HEAD') {
            return new Response('Method Not Allowed', { status: 405 });
        }

        const url = new URL(req.url);
        const path = safeJoin(ROOT, url.pathname);
        if (!path) return new Response('Forbidden', { status: 403 });

        if (existsSync(path) && statSync(path).isFile()) {
            const file = Bun.file(path);
            const etag = `"${(await file.arrayBuffer()).byteLength.toString(16)}-${file.lastModified.toString(16)}"`;
            const headers: Record<string, string> = {
                'Content-Type': contentTypeFor(path),
                'ETag': etag,
                ...CORS_HEADERS,
            };
            // Long cache for fingerprinted assets, short for HTML.
            if (path.endsWith('index.html')) headers['Cache-Control'] = 'no-cache';
            else if (path.includes(`${sep}src${sep}`) || path.includes(`${sep}assets${sep}`)) {
                headers['Cache-Control'] = 'public, max-age=300';
            } else {
                headers['Cache-Control'] = 'public, max-age=60';
            }
            if (req.headers.get('if-none-match') === etag) {
                return new Response(null, { status: 304, headers });
            }
            return new Response(file, { headers });
        }

        // SPA fallback — let the SW / index.html handle it.
        const indexPath = join(ROOT, 'index.html');
        if (existsSync(indexPath)) {
            return new Response(Bun.file(indexPath), {
                headers: {
                    'Content-Type': MIME['.html']!,
                    'Cache-Control': 'no-cache',
                    ...CORS_HEADERS,
                },
            });
        }
        return new Response('Not Found', { status: 404 });
    },
});

console.log(`[superchart] serving ${ROOT}`);
console.log(`[superchart] http://${server.hostname}:${server.port}`);

process.on('SIGINT', () => {
    console.log('\n[superchart] shutting down…');
    server.stop();
    process.exit(0);
});
