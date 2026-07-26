/**
 * Storage plugins catalog — registers built-ins with the unified registry.
 */

import type { StoragePlugin } from '../plugins/types';
import { registry } from '../plugins/registry';
import { localStoragePlugin } from './local';
import { cloudStoragePlugin } from './cloud';
import { gitStoragePlugin } from './git';

export const BUILTIN_STORAGES: StoragePlugin[] = [
  localStoragePlugin,
  cloudStoragePlugin,
  gitStoragePlugin,
];

let registered = false;

export function ensureStoragesRegistered(): void {
  if (registered) return;
  registered = true;
  for (const s of BUILTIN_STORAGES) {
    if (!registry.getStorage(s.id)) {
      registry.registerStorage(s);
    }
  }
}

export function getStorage(id: string): StoragePlugin | undefined {
  ensureStoragesRegistered();
  return registry.getStorage(id);
}

export function listStorages(): StoragePlugin[] {
  ensureStoragesRegistered();
  return registry.listStorages();
}

export function registerDynamicStorage(plugin: StoragePlugin): void {
  ensureStoragesRegistered();
  if (!plugin?.id || plugin.kind !== 'storage') throw new Error('Invalid storage plugin');
  if (typeof plugin.list !== 'function' || typeof plugin.write !== 'function') {
    throw new Error('Storage plugin must implement list/read/write/remove');
  }
  registry.registerStorage({ ...plugin, builtIn: plugin.builtIn ?? false });
}

export function unregisterDynamicStorage(id: string): boolean {
  ensureStoragesRegistered();
  return registry.unregisterStorage(id);
}

/** @internal */
export function _resetStorageRegistrationFlag() {
  registered = false;
}
