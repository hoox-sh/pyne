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
 * PYNE — VS Code extension (HOOX open trading stack).
 * Language Client for pyne-lsp (alias: pynescript-lsp).
 *
 * Server discovery (in order):
 *  1. pynescript.lsp.command if set and not "auto"
 *  2. pyne-lsp on PATH
 *  3. pynescript-lsp on PATH (backward-compatible alias)
 *  4. python -m pynescript.langserver (pynescript.lsp.python)
 *
 * Unofficial independent project. Not affiliated with or endorsed by TradingView, Inc.
 * Pine Script™ and TradingView® are trademarks of TradingView, Inc.
 */

import { execFileSync } from 'child_process';
import * as fs from 'fs';
import {
  commands,
  env,
  ExtensionContext,
  LogOutputChannel,
  StatusBarAlignment,
  StatusBarItem,
  window,
  workspace,
} from 'vscode';
import {
  LanguageClient,
  LanguageClientOptions,
  ServerOptions,
  State,
  TransportKind,
} from 'vscode-languageclient/node';

/** Keep in sync with package.json contributes.commands */
export const COMMANDS = {
  restartServer: 'pynescript.restartServer',
  formatDocument: 'pynescript.formatDocument',
  showLspOutput: 'pynescript.showLspOutput',
  showLspCommand: 'pynescript.showLspCommand',
} as const;

let client: LanguageClient | undefined;
let statusBar: StatusBarItem | undefined;
let output: LogOutputChannel | undefined;
/** Prevent concurrent start/stop races from config changes + palette commands. */
let clientOp: Promise<void> = Promise.resolve();

function log(msg: string): void {
  const line = `[PYNE] ${msg}`;
  output?.appendLine(line);
}

function cfg<T>(key: string): T | undefined {
  return workspace.getConfiguration('pynescript').get<T>(key);
}

/** Expand ${workspaceFolder} (and friends) in lsp.command / lsp.args for Docker. */
function expandWorkspaceVars(value: string): string {
  const folder = workspace.workspaceFolders?.[0]?.uri.fsPath ?? '';
  const base = folder.split(/[/\\]/).pop() ?? '';
  return value
    .split('${workspaceFolder}').join(folder)
    .split('${workspaceRoot}').join(folder)
    .split('${workspaceFolderBasename}').join(base);
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
  found: boolean;
} {
  const configured = expandWorkspaceVars((cfg<string>('lsp.command') || 'auto').trim());
  const python = (cfg<string>('lsp.python') || 'python3').trim() || 'python3';
  const extraArgs = (cfg<string[]>('lsp.args') || []).map(expandWorkspaceVars);

  if (configured && configured !== 'auto') {
    const found = fs.existsSync(configured) || commandOnPath(configured);
    return {
      command: configured,
      args: [...extraArgs],
      label: extraArgs.length ? `${configured} ${extraArgs.join(' ')}` : configured,
      found,
    };
  }

  // Prefer product brand, then legacy alias.
  for (const bin of ['pyne-lsp', 'pynescript-lsp'] as const) {
    if (commandOnPath(bin)) {
      return {
        command: bin,
        args: [...extraArgs],
        label: bin,
        found: true,
      };
    }
  }

  for (const py of [python, 'python3', 'python']) {
    if (!py) continue;
    if (pythonCanImportLangserver(py)) {
      return {
        command: py,
        args: ['-m', 'pynescript.langserver', ...extraArgs],
        label: `${py} -m pynescript.langserver`,
        found: true,
      };
    }
  }

  return {
    command: 'pyne-lsp',
    args: [...extraArgs],
    label: 'pyne-lsp (not found — install: pip install "hoox-pyne[lsp]")',
    found: false,
  };
}

function buildServerOptions(): ServerOptions {
  const launch = resolveLspLaunch();
  // Executable form (stdio). Do not pass TransportKind as a confusing dual field
  // that some client versions mis-handle when combined incorrectly.
  return {
    command: launch.command,
    args: launch.args,
    options: {
      env: { ...process.env },
    },
    transport: TransportKind.stdio,
  };
}

