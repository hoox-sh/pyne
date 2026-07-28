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
 * High-level script library API used by UI and editor.
 * Always dual-writes drafts to the local storage plugin for crash recovery.
 */

import type { ScriptDocument, ScriptMeta, StoragePlugin, StorageStatus } from '../plugins/types';
import { ensureBuiltins } from '../plugins/bootstrap';
import { getActiveStorage, getActiveStorageId } from '../plugins/active';
import { getStorage } from './catalog';
import { localStoragePlugin } from './local';
import { appendLog } from '../store';

function requireActive(): StoragePlugin {
  ensureBuiltins();
  const p = getActiveStorage() || getStorage('local') || localStoragePlugin;
  if (!p) throw new Error('No storage plugin available');
  return p;
}

function localAlways(): StoragePlugin {
  ensureBuiltins();
  return getStorage('local') || localStoragePlugin;
}

export async function listScripts(prefix?: string): Promise<ScriptMeta[]> {
  return requireActive().list({ prefix });
}

export async function readScript(id: string): Promise<ScriptDocument> {
  return requireActive().read(id);
}

export async function writeScript(
  doc: Omit<ScriptDocument, 'updatedAt' | 'revision'> &
    Partial<Pick<ScriptDocument, 'updatedAt' | 'revision' | 'createdAt'>>,
): Promise<ScriptMeta> {
  const full: ScriptDocument = {
    id: doc.id || `s_${Date.now().toString(36)}`,
    name: doc.name || 'Untitled',
    description: doc.description,
    path: doc.path,
    content: doc.content ?? '',
    updatedAt: doc.updatedAt || Date.now(),
    createdAt: doc.createdAt,
    revision: doc.revision,
    tags: doc.tags,
  };
  const meta = await requireActive().write(full);
  appendLog('ok', `Saved "${meta.name}" → ${getActiveStorageId()}`, 'library');
  return meta;
}

export async function removeScript(id: string): Promise<void> {
  await requireActive().remove(id);
  appendLog('info', `Deleted script ${id}`, 'library');
}

/** Debounced draft: always local + active storage if it supports drafts. */
export async function saveDraft(content: string, name?: string): Promise<void> {
  const payload = { content, name };
  await localAlways().saveDraft?.(payload);
  const active = requireActive();
  if (active.id !== 'local' && active.saveDraft) {
    try {
      await active.saveDraft(payload);
    } catch {
      /* active may be offline */
    }
  }
}

export async function loadDraft(): Promise<{ content: string; name?: string } | null> {
  // Prefer local crash draft
  const local = await localAlways().loadDraft?.();
  if (local?.content) return local;
  const active = requireActive();
  if (active.id !== 'local' && active.loadDraft) {
    return active.loadDraft();
  }
  return null;
}

export async function getStorageStatus(): Promise<StorageStatus> {
  const p = requireActive();
  if (p.getStatus) return p.getStatus();
  return { connected: true };
}

export function getActiveStoragePlugin(): StoragePlugin {
  return requireActive();
}

/** Export all scripts from active storage as JSON-friendly array. */
export async function exportLibraryJson(): Promise<ScriptDocument[]> {
  const metas = await listScripts();
  const docs: ScriptDocument[] = [];
  for (const m of metas) {
    docs.push(await readScript(m.id));
  }
  return docs;
}

/** Import scripts into active storage (skips id conflicts by new id if forceNewIds). */
export async function importLibraryJson(
  items: Array<Partial<ScriptDocument> & { script?: string }>,
  opts?: { forceNewIds?: boolean },
): Promise<number> {
  let n = 0;
  for (const item of items) {
    const content = item.content ?? item.script ?? '';
    const id = opts?.forceNewIds
      ? `s_${Date.now().toString(36)}_${n}`
      : item.id || `s_${Date.now().toString(36)}_${n}`;
    await writeScript({
      id,
      name: item.name || `Imported ${n + 1}`,
      description: item.description,
      content: String(content),
      path: item.path,
      tags: item.tags,
    });
    n++;
  }
  return n;
}
