/**
 * Cloud storage plugin unit tests (mocked fetch).
 * Run: `bun test frontend/tests/storage-cloud.test.ts`
 */

import { describe, expect, it, beforeEach, afterEach, mock } from 'bun:test';
import { registry } from '../src/plugins/registry';
import { _resetBootstrapFlag, ensureBuiltins } from '../src/plugins/bootstrap';
import { _resetStorageRegistrationFlag, listStorages } from '../src/storage/catalog';
import { cloudStoragePlugin } from '../src/storage/cloud';
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

beforeEach(() => {
  (globalThis as unknown as { localStorage: MemoryStorage }).localStorage = new MemoryStorage();
  registry.clear();
  _resetSourceRegistrationFlag();
  _resetStreamRegistrationFlag();
  _resetEngineRegistrationFlag();
  _resetStorageRegistrationFlag();
  _resetBootstrapFlag();
  ensureBuiltins();
  setStore('pluginsConfig', 'storage:cloud', {
    endpoint: 'http://cloud.test',
    apiKey: 'pn_' + 'a'.repeat(48),
  });
});

afterEach(() => {
  globalThis.fetch = originalFetch;
});

describe('storage-cloud plugin', () => {
  it('is registered as built-in', () => {
    expect(listStorages().map((s) => s.id)).toContain('cloud');
  });

  it('list() maps remote scripts', async () => {
    globalThis.fetch = mock(async (input: RequestInfo | URL) => {
      const url = String(input);
      expect(url).toContain('/api/scripts');
      return new Response(
        JSON.stringify({
          status: 'success',
          scripts: [
            {
              id: 's1',
              name: 'Remote',
              revision: 'r1',
              createdAt: 1,
              updatedAt: 2,
            },
          ],
        }),
        { status: 200 },
      );
    }) as typeof fetch;

    const list = await cloudStoragePlugin.list({
      config: { endpoint: 'http://cloud.test', apiKey: 'pn_' + 'a'.repeat(48) },
    });
    expect(list).toHaveLength(1);
    expect(list[0].name).toBe('Remote');
  });

  it('write() PUTs script and returns meta', async () => {
    globalThis.fetch = mock(async (_input: RequestInfo | URL, init?: RequestInit) => {
      expect(init?.method).toBe('PUT');
      const auth = (init?.headers as Record<string, string>)?.Authorization;
      expect(auth).toMatch(/^Bearer pn_/);
      return new Response(
        JSON.stringify({
          status: 'success',
          script: {
            id: 's2',
            name: 'Saved',
            content: 'plot(1)',
            revision: 'r2',
            createdAt: 1,
            updatedAt: 3,
          },
        }),
        { status: 200 },
      );
    }) as typeof fetch;

    const meta = await cloudStoragePlugin.write(
      {
        id: 's2',
        name: 'Saved',
        content: 'plot(1)',
        updatedAt: Date.now(),
      },
      { endpoint: 'http://cloud.test', apiKey: 'pn_' + 'a'.repeat(48) },
    );
    expect(meta.id).toBe('s2');
    expect(meta.revision).toBe('r2');
  });

  it('throws when API key missing', async () => {
    setStore('pluginsConfig', 'storage:cloud', { endpoint: 'http://cloud.test', apiKey: '' });
    await expect(
      cloudStoragePlugin.list({ config: { endpoint: 'http://cloud.test', apiKey: '' } }),
    ).rejects.toThrow(/API key/);
  });

  it('getStatus probes /health', async () => {
    globalThis.fetch = mock(async (input: RequestInfo | URL) => {
      expect(String(input)).toContain('/health');
      return new Response(JSON.stringify({ status: 'healthy' }), { status: 200 });
    }) as typeof fetch;

    const st = await cloudStoragePlugin.getStatus?.({
      endpoint: 'http://cloud.test',
      apiKey: 'pn_' + 'a'.repeat(48),
    });
    expect(st?.connected).toBe(true);
  });
});
