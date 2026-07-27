/**
 * Worker auth helpers.
 */

import { describe, expect, it } from 'bun:test';
import { extractBearer, requireApiKey } from '../src/auth';
import type { Env } from '../src/index';

describe('extractBearer', () => {
  it('reads Authorization header', () => {
    const req = new Request('http://x/api/scripts', {
      headers: { Authorization: 'Bearer abc' },
    });
    expect(extractBearer(req)).toBe('abc');
  });

  it('reads ?key=', () => {
    const req = new Request('http://x/api/scripts?key=fromquery');
    expect(extractBearer(req)).toBe('fromquery');
  });
});

describe('requireApiKey', () => {
  it('rejects missing key', async () => {
    const r = await requireApiKey(new Request('http://x/'), {} as Env);
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.status).toBe(401);
  });

  it('ALLOW_OPEN_KEYS accepts any key', async () => {
    const req = new Request('http://x/', { headers: { Authorization: 'Bearer any-key' } });
    const r = await requireApiKey(req, { ALLOW_OPEN_KEYS: '1' } as Env);
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.ctx.userId).toHaveLength(32);
      expect(r.ctx.key).toBe('any-key');
    }
  });

  it('accepts well-formed pn_ keys without KV', async () => {
    const key = 'pn_' + 'ab'.repeat(24);
    const req = new Request('http://x/', { headers: { Authorization: `Bearer ${key}` } });
    const r = await requireApiKey(req, {} as Env);
    expect(r.ok).toBe(true);
  });

  it('rejects malformed keys without open keys', async () => {
    const req = new Request('http://x/', { headers: { Authorization: 'Bearer short' } });
    const r = await requireApiKey(req, {} as Env);
    expect(r.ok).toBe(false);
  });

  it('KV hit/miss', async () => {
    const store = new Map<string, string>();
    const kv = {
      async get(k: string) {
        return store.get(k) ?? null;
      },
    } as unknown as KVNamespace;
    store.set('key:good', JSON.stringify({ tier: 'pro', key: 'good', createdAt: 1 }));

    const ok = await requireApiKey(
      new Request('http://x/', { headers: { Authorization: 'Bearer good' } }),
      { API_KEYS: kv } as Env,
    );
    expect(ok.ok).toBe(true);
    if (ok.ok) expect(ok.ctx.tier).toBe('pro');

    const bad = await requireApiKey(
      new Request('http://x/', { headers: { Authorization: 'Bearer missing' } }),
      { API_KEYS: kv } as Env,
    );
    expect(bad.ok).toBe(false);
  });

  it('stable userId hash', async () => {
    const req = new Request('http://x/', { headers: { Authorization: 'Bearer same' } });
    const a = await requireApiKey(req, { ALLOW_OPEN_KEYS: '1' } as Env);
    const b = await requireApiKey(req, { ALLOW_OPEN_KEYS: '1' } as Env);
    expect(a.ok && b.ok).toBe(true);
    if (a.ok && b.ok) expect(a.ctx.userId).toBe(b.ctx.userId);
  });
});
