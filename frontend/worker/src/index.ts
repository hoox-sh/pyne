// Pynescript SuperChart — Cloudflare Worker.
// Serves the JSON API used by the PWA.  Designed to run alongside the PWA
// hosted on Cloudflare Pages (or any static host); CORS is wide-open for
// the configured origin and for the local-dev `http://localhost:8081`.

import { handleRun } from './runtime';
import { handleKeys } from './keys';
import { SessionDO } from './durable-objects/session';

export { SessionDO };

export interface Env {
    // Bindings (commented out in wrangler.toml until you provision them).
    // API_KEYS?: KVNamespace;
    // USAGE?: KVNamespace;
    // DB?: D1Database;
    // BUNDLES?: R2Bucket;
    SESSIONS?: DurableObjectNamespace;

    // Vars
    EXTERNAL_BACKEND?: string;
    ALLOWED_ORIGIN?: string;
    ADMIN_TOKEN?: string;
    PYODIDE_IN_WORKER?: string;
}

const CORS_HEADERS = (origin: string): Record<string, string> => ({
    'Access-Control-Allow-Origin': origin,
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Admin-Token',
    'Access-Control-Max-Age': '86400',
    'Vary': 'Origin',
});

function pickOrigin(req: Request, env: Env): string {
    const reqOrigin = req.headers.get('Origin') ?? '';
    if (reqOrigin === 'http://localhost:8081' || reqOrigin === 'http://127.0.0.1:8081') return reqOrigin;
    return env.ALLOWED_ORIGIN || 'https://pynescript.ai';
}

function jsonResponse(body: unknown, init: ResponseInit, origin: string): Response {
    return new Response(JSON.stringify(body), {
        ...init,
        headers: {
            ...(init.headers as Record<string, string> | undefined),
            'Content-Type': 'application/json',
            ...CORS_HEADERS(origin),
        },
    });
}

export default {
    async fetch(req: Request, env: Env, _ctx: ExecutionContext): Promise<Response> {
        const origin = pickOrigin(req, env);
        if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: CORS_HEADERS(origin) });

        const url = new URL(req.url);

        // WebSocket session relay: /api/stream → DO
        if (url.pathname === '/api/stream') {
            if (!env.SESSIONS) {
                return jsonResponse(
                    { status: 'error', code: 'NO_DO', message: 'SESSIONS Durable Object not bound. Run `wrangler deploy` after provisioning.' },
                    { status: 503 }, origin,
                );
            }
            const id = env.SESSIONS.idFromName(url.searchParams.get('session') ?? 'default');
            const stub = env.SESSIONS.get(id);
            const wsReq = new Request(`${url.origin}/ws?${url.searchParams.toString()}`, req);
            return stub.fetch(wsReq);
        }

        try {
            switch (url.pathname) {
                case '/':
                case '/health':
                    return jsonResponse(
                        { status: 'healthy', service: 'pynescript-superchart-worker', timestamp: Date.now() },
                        { status: 200 },
                        origin,
                    );
                case '/api/run':
                    return req.method !== 'POST'
                        ? jsonResponse({ status: 'error', code: 'METHOD', message: 'POST required' }, { status: 405 }, origin)
                        : await handleRun(req, env, origin);
                case '/api/keys':
                    return await handleKeys(req, env, origin);
                case '/api/usage':
                    return jsonResponse(
                        { status: 'success', usage: { calls_used: 0, calls_remaining: null } },
                        { status: 200 },
                        origin,
                    );
                default:
                    return jsonResponse(
                        { status: 'error', code: 'NOT_FOUND', message: `Endpoint ${url.pathname} not found` },
                        { status: 404 },
                        origin,
                    );
            }
        } catch (err) {
            return jsonResponse(
                { status: 'error', code: 'INTERNAL', message: err instanceof Error ? err.message : String(err) },
                { status: 500 },
                origin,
            );
        }
    },
} satisfies ExportedHandler<Env>;
