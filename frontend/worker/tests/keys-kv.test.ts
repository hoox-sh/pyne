/**
 * Keys handler with mock KV + invalid tier.
 */

import { describe, expect, it } from 'bun:test';
import { handleKeys } from '../src/keys';
import type { Env } from '../src/index';

const origin = 'http://localhost:3000';

function mockKv(map = new Map<string, string>()) {
  return {
    async get(k: string) {
      return map.get(k) ?? null;
    },
    async put(k: string, v: string) {
      map.set(k, v);
    },
  } as unknown as KVNamespace;
}

describe('keys with KV', () => {
  it('create stores key in KV', async () => {
    const map = new Map<string, string>();
    const r = await handleKeys(
      new Request('http://x/api/keys?action=create', {
        method: 'POST',
        headers: { 'X-Admin-Token': 'adm', 'Content-Type': 'application/json' },
        body: JSON.stringify({ tier: 'pro' }),
      }),
      { ADMIN_TOKEN: 'adm', API_KEYS: mockKv(map) } as Env,
      origin,
    );
    expect(r.status).toBe(200);
    const j = await r.json();
    expect(j.tier).toBe('pro');
    expect(map.has(`key:${j.api_key}`)).toBe(true);
  });

  it('rejects invalid tier', async () => {
    const r = await handleKeys(
      new Request('http://x/api/keys?action=create', {
        method: 'POST',
        headers: { 'X-Admin-Token': 'adm', 'Content-Type': 'application/json' },
        body: JSON.stringify({ tier: 'ultra' }),
      }),
      { ADMIN_TOKEN: 'adm' } as Env,
      origin,
    );
    expect(r.status).toBe(400);
  });

  it('validate hits KV success and miss', async () => {
    const map = new Map<string, string>();
    map.set('key:abc', JSON.stringify({ key: 'abc', tier: 'team', createdAt: 1 }));
    const kv = mockKv(map);

    const ok = await handleKeys(
      new Request('http://x/api/keys?action=validate', {
        headers: { Authorization: 'Bearer abc' },
      }),
      { API_KEYS: kv } as Env,
      origin,
    );
    expect(ok.status).toBe(200);
    expect((await ok.json()).tier).toBe('team');

    const miss = await handleKeys(
      new Request('http://x/api/keys?action=validate&key=nope'),
      { API_KEYS: kv } as Env,
      origin,
    );
    expect(miss.status).toBe(401);
  });

  it('405 unsupported method', async () => {
    const r = await handleKeys(
      new Request('http://x/api/keys', { method: 'DELETE' }),
      {} as Env,
      origin,
    );
    expect(r.status).toBe(405);
  });
});
