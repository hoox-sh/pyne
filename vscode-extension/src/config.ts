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

import { ConfigurationTarget, window, workspace } from 'vscode';

export function cfg<T>(key: string): T | undefined {
  return workspace.getConfiguration('pynescript').get<T>(key);
}

export function settingOn(key: string): boolean {
  return cfg<boolean>(key) !== false;
}

/** Settings mirrored to pyne-lsp (initializationOptions + didChangeConfiguration). */
export function serverSettings(): Record<string, unknown> {
  return {
    formattingEnabled: cfg<boolean>('formatting.enabled') !== false,
    snippetsEnabled: cfg<boolean>('completion.snippets') !== false,
    diagnosticsEnabled: cfg<boolean>('diagnostics.enabled') !== false,
    styleDiagnostics: cfg<boolean>('diagnostics.style') === true,
    semanticDiagnostics: cfg<boolean>('diagnostics.semantic') === true,
    inlayHintsParameters: cfg<boolean>('inlayHints.parameters') !== false,
    completionUserSymbols: true,
  };
}

/**
 * Effective PYNE backend base URL (no trailing slash).
 *
 * `pynescript.backend.useHosted` selects the hosted `pynescript.online` Pro
 * backend; otherwise `pynescript.backend.url` is used.
 */
export function resolveBackendUrl(): string {
  const hosted = cfg<boolean>('backend.useHosted') === true;
  const raw = hosted
    ? (cfg<string>('backend.hostedUrl') || 'https://pynescript.online')
    : (cfg<string>('backend.url') || 'http://127.0.0.1:5002');
  return raw.trim().replace(/\/+$/, '');
}

export async function togglePyneBool(key: string, label: string): Promise<boolean> {
  const next = !settingOn(key);
  await workspace.getConfiguration('pynescript').update(key, next, ConfigurationTarget.Global);
  void window.showInformationMessage(`PYNE ${label} ${next ? 'on' : 'off'}.`);
  return next;
}

export const PINESCRIPT = { languageId: 'pinescript' } as const;

export function pinescriptEditorOn(key: string): boolean {
  const v = workspace.getConfiguration('editor', PINESCRIPT).get(key);
  if (key === 'inlayHints.enabled') {
    return v !== 'off' && v !== false;
  }
  return v !== false;
}

export async function togglePinescriptEditor(
  key: string,
  onValue: unknown,
  offValue: unknown,
  label: string,
): Promise<void> {
  const nextOn = !pinescriptEditorOn(key);
  await workspace
    .getConfiguration('editor', PINESCRIPT)
    .update(key, nextOn ? onValue : offValue, ConfigurationTarget.Global, true);
  void window.showInformationMessage(`PYNE ${label} ${nextOn ? 'on' : 'off'}.`);
}

/** Expand ${workspaceFolder} (and friends) in lsp.command / lsp.args for Docker. */
export function expandWorkspaceVars(value: string): string {
  const folder = workspace.workspaceFolders?.[0]?.uri.fsPath ?? '';
  const base = folder.split(/[/\\]/).pop() ?? '';
  return value
    .split('${workspaceFolder}').join(folder)
    .split('${workspaceRoot}').join(folder)
    .split('${workspaceFolderBasename}').join(base);
}
