/**
 * Public entry for the AXIS plugin system.
 */

export { registry, PluginRegistry } from './registry';
export { ensureBuiltins, registerBuiltins } from './bootstrap';
export {
  getActiveSource,
  getActiveStream,
  getActiveEngine,
  getActiveStorage,
  getActiveSourceId,
  getActiveStreamId,
  getActiveEngineId,
  getActiveStorageId,
  getActiveSourceConfig,
  getActiveStreamConfig,
  getActiveEngineConfig,
} from './active';
export {
  loadPluginFromUrl,
  restoreInstalledPlugins,
  removePlugin,
  getInstalledPlugins,
  PLUGINS_KEY,
} from './loader';
export type * from './types';
export { listStorages, getStorage } from '../storage/catalog';
export {
  listScripts,
  readScript,
  writeScript,
  removeScript,
  saveDraft,
  loadDraft,
  exportLibraryJson,
  importLibraryJson,
  getStorageStatus,
} from '../storage/service';
