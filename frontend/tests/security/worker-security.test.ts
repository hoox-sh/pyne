/**
 * Worker auth isolation and abuse cases.
 */

import { describe, expect, it, beforeEach } from 'bun:test';
import { handleScripts, _clearMemScripts } from '../../worker/src/scripts';
import { requireApiKey, extractBearer } from '../../worker/src/auth';
import { handleKeys } from '../../worker/src/keys';
import type { Env } from '../../worker/src/index';

const env: Env = { ALLOW_OPEN_KEYS: '1' };
const origin = 'http://localhost:3000';

function req(path: string, init: RequestInit & { key?: string } = {}) {
  const headers = new Headers(init.headers || {});
  if (init.key !== '') {
    headers.set('Authorization', `Bearer ${init.key ?? 'user-a'}`);
  }
  if (init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  return new Request(`http://localhost${path}`, { ...init, headers });
}

beforeEach(() => {
  _clearMemScripts();
});

describe('worker security', () => {
  it('missing bearer is 401', async () => {
    const r = await handleScripts(
      new Request('http://localhost/api/scripts'),
      env,
      origin,
      '/api/scripts',
    );
    expect(r.status).toBe(401);
  });

  it('user A cannot read user B script', async () => {
    await handleScripts(
      req('/api/scripts/secret', {
        method: 'PUT',
        key: 'user-a',
        body: JSON.stringify({ name: 'Secret', content: 'plot(1)' }),
      }),
      env,
      origin,
      '/api/scripts/secret',
    );

    const getB = await handleScripts(
      req('/api/scripts/secret', { key: 'user-b' }),
      env,
      origin,
      '/api/scripts/secret',
    );
    expect(getB.status).toBe(404);

    const listB = await handleScripts(
      req('/api/scripts', { key: 'user-b' }),
      env,
      origin,
      '/api/scripts',
    );
    const j = await listB.json();
    expect(j.scripts).toEqual([]);
  });

  it('If-Match conflict returns 409', async () => {
    await handleScripts(
      req('/api/scripts/c', {
        method: 'PUT',
        body: JSON.stringify({ name: 'C', content: 'v1' }),
      }),
      env,
      origin,
      '/api/scripts/c',
    );
    const conflict = await handleScripts(
      req('/api/scripts/c', {
        method: 'PUT',
        headers: { 'If-Match': 'stale' },
        body: JSON.stringify({ name: 'C', content: 'v2' }),
      }),
      env,
      origin,
      '/api/scripts/c',
    );
    expect(conflict.status).toBe(409);
  });

  it('admin keys require token', async () => {
    const r = await handleKeys(
      new Request('http://x/api/keys?action=create', {
        method: 'POST',
        body: '{}',
      }),
      { ADMIN_TOKEN: 'adm' } as Env,
      origin,
    );
    expect(r.status).toBe(403);
  });

  it('malformed pn_ rejected without open keys', async () => {
    const r = await requireApiKey(
      new Request('http://x/', { headers: { Authorization: 'Bearer not-a-pn-key' } }),
      {} as Env,
    );
    expect(r.ok).toBe(false);
  });

  it('extractBearer ignores empty Authorization', () => {
    expect(extractBearer(new Request('http://x/'))).toBe('');
  });

  it('encoded path id stays within user partition', async () => {
    const id = encodeURIComponent('../etc/passwd');
    await handleScripts(
      req(`/api/scripts/${id}`, {
        method: 'PUT',
        key: 'user-a',
        body: JSON.stringify({ name: 'x', content: 'y' }),
      }),
      env,
      origin,
      `/api/scripts/${id}`,
    );
    const listB = await handleScripts(
      req('/api/scripts', { key: 'user-b' }),
      env,
      origin,
      '/api/scripts',
    );
    const j = await listB.json();
    expect(j.scripts.some((s: { id: string }) => s.id.includes('passwd'))).toBe(false);
  });
});
