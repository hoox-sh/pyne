/**
 * GitHub Contents API adapter for script library files.
 * Each write is a commit on the configured branch (auto-push).
 */

import type { ScriptDocument, ScriptMeta } from '../plugins/types';
import {
  type GitConfig,
  assertGitConfig,
  formatCommitMessage,
  indexPath,
  scriptPath,
} from './git-config';

export interface IndexFile {
  version: 1;
  scripts: ScriptMeta[];
}

async function gh(
  cfg: GitConfig,
  path: string,
  init: RequestInit = {},
): Promise<{ status: number; json: Record<string, unknown>; text: string }> {
  assertGitConfig(cfg);
  const headers: Record<string, string> = {
    Accept: 'application/vnd.github+json',
    Authorization: `Bearer ${cfg.token}`,
    'X-GitHub-Api-Version': '2022-11-28',
    ...(init.headers as Record<string, string> | undefined),
  };
  if (init.body && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }
  const res = await fetch(`${cfg.apiBaseUrl}${path}`, {
    ...init,
    headers,
    signal: AbortSignal.timeout(30_000),
  });
  const text = await res.text();
  let json: Record<string, unknown> = {};
  try {
    json = text ? (JSON.parse(text) as Record<string, unknown>) : {};
  } catch {
    /* not json */
  }
  if (!res.ok) {
    const msg = String(json.message || text || `HTTP ${res.status}`);
    const err = new Error(`GitHub: ${msg}`) as Error & { status?: number };
    err.status = res.status;
    throw err;
  }
  return { status: res.status, json, text };
}

function b64Encode(s: string): string {
  // UTF-8 safe
  const bytes = new TextEncoder().encode(s);
  let bin = '';
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin);
}

function b64Decode(s: string): string {
  const bin = atob(s.replace(/\n/g, ''));
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new TextDecoder().decode(bytes);
}

function repoPath(cfg: GitConfig, filePath: string): string {
  const enc = filePath
    .split('/')
    .map((p) => encodeURIComponent(p))
    .join('/');
  return `/repos/${encodeURIComponent(cfg.owner)}/${encodeURIComponent(cfg.repo)}/contents/${enc}`;
}

export async function githubGetFile(
  cfg: GitConfig,
  filePath: string,
): Promise<{ content: string; sha: string } | null> {
  try {
    const { json } = await gh(cfg, `${repoPath(cfg, filePath)}?ref=${encodeURIComponent(cfg.branch)}`);
    if (json.type === 'file' && typeof json.content === 'string') {
      return { content: b64Decode(String(json.content)), sha: String(json.sha) };
    }
    return null;
  } catch (e: unknown) {
    if ((e as { status?: number }).status === 404) return null;
    throw e;
  }
}

export async function githubPutFile(
  cfg: GitConfig,
  filePath: string,
  content: string,
  message: string,
  sha?: string,
): Promise<{ sha: string; commitSha?: string }> {
  const body: Record<string, unknown> = {
    message,
    content: b64Encode(content),
    branch: cfg.branch,
  };
  if (sha) body.sha = sha;
  const { json } = await gh(cfg, repoPath(cfg, filePath), {
    method: 'PUT',
    body: JSON.stringify(body),
  });
  const contentObj = json.content as { sha?: string } | undefined;
  const commitObj = json.commit as { sha?: string } | undefined;
  return {
    sha: String(contentObj?.sha || ''),
    commitSha: commitObj?.sha,
  };
}

export async function githubDeleteFile(
  cfg: GitConfig,
  filePath: string,
  message: string,
  sha: string,
): Promise<void> {
  await gh(cfg, repoPath(cfg, filePath), {
    method: 'DELETE',
    body: JSON.stringify({ message, sha, branch: cfg.branch }),
  });
}

