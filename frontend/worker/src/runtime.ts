// /api/run — accept Pine script + OHLCV bars, return plots + events.
//
// Three execution modes, in order of preference:
//
// 1. PYODIDE_IN_WORKER=enabled → run the script in-Worker via Pyodide (see
//    pyodide_runtime.ts).  Requires the pynescript wheel to be in R2 or
//    reachable over the network.
//
// 2. EXTERNAL_BACKEND set → proxy the request to the configured external
//    backend (the local Flask server, another Worker, etc.).  This works
//    today without any Python runtime on the Worker.
//
// 3. Neither set → 503 with a clear hint pointing at the env vars and
//    worker/RUNTIME.md.

import type { Env } from './index';
import { tryRunInWorker } from './pyodide_runtime';

interface RunRequest {
    script: string;
    data: Array<{ time: number | string; open: number; high: number; low: number; close: number; volume?: number }>;
    mode?: 'interpret' | 'compile';
}

function validate(body: unknown): { ok: true; value: RunRequest } | { ok: false; err: string } {
    if (!body || typeof body !== 'object') return { ok: false, err: 'body must be a JSON object' };
    const b = body as Record<string, unknown>;
    if (typeof b.script !== 'string' || !b.script.trim()) return { ok: false, err: 'script is required' };
    if (!Array.isArray(b.data) || b.data.length === 0) return { ok: false, err: 'data must be a non-empty array' };
    if (b.mode !== undefined && b.mode !== 'interpret' && b.mode !== 'compile') {
        return { ok: false, err: 'mode must be "interpret" or "compile"' };
    }
    return { ok: true, value: b as unknown as RunRequest };
}

async function proxyToExternal(req: Request, env: Env, origin: string): Promise<Response> {
    const target = env.EXTERNAL_BACKEND?.replace(/\/$/, '');
    if (!target) {
        return new Response(
            JSON.stringify({
                status: 'error',
                code: 'NO_BACKEND',
                message:
                    'No EXTERNAL_BACKEND configured and PYODIDE_IN_WORKER is disabled. ' +
                    'Set EXTERNAL_BACKEND=<flask-url> OR PYODIDE_IN_WORKER=enabled (and ship the pynescript wheel in R2).',
            }),
            { status: 503, headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': origin } },
        );
    }
    const body = await req.text();
    const upstream = await fetch(`${target}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
    });
    const text = await upstream.text();
    return new Response(text, {
        status: upstream.status,
        headers: {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': origin,
            'Vary': 'Origin',
        },
    });
}

export async function handleRun(req: Request, env: Env, origin: string): Promise<Response> {
    const body = await req.json().catch(() => null);
    const v = validate(body);
    if (!v.ok) {
        return new Response(JSON.stringify({ status: 'error', code: 'BAD_REQUEST', message: v.err }), {
            status: 400, headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': origin },
        });
    }

    // Increment usage meter (KV). Silently skip if KV not bound.
    const auth = req.headers.get('Authorization') ?? '';
    if (auth.startsWith('Bearer ') && (env as unknown as { USAGE?: KVNamespace }).USAGE) {
        const key = auth.slice(7).trim();
        const usage = (env as unknown as { USAGE: KVNamespace }).USAGE;
        const current = parseInt((await usage.get(`usage:${key}`)) ?? '0', 10);
        await usage.put(`usage:${key}`, String(current + 1), { expirationTtl: 60 * 60 * 24 * 30 });
    }

    // 1) In-Worker Python via Pyodide (preferred when enabled).
    if (env.PYODIDE_IN_WORKER === 'enabled') {
        const pyResult = await tryRunInWorker(v.value.script, v.value.data, env);
        if (pyResult) {
            return new Response(JSON.stringify(pyResult), {
                status: 200, headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': origin },
            });
        }
        // Fall through to external if Pyodide failed to boot.
    }

    // 2) External backend.
    return proxyToExternal(req, env, origin);
}
