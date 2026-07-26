/**
 * Built-in local storage plugin for user Pine scripts.
 * Primary: IndexedDB · Fallback: localStorage · Migrates legacy SuperChart library keys.
 */

import type {
  ScriptDocument,
  ScriptMeta,
  StoragePlugin,
  StorageStatus,
} from '../plugins/types';
import { idbAvailable, idbReq, idbTxDone, openDb } from './idb';

const DB_NAME = 'pynescript.axis.storage';
const DB_VERSION = 1;
const STORE_SCRIPTS = 'scripts';
const STORE_KV = 'kv';

const LS_LIBRARY = 'pynescript.axis.library.v1';
const LS_DRAFT = 'pynescript.axis.library.draft';
const LS_MIGRATED = 'pynescript.axis.library.migrated';

const LEGACY_LIBRARY_KEYS = [
  'pynescript.superchart.library.v1',
  'pynescript.axis.library.legacy',
] as const;

const LEGACY_DRAFT_KEYS = [
  'pynescript.axis.editor.doc',
  'pynescript.superchart.editor.doc',
] as const;

type KvValue =
  | string
  | ScriptDocument
  | ScriptMeta[]
  | boolean
  | null
  | { content: string; name: string };

/** In-memory fallback when neither IDB nor localStorage exist (tests / SSR). */
const memLibrary = new Map<string, ScriptDocument>();
const memKv = new Map<string, KvValue>();

let dbPromise: Promise<IDBDatabase> | null = null;
let migrated = false;

