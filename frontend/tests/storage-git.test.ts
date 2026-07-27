/**
 * Git storage plugin tests (mocked GitHub Contents API).
 * Run: `bun test frontend/tests/storage-git.test.ts`
 */

import { describe, expect, it, beforeEach, afterEach, mock } from 'bun:test';
import { registry } from '../src/plugins/registry';
import { _resetBootstrapFlag, ensureBuiltins } from '../src/plugins/bootstrap';
import { _resetStorageRegistrationFlag, listStorages } from '../src/storage/catalog';
import { gitStoragePlugin } from '../src/storage/git';
import { _resetSourceRegistrationFlag } from '../src/sources/catalog';
import { _resetStreamRegistrationFlag } from '../src/streams/catalog';
import { _resetEngineRegistrationFlag } from '../src/engines/catalog';
import { setStore } from '../src/store';

class MemoryStorage {
  store = new Map<string, string>();
  getItem(k: string) {
    return this.store.get(k) ?? null;
  }
  setItem(k: string, v: string) {
    this.store.set(k, v);
  }
  removeItem(k: string) {
    this.store.delete(k);
  }
  clear() {
    this.store.clear();
  }
}

const originalFetch = globalThis.fetch;

const CFG = {
  provider: 'github' as const,
  apiBaseUrl: 'https://api.github.com',
  token: 'ghp_testtoken',
  owner: 'acme',
  repo: 'pines',
  projectId: '',
  branch: 'main',
  basePath: 'pine-library',
  autoPush: true,
  commitMessageTemplate: 'chore(pine): save {{name}} @ {{iso}}',
};

function b64(s: string): string {
  return btoa(s);
}

beforeEach(() => {
  (globalThis as unknown as { localStorage: MemoryStorage }).localStorage = new MemoryStorage();
  registry.clear();
  _resetSourceRegistrationFlag();
  _resetStreamRegistrationFlag();
  _resetEngineRegistrationFlag();
  _resetStorageRegistrationFlag();
  _resetBootstrapFlag();
  ensureBuiltins();
  setStore('pluginsConfig', 'storage:git', { ...CFG });
});

afterEach(() => {
  globalThis.fetch = originalFetch;
});

