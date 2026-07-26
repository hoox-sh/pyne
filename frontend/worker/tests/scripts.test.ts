/**
 * Worker script library handler tests (in-memory backend).
 * Run from frontend/worker: `bun test tests/scripts.test.ts`
 * Or: `bun test frontend/worker/tests/scripts.test.ts`
 */

import { describe, expect, it, beforeEach } from 'bun:test';
import { handleScripts, _clearMemScripts } from '../src/scripts';
import type { Env } from '../src/index';

const env: Env = {
  ALLOW_OPEN_KEYS: '1',
  ALLOWED_ORIGIN: 'http://localhost:3000',
};

const origin = 'http://localhost:3000';
const KEY = 'test-user-key-1';

function req(
  path: string,
  init: RequestInit & { key?: string } = {},
): Request {
  const headers = new Headers(init.headers || {});
  headers.set('Authorization', `Bearer ${init.key || KEY}`);
  if (init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  return new Request(`http://localhost${path}`, { ...init, headers });
}

beforeEach(() => {
  _clearMemScripts();
});

describe('handleScripts', () => {
  it('rejects missing API key', async () => {
    const r = await handleScripts(
      new Request('http://localhost/api/scripts'),
      env,
      origin,
      '/api/scripts',
    );
    expect(r.status).toBe(401);
  });

  it('lists empty library', async () => {
    const r = await handleScripts(req('/api/scripts'), env, origin, '/api/scripts');
    expect(r.status).toBe(200);
    const j = await r.json();
    expect(j.status).toBe('success');
    expect(j.scripts).toEqual([]);
  });

  it('PUT create + GET + list + DELETE', async () => {
    const put = await handleScripts(
      req('/api/scripts/s1', {
        method: 'PUT',
        body: JSON.stringify({ name: 'Demo', content: 'plot(close)' }),
      }),
      env,
      origin,
      '/api/scripts/s1',
    );
    expect([200, 201]).toContain(put.status);
    const putJ = await put.json();
    expect(putJ.script.name).toBe('Demo');
    expect(putJ.script.revision).toBeDefined();

    const get = await handleScripts(req('/api/scripts/s1'), env, origin, '/api/scripts/s1');
    expect(get.status).toBe(200);
    const getJ = await get.json();
    expect(getJ.script.content).toBe('plot(close)');

    const list = await handleScripts(req('/api/scripts'), env, origin, '/api/scripts');
    const listJ = await list.json();
    expect(listJ.scripts.some((s: { id: string }) => s.id === 's1')).toBe(true);

    const del = await handleScripts(
      req('/api/scripts/s1', { method: 'DELETE' }),
      env,
      origin,
      '/api/scripts/s1',
    );
    expect(del.status).toBe(200);

    const get2 = await handleScripts(req('/api/scripts/s1'), env, origin, '/api/scripts/s1');
    expect(get2.status).toBe(404);
  });

  it('partitions by API key', async () => {
    await handleScripts(
      req('/api/scripts/a', {
        method: 'PUT',
        key: 'user-a',
        body: JSON.stringify({ name: 'A', content: '1' }),
      }),
      env,
      origin,
      '/api/scripts/a',
    );
    const listB = await handleScripts(
      req('/api/scripts', { key: 'user-b' }),
      env,
      origin,
      '/api/scripts',
    );
    const j = await listB.json();
    expect(j.scripts).toEqual([]);
  });

  it('draft save/load', async () => {
    await handleScripts(
      req('/api/scripts/_draft', {
        method: 'PUT',
        body: JSON.stringify({ content: 'draft body', name: 'D' }),
      }),
      env,
      origin,
      '/api/scripts/_draft',
    );
    const get = await handleScripts(
      req('/api/scripts/_draft'),
      env,
      origin,
      '/api/scripts/_draft',
    );
    const j = await get.json();
    expect(j.draft.content).toBe('draft body');
  });

  it('conflict on If-Match mismatch', async () => {
    const put1 = await handleScripts(
      req('/api/scripts/c1', {
        method: 'PUT',
        body: JSON.stringify({ name: 'C', content: 'v1' }),
      }),
      env,
      origin,
      '/api/scripts/c1',
    );
    const rev = (await put1.json()).script.revision as string;

    const put2 = await handleScripts(
      req('/api/scripts/c1', {
        method: 'PUT',
        headers: { 'If-Match': 'stale-rev' },
        body: JSON.stringify({ name: 'C', content: 'v2' }),
      }),
      env,
      origin,
      '/api/scripts/c1',
    );
    expect(put2.status).toBe(409);

    const put3 = await handleScripts(
      req('/api/scripts/c1', {
        method: 'PUT',
        headers: { 'If-Match': rev },
        body: JSON.stringify({ name: 'C', content: 'v2' }),
      }),
      env,
      origin,
      '/api/scripts/c1',
    );
    expect(put3.status).toBe(200);
  });
});
