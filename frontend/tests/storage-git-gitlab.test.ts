/**
 * GitLab storage adapter tests (mocked API).
 */

import './setup';
import { describe, expect, it, beforeEach, afterEach, mock } from 'bun:test';
import { registry } from '../src/plugins/registry';
import { ensureBuiltins, _resetBootstrapFlag } from '../src/plugins/bootstrap';
import { _resetStorageRegistrationFlag } from '../src/storage/catalog';
import { _resetSourceRegistrationFlag } from '../src/sources/catalog';
import { _resetStreamRegistrationFlag } from '../src/streams/catalog';
import { _resetEngineRegistrationFlag } from '../src/engines/catalog';
import { setStore } from '../src/store';
import { gitStoragePlugin } from '../src/storage/git';
import * as gl from '../src/storage/git-gitlab';

const originalFetch = globalThis.fetch;

const CFG = {
  provider: 'gitlab' as const,
  apiBaseUrl: 'https://gitlab.com/api/v4',
  token: 'glpat-testtoken00000000',
  owner: 'acme',
  repo: 'pines',
  projectId: 'acme%2Fpines',
  branch: 'main',
  basePath: 'pine-library',
  autoPush: true,
  commitMessageTemplate: 'chore(pine): save {{name}} @ {{iso}}',
};

function b64(s: string): string {
  return btoa(s);
}

beforeEach(() => {
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

describe('git-gitlab adapter', () => {
  it('list reads index.json', async () => {
    const index = {
      version: 1,
      scripts: [{ id: 's1', name: 'RSI', path: 'pine-library/library/s1.pine', updatedAt: 1 }],
    };
    globalThis.fetch = mock(async (input: RequestInfo | URL) => {
      const url = String(input);
      expect(url).toContain('/repository/files/');
      expect(url).toContain('index.json');
      return new Response(
        JSON.stringify({
          encoding: 'base64',
          content: b64(JSON.stringify(index)),
          blob_id: 'b1',
        }),
        { status: 200 },
      );
    }) as typeof fetch;

    const list = await gl.gitlabList(CFG);
    expect(list).toHaveLength(1);
    expect(list[0].name).toBe('RSI');
  });

  it('list empty when index 404', async () => {
    globalThis.fetch = mock(async () => new Response('{}', { status: 404 })) as typeof fetch;
    const list = await gl.gitlabList(CFG);
    expect(list).toEqual([]);
  });

  it('write creates pine + index', async () => {
    const calls: string[] = [];
    globalThis.fetch = mock(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method || 'GET').toUpperCase();
      calls.push(`${method} ${url}`);
      if (method === 'GET') {
        return new Response(JSON.stringify({ message: '404' }), { status: 404 });
      }
      if (method === 'POST' || method === 'PUT') {
        return new Response(JSON.stringify({ file_path: 'x', commit_id: 'c1' }), { status: 201 });
      }
      return new Response('{}', { status: 500 });
    }) as typeof fetch;

    const meta = await gl.gitlabWrite(CFG, {
      id: 's_new',
      name: 'GL Script',
      content: 'plot(1)',
      updatedAt: Date.now(),
    });
    expect(meta.id).toBe('s_new');
    expect(calls.some((c) => c.startsWith('POST') || c.startsWith('PUT'))).toBe(true);
  });

  it('read loads content', async () => {
    globalThis.fetch = mock(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('index.json')) {
        return new Response(
          JSON.stringify({
            encoding: 'text',
            content: JSON.stringify({
              version: 1,
              scripts: [{ id: 's1', name: 'A', path: 'pine-library/library/s1.pine', updatedAt: 1 }],
            }),
          }),
          { status: 200 },
        );
      }
      return new Response(
        JSON.stringify({ encoding: 'text', content: 'plot(close)', blob_id: 'bb' }),
        { status: 200 },
      );
    }) as typeof fetch;

    const doc = await gl.gitlabRead(CFG, 's1');
    expect(doc.content).toContain('plot');
    expect(doc.name).toBe('A');
  });

  it('remove deletes file and updates index', async () => {
    let indexBody = JSON.stringify({
      version: 1,
      scripts: [{ id: 's1', name: 'A', path: 'pine-library/library/s1.pine', updatedAt: 1 }],
    });
    globalThis.fetch = mock(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method || 'GET').toUpperCase();
      if (method === 'GET' && url.includes('index.json')) {
        return new Response(JSON.stringify({ encoding: 'text', content: indexBody }), {
          status: 200,
        });
      }
      if (method === 'GET' && url.includes('.pine')) {
        return new Response(JSON.stringify({ encoding: 'text', content: 'x', blob_id: '1' }), {
          status: 200,
        });
      }
      if (method === 'DELETE') {
        return new Response(JSON.stringify({}), { status: 200 });
      }
      if (method === 'PUT' || method === 'POST') {
        if (init?.body) {
          const b = JSON.parse(String(init.body));
          if (b.content && String(b.content).includes('scripts')) indexBody = b.content;
        }
        return new Response(JSON.stringify({ commit_id: 'c2' }), { status: 200 });
      }
      return new Response('{}', { status: 500 });
    }) as typeof fetch;

    await gl.gitlabRemove(CFG, 's1');
    const list = await gl.gitlabList(CFG);
    expect(list.some((s) => s.id === 's1')).toBe(false);
  });

  it('status hits project endpoint', async () => {
    globalThis.fetch = mock(async (input: RequestInfo | URL) => {
      expect(String(input)).toContain('/projects/');
      return new Response(JSON.stringify({ path_with_namespace: 'acme/pines' }), { status: 200 });
    }) as typeof fetch;

    const st = await gl.gitlabStatus(CFG);
    expect(st.connected).toBe(true);
    expect(st.remote).toContain('acme');
  });

  it('plugin routes provider=gitlab', async () => {
    globalThis.fetch = mock(async () => new Response(JSON.stringify({ message: '404' }), { status: 404 })) as typeof fetch;
    const list = await gitStoragePlugin.list({ config: CFG });
    expect(list).toEqual([]);
  });
});
