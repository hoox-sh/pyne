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
 * PYNE / pynescript VS Code extension — Language Client for pynescript-lsp.
 *
 * Server discovery (in order):
 *  1. pynescript.lsp.command if set and not "auto"
 *  2. pynescript-lsp on PATH
 *  3. python -m pynescript.langserver (pynescript.lsp.python)
 */

import { execFileSync } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';
import {
  commands,
  ExtensionContext,
  StatusBarAlignment,
  StatusBarItem,
  window,
  workspace,
} from 'vscode';
import {
  LanguageClient,
  LanguageClientOptions,
  ServerOptions,
  TransportKind,
} from 'vscode-languageclient/node';

let client: LanguageClient | undefined;
let statusBar: StatusBarItem | undefined;

function cfg<T>(key: string): T | undefined {
  return workspace.getConfiguration('pynescript').get<T>(key);
}

function commandOnPath(cmd: string): boolean {
  try {
    if (process.platform === 'win32') {
      execFileSync('where', [cmd], { stdio: 'ignore' });
    } else {
      execFileSync('which', [cmd], { stdio: 'ignore' });
    }
    return true;
  } catch {
    return false;
  }
}

function pythonCanImportLangserver(python: string): boolean {
  try {
    execFileSync(
      python,
      ['-c', 'import pynescript.langserver; print("ok")'],
      { stdio: 'ignore', timeout: 8000 },
    );
    return true;
  } catch {
    return false;
  }
}

/**
 * Resolve how to spawn the language server.
 * Returns command + args for stdio transport.
 */
export function resolveLspLaunch(): {
  command: string;
  args: string[];
  label: string;
} {
  const configured = (cfg<string>('lsp.command') || 'auto').trim();
  const python = (cfg<string>('lsp.python') || 'python3').trim() || 'python3';
  const extraArgs = cfg<string[]>('lsp.args') || [];

  // Explicit binary or module command (not auto)
  if (configured && configured !== 'auto') {
    // Absolute path to binary
    if (fs.existsSync(configured) || commandOnPath(configured)) {
      return {
        command: configured,
        args: [...extraArgs],
        label: configured,
      };
    }
    // Fall through — still try configured as command
    return {
      command: configured,
      args: [...extraArgs],
      label: configured,
    };
  }

  // Prefer installed console script
  if (commandOnPath('pynescript-lsp')) {
    return {
      command: 'pynescript-lsp',
      args: [...extraArgs],
      label: 'pynescript-lsp',
    };
  }

  // python -m pynescript.langserver
  for (const py of [python, 'python3', 'python']) {
    if (!py) continue;
    if (pythonCanImportLangserver(py)) {
      return {
        command: py,
        args: ['-m', 'pynescript.langserver', ...extraArgs],
        label: `${py} -m pynescript.langserver`,
      };
    }
  }

  // Last resort: hope pynescript-lsp is installable later
  return {
    command: 'pynescript-lsp',
    args: [...extraArgs],
    label: 'pynescript-lsp (not found — install: pip install pynescript[lsp])',
  };
}

function buildServerOptions(): ServerOptions {
  const launch = resolveLspLaunch();
  return {
    command: launch.command,
    args: launch.args,
    transport: TransportKind.stdio,
    options: {
      env: { ...process.env },
    },
  };
}

function buildClientOptions(): LanguageClientOptions {
  return {
    documentSelector: [
      { language: 'pinescript', scheme: 'file' },
      { language: 'pinescript', scheme: 'untitled' },
    ],
    synchronize: {
      fileEvents: workspace.createFileSystemWatcher('**/*.{pine,pinev5,pinev6}'),
    },
    diagnosticCollectionName: 'pynescript',
    initializationOptions: {
      formattingEnabled: cfg('formatting.enabled') !== false,
      snippetsEnabled: cfg('completion.snippets') !== false,
      diagnosticsEnabled: cfg('diagnostics.enabled') !== false,
    },
    outputChannelName: 'PYNE Language Server',
  };
}

function setStatus(text: string, tooltip?: string): void {
  if (!statusBar) return;
  statusBar.text = text;
  statusBar.tooltip = tooltip || text;
  statusBar.show();
}

async function startClient(context: ExtensionContext): Promise<void> {
  if (cfg<boolean>('lsp.enabled') === false) {
    setStatus('$(circle-slash) PYNE LSP off', 'pynescript.lsp.enabled is false');
    return;
  }

  const launch = resolveLspLaunch();
  const serverOptions = buildServerOptions();
  const clientOptions = buildClientOptions();

  client = new LanguageClient(
    'pynescript-lsp',
    'PYNE Pine Script Language Server',
    serverOptions,
    clientOptions,
  );

  setStatus('$(sync~spin) PYNE LSP…', `Starting: ${launch.label}`);

  try {
    await client.start();
    setStatus('$(check) PYNE LSP', `Running: ${launch.label}`);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    setStatus('$(error) PYNE LSP', msg);
    void window.showErrorMessage(
      `PYNE language server failed to start (${launch.label}). ` +
        `Install with: pip install "pynescript[lsp]"  then set pynescript.lsp.python if needed. ` +
        `Error: ${msg}`,
    );
    throw err;
  }
}

async function stopClient(): Promise<void> {
  if (client) {
    await client.stop();
    client = undefined;
  }
}

export async function activate(context: ExtensionContext): Promise<void> {
  statusBar = window.createStatusBarItem(StatusBarAlignment.Right, 100);
  statusBar.command = 'pynescript.showLspOutput';
  context.subscriptions.push(statusBar);

  context.subscriptions.push(
    commands.registerCommand('pynescript.showLspOutput', () => {
      client?.outputChannel.show(true);
    }),
  );

  context.subscriptions.push(
    commands.registerCommand('pynescript.restartServer', async () => {
      try {
        await stopClient();
        await startClient(context);
        void window.showInformationMessage('PYNE language server restarted.');
      } catch {
        /* error already shown */
      }
    }),
  );

  context.subscriptions.push(
    commands.registerCommand('pynescript.formatDocument', async () => {
      const editor = window.activeTextEditor;
      if (editor) {
        await commands.executeCommand('editor.action.formatDocument');
      }
    }),
  );

  context.subscriptions.push(
    commands.registerCommand('pynescript.showLspCommand', () => {
      const launch = resolveLspLaunch();
      void window.showInformationMessage(
        `LSP launch: ${launch.command} ${launch.args.join(' ')}`.trim(),
      );
    }),
  );

  // Restart when relevant settings change
  context.subscriptions.push(
    workspace.onDidChangeConfiguration(async (e) => {
      if (
        e.affectsConfiguration('pynescript.lsp') ||
        e.affectsConfiguration('pynescript.formatting') ||
        e.affectsConfiguration('pynescript.diagnostics') ||
        e.affectsConfiguration('pynescript.completion')
      ) {
        try {
          await stopClient();
          await startClient(context);
        } catch {
          /* shown */
        }
      }
    }),
  );

  try {
    await startClient(context);
  } catch {
    /* already reported */
  }
}

export function deactivate(): Promise<void> | undefined {
  statusBar?.dispose();
  return stopClient();
}