describe('storage-git plugin', () => {
  it('is registered as built-in', () => {
    expect(listStorages().map((s) => s.id)).toContain('git');
  });

  it('list() reads index.json from GitHub', async () => {
    const index = {
      version: 1,
      scripts: [
        {
          id: 's1',
          name: 'RSI',
          path: 'pine-library/library/s1.pine',
          updatedAt: 100,
          revision: 'abc',
        },
      ],
    };
    globalThis.fetch = mock(async (input: RequestInfo | URL) => {
      const url = String(input);
      expect(url).toContain('/repos/acme/pines/contents/');
      expect(url).toContain('index.json');
      return new Response(
        JSON.stringify({
          type: 'file',
          content: b64(JSON.stringify(index)),
          sha: 'idxsha',
          encoding: 'base64',
        }),
        { status: 200 },
      );
    }) as typeof fetch;

    const list = await gitStoragePlugin.list({ config: CFG });
    expect(list).toHaveLength(1);
    expect(list[0].name).toBe('RSI');
  });

  it('write() puts pine file and updates index', async () => {
    const calls: string[] = [];
    let indexSha: string | null = null;

    globalThis.fetch = mock(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method || 'GET').toUpperCase();
      calls.push(`${method} ${url}`);

      if (method === 'GET' && url.includes('index.json')) {
        if (!indexSha) {
          return new Response(JSON.stringify({ message: 'Not Found' }), { status: 404 });
        }
        return new Response(
          JSON.stringify({
            type: 'file',
            content: b64(JSON.stringify({ version: 1, scripts: [] })),
            sha: indexSha,
          }),
          { status: 200 },
        );
      }

      if (method === 'GET' && url.includes('.pine')) {
        return new Response(JSON.stringify({ message: 'Not Found' }), { status: 404 });
      }

      if (method === 'PUT') {
        const body = JSON.parse(String(init?.body || '{}')) as { message?: string; content?: string };
        expect(body.message).toBeDefined();
        expect(body.content).toBeDefined();
        if (url.includes('index.json')) indexSha = 'idx2';
        return new Response(
          JSON.stringify({
            content: { sha: 'filesha1' },
            commit: { sha: 'commit1' },
          }),
          { status: 201 },
        );
      }

      return new Response(JSON.stringify({ message: 'unexpected ' + url }), { status: 500 });
    }) as typeof fetch;

    const meta = await gitStoragePlugin.write(
      {
        id: 's_new',
        name: 'My Script',
        content: '//@version=5\nplot(close)',
        updatedAt: Date.now(),
      },
      CFG,
    );
    expect(meta.name).toBe('My Script');
    expect(meta.id).toBe('s_new');
    expect(calls.some((c) => c.startsWith('PUT') && c.includes('.pine'))).toBe(true);
    expect(calls.some((c) => c.startsWith('PUT') && c.includes('index.json'))).toBe(true);
  });

  it('requires token', async () => {
    await expect(
      gitStoragePlugin.list({
        config: { ...CFG, token: '' },
      }),
    ).rejects.toThrow(/token/i);
  });

  it('getStatus hits repo endpoint', async () => {
    globalThis.fetch = mock(async (input: RequestInfo | URL) => {
      expect(String(input)).toContain('/repos/acme/pines');
      return new Response(JSON.stringify({ full_name: 'acme/pines' }), { status: 200 });
    }) as typeof fetch;

    const st = await gitStoragePlugin.getStatus?.(CFG);
    expect(st?.connected).toBe(true);
    expect(st?.remote).toBe('acme/pines');
    expect(st?.branch).toBe('main');
  });

  it('saveDraft is a no-op (drafts stay local)', async () => {
    let fetchCalled = false;
    globalThis.fetch = mock(async () => {
      fetchCalled = true;
      return new Response('{}', { status: 200 });
    }) as typeof fetch;
    await gitStoragePlugin.saveDraft?.({ content: 'x' }, CFG);
    expect(fetchCalled).toBe(false);
  });

  it('loadDraft always returns null', async () => {
    expect(await gitStoragePlugin.loadDraft?.(CFG)).toBeNull();
  });

  it('list filters by prefix', async () => {
    globalThis.fetch = mock(async () =>
      new Response(
        JSON.stringify({
          type: 'file',
          content: b64(
            JSON.stringify({
              version: 1,
              scripts: [
                { id: 'a', name: 'Alpha', path: 'pine-library/library/a.pine', updatedAt: 1 },
                { id: 'b', name: 'Beta', path: 'other/b.pine', updatedAt: 2 },
              ],
            }),
          ),
          sha: 'x',
        }),
        { status: 200 },
      ),
    ) as typeof fetch;

    const list = await gitStoragePlugin.list({ config: CFG, prefix: 'Al' });
    expect(list).toHaveLength(1);
    expect(list[0].name).toBe('Alpha');
  });

  it('sync pull reports count or error', async () => {
    globalThis.fetch = mock(async () =>
      new Response(
        JSON.stringify({
          type: 'file',
          content: b64(JSON.stringify({ version: 1, scripts: [{ id: 's1', name: 'RSI' }] })),
          sha: 'x',
        }),
        { status: 200 },
      ),
    ) as typeof fetch;

    const ok = await gitStoragePlugin.sync?.('pull', CFG);
    expect(ok?.ok).toBe(true);
    expect(ok?.message).toMatch(/1 script/);

    globalThis.fetch = mock(async () => new Response('nope', { status: 500 })) as typeof fetch;
    const bad = await gitStoragePlugin.sync?.('pull', CFG);
    expect(bad?.ok).toBe(false);
  });
});
