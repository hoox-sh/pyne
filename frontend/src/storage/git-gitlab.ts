/**
 * GitLab Repository Files API adapter for script library files.
 * Each write is a commit on the configured branch.
 */

import type { ScriptDocument, ScriptMeta } from '../plugins/types';
import {
  type GitConfig,
  assertGitConfig,
  formatCommitMessage,
  indexPath,
  scriptPath,
} from './git-config';
import type { IndexFile } from './git-github';

function projectRef(cfg: GitConfig): string {
  if (cfg.projectId) return encodeURIComponent(cfg.projectId);
  return encodeURIComponent(`${cfg.owner}/${cfg.repo}`);
}

function fileUrl(cfg: GitConfig, filePath: string): string {
  const enc = encodeURIComponent(filePath);
  return `${cfg.apiBaseUrl}/projects/${projectRef(cfg)}/repository/files/${enc}`;
}

async function gl(
  cfg: GitConfig,
  url: string,
  init: RequestInit = {},
): Promise<{ status: number; json: Record<string, unknown> }> {
  assertGitConfig(cfg);
  const headers: Record<string, string> = {
    'PRIVATE-TOKEN': cfg.token,
    ...(init.headers as Record<string, string> | undefined),
  };
  // Also support OAuth-style tokens
  if (cfg.token.startsWith('glpat-') || cfg.token.length > 20) {
    headers['PRIVATE-TOKEN'] = cfg.token;
  }
  if (init.body && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }
  const res = await fetch(url, {
    ...init,
    headers,
    signal: AbortSignal.timeout(30_000),
  });
  const text = await res.text();
  let json: Record<string, unknown> = {};
  try {
    json = text ? (JSON.parse(text) as Record<string, unknown>) : {};
  } catch {
    /* ignore */
  }
  if (!res.ok) {
    const msg = String(json.message || json.error || text || `HTTP ${res.status}`);
    const err = new Error(`GitLab: ${msg}`) as Error & { status?: number };
    err.status = res.status;
    throw err;
  }
  return { status: res.status, json };
}

function b64Decode(s: string): string {
  const bin = atob(s.replace(/\n/g, ''));
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new TextDecoder().decode(bytes);
}

export async function gitlabGetFile(
  cfg: GitConfig,
  filePath: string,
): Promise<{ content: string; blobId: string } | null> {
  try {
    const { json } = await gl(
      cfg,
      `${fileUrl(cfg, filePath)}?ref=${encodeURIComponent(cfg.branch)}`,
    );
    const encoding = String(json.encoding || 'base64');
    const raw = String(json.content || '');
    const content = encoding === 'base64' ? b64Decode(raw) : raw;
    return { content, blobId: String(json.blob_id || json.commit_id || '') };
  } catch (e: unknown) {
    if ((e as { status?: number }).status === 404) return null;
    throw e;
  }
}

export async function gitlabPutFile(
  cfg: GitConfig,
  filePath: string,
  content: string,
  message: string,
  exists: boolean,
): Promise<{ commitId?: string }> {
  const body = {
    branch: cfg.branch,
    content,
    commit_message: message,
    encoding: 'text',
  };
  const { json } = await gl(cfg, fileUrl(cfg, filePath), {
    method: exists ? 'PUT' : 'POST',
    body: JSON.stringify(body),
  });
  return { commitId: String(json.file_path ? json.commit_id || '' : json.commit_id || '') };
}

export async function gitlabDeleteFile(
  cfg: GitConfig,
  filePath: string,
  message: string,
): Promise<void> {
  await gl(cfg, fileUrl(cfg, filePath), {
    method: 'DELETE',
    body: JSON.stringify({
      branch: cfg.branch,
      commit_message: message,
    }),
  });
}

export async function gitlabReadIndex(cfg: GitConfig): Promise<{
  index: IndexFile;
  exists: boolean;
}> {
  const file = await gitlabGetFile(cfg, indexPath(cfg));
  if (!file) return { index: { version: 1, scripts: [] }, exists: false };
  try {
    const parsed = JSON.parse(file.content) as IndexFile;
    if (!parsed.scripts) parsed.scripts = [];
    return { index: parsed, exists: true };
  } catch {
    return { index: { version: 1, scripts: [] }, exists: true };
  }
}

