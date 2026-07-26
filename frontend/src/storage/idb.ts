/**
 * Minimal IndexedDB helpers for AXIS script storage.
 * Falls back gracefully when IDB is unavailable (SSR / some test runners).
 */

export function idbAvailable(): boolean {
  try {
    return typeof indexedDB !== 'undefined' && indexedDB !== null;
  } catch {
    return false;
  }
}

export function openDb(
  name: string,
  version: number,
  onUpgrade: (db: IDBDatabase, oldVersion: number) => void,
): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (!idbAvailable()) {
      reject(new Error('IndexedDB unavailable'));
      return;
    }
    const req = indexedDB.open(name, version);
    req.onerror = () => reject(req.error || new Error('IDB open failed'));
    req.onsuccess = () => resolve(req.result);
    req.onupgradeneeded = (ev) => {
      const oldVersion = (ev.target as IDBOpenDBRequest).result
        ? (ev as IDBVersionChangeEvent).oldVersion
        : 0;
      onUpgrade(req.result, oldVersion);
    };
  });
}

export function idbReq<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error('IDB request failed'));
  });
}

export function idbTxDone(tx: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error || new Error('IDB transaction failed'));
    tx.onabort = () => reject(tx.error || new Error('IDB transaction aborted'));
  });
}
