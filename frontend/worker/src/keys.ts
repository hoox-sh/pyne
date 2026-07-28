// Copyright (C) 2024-2026 jango_blockchained
//
// This file is part of pynescript.
//
// pynescript is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// pynescript is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
//
// SPDX-License-Identifier: AGPL-3.0-or-later

// /api/keys — minimal admin-only API key creation + listing.
// Backed by KV when available, in-memory otherwise (for dev).

import type { Env } from './index';

interface KeyRecord {
    key: string;
    tier: 'free' | 'hobby' | 'pro' | 'team' | 'enterprise';
    createdAt: number;
}

function isAdmin(req: Request, env: Env): boolean {
    if (!env.ADMIN_TOKEN) return false;
    const header = req.headers.get('X-Admin-Token') ?? '';
    return header === env.ADMIN_TOKEN;
}

function genKey(): string {
    const bytes = new Uint8Array(24);
    crypto.getRandomValues(bytes);
    return 'pn_' + Array.from(bytes).map((b) => b.toString(16).padStart(2, '0')).join('');
}

export async function handleKeys(req: Request, env: Env, origin: string): Promise<Response> {
    const url = new URL(req.url);
    const kv = (env as unknown as { API_KEYS?: KVNamespace }).API_KEYS;

    if (url.searchParams.get('action') === 'create' || req.method === 'POST') {
        if (!isAdmin(req, env)) {
            return new Response(JSON.stringify({ status: 'error', code: 'FORBIDDEN', message: 'admin token required' }), {
                status: 403, headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': origin },
            });
        }
        const body = await req.json().catch(() => ({} as Record<string, unknown>));
        const tier = String((body as { tier?: unknown })?.tier ?? 'hobby') as KeyRecord['tier'];
        if (!['free', 'hobby', 'pro', 'team', 'enterprise'].includes(tier)) {
            return new Response(JSON.stringify({ status: 'error', code: 'INVALID_TIER', message: 'unknown tier' }), {
                status: 400, headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': origin },
            });
        }
        const record: KeyRecord = { key: genKey(), tier, createdAt: Date.now() };
        if (kv) await kv.put(`key:${record.key}`, JSON.stringify(record), { expirationTtl: 60 * 60 * 24 * 365 });
        return new Response(JSON.stringify({ status: 'success', api_key: record.key, tier, created_at: record.createdAt }), {
            status: 200, headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': origin },
        });
    }

    if (url.searchParams.get('action') === 'validate' || req.method === 'GET') {
        const provided = req.headers.get('Authorization')?.replace(/^Bearer\s+/i, '') || url.searchParams.get('key') || '';
        if (!provided) {
            return new Response(JSON.stringify({ status: 'error', code: 'NO_KEY', message: 'api_key required' }), {
                status: 400, headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': origin },
            });
        }
        if (kv) {
            const raw = await kv.get(`key:${provided}`);
            if (!raw) {
                return new Response(JSON.stringify({ status: 'error', code: 'INVALID_KEY', message: 'unknown key' }), {
                    status: 401, headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': origin },
                });
            }
            const rec = JSON.parse(raw) as KeyRecord;
            return new Response(JSON.stringify({ status: 'success', tier: rec.tier, created_at: rec.createdAt }), {
                status: 200, headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': origin },
            });
        }
        // No KV bound: accept any well-formed key (dev-only).
        if (!/^pn_[a-f0-9]{48}$/.test(provided)) {
            return new Response(JSON.stringify({ status: 'error', code: 'INVALID_KEY', message: 'malformed key' }), {
                status: 401, headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': origin },
            });
        }
        return new Response(JSON.stringify({ status: 'success', tier: 'hobby' }), {
            status: 200, headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': origin },
        });
    }

    return new Response(JSON.stringify({ status: 'error', code: 'METHOD', message: 'unsupported' }), {
        status: 405, headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': origin },
    });
}
