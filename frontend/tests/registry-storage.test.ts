/**
 * Registry storage/component register + unregister.
 */

import './setup';
import { describe, expect, it, beforeEach } from 'bun:test';
import { PluginRegistry } from '../src/plugins/registry';
import type { StoragePlugin, ComponentPlugin } from '../src/plugins/types';

const memStorage = (): StoragePlugin => ({
  id: 'mem',
  name: 'Mem',
  kind: 'storage',
  builtIn: false,
  async list() {
    return [];
  },
  async read() {
    throw new Error('nf');
  },
  async write(doc) {
    return { id: doc.id, name: doc.name, updatedAt: Date.now() };
  },
  async remove() {},
});

describe('registry storage/component', () => {
  let r: PluginRegistry;

  beforeEach(() => {
    r = new PluginRegistry();
  });

  it('registerStorage / list / unregister', () => {
    r.registerStorage(memStorage());
    expect(r.listStorages()).toHaveLength(1);
    expect(r.getStorage('mem')?.name).toBe('Mem');
    expect(r.unregisterStorage('mem')).toBe(true);
    expect(r.listStorages()).toHaveLength(0);
  });

  it('protects built-in storage', () => {
    r.registerStorage({ ...memStorage(), id: 'local', builtIn: true });
    expect(r.unregisterStorage('local')).toBe(false);
    expect(r.unregisterStorage('local', { allowBuiltIn: true })).toBe(true);
  });

  it('registerComponent / list / unregister', () => {
    const c: ComponentPlugin = {
      id: 'c1',
      name: 'C',
      kind: 'component',
      slots: ['manager-tab'],
      mount: () => () => {},
    };
    r.registerComponent(c);
    expect(r.listComponents()).toHaveLength(1);
    expect(r.unregister('component', 'c1')).toBe(true);
  });

  it('register() dispatches storage', () => {
    r.register(memStorage());
    expect(r.summary().storages).toHaveLength(1);
  });

  it('rejects bad storage', () => {
    expect(() =>
      r.registerStorage({ id: 'x', name: 'x', kind: 'storage' } as never),
    ).toThrow(/list/);
  });
});
