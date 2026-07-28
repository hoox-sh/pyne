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
