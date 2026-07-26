/**
 * Cloud storage plugin — AXIS Worker `/api/scripts` (D1 or in-memory).
 * Auth: Pro API keys via Authorization: Bearer.
 */

import type {
  ScriptDocument,
  ScriptMeta,
  StoragePlugin,
  StorageStatus,
} from '../plugins/types';
import { store } from '../store';
import { pluginKey } from '../plugins/types';

export type CloudConfig = {
  endpoint: string;
  apiKey: string;
};

function resolveCloudConfig(config?: Record<string, unknown>): CloudConfig {
  const fromSchema = {
    endpoint: (config?.endpoint as string) || '',
    apiKey: (config?.apiKey as string) || '',
  };
  // Prefer pluginsConfig storage:cloud, then bare cloud, then store.endpoint
  const pc = store.pluginsConfig || {};
  const saved =
    pc[pluginKey('storage', 'cloud')] ||
    pc['cloud'] ||
    pc['storage:cloud'] ||
    {};
  const endpoint = String(
    fromSchema.endpoint ||
      saved.endpoint ||
      store.endpoint ||
      'http://127.0.0.1:8787',
  ).replace(/\/$/, '');
  const apiKey = String(fromSchema.apiKey || saved.apiKey || '');
  return { endpoint, apiKey };
}

async function api(
  path: string,
  opts: {
    method?: string;
    body?: unknown;
    config?: Record<string, unknown>;
    ifMatch?: string;
  } = {},
): Promise<{ status: number; json: Record<string, unknown> }> {
  const cfg = resolveCloudConfig(opts.config);
  if (!cfg.apiKey) {
    throw new Error('Cloud storage requires an API key (Settings / storage config)');
  }
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${cfg.apiKey}`,
  };
  if (opts.ifMatch) headers['If-Match'] = opts.ifMatch;
  const res = await fetch(`${cfg.endpoint}${path}`, {
    method: opts.method || 'GET',
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    signal: AbortSignal.timeout(30_000),
  });
  const json = (await res.json().catch(() => ({}))) as Record<string, unknown>;
  if (!res.ok) {
    const msg = String(json.message || json.error || `HTTP ${res.status}`);
    const err = new Error(msg) as Error & { status?: number; code?: string };
    err.status = res.status;
    err.code = String(json.code || '');
    throw err;
  }
  return { status: res.status, json };
}

function metaFromRemote(r: Record<string, unknown>): ScriptMeta {
  return {
    id: String(r.id),
    name: String(r.name || 'Untitled'),
    description: r.description ? String(r.description) : undefined,
    path: r.path ? String(r.path) : undefined,
    revision: r.revision ? String(r.revision) : undefined,
    createdAt: Number(r.createdAt ?? r.created_at ?? Date.now()),
    updatedAt: Number(r.updatedAt ?? r.updated_at ?? Date.now()),
  };
}

function docFromRemote(r: Record<string, unknown>): ScriptDocument {
  return {
    ...metaFromRemote(r),
    content: String(r.content ?? ''),
  };
}

export const cloudStoragePlugin: StoragePlugin = {
  id: 'cloud',
  name: 'Cloud (Worker)',
  kind: 'storage',
  builtIn: true,
  description:
    'Stores scripts on the AXIS Cloudflare Worker (/api/scripts). Uses Pro API keys; partition per key.',
  capabilities: { needsNetwork: true, needsAuth: true },
  configSchema: {
    endpoint: {
      type: 'string',
      default: 'http://127.0.0.1:8787',
      label: 'Worker URL',
      description: 'AXIS Worker base URL (no trailing slash)',
    },
    apiKey: {
      type: 'string',
      default: '',
      label: 'API key',
      description: 'Bearer key from /api/keys (pn_…)',
      placeholder: 'pn_…',
    },
  },

  async list(opts) {
    const { json } = await api('/api/scripts', { config: opts?.config });
    const scripts = (json.scripts as Record<string, unknown>[]) || [];
    let metas = scripts.map(metaFromRemote);
    const prefix = opts?.prefix;
    if (prefix) {
      metas = metas.filter(
        (m) => m.name.startsWith(prefix) || (m.path && m.path.startsWith(prefix)),
      );
    }
    return metas;
  },

  async read(id, config) {
    const { json } = await api(`/api/scripts/${encodeURIComponent(id)}`, { config });
    const script = json.script as Record<string, unknown>;
    if (!script) throw new Error(`Script not found: ${id}`);
    return docFromRemote(script);
  },

  async write(doc, config) {
    const body = {
      name: doc.name,
      description: doc.description,
      path: doc.path,
      content: doc.content,
      revision: doc.revision,
    };
    const { json } = await api(`/api/scripts/${encodeURIComponent(doc.id)}`, {
      method: 'PUT',
      body,
      config,
      ifMatch: doc.revision,
    });
    const script = json.script as Record<string, unknown>;
    return metaFromRemote(script || { ...doc, revision: doc.revision });
  },

  async remove(id, config) {
    await api(`/api/scripts/${encodeURIComponent(id)}`, {
      method: 'DELETE',
      config,
    });
  },

  async saveDraft(doc, config) {
    await api('/api/scripts/_draft', {
      method: 'PUT',
      body: { content: doc.content, name: doc.name },
      config,
    });
  },

  async loadDraft(config) {
    const { json } = await api('/api/scripts/_draft', { config });
    const draft = json.draft as { content?: string; name?: string } | null;
    if (!draft || draft.content == null) return null;
    return { content: String(draft.content), name: draft.name };
  },

  async getStatus(config): Promise<StorageStatus> {
    try {
      const cfg = resolveCloudConfig(config);
      if (!cfg.apiKey) {
        return { connected: false, error: 'API key not set', remote: cfg.endpoint };
      }
      const res = await fetch(`${cfg.endpoint}/health`, {
        signal: AbortSignal.timeout(8_000),
      });
      if (!res.ok) {
        return { connected: false, error: `HTTP ${res.status}`, remote: cfg.endpoint };
      }
      return { connected: true, remote: cfg.endpoint, lastSyncAt: Date.now() };
    } catch (e: unknown) {
      return {
        connected: false,
        error: e instanceof Error ? e.message : String(e),
      };
    }
  },
};
