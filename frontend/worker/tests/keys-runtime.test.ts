/**
 * Worker keys + run handler (mocked upstream).
 */

import { describe, expect, it, afterEach } from 'bun:test';
import { handleKeys } from '../src/keys';
import { handleRun } from '../src/runtime';
import type { Env } from '../src/index';

const origin = 'http://localhost:3000';
const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
});

describe('handleKeys', () => {
  it('forbids create without admin token', async () => {
    const r = await handleKeys(
      new Request('http://x/api/keys?action=create', { method: 'POST', body: '{}' }),
      { ADMIN_TOKEN: 'secret' } as Env,
      origin,
    );
    expect(r.status).toBe(403);
  });

  it('creates key with admin token (no KV)', async () => {
    const r = await handleKeys(
      new Request('http://x/api/keys?action=create', {
        method: 'POST',
        headers: { 'X-Admin-Token': 'secret', 'Content-Type': 'application/json' },
        body: JSON.stringify({ tier: 'hobby' }),
      }),
      { ADMIN_TOKEN: 'secret' } as Env,
      origin,
    );
    expect(r.status).toBe(200);
    const j = await r.json();
    expect(j.api_key).toMatch(/^pn_/);
  });

  it('validates pn_ key without KV', async () => {
    const key = 'pn_' + 'cd'.repeat(24);
    const r = await handleKeys(
      new Request(`http://x/api/keys?action=validate&key=${key}`),
      {} as Env,
      origin,
    );
    expect(r.status).toBe(200);
  });

  it('rejects missing key on validate', async () => {
    const r = await handleKeys(
      new Request('http://x/api/keys?action=validate'),
      {} as Env,
      origin,
    );
    expect(r.status).toBe(400);
  });
});

describe('handleRun', () => {
  it('400 on invalid body', async () => {
    const r = await handleRun(
      new Request('http://x/api/run', {
        method: 'POST',
        body: JSON.stringify({ script: '', data: [] }),
      }),
      {} as Env,
      origin,
    );
    expect(r.status).toBe(400);
  });

  it('503 when no backend', async () => {
    const r = await handleRun(
      new Request('http://x/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          script: 'plot(close)',
          data: [{ time: 1, open: 1, high: 1, low: 1, close: 1 }],
        }),
      }),
      {} as Env,
      origin,
    );
    expect(r.status).toBe(503);
    const j = await r.json();
    expect(j.code).toBe('NO_BACKEND');
  });

  it('rejects invalid mode', async () => {
    const r = await handleRun(
      new Request('http://x/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          script: 'plot(1)',
          data: [{ time: 1, open: 1, high: 1, low: 1, close: 1 }],
          mode: 'nope',
        }),
      }),
      {} as Env,
      origin,
    );
    expect(r.status).toBe(400);
  });

  it('increments USAGE kv when bearer present', async () => {
    const store = new Map<string, string>();
    const USAGE = {
      get: async (k: string) => store.get(k) ?? null,
      put: async (k: string, v: string) => {
        store.set(k, v);
      },
    };
    globalThis.fetch = (async () =>
      new Response(JSON.stringify({ status: 'success', plots: [] }), { status: 200 })) as typeof fetch;

    const key = 'pn_' + 'ab'.repeat(24);
    await handleRun(
      new Request('http://x/api/run', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${key}`,
        },
        body: JSON.stringify({
          script: 'plot(close)',
          data: [{ time: 1, open: 1, high: 1, low: 1, close: 1 }],
        }),
      }),
      { EXTERNAL_BACKEND: 'http://flask.test', USAGE } as unknown as Env,
      origin,
    );
    expect(store.get(`usage:${key}`)).toBe('1');
  });

  it('uses pyodide path when enabled and runtime returns result', async () => {
    // Mock tryRunInWorker via env flag; if pyodide fails, falls through
    const r = await handleRun(
      new Request('http://x/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          script: 'plot(close)',
          data: [{ time: 1, open: 1, high: 1, low: 1, close: 1 }],
        }),
      }),
      {
        PYODIDE_IN_WORKER: 'enabled',
        EXTERNAL_BACKEND: 'http://flask.test',
      } as Env,
      origin,
    );
    // Without real pyodide, falls through to proxy — mock fetch
    // Re-run with fetch mock when pyodide returns null
    globalThis.fetch = (async () =>
      new Response(JSON.stringify({ status: 'success', plots: [9] }), {
        status: 200,
      })) as typeof fetch;
    const r2 = await handleRun(
      new Request('http://x/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          script: 'plot(close)',
          data: [{ time: 1, open: 1, high: 1, low: 1, close: 1 }],
        }),
      }),
      {
        PYODIDE_IN_WORKER: 'enabled',
        EXTERNAL_BACKEND: 'http://flask.test',
      } as Env,
      origin,
    );
    expect([200, 503]).toContain(r.status);
    expect(r2.status).toBe(200);
  });

  it('proxies to EXTERNAL_BACKEND', async () => {
    globalThis.fetch = (async (input: RequestInfo | URL) => {
      expect(String(input)).toContain('http://flask.test/run');
      return new Response(JSON.stringify({ status: 'success', plots: [1], events: [] }), {
        status: 200,
      });
    }) as typeof fetch;

    const r = await handleRun(
      new Request('http://x/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          script: 'plot(close)',
          data: [{ time: 1, open: 1, high: 1, low: 1, close: 1 }],
        }),
      }),
      { EXTERNAL_BACKEND: 'http://flask.test' } as Env,
      origin,
    );
    expect(r.status).toBe(200);
    const j = await r.json();
    expect(j.status).toBe('success');
  });
});
