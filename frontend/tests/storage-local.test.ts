/**
 * Local storage plugin + library service tests.
 * Uses localStorage fallback when IndexedDB is unavailable.
 * Run: `bun test frontend/tests/storage-local.test.ts`
 */

import { describe, expect, it, beforeEach } from 'bun:test';
import { registry } from '../src/plugins/registry';
import { _resetBootstrapFlag, ensureBuiltins } from '../src/plugins/bootstrap';
import { _resetStorageRegistrationFlag, listStorages } from '../src/storage/catalog';
import {
  localStoragePlugin,
  _clearLocalLibraryForTests,
  _resetLocalMigrationFlag,
} from '../src/storage/local';
import {
  listScripts,
  writeScript,
  readScript,
  removeScript,
  saveDraft,
  loadDraft,
  exportLibraryJson,
  importLibraryJson,
} from '../src/storage/service';
import { _resetSourceRegistrationFlag } from '../src/sources/catalog';
import { _resetStreamRegistrationFlag } from '../src/streams/catalog';
import { _resetEngineRegistrationFlag } from '../src/engines/catalog';

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

beforeEach(async () => {
  (globalThis as unknown as { localStorage: MemoryStorage }).localStorage = new MemoryStorage();
  registry.clear();
  _resetSourceRegistrationFlag();
  _resetStreamRegistrationFlag();
  _resetEngineRegistrationFlag();
  _resetStorageRegistrationFlag();
  _resetBootstrapFlag();
  _resetLocalMigrationFlag();
  await _clearLocalLibraryForTests();
  ensureBuiltins();
});

describe('storage-local plugin', () => {
  it('is registered as built-in storage', () => {
    const ids = listStorages().map((s) => s.id);
    expect(ids).toContain('local');
    expect(listStorages().find((s) => s.id === 'local')?.builtIn).toBe(true);
  });

  it('write / list / read / remove round-trip', async () => {
    const meta = await localStoragePlugin.write({
      id: 's_test1',
      name: 'RSI',
      description: 'demo',
      content: '//@version=5\nindicator("x")\nplot(close)',
      updatedAt: Date.now(),
    });
    expect(meta.id).toBe('s_test1');
    expect(meta.name).toBe('RSI');
    expect(meta.revision).toBeDefined();

    const list = await localStoragePlugin.list();
    expect(list.some((m) => m.id === 's_test1')).toBe(true);

    const doc = await localStoragePlugin.read('s_test1');
    expect(doc.content).toContain('indicator');
    expect(doc.name).toBe('RSI');

    await localStoragePlugin.remove('s_test1');
    const list2 = await localStoragePlugin.list();
    expect(list2.some((m) => m.id === 's_test1')).toBe(false);
  });

  it('saveDraft / loadDraft', async () => {
    await localStoragePlugin.saveDraft?.({ content: 'plot(1)', name: 'Draft' });
    const d = await localStoragePlugin.loadDraft?.();
    expect(d?.content).toBe('plot(1)');
  });

  it('migrates legacy superchart library once', async () => {
    localStorage.setItem(
      'pynescript.superchart.library.v1',
      JSON.stringify([
        {
          id: 'legacy1',
          name: 'Old Script',
          description: 'from v1',
          script: 'plot(open)',
          savedAt: 1000,
        },
      ]),
    );
    _resetLocalMigrationFlag();
    localStorage.removeItem('pynescript.axis.library.migrated');

    const list = await localStoragePlugin.list();
    expect(list.some((m) => m.id === 'legacy1' || m.name === 'Old Script')).toBe(true);
    const found = list.find((m) => m.name === 'Old Script');
    expect(found).toBeDefined();
    if (found) {
      const doc = await localStoragePlugin.read(found.id);
      expect(doc.content).toContain('plot(open)');
    }
  });
});

describe('storage service', () => {
  it('writeScript / listScripts via active local backend', async () => {
    await writeScript({
      id: 'svc1',
      name: 'Service Test',
      content: 'plot(high)',
    });
    const list = await listScripts();
    expect(list.some((m) => m.id === 'svc1')).toBe(true);
    const doc = await readScript('svc1');
    expect(doc.content).toBe('plot(high)');
    await removeScript('svc1');
  });

  it('export / import JSON', async () => {
    await writeScript({ id: 'ex1', name: 'A', content: 'plot(1)' });
    const exported = await exportLibraryJson();
    expect(exported.some((d) => d.id === 'ex1')).toBe(true);
    await removeScript('ex1');
    const n = await importLibraryJson(exported, { forceNewIds: true });
    expect(n).toBeGreaterThanOrEqual(1);
    const list = await listScripts();
    expect(list.length).toBeGreaterThanOrEqual(1);
  });

  it('saveDraft dual-write helper', async () => {
    await saveDraft('//@version=5\nplot(close)', 'Main');
    const d = await loadDraft();
    expect(d?.content).toContain('plot(close)');
  });
});

describe('storage-local extras', () => {
  it('getStatus reports connected local backend', async () => {
    const st = await localStoragePlugin.getStatus?.();
    expect(st?.connected).toBe(true);
    expect(st?.remote === 'indexedDB' || st?.remote === 'localStorage').toBe(true);
  });

  it('survives corrupt library JSON in localStorage', async () => {
    localStorage.setItem('pynescript.axis.library.v1', '{not-json');
    // Should not throw — empty or recoverable list
    const list = await localStoragePlugin.list();
    expect(Array.isArray(list)).toBe(true);
  });

  it('auto-generates id when write omits id', async () => {
    const meta = await localStoragePlugin.write({
      name: 'No Id',
      content: 'plot(1)',
      updatedAt: Date.now(),
    } as never);
    expect(meta.id).toMatch(/^s_/);
    const doc = await localStoragePlugin.read(meta.id);
    expect(doc.name).toBe('No Id');
  });
});
