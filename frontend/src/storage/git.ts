/**
 * Built-in git storage plugin — GitHub or GitLab.
 * Commits only on explicit write/remove (Save); drafts stay local (no remote commits).
 */

import type {
  ScriptDocument,
  ScriptMeta,
  StoragePlugin,
  StorageStatus,
  SyncResult,
} from '../plugins/types';
import { resolveGitConfig } from './git-config';
import * as gh from './git-github';
import * as gl from './git-gitlab';

export const gitStoragePlugin: StoragePlugin = {
  id: 'git',
  name: 'Git (GitHub / GitLab)',
  kind: 'storage',
  builtIn: true,
  description:
    'Store Pine scripts in a git repo. Each Save commits (and pushes) via the host API. Drafts stay local.',
  capabilities: { needsNetwork: true, needsAuth: true },
  configSchema: {
    provider: {
      type: 'select',
      options: ['github', 'gitlab'],
      default: 'github',
      label: 'Provider',
    },
    apiBaseUrl: {
      type: 'string',
      default: '',
      label: 'API base URL',
      description: 'Empty = api.github.com or gitlab.com/api/v4. Set for self-hosted.',
      placeholder: 'https://api.github.com',
    },
    token: {
      type: 'string',
      default: '',
      label: 'Personal access token',
      description: 'GitHub: contents:write. GitLab: api or write_repository.',
      placeholder: 'ghp_… / glpat-…',
    },
    owner: { type: 'string', default: '', label: 'Owner / namespace' },
    repo: { type: 'string', default: '', label: 'Repository' },
    projectId: {
      type: 'string',
      default: '',
      label: 'GitLab project id (optional)',
      description: 'Numeric id or group/project path; overrides owner/repo for GitLab',
    },
    branch: { type: 'string', default: 'main', label: 'Branch' },
    basePath: {
      type: 'string',
      default: 'pine-library',
      label: 'Base path in repo',
    },
    commitMessageTemplate: {
      type: 'string',
      default: 'chore(pine): save {{name}} @ {{iso}}',
      label: 'Commit message template',
    },
  },

  async list(opts) {
    const cfg = resolveGitConfig(opts?.config);
    const metas = cfg.provider === 'gitlab' ? await gl.gitlabList(cfg) : await gh.githubList(cfg);
    const prefix = opts?.prefix;
    if (!prefix) return metas;
    return metas.filter(
      (m) => m.name.startsWith(prefix) || (m.path && m.path.startsWith(prefix)),
    );
  },

  async read(id, config) {
    const cfg = resolveGitConfig(config);
    return cfg.provider === 'gitlab' ? gl.gitlabRead(cfg, id) : gh.githubRead(cfg, id);
  },

  async write(doc, config) {
    const cfg = resolveGitConfig(config);
    // Explicit Save only — this is the commit boundary
    return cfg.provider === 'gitlab' ? gl.gitlabWrite(cfg, doc) : gh.githubWrite(cfg, doc);
  },

  async remove(id, config) {
    const cfg = resolveGitConfig(config);
    if (cfg.provider === 'gitlab') await gl.gitlabRemove(cfg, id);
    else await gh.githubRemove(cfg, id);
  },

  // Drafts intentionally not pushed to git — local dual-write handles crash recovery
  async saveDraft() {
    /* no-op: use local storage draft */
  },

  async loadDraft() {
    return null;
  },

  async sync(_direction, config): Promise<SyncResult> {
    try {
      const cfg = resolveGitConfig(config);
      const list =
        cfg.provider === 'gitlab' ? await gl.gitlabList(cfg) : await gh.githubList(cfg);
      return {
        ok: true,
        message: `Pulled ${list.length} script(s) from ${cfg.provider}`,
        revision: list[0]?.revision,
      };
    } catch (e: unknown) {
      return { ok: false, message: e instanceof Error ? e.message : String(e) };
    }
  },

  async getStatus(config): Promise<StorageStatus> {
    const cfg = resolveGitConfig(config);
    const st =
      cfg.provider === 'gitlab' ? await gl.gitlabStatus(cfg) : await gh.githubStatus(cfg);
    return {
      connected: st.connected,
      remote: st.remote,
      branch: st.branch || cfg.branch,
      error: st.error,
      lastSyncAt: st.connected ? Date.now() : undefined,
    };
  },
};

export type { ScriptMeta, ScriptDocument };