function buildClientOptions(): LanguageClientOptions {
  return {
    documentSelector: [
      { language: 'pinescript', scheme: 'file' },
      { language: 'pinescript', scheme: 'untitled' },
    ],
    synchronize: {
      fileEvents: workspace.createFileSystemWatcher('**/*.{pyne,pine,pinev5,pinev6,pinescript}'),
    },
    diagnosticCollectionName: 'pynescript',
    initializationOptions: {
      formattingEnabled: cfg('formatting.enabled') !== false,
      snippetsEnabled: cfg('completion.snippets') !== false,
      diagnosticsEnabled: cfg('diagnostics.enabled') !== false,
    },
    // Share our channel so Show Output works even when client is mid-start/fail.
    outputChannel: output,
    traceOutputChannel: output,
  };
}

function setStatus(text: string, tooltip?: string): void {
  if (!statusBar) return;
  statusBar.text = text;
  statusBar.tooltip = tooltip || text;
  statusBar.show();
}

function isClientRunning(): boolean {
  return !!client && client.state === State.Running;
}

async function stopClient(): Promise<void> {
  if (!client) return;
  const c = client;
  client = undefined;
  try {
    if (c.state !== State.Stopped) {
      await c.stop();
    }
  } catch (err) {
    log(`stopClient: ${err instanceof Error ? err.message : String(err)}`);
  }
  try {
    c.dispose();
  } catch {
    /* ignore */
  }
}

async function startClient(): Promise<void> {
  if (cfg<boolean>('lsp.enabled') === false) {
    setStatus('$(circle-slash) PYNE LSP off', 'pynescript.lsp.enabled is false');
    log('LSP disabled via pynescript.lsp.enabled');
    return;
  }

  // Ensure previous instance is fully gone
  await stopClient();

  const launch = resolveLspLaunch();
  log(`Resolving LSP: ${launch.label} (found=${launch.found})`);

  if (!launch.found && (cfg<string>('lsp.command') || 'auto') === 'auto') {
    setStatus('$(error) PYNE LSP', launch.label);
    void window.showErrorMessage(
      'PYNE language server not found. Install with: pip install "hoox-pyne[lsp]" ' +
        'or set pynescript.lsp.command / pynescript.lsp.python. ' +
        'Run “PYNE: Show Language Server Output” for details.',
    );
    log('No language server binary/module found on PATH.');
    return;
  }

  const serverOptions = buildServerOptions();
  const clientOptions = buildClientOptions();

  client = new LanguageClient(
    'pyne-lsp',
    'PYNE Language Server',
    serverOptions,
    clientOptions,
  );

  client.onDidChangeState((e) => {
    log(`client state: ${State[e.oldState]} → ${State[e.newState]}`);
    if (e.newState === State.Running) {
      setStatus('$(check) PYNE LSP', `Running: ${launch.label}`);
    } else if (e.newState === State.Stopped) {
      setStatus('$(circle-slash) PYNE LSP', 'Language server stopped');
    }
  });

  setStatus('$(sync~spin) PYNE LSP…', `Starting: ${launch.label}`);
  log(`Starting: ${launch.command} ${launch.args.join(' ')}`);

  try {
    await client.start();
    setStatus('$(check) PYNE LSP', `Running: ${launch.label}`);
    log('Language server started.');
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    setStatus('$(error) PYNE LSP', msg);
    log(`Start failed: ${msg}`);
    void window.showErrorMessage(
      `PYNE language server failed to start (${launch.label}). ` +
        `Install with: pip install "hoox-pyne[lsp]" then set pynescript.lsp.python if needed. ` +
        `Error: ${msg}`,
    );
    await stopClient();
    throw err;
  }
}

/** Serialize client lifecycle ops so restart/config don't race. */
function withClientLock(fn: () => Promise<void>): Promise<void> {
  clientOp = clientOp.then(fn, fn);
  return clientOp;
}

