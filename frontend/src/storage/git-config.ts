/**
 * Shared git storage config resolution (GitHub + GitLab).
 */

import { store } from '../store';
import { pluginKey } from '../plugins/types';

export type GitProvider = 'github' | 'gitlab';

export interface GitConfig {
  provider: GitProvider;
  apiBaseUrl: string;
  token: string;
  owner: string;
  repo: string;
  /** GitLab project path (group/repo) or numeric id — falls back to owner/repo */
  projectId: string;
  branch: string;
  basePath: string;
  autoPush: boolean;
  commitMessageTemplate: string;
}

export const DEFAULT_GIT_CONFIG: GitConfig = {
  provider: 'github',
  apiBaseUrl: '',
  token: '',
  owner: '',
  repo: '',
  projectId: '',
  branch: 'main',
  basePath: 'pine-library',
  autoPush: true,
  commitMessageTemplate: 'chore(pine): save {{name}} @ {{iso}}',
};

export function resolveGitConfig(config?: Record<string, unknown>): GitConfig {
  const pc = store.pluginsConfig || {};
  const saved = (pc[pluginKey('storage', 'git')] || pc['git'] || {}) as Record<string, unknown>;
  const merged = { ...DEFAULT_GIT_CONFIG, ...saved, ...(config || {}) } as Record<string, unknown>;

  const provider = (String(merged.provider || 'github') as GitProvider) === 'gitlab' ? 'gitlab' : 'github';
  let apiBaseUrl = String(merged.apiBaseUrl || '').replace(/\/$/, '');
  if (!apiBaseUrl) {
    apiBaseUrl = provider === 'gitlab' ? 'https://gitlab.com/api/v4' : 'https://api.github.com';
  }

  return {
    provider,
    apiBaseUrl,
    token: String(merged.token || ''),
    owner: String(merged.owner || ''),
    repo: String(merged.repo || ''),
    projectId: String(merged.projectId || ''),
    branch: String(merged.branch || 'main'),
    basePath: String(merged.basePath || 'pine-library').replace(/^\/+|\/+$/g, ''),
    autoPush: merged.autoPush !== false && merged.autoPush !== 'false',
    commitMessageTemplate: String(
      merged.commitMessageTemplate || DEFAULT_GIT_CONFIG.commitMessageTemplate,
    ),
  };
}

export function formatCommitMessage(template: string, name: string): string {
  const iso = new Date().toISOString();
  return template.replace(/\{\{name\}\}/g, name).replace(/\{\{iso\}\}/g, iso);
}

export function libraryDir(cfg: GitConfig): string {
  return `${cfg.basePath}/library`.replace(/\/+/g, '/');
}

export function indexPath(cfg: GitConfig): string {
  return `${libraryDir(cfg)}/index.json`;
}

export function scriptPath(cfg: GitConfig, id: string): string {
  const safe = id.replace(/[^a-zA-Z0-9._-]/g, '_');
  return `${libraryDir(cfg)}/${safe}.pine`;
}

export function assertGitConfig(cfg: GitConfig): void {
  if (!cfg.token) throw new Error('Git storage: PAT / token required');
  if (cfg.provider === 'github') {
    if (!cfg.owner || !cfg.repo) throw new Error('Git storage: owner and repo required');
  } else {
    if (!cfg.projectId && !(cfg.owner && cfg.repo)) {
      throw new Error('Git storage: projectId or owner/repo required for GitLab');
    }
  }
}
