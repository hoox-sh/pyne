/**
 * Extra worker scripts coverage: POST create, conflict path already in scripts.test.
 * Run from frontend/: bun test tests/worker-scripts-extra.test.ts worker/tests/
 */

import { describe, expect, it, beforeEach } from 'bun:test';
import { handleScripts, _clearMemScripts } from '../worker/src/scripts';
import type { Env } from '../worker/src/index';

const env: Env = { ALLOW_OPEN_KEYS: '1' };
const origin = 'http://localhost:3000';
const KEY = 'extra-user-key';

function req(path: string, init: RequestInit & { key?: string } = {}) {
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

describe('scripts extra', () => {
  it('POST collection creates script', async () => {
    const r = await handleScripts(
      req('/api/scripts', {
        method: 'POST',
        body: JSON.stringify({ name: 'N', content: 'plot(1)' }),
      }),
      env,
      origin,
      '/api/scripts',
    );
    expect([200, 201]).toContain(r.status);
    const j = await r.json();
    expect(j.script.content).toBe('plot(1)');
  });

  it('health-less list reports memory backend', async () => {
    const r = await handleScripts(req('/api/scripts'), env, origin, '/api/scripts');
    const j = await r.json();
    expect(j.backend).toBe('memory');
  });
});
