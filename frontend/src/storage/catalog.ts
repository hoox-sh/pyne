// Copyright (C) 2024-2026 jango_blockchained
//
// This file is part of pynescript.
//
// pynescript is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// pynescript is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
//
// SPDX-License-Identifier: AGPL-3.0-or-later

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
