// End-to-end test of the Bun static file server.

import { describe, expect, it, beforeAll, afterAll } from 'bun:test';
import { resolve, join } from 'node:path';

const ROOT = resolve(import.meta.dir, '..');
const PORT = 18099;  // use a non-default port to avoid conflicts
let server: ReturnType<typeof Bun.serve> | undefined;

beforeAll(async () => {
    // Spawn the server in a child process so we test the real entry point.
    const proc = Bun.spawn(['bun', 'run', join(ROOT, 'server.ts')], {
        cwd: join(ROOT, '..'),
        env: { ...process.env, PORT: String(PORT), HOST: '127.0.0.1', NODE_ENV: 'test' },
        stdout: 'pipe', stderr: 'pipe',
    });
    // Wait until the server is accepting connections.
    for (let i = 0; i < 50; i++) {
        try {
            const r = await fetch(`http://127.0.0.1:${PORT}/`);
            if (r.ok) { server = proc as any; return; }
        } catch (_) { /* not ready */ }
        await new Promise((r) => setTimeout(r, 100));
    }
    throw new Error('Server did not start within 5s');
});

afterAll(() => {
    // The child process will be killed when this test runner exits.
});

describe('Static server', () => {
    it('serves index.html at /', async () => {
        const r = await fetch(`http://127.0.0.1:${PORT}/`);
        expect(r.status).toBe(200);
        const ct = r.headers.get('content-type');
        expect(ct).toContain('text/html');
        const text = await r.text();
        expect(text).toContain('<title>SuperChart Lite');
    });

    it('serves manifest.webmanifest with the right MIME type', async () => {
        const r = await fetch(`http://127.0.0.1:${PORT}/manifest.webmanifest`);
        expect(r.status).toBe(200);
        expect(r.headers.get('content-type')).toContain('manifest+json');
    });

    it('serves a JS file with application/javascript', async () => {
        const r = await fetch(`http://127.0.0.1:${PORT}/src/main.js`);
        expect(r.status).toBe(200);
        expect(r.headers.get('content-type')).toContain('javascript');
    });

    it('falls back to index.html for unknown paths (SPA)', async () => {
        const r = await fetch(`http://127.0.0.1:${PORT}/this/path/does/not/exist`);
        expect(r.status).toBe(200);
        expect(r.headers.get('content-type')).toContain('text/html');
    });

    it('rejects path traversal', async () => {
        const r = await fetch(`http://127.0.0.1:${PORT}/../package.json`);
        // Either 403 (blocked) or 200 (but body should be index.html, not the file)
        if (r.status === 200) {
            const text = await r.text();
            expect(text).not.toContain('"pynescript"');
        } else {
            expect(r.status).toBe(403);
        }
    });

    it('responds to CORS preflight (OPTIONS)', async () => {
        const r = await fetch(`http://127.0.0.1:${PORT}/`, { method: 'OPTIONS' });
        expect(r.status).toBe(204);
        expect(r.headers.get('access-control-allow-origin')).toBe('*');
    });

    it('sets ETag and honors If-None-Match', async () => {
        const r1 = await fetch(`http://127.0.0.1:${PORT}/src/main.js`);
        const etag = r1.headers.get('etag');
        expect(etag).toBeTruthy();
        const r2 = await fetch(`http://127.0.0.1:${PORT}/src/main.js`, {
            headers: { 'if-none-match': etag! },
        });
        expect(r2.status).toBe(304);
    });
});
