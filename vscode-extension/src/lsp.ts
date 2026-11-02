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
import { window, workspace } from 'vscode';
import {
  LanguageClient,
  LanguageClientOptions,
  ServerOptions,
  State,
  TransportKind,
} from 'vscode-languageclient/node';
import { COMMANDS } from './commands';
import { cfg, expandWorkspaceVars, serverSettings, settingOn } from './config';
import { commandOnPath, handleMissingServer, pythonCanImportLangserver } from './install';
import { log, setStatus } from './log';
import { state } from './state';

/** Default `docker run` when lsp.command is docker and lsp.args is empty. */
const DEFAULT_DOCKER_ARGS = ['run', '-i', '--rm', 'ghcr.io/hoox-sh/pyne/lsp:0.6.30'];

/**
 * Resolve how to spawn the language server.
 * Returns command + args for stdio transport.
 *
 * Discovery (in order):
 *  1. pynescript.lsp.command if set and not "auto"
 *  2. pyne-lsp on PATH
 *  3. pynescript-lsp on PATH (backward-compatible alias)
 *  4. python -m pynescript.langserver (pynescript.lsp.python)
 */
export function resolveLspLaunch(): {
  command: string;
  args: string[];
  label: string;
  found: boolean;
} {
  const configured = expandWorkspaceVars((cfg<string>('lsp.command') || 'auto').trim());
  const python = (cfg<string>('lsp.python') || 'python3').trim() || 'python3';
  const installPython = (cfg<string>('install.python') || '').trim();
  const extraArgs = (cfg<string[]>('lsp.args') || []).map(expandWorkspaceVars);

  if (configured && configured !== 'auto') {
    const args =
      configured.toLowerCase() === 'docker' && extraArgs.length === 0
        ? [...DEFAULT_DOCKER_ARGS]
        : extraArgs;
    const found = fs.existsSync(configured) || commandOnPath(configured);
    return {
      command: configured,
      args: [...args],
      label: args.length ? `${configured} ${args.join(' ')}` : configured,
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

  for (const py of [python, installPython, 'python3', 'python', process.platform === 'win32' ? 'py' : '']) {
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

export function buildServerOptions(): ServerOptions {
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

export function buildClientOptions(): LanguageClientOptions {
  return {
    documentSelector: [
      { language: 'pinescript', scheme: 'file' },
      { language: 'pinescript', scheme: 'untitled' },
    ],
    synchronize: {
      fileEvents: workspace.createFileSystemWatcher('**/*.{pyne,pine,pinev5,pinev6,pinescript}'),
      // The client sends workspace/didChangeConfiguration with the
      // `pynescript` section; the server applies it live (no restart).
      configurationSection: 'pynescript',
    },
    diagnosticCollectionName: 'pynescript',
    initializationOptions: serverSettings(),
    middleware: {
      handleDiagnostics(uri, diagnostics, next) {
        if (cfg<boolean>('diagnostics.enabled') === false) {
          next(uri, []);
          return;
        }
        const overrides = cfg<Record<string, string>>('diagnostics.severity') || {};
        const keys = Object.keys(overrides);
        if (keys.length > 0) {
          const mapped = diagnostics.map((d) => {
            const code = typeof d.code === 'string' ? d.code : String(d.code ?? '');
            let override: string | undefined;
            for (const prefix of keys) {
              if (code.startsWith(prefix)) {
                override = overrides[prefix];
                break;
              }
            }
            if (!override) {
              return d;
            }
            const sev = {
              Error: 1,
              Warning: 2,
              Information: 3,
              Hint: 4,
            }[override];
            return sev !== undefined ? { ...d, severity: sev } : d;
          });
          next(uri, mapped);
          return;
        }
        next(uri, diagnostics);
      },
      // --- Client-side feature gates ---------------------------------------
      // Read live settings so toggles take effect without a server restart.
      // Returning an empty/null result short-circuits the request; calling
      // `next(...)` forwards to pyne-lsp.
      provideHover(document, position, token, next) {
        if (!settingOn('hover.enabled')) {
          return null;
        }
        return next(document, position, token);
      },
      provideSignatureHelp(document, position, context, token, next) {
        if (!settingOn('signatureHelp.enabled')) {
          return null;
        }
        return next(document, position, context, token);
      },
      provideDocumentHighlights(document, position, token, next) {
        if (!settingOn('documentHighlight.enabled')) {
          return [];
        }
        return next(document, position, token);
      },
      provideSelectionRanges(document, positions, token, next) {
        if (!settingOn('selectionRange.enabled')) {
          return [];
        }
        return next(document, positions, token);
      },
      provideDocumentLinks(document, token, next) {
        if (!settingOn('documentLink.enabled')) {
          return [];
        }
        return next(document, token);
      },
      provideCodeActions(document, range, context, token, next) {
        if (!settingOn('codeAction.enabled')) {
          return [];
        }
        return next(document, range, context, token);
      },
      provideDocumentSemanticTokens(document, token, next) {
        if (!settingOn('semanticTokens.enabled')) {
          return null;
        }
        return next(document, token);
      },
      provideDocumentRangeSemanticTokens(document, range, token, next) {
        if (!settingOn('semanticTokens.enabled')) {
          return null;
        }
        return next(document, range, token);
      },
      provideLinkedEditingRange(document, position, token, next) {
        if (!settingOn('linkedEditing.enabled')) {
          return null;
        }
        return next(document, position, token);
      },
    },
    // Share our channel so Show Output works even when client is mid-start/fail.
    outputChannel: state.output,
    traceOutputChannel: state.output,
  };
}

export function getClient(): LanguageClient | undefined {
  return state.client;
}

export function isClientRunning(): boolean {
  return !!state.client && state.client.state === State.Running;
}

export async function stopClient(): Promise<void> {
  if (!state.client) return;
  const c = state.client;
  state.client = undefined;
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

export async function startClient(): Promise<void> {
  if (cfg<boolean>('lsp.enabled') === false) {
    setStatus('$(circle-slash) PYNE LSP off', 'pynescript.lsp.enabled is false', true);
    log('LSP disabled via pynescript.lsp.enabled');
    return;
  }

  // Ensure previous instance is fully gone
  await stopClient();

  const launch = resolveLspLaunch();
  log(`Resolving LSP: ${launch.label} (found=${launch.found})`);

  if (!launch.found && (cfg<string>('lsp.command') || 'auto') === 'auto') {
    setStatus('$(error) PYNE LSP', launch.label, true);
    log('No language server binary/module found on PATH.');
    // Fire-and-forget: the prompt/install restarts the client via the lock once
    // it completes, so we must not await here (startClient already holds it).
    void handleMissingServer(launch.label);
    return;
  }

  const serverOptions = buildServerOptions();
  const clientOptions = buildClientOptions();

  state.client = new LanguageClient(
    'pyne-lsp',
    'PYNE Language Server',
    serverOptions,
    clientOptions,
  );

  state.client.onDidChangeState((e) => {
    log(`client state: ${State[e.oldState]} → ${State[e.newState]}`);
    if (e.newState === State.Running) {
      setStatus(
        '$(check) PYNE LSP',
        `Running: ${launch.label}  ·  ${Object.keys(COMMANDS).length} commands`,
      );
    } else if (e.newState === State.Stopped) {
      setStatus('$(circle-slash) PYNE LSP', 'Language server stopped', true);
    }
  });

  setStatus('$(sync~spin) PYNE LSP…', `Starting: ${launch.label}`);
  log(`Starting: ${launch.command} ${launch.args.join(' ')}`);

  try {
    await state.client.start();
    setStatus('$(check) PYNE LSP', `Running: ${launch.label}`);
    log('Language server started.');
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    setStatus('$(error) PYNE LSP', msg, true);
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
export function withClientLock(fn: () => Promise<void>): Promise<void> {
  state.clientOp = state.clientOp.then(fn, fn);
  return state.clientOp;
}
