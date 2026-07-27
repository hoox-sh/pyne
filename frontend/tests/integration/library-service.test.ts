/**
 * Library service roundtrip on local storage.
 */

import '../setup';
import { describe, expect, it, beforeEach } from 'bun:test';
import { registry } from '../../src/plugins/registry';
import { ensureBuiltins, _resetBootstrapFlag } from '../../src/plugins/bootstrap';
import { _resetSourceRegistrationFlag } from '../../src/sources/catalog';
import { _resetStreamRegistrationFlag } from '../../src/streams/catalog';
import { _resetEngineRegistrationFlag } from '../../src/engines/catalog';
import { _resetStorageRegistrationFlag } from '../../src/storage/catalog';
import {
  _clearLocalLibraryForTests,
  _resetLocalMigrationFlag,
} from '../../src/storage/local';
import { setActivePlugin } from '../../src/store';
import {
  writeScript,
  listScripts,
  readScript,
  removeScript,
  exportLibraryJson,
  importLibraryJson,
  saveDraft,
  loadDraft,
} from '../../src/storage/service';

beforeEach(async () => {
  registry.clear();
  _resetSourceRegistrationFlag();
  _resetStreamRegistrationFlag();
  _resetEngineRegistrationFlag();
  _resetStorageRegistrationFlag();
  _resetBootstrapFlag();
  _resetLocalMigrationFlag();
  await _clearLocalLibraryForTests();
  ensureBuiltins();
  setActivePlugin('storage', 'local');
});

describe('library service', () => {
  it('write → list → read → export → remove → import', async () => {
    await writeScript({
      id: 'lib1',
      name: 'Alpha',
      content: 'plot(open)',
    });
    const list = await listScripts();
    expect(list.some((m) => m.id === 'lib1')).toBe(true);

    const doc = await readScript('lib1');
    expect(doc.content).toBe('plot(open)');

    const exported = await exportLibraryJson();
    expect(exported.some((d) => d.id === 'lib1')).toBe(true);

    await removeScript('lib1');
    expect((await listScripts()).some((m) => m.id === 'lib1')).toBe(false);

    const n = await importLibraryJson(exported, { forceNewIds: true });
    expect(n).toBeGreaterThanOrEqual(1);
    expect((await listScripts()).length).toBeGreaterThanOrEqual(1);
  });

  it('draft dual-write', async () => {
    await saveDraft('//@version=5\nplot(high)', 'Drafty');
    const d = await loadDraft();
    expect(d?.content).toContain('plot(high)');
  });
});
