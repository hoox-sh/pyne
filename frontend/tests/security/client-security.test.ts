/**
 * Client-side security tests for AXIS plugins / storage.
 */

import '../setup';
import { describe, expect, it, beforeEach } from 'bun:test';
import { pathToFileURL } from 'node:url';
import { join } from 'node:path';
import { registry } from '../../src/plugins/registry';
import { ensureBuiltins, _resetBootstrapFlag } from '../../src/plugins/bootstrap';
import { _resetSourceRegistrationFlag } from '../../src/sources/catalog';
import { _resetStreamRegistrationFlag } from '../../src/streams/catalog';
import { _resetEngineRegistrationFlag } from '../../src/engines/catalog';
import { _resetStorageRegistrationFlag } from '../../src/storage/catalog';
import {
  loadPluginFromUrl,
  assertSafePluginUrl,
  normalizePluginUrl,
  PLUGINS_KEY,
} from '../../src/plugins/loader';
import { STORAGE_KEY } from '../../src/store';

beforeEach(() => {
  registry.clear();
  _resetSourceRegistrationFlag();
  _resetStreamRegistrationFlag();
  _resetEngineRegistrationFlag();
  _resetStorageRegistrationFlag();
  _resetBootstrapFlag();
  localStorage.removeItem(PLUGINS_KEY);
  ensureBuiltins();
});

describe('plugin URL safety', () => {
  it('rejects javascript: scheme', () => {
    expect(() => assertSafePluginUrl('javascript:alert(1)')).toThrow(/not allowed/i);
  });

  it('rejects data:text/html', () => {
    expect(() => assertSafePluginUrl('data:text/html,<script>alert(1)</script>')).toThrow(
      /not allowed/i,
    );
  });

  it('allows relative and https plugin paths', () => {
    expect(() => assertSafePluginUrl('/plugins/example.js')).not.toThrow();
    expect(() => assertSafePluginUrl('https://cdn.example/plugin.js')).not.toThrow();
  });

  it('normalizePluginUrl does not open open-redirect style src rewrite on js urls', () => {
    // still blocked by assertSafePluginUrl after normalize
    const n = normalizePluginUrl('javascript:void(0)');
    expect(() => assertSafePluginUrl(n)).toThrow();
  });

  it('loadPluginFromUrl rejects javascript:', async () => {
    await expect(loadPluginFromUrl('javascript:alert(1)')).rejects.toThrow(/not allowed|URL/i);
  });

  it('rejects storage plugins via URL', async () => {
    const code = `export default { id: 'evil', name: 'E', kind: 'storage', list(){}, read(){}, write(){}, remove(){} }`;
    const url = `data:text/javascript,${encodeURIComponent(code)}`;
    await expect(loadPluginFromUrl(url)).rejects.toThrow(/storage/i);
  });
});

describe('localStorage poisoning', () => {
  it('corrupt plugins list does not throw on read path', async () => {
    localStorage.setItem(PLUGINS_KEY, '{not-json');
    // re-import style: getInstalledPlugins via load empty
    const { getInstalledPlugins } = await import('../../src/plugins/loader');
    expect(getInstalledPlugins()).toEqual([]);
  });

  it('corrupt app state key is survivable on next parse attempt', () => {
    localStorage.setItem(STORAGE_KEY, '[[[bad');
    // store already hydrated; ensure we can still write
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ symbol: 'ETHUSDT' }));
    expect(localStorage.getItem(STORAGE_KEY)).toContain('ETHUSDT');
  });
});

describe('git/cloud error messages', () => {
  it('GitHub error does not embed full token in message', async () => {
    const token = 'ghp_supersecret_token_value_12345';
    const { githubStatus } = await import('../../src/storage/git-github');
    const original = globalThis.fetch;
    globalThis.fetch = (async () =>
      new Response(JSON.stringify({ message: 'Bad credentials' }), { status: 401 })) as typeof fetch;
    try {
      const st = await githubStatus({
        provider: 'github',
        apiBaseUrl: 'https://api.github.com',
        token,
        owner: 'o',
        repo: 'r',
        projectId: '',
        branch: 'main',
        basePath: 'pine-library',
        autoPush: true,
        commitMessageTemplate: 'x',
      });
      expect(st.connected).toBe(false);
      expect(st.error || '').not.toContain(token);
    } finally {
      globalThis.fetch = original;
    }
  });
});

describe('fixture plugin load still works', () => {
  it('loads file URL engine fixture', async () => {
    const url = pathToFileURL(join(import.meta.dir, '../fixtures/plugins/fake-engine.js')).href;
    const entry = await loadPluginFromUrl(url);
    expect(entry.kind).toBe('engine');
  });
});