export async function githubReadIndex(cfg: GitConfig): Promise<{
  index: IndexFile;
  sha: string | null;
}> {
  const file = await githubGetFile(cfg, indexPath(cfg));
  if (!file) return { index: { version: 1, scripts: [] }, sha: null };
  try {
    const parsed = JSON.parse(file.content) as IndexFile;
    if (!parsed.scripts) parsed.scripts = [];
    return { index: parsed, sha: file.sha };
  } catch {
    return { index: { version: 1, scripts: [] }, sha: file.sha };
  }
}

export async function githubWriteIndex(
  cfg: GitConfig,
  index: IndexFile,
  sha: string | null,
  message: string,
): Promise<string | undefined> {
  const r = await githubPutFile(cfg, indexPath(cfg), JSON.stringify(index, null, 2) + '\n', message, sha || undefined);
  return r.commitSha;
}

export async function githubList(cfg: GitConfig): Promise<ScriptMeta[]> {
  const { index } = await githubReadIndex(cfg);
  return [...index.scripts].sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
}

export async function githubRead(cfg: GitConfig, id: string): Promise<ScriptDocument> {
  const { index } = await githubReadIndex(cfg);
  const meta = index.scripts.find((s) => s.id === id);
  const path = meta?.path || scriptPath(cfg, id);
  const file = await githubGetFile(cfg, path);
  if (!file) throw new Error(`Script not found in repo: ${id}`);
  return {
    id,
    name: meta?.name || id,
    description: meta?.description,
    path,
    content: file.content,
    updatedAt: meta?.updatedAt || Date.now(),
    createdAt: meta?.createdAt,
    revision: file.sha,
    tags: meta?.tags,
  };
}

export async function githubWrite(cfg: GitConfig, doc: ScriptDocument): Promise<ScriptMeta> {
  const now = Date.now();
  const path = doc.path || scriptPath(cfg, doc.id);
  const existing = await githubGetFile(cfg, path);
  const msg = formatCommitMessage(cfg.commitMessageTemplate, doc.name);
  const put = await githubPutFile(cfg, path, doc.content, msg, existing?.sha);

  const { index, sha: indexSha } = await githubReadIndex(cfg);
  const prev = index.scripts.find((s) => s.id === doc.id);
  const meta: ScriptMeta = {
    id: doc.id,
    name: doc.name,
    description: doc.description,
    path,
    updatedAt: now,
    createdAt: prev?.createdAt || doc.createdAt || now,
    revision: put.sha || put.commitSha,
    tags: doc.tags,
  };
  index.scripts = index.scripts.filter((s) => s.id !== doc.id);
  index.scripts.push(meta);
  await githubWriteIndex(cfg, index, indexSha, formatCommitMessage(cfg.commitMessageTemplate, `index ${doc.name}`));
  return meta;
}

export async function githubRemove(cfg: GitConfig, id: string): Promise<void> {
  const { index, sha: indexSha } = await githubReadIndex(cfg);
  const meta = index.scripts.find((s) => s.id === id);
  const path = meta?.path || scriptPath(cfg, id);
  const file = await githubGetFile(cfg, path);
  if (file) {
    await githubDeleteFile(
      cfg,
      path,
      formatCommitMessage(cfg.commitMessageTemplate, `delete ${meta?.name || id}`),
      file.sha,
    );
  }
  index.scripts = index.scripts.filter((s) => s.id !== id);
  await githubWriteIndex(
    cfg,
    index,
    indexSha,
    formatCommitMessage(cfg.commitMessageTemplate, `index remove ${id}`),
  );
}

export async function githubStatus(cfg: GitConfig): Promise<{
  connected: boolean;
  remote?: string;
  branch?: string;
  error?: string;
}> {
  try {
    assertGitConfig(cfg);
    const { json } = await gh(
      cfg,
      `/repos/${encodeURIComponent(cfg.owner)}/${encodeURIComponent(cfg.repo)}`,
    );
    return {
      connected: true,
      remote: String(json.full_name || `${cfg.owner}/${cfg.repo}`),
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
