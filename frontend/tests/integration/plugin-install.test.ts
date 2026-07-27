/**
 * Dynamic plugin install from fixture URL → registry.
 */
import './../setup';
import { describe, expect, it, beforeEach } from 'bun:test';
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';
import { registry } from '../../src/plugins/registry';
import { _resetBootstrapFlag, ensureBuiltins } from '../../src/plugins/bootstrap';
import { _resetSourceRegistrationFlag } from '../../src/sources/catalog';
import { _resetStreamRegistrationFlag } from '../../src/streams/catalog';
import { _resetEngineRegistrationFlag } from '../../src/engines/catalog';
import { _resetStorageRegistrationFlag } from '../../src/storage/catalog';
import { loadPluginFromUrl, getInstalledPlugins } from '../../src/plugins/loader';
import { listEngines } from '../../src/engines/catalog';

beforeEach(() => {
  registry.clear();
  _resetSourceRegistrationFlag();
  _resetStreamRegistrationFlag();
  _resetEngineRegistrationFlag();
  _resetStorageRegistrationFlag();
  _resetBootstrapFlag();
  ensureBuiltins();
  localStorage.removeItem('pynescript.axis.plugins.v1');
});

describe('plugin install integration', () => {
  it('loads fixture engine module into registry', async () => {
    const fixture = resolve(import.meta.dir, '../fixtures/plugins/fake-engine.js');
    const url = pathToFileURL(fixture).href;
    const installed = await loadPluginFromUrl(url);
    expect(installed.id).toBeTruthy();
    expect(installed.kind).toBe('engine');

    const engines = listEngines();
    expect(engines.some((e) => e.id === installed.id)).toBe(true);

    const listed = getInstalledPlugins();
    expect(listed.some((p) => p.id === installed.id)).toBe(true);
  });
});
