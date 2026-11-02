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

import { execFileSync, spawn } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';
import { CancellationToken, ConfigurationTarget, ProgressLocation, window, workspace } from 'vscode';
import { cfg } from './config';
import { log, setStatus } from './log';
import { state } from './state';

/** Wired from activate so pip-install success can restart without importing lsp.ts. */
let restartLanguageServer: (() => Promise<void>) | undefined;

export function setLanguageServerRestarter(fn: () => Promise<void>): void {
  restartLanguageServer = fn;
}

export function commandOnPath(cmd: string): boolean {
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

export function pythonCanImportLangserver(python: string): boolean {
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

/** True when *cmd* can be spawned and exits 0 for *args*. */
function isRunnable(cmd: string, args: string[]): boolean {
  try {
    execFileSync(cmd, args, { stdio: 'ignore', timeout: 8000 });
    return true;
  } catch {
    return false;
  }
}

/**
 * Pick a Python interpreter for `pip install`.
 *
 * Order: `pynescript.install.python` → `pynescript.lsp.python` → `python3`
 * → `python` → `py` (Windows launcher). Absolute paths must exist; bare names
 * must be on PATH.
 */
export function resolvePythonForInstall(): string | undefined {
  const candidates = [
    (cfg<string>('install.python') || '').trim(),
    (cfg<string>('lsp.python') || '').trim(),
    'python3',
    'python',
    process.platform === 'win32' ? 'py' : '',
  ].filter((c) => c.length > 0);
  for (const py of candidates) {
    const isPath = py.includes('/') || py.includes('\\');
    if (isPath) {
      if (fs.existsSync(py) && isRunnable(py, ['--version'])) {
        return py;
      }
    } else if (commandOnPath(py) && isRunnable(py, ['--version'])) {
      return py;
    }
  }
  return undefined;
}

function pythonHasPip(python: string): boolean {
  return isRunnable(python, ['-m', 'pip', '--version']);
}

function pythonVersionAtLeast(python: string, major: number, minor: number): boolean {
  try {
    const out = execFileSync(
      python,
      ['-c', 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")'],
      { encoding: 'utf8', timeout: 8000 },
    ).trim();
    const [ma, mi] = out.split('.').map((n) => Number.parseInt(n, 10));
    return ma > major || (ma === major && mi >= minor);
  } catch {
    return false;
  }
}

/** True when *python* is PEP 668 externally managed (and not already a venv). */
function pythonIsExternallyManaged(python: string): boolean {
  try {
    const out = execFileSync(
      python,
      [
        '-c',
        'import os, sys, sysconfig; ' +
          'marker = os.path.exists(os.path.join(sysconfig.get_path("stdlib"), "EXTERNALLY-MANAGED")); ' +
          'print("1" if marker and sys.prefix == sys.base_prefix else "0")',
      ],
      { encoding: 'utf8', timeout: 8000 },
    ).trim();
    return out === '1';
  } catch {
    return false;
  }
}

/** Interpreter path inside a virtualenv directory for the current platform. */
function venvPythonPath(venvDir: string): string {
  return process.platform === 'win32'
    ? path.join(venvDir, 'Scripts', 'python.exe')
    : path.join(venvDir, 'bin', 'python');
}

/** Return the venv interpreter, creating the virtualenv when absent. */
function ensureVenv(basePython: string, venvDir: string): string | undefined {
  const venvPy = venvPythonPath(venvDir);
  if (fs.existsSync(venvPy) && isRunnable(venvPy, ['--version'])) {
    return venvPy;
  }
  log(`Creating virtualenv at ${venvDir}…`);
  try {
    fs.mkdirSync(path.dirname(venvDir), { recursive: true });
    execFileSync(basePython, ['-m', 'venv', venvDir], { stdio: 'ignore', timeout: 120_000 });
  } catch (err) {
    log(`venv creation failed: ${err instanceof Error ? err.message : String(err)}`);
    return undefined;
  }
  if (fs.existsSync(venvPy) && isRunnable(venvPy, ['--version'])) {
    log(`Virtualenv ready: ${venvPy}`);
    return venvPy;
  }
  return undefined;
}

/** Run `python -m pip install --upgrade <spec>` and stream output to the channel. */
function runPipInstall(
  python: string,
  spec: string,
  extraArgs: string[],
  token: CancellationToken,
): Promise<{ ok: boolean; code: number | null; output: string }> {
  return new Promise((resolve) => {
    const args = ['-m', 'pip', 'install', '--upgrade', '--disable-pip-version-check', ...extraArgs, spec];
    log(`Running: ${python} ${args.join(' ')}`);
    const child = spawn(python, args, { env: { ...process.env } });
    let captured = '';
    const onData = (buf: Buffer): void => {
      const text = buf.toString();
      captured += text;
      for (const line of text.split('\n')) {
        if (line.trim()) {
          log(`[pip] ${line}`);
        }
      }
    };
    child.stdout?.on('data', onData);
    child.stderr?.on('data', onData);
    const cancel = token.onCancellationRequested(() => {
      log('Install cancelled by user.');
      child.kill();
    });
    child.on('error', (err) => {
      cancel.dispose();
      resolve({ ok: false, code: null, output: `${captured}\n${err.message}` });
    });
    child.on('close', (code) => {
      cancel.dispose();
      resolve({ ok: code === 0, code, output: captured });
    });
  });
}

/**
 * Install a pip requirement spec with the resolved Python.
 *
 * Resolves the interpreter, creates an isolated venv when the system Python is
 * externally managed (PEP 668), checks pip and Python >= 3.10, streams pip
 * output to the PYNE output channel, and deduplicates concurrent calls.
 *
 * Args:
 *   spec: pip requirement spec (e.g. ``hoox-pyne[lsp]``).
 *   label: short human label used in notifications and the status bar.
 *   options.restartLsp: restart the language client on success.
 */
function installPipPackage(
  spec: string,
  label: string,
  options: { restartLsp?: boolean } = {},
): Promise<void> {
  if (state.installInFlight) {
    return state.installInFlight;
  }
  const run = async (): Promise<void> => {
    const extraArgs = (cfg<string[]>('install.args') || []).filter((a) => typeof a === 'string' && a.length > 0);
    const python = resolvePythonForInstall();
    if (!python) {
      void window.showErrorMessage(
        'PYNE: no Python interpreter found. Install Python 3.10+ or set pynescript.install.python.',
      );
      return;
    }
    if (!pythonVersionAtLeast(python, 3, 10)) {
      void window.showErrorMessage(
        `PYNE: ${python} is older than Python 3.10 (hoox-pyne requires >= 3.10). ` +
          'Install a newer Python or set pynescript.install.python.',
      );
      return;
    }
    // Choose the interpreter to install into. When the system Python is
    // externally managed (PEP 668) or an explicit venv is configured, install
    // into an isolated virtualenv and remember it for module launch.
    let targetPython = python;
    const explicitVenv = (cfg<string>('install.venv') || '').trim();
    const createVenv = cfg<boolean>('install.createVenv') !== false;
    const managed = pythonIsExternallyManaged(python);
    if (explicitVenv || (managed && createVenv)) {
      const venvDir = explicitVenv || (state.globalStorageDir ? path.join(state.globalStorageDir, 'pyne-venv') : '');
      if (venvDir) {
        const venvPy = ensureVenv(python, venvDir);
        if (!venvPy) {
          void window.showErrorMessage(
            `PYNE: could not create a virtualenv at ${venvDir}. ` +
              'Set pynescript.install.venv or install manually with pip.',
          );
          return;
        }
        targetPython = venvPy;
      } else {
        log('No global storage dir for the virtualenv; using the system Python.');
      }
    }

    if (!pythonHasPip(targetPython)) {
      void window.showErrorMessage(
        `PYNE: ${targetPython} has no pip. Run "${targetPython} -m ensurepip --upgrade" (or install pip), then retry.`,
      );
      return;
    }

    setStatus('$(sync~spin) PYNE LSP…', `Installing ${label}`);
    log(`Installing ${spec} (${label}) with ${targetPython}…`);
    const result = await window.withProgress(
      {
        location: ProgressLocation.Notification,
        title: `PYNE: Installing ${label}…`,
        cancellable: true,
      },
      async (progress, token) => {
        progress.report({ message: `using ${targetPython}` });
        return runPipInstall(targetPython, spec, extraArgs, token);
      },
    );

    if (result.ok) {
      log('Install succeeded.');
      if (targetPython !== python) {
        // Remember the venv interpreter so module launch uses it. This key is
        // not in the restart-on-change set, so the explicit restart below is
        // the only one.
        await workspace
          .getConfiguration('pynescript')
          .update('install.python', targetPython, ConfigurationTarget.Global);
        log(`Set pynescript.install.python to ${targetPython}`);
      }
      void window.showInformationMessage(`PYNE: installed ${spec}.`);
      if (options.restartLsp === true) {
        log('Restarting language server after install…');
        if (restartLanguageServer) {
          await restartLanguageServer();
        }
      } else {
        setStatus('$(check) PYNE LSP', `Installed ${label}`);
      }
      return;
    }

    if (result.code === null) {
      setStatus('$(error) PYNE LSP', 'Install cancelled', true);
      void window.showWarningMessage(`PYNE: ${label} install cancelled or could not start.`);
      return;
    }

    const tail = result.output.trim().split('\n').slice(-8).join('\n');
    setStatus('$(error) PYNE LSP', `pip install failed (exit ${result.code})`, true);
    log(`Install failed (exit ${result.code}).\n${tail}`);
    void window.showErrorMessage(
      `PYNE: pip install failed (exit ${result.code}). See “PYNE: Show Language Server Output”. ` +
        'Set pynescript.install.venv to a writable virtualenv, or set ' +
        'pynescript.install.createVenv to true for PEP 668 (externally managed) Python.',
    );
  };

  state.installInFlight = run().finally(() => {
    state.installInFlight = null;
  });
  return state.installInFlight;
}

/** Install/upgrade the language server and restart the client. */
export function installLanguageServer(options: { restart?: boolean } = {}): Promise<void> {
  const spec = (cfg<string>('install.package') || 'hoox-pyne[lsp]').trim() || 'hoox-pyne[lsp]';
  return installPipPackage(spec, 'language server', { restartLsp: options.restart !== false });
}

/** Install/upgrade the full backend extras (Pro API) into the same environment. */
export function installBackend(): Promise<void> {
  const spec = (cfg<string>('backend.package') || 'hoox-pyne[pro,lsp]').trim() || 'hoox-pyne[pro,lsp]';
  // The full spec includes [lsp], so restart the client to pick up the venv.
  return installPipPackage(spec, 'backend (Pro API)', { restartLsp: true });
}

/** Offer to install the language server when it is missing on activation. */
export async function handleMissingServer(label: string): Promise<void> {
  if (cfg<boolean>('install.autoInstall') === true) {
    log('pynescript.install.autoInstall is on — installing automatically.');
    void installLanguageServer({ restart: true });
    return;
  }
  if (cfg<boolean>('install.autoPrompt') !== false && !state.installPromptDismissed) {
    state.installPromptDismissed = true;
    const choice = await window.showWarningMessage(
      'PYNE language server not found. Install it now with pip?',
      {
        modal: true,
        detail:
          'This runs: pip install --upgrade "hoox-pyne[lsp]"\n\n' +
          `Resolved launch: ${label}\n\n` +
          'You can also run “PYNE: Install Language Server” at any time.',
      },
      'Install now',
      'Later',
      "Don't ask again",
    );
    if (choice === 'Install now') {
      void installLanguageServer({ restart: true });
      return;
    }
    if (choice === "Don't ask again") {
      await workspace
        .getConfiguration('pynescript')
        .update('install.autoPrompt', false, ConfigurationTarget.Global);
    }
    // "Later" / dismissed: stay quiet for the rest of the session; the status
    // bar keeps the error state and the palette command stays available.
    return;
  }
  if (!state.installPromptDismissed) {
    state.installPromptDismissed = true;
    void window.showErrorMessage(
      'PYNE language server not found. Run “PYNE: Install Language Server” ' +
        'or install with: pip install "hoox-pyne[lsp]".',
    );
  }
}
