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

import * as fs from 'fs';
import * as path from 'path';
import { window, workspace } from 'vscode';
import { cfg, expandWorkspaceVars, resolveBackendUrl } from './config';
import { resolvePythonForInstall } from './install';
import { log } from './log';

/**
 * Start the PYNE backend from a checkout (`python -m backend.app`) in a
 * terminal. Uses `pynescript.backend.path` or the first workspace folder.
 */
export async function startBackend(): Promise<void> {
  if (cfg<boolean>('backend.useHosted') === true) {
    void window.showWarningMessage(
      'PYNE: pynescript.backend.useHosted is on (pynescript.online). ' +
        'Turn it off to start a local backend.',
    );
    return;
  }
  const configured = (cfg<string>('backend.path') || '').trim();
  const baseDir = configured
    ? expandWorkspaceVars(configured)
    : (workspace.workspaceFolders?.[0]?.uri.fsPath ?? '');
  if (!baseDir) {
    void window.showErrorMessage(
      'PYNE: no workspace folder. Set pynescript.backend.path to a PYNE checkout, ' +
        'or enable pynescript.backend.useHosted to use pynescript.online.',
    );
    return;
  }
  const appPy = path.join(baseDir, 'backend', 'app.py');
  if (!fs.existsSync(appPy)) {
    void window.showErrorMessage(
      `PYNE: backend/app.py not found under ${baseDir}. Set pynescript.backend.path to a PYNE checkout, ` +
        'or enable pynescript.backend.useHosted to use pynescript.online.',
    );
    return;
  }
  const python = resolvePythonForInstall() || (cfg<string>('lsp.python') || 'python3').trim() || 'python3';
  const url = resolveBackendUrl();
  let port = '5002';
  try {
    const parsed = new URL(url);
    port = parsed.port || (parsed.protocol === 'https:' ? '443' : '80');
  } catch {
    /* keep default */
  }
  const env: Record<string, string | undefined> = { ...process.env, PORT: port };
  const term = window.createTerminal({ name: 'PYNE Backend', cwd: baseDir, env });
  term.show(true);
  term.sendText(`"${python}" -m backend.app`, true);
  log(`Started backend: ${python} -m backend.app (cwd=${baseDir}, PORT=${port})`);
  void window.showInformationMessage(`PYNE backend starting on ${url}. See the “PYNE Backend” terminal.`);
}

/** Ping the configured backend `/health` endpoint. */
export async function testBackend(): Promise<void> {
  const url = resolveBackendUrl();
  const health = `${url}/health`;
  log(`GET ${health}`);
  try {
    const res = await fetch(health, { method: 'GET' });
    const text = await res.text();
    if (res.ok) {
      void window.showInformationMessage(`PYNE backend OK (HTTP ${res.status}) at ${url}.`);
    } else {
      void window.showWarningMessage(`PYNE backend returned HTTP ${res.status} at ${health}.`);
    }
    log(`Backend health ${res.status}: ${text.slice(0, 500)}`);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    void window.showErrorMessage(`PYNE backend unreachable at ${health}: ${msg}`);
    log(`Backend health failed: ${msg}`);
  }
}

/** POST the active Pine buffer to the Pro `/run` endpoint. */
export async function runOnPro(): Promise<void> {
  if (cfg<boolean>('pro.enabled') === false) {
    void window.showWarningMessage(
      'PYNE Pro is disabled. Enable pynescript.pro.enabled to run on Pro.',
    );
    return;
  }
  const editor = window.activeTextEditor;
  if (!editor || editor.document.languageId !== 'pinescript') {
    void window.showWarningMessage('No active .pyne / .pine document to run.');
    return;
  }
  const apiKey = (cfg<string>('pro.apiKey') || '').trim();
  const useHosted = cfg<boolean>('backend.useHosted') === true;
  const endpoint = resolveBackendUrl();
  if (useHosted && !apiKey) {
    void window.showWarningMessage(
      'PYNE Pro: the hosted backend (pynescript.online) requires pynescript.pro.apiKey. ' +
        'Set it or turn off pynescript.backend.useHosted.',
    );
    return;
  }
  const source = editor.document.getText();
  const url = `${endpoint}/run`;
  // Minimal single-bar OHLCV so the script at least compiles/executes.
  const body = {
    script: source,
    data: [{ open: 100, high: 101, low: 99, close: 100, volume: 1000 }],
    symbol: 'CHART',
    mode: 'auto',
  };
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (apiKey) {
    headers.Authorization = `Bearer ${apiKey}`;
  }
  log(`PYNE Pro POST ${url} (script ${source.length} chars)`);
  try {
    const res = await fetch(url, { method: 'POST', headers, body: JSON.stringify(body) });
    let result: any;
    try {
      result = await res.json();
    } catch {
      result = { status: 'error', code: 'INVALID_RESPONSE', message: `HTTP ${res.status}` };
    }
    if (!res.ok) {
      void window.showErrorMessage(
        `PYNE Pro run failed: ${result?.code ?? 'HTTP ' + res.status} — ${result?.message ?? ''}`,
      );
      return;
    }
    if (result.status === 'error') {
      void window.showErrorMessage(
        `PYNE Pro: ${result?.code ?? 'error'} — ${result?.message ?? ''}`,
      );
      return;
    }
    void window.showInformationMessage('PYNE Pro: script ran successfully.');
    log(`PYNE Pro result: ${JSON.stringify(result).slice(0, 2000)}`);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    log(`PYNE Pro request failed: ${msg}`);
    void window.showErrorMessage(`PYNE Pro request failed: ${msg}`);
  }
}
