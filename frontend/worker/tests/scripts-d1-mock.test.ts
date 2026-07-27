/**
 * Scripts handler D1 branches with a minimal mock DB.
 */

import { describe, expect, it, beforeEach } from 'bun:test';
import { handleScripts, _clearMemScripts } from '../src/scripts';
import type { Env } from '../src/index';

const origin = 'http://localhost:3000';

type Row = Record<string, unknown>;

function mockD1(opts?: { failList?: boolean }) {
  const scripts = new Map<string, Row>(); // key userId::id
  const drafts = new Map<string, Row>();

  function key(userId: string, id: string) {
    return `${userId}::${id}`;
  }

  const db = {
    prepare(sql: string) {
      const s = sql.replace(/\s+/g, ' ').trim();
      return {
        bind(...args: unknown[]) {
          const chain = {
            async all<T>() {
              if (opts?.failList && s.includes('FROM scripts') && s.includes('ORDER BY')) {
                throw new Error('no such table: scripts');
              }
              const userId = String(args[0]);
              const rows: T[] = [];
              for (const [k, v] of scripts) {
                if (k.startsWith(userId + '::')) rows.push(v as T);
              }
              rows.sort(
                (a, b) =>
                  Number((b as Row).updated_at || 0) - Number((a as Row).updated_at || 0),
              );
              return { results: rows };
            },
            async first<T>() {
              if (s.includes('FROM script_drafts') || s.includes('script_drafts WHERE')) {
                const userId = String(args[0]);
                const row = drafts.get(userId);
                return (row as T) ?? null;
              }
              if (s.includes('FROM scripts') && s.includes('AND id')) {
                const userId = String(args[0]);
                const id = String(args[1]);
                return (scripts.get(key(userId, id)) as T) || null;
              }
              return null;
            },
            async run() {
              if (s.includes('INTO script_drafts') || s.includes('UPDATE script_drafts')) {
                const [userId, content, name, updated_at] = args as (string | number | null)[];
                drafts.set(String(userId), {
                  content: String(content ?? ''),
                  name: name ?? null,
                  updated_at,
                });
                return { meta: { changes: 1 } };
              }
              if (s.includes('INTO scripts') || (s.includes('ON CONFLICT') && s.includes('scripts'))) {
                const [userId, id, name, description, path, content, revision, created_at, updated_at] =
                  args as (string | number | null)[];
                scripts.set(key(String(userId), String(id)), {
                  id,
                  name,
                  description,
                  path,
                  content,
                  revision,
                  created_at,
                  updated_at,
                });
                return { meta: { changes: 1 } };
              }
              if (s.includes('DELETE FROM scripts')) {
                const userId = String(args[0]);
                const id = String(args[1]);
                const had = scripts.delete(key(userId, id));
                return { meta: { changes: had ? 1 : 0 } };
              }
              return { meta: { changes: 0 } };
            },
          };
          return chain;
        },
      };
    },
  };

  return db as unknown as D1Database;
}

function req(path: string, init: RequestInit & { key?: string } = {}) {
  const headers = new Headers(init.headers || {});
  headers.set('Authorization', `Bearer ${init.key || 'd1-user'}`);
  if (init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  return new Request(`http://localhost${path}`, { ...init, headers });
}

beforeEach(() => {
  _clearMemScripts();
});

describe('scripts D1 mock', () => {
  it('list/put/get/delete via D1', async () => {
    const env = { ALLOW_OPEN_KEYS: '1', DB: mockD1() } as Env;
    const put = await handleScripts(
      req('/api/scripts/s1', {
        method: 'PUT',
        body: JSON.stringify({ name: 'D1', content: 'plot(1)' }),
      }),
      env,
      origin,
      '/api/scripts/s1',
    );
    expect([200, 201]).toContain(put.status);

    const list = await handleScripts(req('/api/scripts'), env, origin, '/api/scripts');
    const lj = await list.json();
    expect(lj.scripts.some((s: { id: string }) => s.id === 's1')).toBe(true);
    expect(lj.backend).toBeUndefined(); // D1 path doesn't set memory backend flag

    const get = await handleScripts(req('/api/scripts/s1'), env, origin, '/api/scripts/s1');
    expect((await get.json()).script.content).toBe('plot(1)');

    const del = await handleScripts(
      req('/api/scripts/s1', { method: 'DELETE' }),
      env,
      origin,
      '/api/scripts/s1',
    );
    expect(del.status).toBe(200);
  });

  it('draft put/get via D1', async () => {
    const env = { ALLOW_OPEN_KEYS: '1', DB: mockD1() } as Env;
    await handleScripts(
      req('/api/scripts/_draft', {
        method: 'PUT',
        body: JSON.stringify({ content: 'draft', name: 'D' }),
      }),
      env,
      origin,
      '/api/scripts/_draft',
    );
    const get = await handleScripts(req('/api/scripts/_draft'), env, origin, '/api/scripts/_draft');
    const j = await get.json();
    expect(j.draft.content).toBe('draft');
  });

  it('NO_SCHEMA when list fails missing table', async () => {
    const env = { ALLOW_OPEN_KEYS: '1', DB: mockD1({ failList: true }) } as Env;
    const list = await handleScripts(req('/api/scripts'), env, origin, '/api/scripts');
    expect(list.status).toBe(503);
    expect((await list.json()).code).toBe('NO_SCHEMA');
  });

  it('method not allowed on collection', async () => {
    const env = { ALLOW_OPEN_KEYS: '1', DB: mockD1() } as Env;
    const r = await handleScripts(
      req('/api/scripts', { method: 'DELETE' }),
      env,
      origin,
      '/api/scripts',
    );
    expect(r.status).toBe(405);
  });
});