function registerCommands(context: ExtensionContext): void {
  context.subscriptions.push(
    commands.registerCommand(COMMANDS.showLspOutput, () => {
      if (!output) {
        void window.showWarningMessage('PYNE output channel is not available.');
        return;
      }
      output.show(true);
    }),
  );

  context.subscriptions.push(
    commands.registerCommand(COMMANDS.restartServer, async () => {
      try {
        await withClientLock(async () => {
          log('Restart requested.');
          await startClient();
        });
        if (isClientRunning()) {
          void window.showInformationMessage('PYNE language server restarted.');
        } else if (cfg<boolean>('lsp.enabled') !== false) {
          void window.showWarningMessage(
            'PYNE language server did not start. See “PYNE: Show Language Server Output”.',
          );
        }
      } catch {
        /* error already shown / logged */
      }
    }),
  );

  context.subscriptions.push(
    commands.registerCommand(COMMANDS.formatDocument, async () => {
      const editor = window.activeTextEditor;
      if (!editor) {
        void window.showWarningMessage('No active editor to format.');
        return;
      }
      if (editor.document.languageId !== 'pinescript') {
        void window.showWarningMessage('Format Document is only available for .pyne / .pine files.');
        return;
      }
      if (cfg<boolean>('formatting.enabled') === false) {
        void window.showWarningMessage('Formatting is disabled (pynescript.formatting.enabled).');
        return;
      }
      if (!isClientRunning()) {
        void window.showWarningMessage(
          'PYNE language server is not running — cannot format. Try “PYNE: Restart Language Server”.',
        );
        return;
      }
      try {
        await commands.executeCommand('editor.action.formatDocument');
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        log(`formatDocument failed: ${msg}`);
        void window.showErrorMessage(`Format failed: ${msg}`);
      }
    }),
  );

  context.subscriptions.push(
    commands.registerCommand(COMMANDS.showLspCommand, async () => {
      const launch = resolveLspLaunch();
      const line = `${launch.command} ${launch.args.join(' ')}`.trim();
      log(`Resolved launch: ${line} (found=${launch.found}, running=${isClientRunning()})`);
      const pick = await window.showInformationMessage(
        `LSP launch: ${line}`,
        'Copy',
        'Show Output',
      );
      if (pick === 'Copy') {
        await env.clipboard.writeText(line);
        void window.showInformationMessage('Copied LSP launch command.');
      } else if (pick === 'Show Output') {
        output?.show(true);
      }
    }),
  );
}

export async function activate(context: ExtensionContext): Promise<void> {
  output = window.createOutputChannel('PYNE Language Server', { log: true });
  context.subscriptions.push(output);
  log('Activating PYNE extension…');

  statusBar = window.createStatusBarItem(StatusBarAlignment.Right, 100);
  statusBar.name = 'PYNE LSP';
  statusBar.command = COMMANDS.showLspOutput;
  context.subscriptions.push(statusBar);
  setStatus('$(sync~spin) PYNE…', 'Activating');

  // Register commands first so palette never shows "command not found"
  // even if the language server fails to start.
  registerCommands(context);

  context.subscriptions.push(
    workspace.onDidChangeConfiguration(async (e) => {
      if (
        e.affectsConfiguration('pynescript.lsp') ||
        e.affectsConfiguration('pynescript.formatting') ||
        e.affectsConfiguration('pynescript.diagnostics') ||
        e.affectsConfiguration('pynescript.completion')
      ) {
        log('Configuration changed — restarting LSP.');
        try {
          await withClientLock(() => startClient());
        } catch {
          /* shown */
        }
      }
    }),
  );

  try {
    await withClientLock(() => startClient());
  } catch {
    /* already reported */
  }

  log('Activation complete.');
}

export function deactivate(): Promise<void> | undefined {
  statusBar?.dispose();
  return withClientLock(() => stopClient());
}
