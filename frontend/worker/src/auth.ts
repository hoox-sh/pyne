/**
 * API key auth helpers for script library (and shared endpoints).
 * Reuses Pro API key shape (pn_…) and optional KV-backed validation.
 */

import type { Env } from './index';

export interface AuthContext {
  key: string;
  /** Stable partition id derived from the key (never the raw key in D1 if hashed). */
  userId: string;
  tier: string;
}

async function hashKey(key: string): Promise<string> {
  const data = new TextEncoder().encode(key);
  const digest = await crypto.subtle.digest('SHA-256', data);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
    .slice(0, 32);
}

export function extractBearer(req: Request): string {
  const auth = req.headers.get('Authorization') || '';
  const m = /^Bearer\s+(.+)$/i.exec(auth);
  if (m) return m[1].trim();
  const url = new URL(req.url);
  return (url.searchParams.get('key') || '').trim();
}

/**
 * Validate API key. When KV is unbound, accept well-formed `pn_` keys (dev)
 * or any non-empty key if `ALLOW_OPEN_KEYS=1` (local demos only).
 */
export async function requireApiKey(
  req: Request,
  env: Env,
): Promise<{ ok: true; ctx: AuthContext } | { ok: false; status: number; code: string; message: string }> {
  const key = extractBearer(req);
  if (!key) {
    return { ok: false, status: 401, code: 'NO_KEY', message: 'Authorization: Bearer <api_key> required' };
  }

  const kv = env.API_KEYS;
  if (kv) {
    const raw = await kv.get(`key:${key}`);
    if (!raw) {
      return { ok: false, status: 401, code: 'INVALID_KEY', message: 'unknown key' };
    }
    let tier = 'hobby';
    try {
      tier = (JSON.parse(raw) as { tier?: string }).tier || 'hobby';
    } catch {
      /* ignore */
    }
    return { ok: true, ctx: { key, userId: await hashKey(key), tier } };
  }

  // Dev without KV
  if (env.ALLOW_OPEN_KEYS === '1' || env.ALLOW_OPEN_KEYS === 'true') {
    return { ok: true, ctx: { key, userId: await hashKey(key), tier: 'hobby' } };
  }

  if (/^pn_[a-f0-9]{48}$/.test(key)) {
    return { ok: true, ctx: { key, userId: await hashKey(key), tier: 'hobby' } };
  }

  return {
    ok: false,
    status: 401,
    code: 'INVALID_KEY',
    message: 'malformed key (expected pn_… from /api/keys) or bind API_KEYS KV',
  };
}