function lsGet(key: string): string | null {
  try {
    if (typeof localStorage === 'undefined') return null;
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function lsSet(key: string, value: string): void {
  try {
    if (typeof localStorage === 'undefined') return;
    localStorage.setItem(key, value);
  } catch {
    /* quota / private mode */
  }
}

function lsRemove(key: string): void {
  try {
    if (typeof localStorage === 'undefined') return;
    localStorage.removeItem(key);
  } catch {
    /* ignore */
  }
}

function newId(): string {
  return `s_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

function toMeta(doc: ScriptDocument): ScriptMeta {
  const { content: _c, ...meta } = doc;
  return meta;
}

function normalizeDoc(raw: Partial<ScriptDocument> & { script?: string }): ScriptDocument {
  const now = Date.now();
  const content = raw.content ?? raw.script ?? '';
  return {
    id: raw.id || newId(),
    name: raw.name || 'Untitled',
    description: raw.description,
    path: raw.path,
    content: String(content),
    updatedAt: raw.updatedAt || now,
    createdAt: raw.createdAt || now,
    revision: raw.revision || `local-${now}`,
    tags: raw.tags,
  };
}

async function getDb(): Promise<IDBDatabase | null> {
  if (!idbAvailable()) return null;
  if (!dbPromise) {
    dbPromise = openDb(DB_NAME, DB_VERSION, (db) => {
      if (!db.objectStoreNames.contains(STORE_SCRIPTS)) {
        db.createObjectStore(STORE_SCRIPTS, { keyPath: 'id' });
      }
      if (!db.objectStoreNames.contains(STORE_KV)) {
        db.createObjectStore(STORE_KV);
      }
    }).catch((err) => {
      dbPromise = null;
      throw err;
    });
  }
  try {
    return await dbPromise;
  } catch {
    return null;
  }
}

// --- localStorage fallback ---

function lsReadLibrary(): ScriptDocument[] {
  const raw = lsGet(LS_LIBRARY);
  if (!raw) {
    if (memLibrary.size) return [...memLibrary.values()].map((d) => normalizeDoc(d));
    return [];
  }
  try {
    const arr = JSON.parse(raw);
    if (!Array.isArray(arr)) return [];
    return arr.map((x: Partial<ScriptDocument>) => normalizeDoc(x));
  } catch {
    return [];
  }
}

function lsWriteLibrary(docs: ScriptDocument[]) {
  memLibrary.clear();
  for (const d of docs) memLibrary.set(d.id, d);
  lsSet(LS_LIBRARY, JSON.stringify(docs));
}

// --- IDB ops ---

async function idbList(): Promise<ScriptDocument[]> {
  const db = await getDb();
  if (!db) return lsReadLibrary();
  const tx = db.transaction(STORE_SCRIPTS, 'readonly');
  const store = tx.objectStore(STORE_SCRIPTS);
  const all = await idbReq(store.getAll() as IDBRequest<ScriptDocument[]>);
  await idbTxDone(tx);
  return (all || []).map((d) => normalizeDoc(d));
}

async function idbGet(id: string): Promise<ScriptDocument | undefined> {
  const db = await getDb();
  if (!db) return lsReadLibrary().find((d) => d.id === id);
  const tx = db.transaction(STORE_SCRIPTS, 'readonly');
  const doc = await idbReq(tx.objectStore(STORE_SCRIPTS).get(id) as IDBRequest<ScriptDocument | undefined>);
  await idbTxDone(tx);
  return doc ? normalizeDoc(doc) : undefined;
}

async function idbPut(doc: ScriptDocument): Promise<void> {
  const db = await getDb();
  if (!db) {
    const lib = lsReadLibrary().filter((d) => d.id !== doc.id);
    lib.push(doc);
    lsWriteLibrary(lib);
    return;
  }
  const tx = db.transaction(STORE_SCRIPTS, 'readwrite');
  tx.objectStore(STORE_SCRIPTS).put(doc);
  await idbTxDone(tx);
}

async function idbDelete(id: string): Promise<void> {
  const db = await getDb();
  if (!db) {
    lsWriteLibrary(lsReadLibrary().filter((d) => d.id !== id));
    return;
  }
  const tx = db.transaction(STORE_SCRIPTS, 'readwrite');
  tx.objectStore(STORE_SCRIPTS).delete(id);
  await idbTxDone(tx);
}

async function idbKvGet(key: string): Promise<KvValue> {
  const db = await getDb();
  if (!db) {
    if (memKv.has(key)) return memKv.get(key) ?? null;
    const raw = lsGet(`${LS_DRAFT}:${key}`);
    if (raw == null) return null;
    try {
      return JSON.parse(raw) as KvValue;
    } catch {
      return raw;
    }
  }
  const tx = db.transaction(STORE_KV, 'readonly');
  const v = await idbReq(tx.objectStore(STORE_KV).get(key) as IDBRequest<KvValue>);
  await idbTxDone(tx);
  return v ?? null;
}

async function idbKvSet(key: string, value: KvValue): Promise<void> {
  const db = await getDb();
  if (!db) {
    memKv.set(key, value);
    lsSet(`${LS_DRAFT}:${key}`, JSON.stringify(value));
    return;
  }
  const tx = db.transaction(STORE_KV, 'readwrite');
  tx.objectStore(STORE_KV).put(value, key);
  await idbTxDone(tx);
}

// --- Migration ---

async function migrateOnce(): Promise<void> {
  if (migrated) return;
  migrated = true;

  const already = lsGet(LS_MIGRATED) === '1';
  const flag = await idbKvGet('migratedLibrary');
  if (already || flag === true) return;

  const existing = await idbList();
  const have = new Set(existing.map((d) => d.id));
  let imported = 0;

  for (const key of LEGACY_LIBRARY_KEYS) {
    try {
      const raw = lsGet(key);
      if (!raw) continue;
      const arr = JSON.parse(raw);
      if (!Array.isArray(arr)) continue;
      for (const item of arr) {
        const doc = normalizeDoc(item);
        if (have.has(doc.id)) continue;
        await idbPut(doc);
        have.add(doc.id);
        imported++;
      }
    } catch {
      /* ignore bad legacy */
    }
  }

  // Draft from editor doc keys if no draft yet
  const draft = await idbKvGet('draft');
  if (!draft) {
    for (const key of LEGACY_DRAFT_KEYS) {
      const content = lsGet(key);
      if (content && content.trim()) {
        await idbKvSet('draft', { content, name: 'Draft' });
        break;
      }
    }
  }

  lsSet(LS_MIGRATED, '1');
  await idbKvSet('migratedLibrary', true);
  if (imported > 0) {
    console.info(`[storage-local] migrated ${imported} script(s) from legacy keys`);
  }
}

/** Reset migration flag (tests). */
export function _resetLocalMigrationFlag() {
  migrated = false;
}

export const localStoragePlugin: StoragePlugin = {
  id: 'local',
  name: 'Local (this browser)',
  kind: 'storage',
  builtIn: true,
  description:
    'Stores your Pine scripts in this browser (IndexedDB, with localStorage fallback). Works offline.',
  capabilities: { offline: true },
  configSchema: {
    namespace: { type: 'string', default: 'default', label: 'Namespace (advanced)' },
  },

  async list(opts) {
    await migrateOnce();
    let docs = await idbList();
    const prefix = opts?.prefix;
    if (prefix) {
      docs = docs.filter(
        (d) => d.name.startsWith(prefix) || (d.path && d.path.startsWith(prefix)),
      );
    }
    docs.sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
    return docs.map(toMeta);
  },

  async read(id) {
    await migrateOnce();
    const doc = await idbGet(id);
    if (!doc) throw new Error(`Script not found: ${id}`);
    return doc;
  },

  async write(doc) {
    await migrateOnce();
    const now = Date.now();
    const prev = doc.id ? await idbGet(doc.id).catch(() => undefined) : undefined;
    const next = normalizeDoc({
      ...doc,
      id: doc.id || newId(),
      createdAt: prev?.createdAt || doc.createdAt || now,
      updatedAt: now,
      revision: `local-${now}`,
    });
    await idbPut(next);
    return toMeta(next);
  },

  async remove(id) {
    await migrateOnce();
    await idbDelete(id);
  },

  async saveDraft(doc) {
    await migrateOnce();
    await idbKvSet('draft', {
      content: doc.content ?? '',
      name: doc.name || 'Draft',
    });
    // Mirror to legacy editor doc key for bridge / late joiners
    lsSet('pynescript.axis.editor.doc', doc.content ?? '');
  },

  async loadDraft() {
    await migrateOnce();
    const v = await idbKvGet('draft');
    if (v && typeof v === 'object' && v !== null && 'content' in (v as object)) {
      const d = v as { content: string; name?: string };
      return { content: String(d.content ?? ''), name: d.name };
    }
    if (typeof v === 'string') return { content: v, name: 'Draft' };
    // Fallback editor key
    const content = lsGet('pynescript.axis.editor.doc');
    if (content) return { content, name: 'Draft' };
    return null;
  },

  async getStatus(): Promise<StorageStatus> {
    const offline = true;
    return {
      connected: true,
      dirty: false,
      remote: idbAvailable() ? 'indexedDB' : 'localStorage',
      branch: undefined,
      lastSyncAt: Date.now(),
      error: offline ? undefined : undefined,
    };
  },
};

/** Test helper: wipe library (localStorage path + flag). */
export async function _clearLocalLibraryForTests() {
  migrated = false;
  memLibrary.clear();
  memKv.clear();
  lsRemove(LS_LIBRARY);
  lsRemove(LS_MIGRATED);
  lsRemove(`${LS_DRAFT}:draft`);
  lsRemove(`${LS_DRAFT}:migratedLibrary`);
  const db = await getDb();
  if (db) {
    const tx = db.transaction([STORE_SCRIPTS, STORE_KV], 'readwrite');
    tx.objectStore(STORE_SCRIPTS).clear();
    tx.objectStore(STORE_KV).clear();
    await idbTxDone(tx);
  }
}