export async function gitlabWriteIndex(
  cfg: GitConfig,
  index: IndexFile,
  exists: boolean,
  message: string,
): Promise<void> {
  await gitlabPutFile(cfg, indexPath(cfg), JSON.stringify(index, null, 2) + '\n', message, exists);
}

export async function gitlabList(cfg: GitConfig): Promise<ScriptMeta[]> {
  const { index } = await gitlabReadIndex(cfg);
  return [...index.scripts].sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
}

export async function gitlabRead(cfg: GitConfig, id: string): Promise<ScriptDocument> {
  const { index } = await gitlabReadIndex(cfg);
  const meta = index.scripts.find((s) => s.id === id);
  const path = meta?.path || scriptPath(cfg, id);
  const file = await gitlabGetFile(cfg, path);
  if (!file) throw new Error(`Script not found in repo: ${id}`);
  return {
    id,
    name: meta?.name || id,
    description: meta?.description,
    path,
    content: file.content,
    updatedAt: meta?.updatedAt || Date.now(),
    createdAt: meta?.createdAt,
    revision: file.blobId || meta?.revision,
    tags: meta?.tags,
  };
}

export async function gitlabWrite(cfg: GitConfig, doc: ScriptDocument): Promise<ScriptMeta> {
  const now = Date.now();
  const path = doc.path || scriptPath(cfg, doc.id);
  const existing = await gitlabGetFile(cfg, path);
  const msg = formatCommitMessage(cfg.commitMessageTemplate, doc.name);
  const put = await gitlabPutFile(cfg, path, doc.content, msg, !!existing);

  const { index, exists } = await gitlabReadIndex(cfg);
  const prev = index.scripts.find((s) => s.id === doc.id);
  const meta: ScriptMeta = {
    id: doc.id,
    name: doc.name,
    description: doc.description,
    path,
    updatedAt: now,
    createdAt: prev?.createdAt || doc.createdAt || now,
    revision: put.commitId || `gl-${now}`,
    tags: doc.tags,
  };
  index.scripts = index.scripts.filter((s) => s.id !== doc.id);
  index.scripts.push(meta);
  await gitlabWriteIndex(
    cfg,
    index,
    exists,
    formatCommitMessage(cfg.commitMessageTemplate, `index ${doc.name}`),
  );
  return meta;
}

export async function gitlabRemove(cfg: GitConfig, id: string): Promise<void> {
  const { index, exists } = await gitlabReadIndex(cfg);
  const meta = index.scripts.find((s) => s.id === id);
  const path = meta?.path || scriptPath(cfg, id);
  const file = await gitlabGetFile(cfg, path);
  if (file) {
    await gitlabDeleteFile(
      cfg,
      path,
      formatCommitMessage(cfg.commitMessageTemplate, `delete ${meta?.name || id}`),
    );
  }
  index.scripts = index.scripts.filter((s) => s.id !== id);
  if (exists || index.scripts.length) {
    await gitlabWriteIndex(
      cfg,
      index,
      exists,
      formatCommitMessage(cfg.commitMessageTemplate, `index remove ${id}`),
    );
  }
}

export async function gitlabStatus(cfg: GitConfig): Promise<{
  connected: boolean;
  remote?: string;
  branch?: string;
  error?: string;
}> {
  try {
    assertGitConfig(cfg);
    const { json } = await gl(cfg, `${cfg.apiBaseUrl}/projects/${projectRef(cfg)}`);
    return {
      connected: true,
      remote: String(json.path_with_namespace || json.name || cfg.projectId || `${cfg.owner}/${cfg.repo}`),
      branch: cfg.branch,
    };
  } catch (e: unknown) {
    return {
      connected: false,
      error: e instanceof Error ? e.message : String(e),
      branch: cfg.branch,
    };
  }
}
