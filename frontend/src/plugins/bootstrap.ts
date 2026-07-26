/**
 * Register all built-in plugins with the unified registry.
 * Safe to call multiple times (idempotent).
 */

import { ensureSourcesRegistered } from '../sources/catalog';
import { ensureStreamsRegistered } from '../streams/catalog';
import { ensureEnginesRegistered } from '../engines/catalog';
import { ensureStoragesRegistered } from '../storage/catalog';

let done = false;

export function ensureBuiltins(): void {
  if (done) return;
  ensureSourcesRegistered();
  ensureStreamsRegistered();
  ensureEnginesRegistered();
  ensureStoragesRegistered();
  done = true;
}

/** Alias used at app entry */
export function registerBuiltins(): void {
  ensureBuiltins();
}

/** @internal test helper — does not clear registry; only resets local flag */
export function _resetBootstrapFlag() {
  done = false;
}
