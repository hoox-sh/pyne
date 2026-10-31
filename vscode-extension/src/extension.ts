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

import { execFileSync, spawn } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';
import {
  CancellationToken,
  commands,
  ConfigurationTarget,
  env,
  ExtensionContext,
  LogOutputChannel,
  ProgressLocation,
  Range,
  StatusBarAlignment,
  StatusBarItem,
  Uri,
  window,
  workspace,
} from 'vscode';
import {
  ExecuteCommandRequest,
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
  convertToV6: 'pynescript.convertToV6',
  diagnosticsToggle: 'pynescript.diagnosticsToggle',
  completionToggle: 'pynescript.completionToggle',
  inlayHintsToggle: 'pynescript.inlayHintsToggle',
  foldingToggle: 'pynescript.foldingToggle',
  colorPreviewToggle: 'pynescript.colorPreviewToggle',
  toggleHover: 'pynescript.toggleHover',
  toggleSignatureHelp: 'pynescript.toggleSignatureHelp',
  toggleSemanticTokens: 'pynescript.toggleSemanticTokens',
  toggleDocumentHighlight: 'pynescript.toggleDocumentHighlight',
  toggleLinkedEditing: 'pynescript.toggleLinkedEditing',
  toggleSelectionRange: 'pynescript.toggleSelectionRange',
  toggleDocumentLink: 'pynescript.toggleDocumentLink',
  toggleCodeAction: 'pynescript.toggleCodeAction',
  toggleFormatOnSave: 'pynescript.toggleFormatOnSave',
  openDocumentLink: 'pynescript.openDocumentLink',
  runOnPro: 'pynescript.runOnPro',
  installLanguageServer: 'pynescript.installLanguageServer',
  installBackend: 'pynescript.installBackend',
  startBackend: 'pynescript.startBackend',
  testBackend: 'pynescript.testBackend',
  selectTheme: 'pynescript.selectTheme',
  selectSyntax: 'pynescript.selectSyntax',
} as const;

let client: LanguageClient | undefined;
let statusBar: StatusBarItem | undefined;
let output: LogOutputChannel | undefined;
/** Prevent concurrent start/stop races from config changes + palette commands. */
let clientOp: Promise<void> = Promise.resolve();
/** Deduplicate concurrent pip installs (palette + activation prompt). */
let installInFlight: Promise<void> | null = null;
/** Avoid re-prompting on every startClient in one session after "Later". */
let installPromptDismissed = false;
/** Extension global storage (for the auto-created virtualenv). */
let globalStorageDir: string | undefined;
/** Extension install root (to read the bundled `themes/*.json`). */
let extensionPath: string | undefined;

function log(msg: string): void {
  const line = `[PYNE] ${msg}`;
  output?.appendLine(line);
}

function cfg<T>(key: string): T | undefined {
  return workspace.getConfiguration('pynescript').get<T>(key);
}

function settingOn(key: string): boolean {
  return cfg<boolean>(key) !== false;
}

/**
 * Effective PYNE backend base URL (no trailing slash).
 *
 * `pynescript.backend.useHosted` selects the hosted `pynescript.online` Pro
 * backend; otherwise `pynescript.backend.url` is used.
 */
function resolveBackendUrl(): string {
  const hosted = cfg<boolean>('backend.useHosted') === true;
  const raw = hosted
    ? (cfg<string>('backend.hostedUrl') || 'https://pynescript.online')
    : (cfg<string>('backend.url') || 'http://127.0.0.1:5002');
  return raw.trim().replace(/\/+$/, '');
}

/** PYNE product themes (contributed color themes under `themes/`). */
const PYNE_THEMES: Record<string, { label: string; file: string; description: string }> = {
  void: { label: 'AXIS Void', file: 'axis-void', description: 'Periwinkle accent · dark grey surfaces' },
  signal: { label: 'Hoox Signal', file: 'hoox-signal', description: 'Signal-orange accent · near-black surfaces' },
  volt: { label: 'PYNE Volt', file: 'pyne-volt', description: 'Lime accent · neutral near-black surfaces' },
};

/** Legacy ids kept working for users who saved them before the rename. */
const THEME_ALIASES: Record<string, string> = { orange: 'signal' };

function normalizeThemeId(value: string | undefined, fallback: string): string {
  const raw = (value || fallback).toLowerCase();
  const id = THEME_ALIASES[raw] ?? raw;
  return id === 'none' || id in PYNE_THEMES ? id : fallback;
}

/** Quick-pick items: None first, then the three product themes. */
function themeChoices() {
  return [
    { id: 'none', label: 'None', description: 'Use user/system settings' },
    ...Object.entries(PYNE_THEMES).map(([id, theme]) => ({
      id,
      label: theme.label,
      description: theme.description,
    })),
  ];
}

// NOTE: workbench theme switching is disabled for now. The extension never
// changes `workbench.colorTheme`; users pick AXIS Void / Hoox Signal /
// PYNE Volt from the normal VS Code Color Theme picker. The contributed
// themes still ship, and `pynescript.syntaxHighlighting` is unaffected.
//
// function currentThemeId() {
//   return normalizeThemeId(cfg<string>('theme'), 'none');
// }

function currentSyntaxId() {
  return normalizeThemeId(cfg<string>('syntaxHighlighting'), 'void');
}

// /**
//  * Workbench theme (UI chrome + hover cards). `none` leaves the user/system
//  * theme untouched.
//  */
// async function applyPyneTheme() {
//   const id = currentThemeId();
//   if (id === 'none') {
//     log('PYNE workbench theme: none (keeping user/system theme).');
//     return;
//   }
//   const theme = PYNE_THEMES[id];
//   const current = workspace.getConfiguration('workbench').get<string>('colorTheme');
//   if (current === theme.label) {
//     return;
//   }
//   try {
//     await workspace
//       .getConfiguration('workbench')
//       .update('colorTheme', theme.label, ConfigurationTarget.Global);
//     log(`Applied workbench theme: ${theme.label}`);
//   } catch (err) {
//     const msg = err instanceof Error ? err.message : String(err);
//     log(`Could not apply theme ${theme.label}: ${msg}`);
//   }
// }

/** Read the bundled `themes/<file>-color-theme.json`. */
function loadThemeJson(
  id: string,
): { tokenColors?: unknown[]; semanticTokenColors?: Record<string, unknown> } | undefined {
  const theme = PYNE_THEMES[id];
  if (!extensionPath || !theme) {
    return undefined;
  }
  const file = path.join(extensionPath, 'themes', `${theme.file}-color-theme.json`);
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch (err) {
    log(`Could not read ${file}: ${err instanceof Error ? err.message : String(err)}`);
    return undefined;
  }
}

/**
 * Pine syntax highlighting, independent of the workbench theme.
 *
 * Writes language-scoped `editor.tokenColorCustomizations` and
 * `editor.semanticTokenColorCustomizations` for `pinescript`; `none` removes
 * the overrides so the active theme's colors apply.
 */
async function applyPyneSyntax() {
  const id = currentSyntaxId();
  const editorConfig = workspace.getConfiguration('editor', { languageId: 'pinescript' });
  if (id === 'none') {
    try {
      await editorConfig.update('tokenColorCustomizations', undefined, ConfigurationTarget.Global, true);
      await editorConfig.update('semanticTokenColorCustomizations', undefined, ConfigurationTarget.Global, true);
      log('Cleared Pine syntax overrides (using active theme).');
    } catch (err) {
      log(`Could not clear Pine syntax overrides: ${err instanceof Error ? err.message : String(err)}`);
    }
    return;
  }
  const theme = loadThemeJson(id);
  if (!theme) {
    return;
  }
  try {
    await editorConfig.update(
      'tokenColorCustomizations',
      { textMateRules: theme.tokenColors ?? [] },
      ConfigurationTarget.Global,
      true,
    );
    await editorConfig.update(
      'semanticTokenColorCustomizations',
      { enabled: true, rules: theme.semanticTokenColors ?? {} },
      ConfigurationTarget.Global,
      true,
    );
    log(`Applied Pine syntax highlighting: ${id}`);
  } catch (err) {
    log(`Could not apply Pine syntax ${id}: ${err instanceof Error ? err.message : String(err)}`);
  }
}

async function togglePyneBool(key: string, label: string): Promise<boolean> {
  const next = !settingOn(key);
  await workspace.getConfiguration('pynescript').update(key, next, ConfigurationTarget.Global);
  void window.showInformationMessage(`PYNE ${label} ${next ? 'on' : 'off'}.`);
  return next;
}

const PINESCRIPT = { languageId: 'pinescript' } as const;

function pinescriptEditorOn(key: string): boolean {
  const v = workspace.getConfiguration('editor', PINESCRIPT).get(key);
  if (key === 'inlayHints.enabled') {
    return v !== 'off' && v !== false;
  }
  return v !== false;
}

async function togglePinescriptEditor(
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
function resolvePythonForInstall(): string | undefined {
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
  if (installInFlight) {
    return installInFlight;
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
      const venvDir = explicitVenv || (globalStorageDir ? path.join(globalStorageDir, 'pyne-venv') : '');
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
        await withClientLock(() => startClient());
      } else {
        setStatus('$(check) PYNE LSP', `Installed ${label}`);
      }
      return;
    }

    if (result.code === null) {
      setStatus('$(error) PYNE LSP', 'Install cancelled');
      void window.showWarningMessage(`PYNE: ${label} install cancelled or could not start.`);
      return;
    }

    const tail = result.output.trim().split('\n').slice(-8).join('\n');
    setStatus('$(error) PYNE LSP', `pip install failed (exit ${result.code})`);
    log(`Install failed (exit ${result.code}).\n${tail}`);
    void window.showErrorMessage(
      `PYNE: pip install failed (exit ${result.code}). See “PYNE: Show Language Server Output”. ` +
        'Set pynescript.install.venv to a writable virtualenv, or set ' +
        'pynescript.install.createVenv to true for PEP 668 (externally managed) Python.',
    );
  };

  installInFlight = run().finally(() => {
    installInFlight = null;
  });
  return installInFlight;
}

/** Install/upgrade the language server and restart the client. */
function installLanguageServer(options: { restart?: boolean } = {}): Promise<void> {
  const spec = (cfg<string>('install.package') || 'hoox-pyne[lsp]').trim() || 'hoox-pyne[lsp]';
  return installPipPackage(spec, 'language server', { restartLsp: options.restart !== false });
}

/** Install/upgrade the full backend extras (Pro API) into the same environment. */
function installBackend(): Promise<void> {
  const spec = (cfg<string>('backend.package') || 'hoox-pyne[pro,lsp]').trim() || 'hoox-pyne[pro,lsp]';
  // The full spec includes [lsp], so restart the client to pick up the venv.
  return installPipPackage(spec, 'backend (Pro API)', { restartLsp: true });
}

/**
 * Start the PYNE backend from a checkout (`python -m backend.app`) in a
 * terminal. Uses `pynescript.backend.path` or the first workspace folder.
 */
async function startBackend(): Promise<void> {
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
async function testBackend(): Promise<void> {
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

/** Offer to install the language server when it is missing on activation. */
async function handleMissingServer(label: string): Promise<void> {
  if (cfg<boolean>('install.autoInstall') === true) {
    log('pynescript.install.autoInstall is on — installing automatically.');
    void installLanguageServer({ restart: true });
    return;
  }
  if (cfg<boolean>('install.autoPrompt') !== false && !installPromptDismissed) {
    installPromptDismissed = true;
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
  if (!installPromptDismissed) {
    installPromptDismissed = true;
    void window.showErrorMessage(
      'PYNE language server not found. Run “PYNE: Install Language Server” ' +
        'or install with: pip install "hoox-pyne[lsp]".',
    );
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
  const installPython = (cfg<string>('install.python') || '').trim();
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
    log('No language server binary/module found on PATH.');
    // Fire-and-forget: the prompt/install restarts the client via the lock once
    // it completes, so we must not await here (startClient already holds it).
    void handleMissingServer(launch.label);
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
      setStatus(
        '$(check) PYNE LSP',
        `Running: ${launch.label}  ·  ${Object.keys(COMMANDS).length} commands`,
      );
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
    commands.registerCommand(COMMANDS.installLanguageServer, async () => {
      await installLanguageServer({ restart: true });
    }),
  );

  context.subscriptions.push(
    commands.registerCommand(COMMANDS.installBackend, async () => {
      await installBackend();
    }),
  );

  context.subscriptions.push(
    commands.registerCommand(COMMANDS.startBackend, async () => {
      await startBackend();
    }),
  );

  context.subscriptions.push(
    commands.registerCommand(COMMANDS.testBackend, async () => {
      await testBackend();
    }),
  );

  // Workbench theme switching is disabled — see the note above
  // `currentSyntaxId`. Users select the contributed themes from the normal
  // VS Code Color Theme picker instead.
  //
  // context.subscriptions.push(
  //   commands.registerCommand(COMMANDS.selectTheme, async () => {
  //     const pick = await window.showQuickPick(themeChoices(), {
  //       placeHolder: 'Select a PYNE workbench theme (None = user/system)',
  //       matchOnDescription: true,
  //     });
  //     if (!pick) {
  //       return;
  //     }
  //     await workspace
  //       .getConfiguration('pynescript')
  //       .update('theme', pick.id, ConfigurationTarget.Global);
  //     await applyPyneTheme();
  //     void window.showInformationMessage(`PYNE workbench theme: ${pick.label}.`);
  //   }),
  // );

  context.subscriptions.push(
    commands.registerCommand(COMMANDS.selectSyntax, async () => {
      const pick = await window.showQuickPick(themeChoices(), {
        placeHolder: 'Select a Pine syntax highlighting palette (None = active theme)',
        matchOnDescription: true,
      });
      if (!pick) {
        return;
      }
      await workspace
        .getConfiguration('pynescript')
        .update('syntaxHighlighting', pick.id, ConfigurationTarget.Global);
      await applyPyneSyntax();
      void window.showInformationMessage(`PYNE syntax highlighting: ${pick.label}.`);
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

  context.subscriptions.push(
    commands.registerCommand(COMMANDS.convertToV6, async () => {
      const editor = window.activeTextEditor;
      if (!editor) {
        void window.showWarningMessage('No active editor to convert.');
        return;
      }
      if (editor.document.languageId !== 'pinescript') {
        void window.showWarningMessage('Convert to Pine v6 is only available for .pyne / .pine files.');
        return;
      }
      const prev = editor.document.getText();
      let next = prev;
      try {
        if (isClientRunning() && client) {
          const payload = (await client.sendRequest(ExecuteCommandRequest.type, {
            command: COMMANDS.convertToV6,
            arguments: [editor.document.uri.toString()],
          })) as { source?: string; from_version?: number; changed?: boolean } | null;
          if (payload && typeof payload.source === 'string') {
            next = payload.source;
          } else {
            next = convertViaPython(prev);
          }
        } else {
          next = convertViaPython(prev);
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        log(`convertToV6 failed: ${msg}`);
        try {
          next = convertViaPython(prev);
        } catch (err2) {
          const msg2 = err2 instanceof Error ? err2.message : String(err2);
          void window.showErrorMessage(`Convert to Pine v6 failed: ${msg2}`);
          return;
        }
      }
      if (next === prev) {
        void window.showInformationMessage('Already Pine v6.');
        return;
      }
      const full = new Range(
        editor.document.positionAt(0),
        editor.document.positionAt(prev.length),
      );
      const ok = await editor.edit((builder) => builder.replace(full, next));
      if (!ok) {
        void window.showErrorMessage('Convert to Pine v6 could not apply the edit.');
        return;
      }
      void window.showInformationMessage('Converted script to Pine v6.');
    }),
  );

  context.subscriptions.push(
    commands.registerCommand(COMMANDS.diagnosticsToggle, async () => {
      const next = await togglePyneBool('diagnostics.enabled', 'diagnostics');
      if (!next) {
        client?.diagnostics?.clear();
      }
    }),
  );

  context.subscriptions.push(
    commands.registerCommand(COMMANDS.completionToggle, async () => {
      await togglePyneBool('completion.snippets', 'snippet completions');
    }),
  );

  context.subscriptions.push(
    commands.registerCommand(COMMANDS.inlayHintsToggle, async () => {
      await togglePinescriptEditor('inlayHints.enabled', 'on', 'off', 'inlay hints');
    }),
  );

  context.subscriptions.push(
    commands.registerCommand(COMMANDS.foldingToggle, async () => {
      await togglePinescriptEditor('folding', true, false, 'folding');
    }),
  );

  context.subscriptions.push(
    commands.registerCommand(COMMANDS.colorPreviewToggle, async () => {
      await togglePinescriptEditor('colorDecorators', true, false, 'color preview');
    }),
  );

  context.subscriptions.push(
    commands.registerCommand(COMMANDS.toggleHover, async () => {
      await togglePyneBool('hover.enabled', 'hover');
    }),
  );

  context.subscriptions.push(
    commands.registerCommand(COMMANDS.toggleSignatureHelp, async () => {
      await togglePyneBool('signatureHelp.enabled', 'signature help');
    }),
  );

  context.subscriptions.push(
    commands.registerCommand(COMMANDS.toggleSemanticTokens, async () => {
      // Gate is enforced client-side via pynescript.semanticTokens.enabled.
      // Also flip the editor setting so VS Code stops requesting tokens.
      const next = await togglePyneBool('semanticTokens.enabled', 'semantic tokens');
      await workspace
        .getConfiguration('editor', PINESCRIPT)
        .update('semanticHighlighting.enabled', next, ConfigurationTarget.Global, true);
    }),
  );

  context.subscriptions.push(
    commands.registerCommand(COMMANDS.toggleDocumentHighlight, async () => {
      await togglePyneBool('documentHighlight.enabled', 'document highlight');
    }),
  );

  context.subscriptions.push(
    commands.registerCommand(COMMANDS.toggleLinkedEditing, async () => {
      await togglePyneBool('linkedEditing.enabled', 'linked editing');
    }),
  );

  context.subscriptions.push(
    commands.registerCommand(COMMANDS.toggleSelectionRange, async () => {
      await togglePyneBool('selectionRange.enabled', 'selection range');
    }),
  );

  context.subscriptions.push(
    commands.registerCommand(COMMANDS.toggleDocumentLink, async () => {
      await togglePyneBool('documentLink.enabled', 'document links');
    }),
  );

  context.subscriptions.push(
    commands.registerCommand(COMMANDS.toggleCodeAction, async () => {
      await togglePyneBool('codeAction.enabled', 'code actions');
    }),
  );

  context.subscriptions.push(
    commands.registerCommand(COMMANDS.toggleFormatOnSave, async () => {
      await togglePyneBool('formatOnSave.enabled', 'format on save');
    }),
  );

  context.subscriptions.push(
    commands.registerCommand(COMMANDS.openDocumentLink, async () => {
      const editor = window.activeTextEditor;
      if (!editor || editor.document.languageId !== 'pinescript') {
        return;
      }
      const { document } = editor;
      const offset = document.offsetAt(editor.selection.active);
      const line = document.lineAt(editor.selection.active.line);
      const text = line.text;
      // Scan the current line for http(s) URLs and open the one covering offset.
      const urlRe = /https?:\/\/[^\s<>\"'`*]+/g;
      let match: RegExpExecArray | null;
      while ((match = urlRe.exec(text)) !== null) {
        const url = match[0].replace(/[.,;:!?]+$/, '');
        const start = line.range.start.character + match.index;
        const end = start + url.length;
        if (offset >= start && offset <= end) {
          try {
            await env.openExternal(Uri.parse(url));
          } catch {
            void window.showWarningMessage(`Could not open link: ${url}`);
          }
          return;
        }
      }
      void window.showInformationMessage('No link under the cursor.');
    }),
  );

  context.subscriptions.push(
    commands.registerCommand(COMMANDS.runOnPro, async () => {
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
    }),
  );
}

function convertViaPython(source: string): string {
  const launch = resolveLspLaunch();
  const python =
    launch.command === 'python' ||
    launch.command === 'python3' ||
    launch.command.endsWith('/python') ||
    launch.command.endsWith('/python3')
      ? launch.command
      : (cfg<string>('lsp.python') || 'python3').trim() || 'python3';
  const script =
    'from pynescript.util.pine_convert import convert_to_v6\n' +
    'import sys\n' +
    'sys.stdout.write(convert_to_v6(sys.stdin.read()))\n';
  try {
    return execFileSync(python, ['-c', script], {
      input: source,
      encoding: 'utf8',
      timeout: 15000,
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    throw new Error(
      `Need Python with hoox-pyne installed (pip install hoox-pyne). ${msg}`,
    );
  }
}

export async function activate(context: ExtensionContext): Promise<void> {
  globalStorageDir = context.globalStorageUri.fsPath;
  extensionPath = context.extensionPath;
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
      // Workbench theme switching is disabled (see the note near
      // `currentSyntaxId`); only the Pine syntax palette is applied.
      //
      // if (e.affectsConfiguration('pynescript.theme')) {
      //   await applyPyneTheme();
      // }
      if (e.affectsConfiguration('pynescript.syntaxHighlighting')) {
        await applyPyneSyntax();
      }
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

  // Only the Pine syntax palette is applied on activation. The workbench
  // theme is never changed automatically — users pick AXIS Void / Hoox Signal
  // / PYNE Volt from the VS Code Color Theme picker.
  await applyPyneSyntax();

  try {
    await withClientLock(() => startClient());
  } catch {
    /* already reported */
  }

  // Format on save: runs the server formatter when the document is saved.
  context.subscriptions.push(
    workspace.onDidSaveTextDocument(async (document) => {
      if (document.languageId !== 'pinescript') {
        return;
      }
      if (cfg<boolean>('formatOnSave.enabled') === false) {
        return;
      }
      if (cfg<boolean>('formatting.enabled') === false) {
        return;
      }
      if (!isClientRunning()) {
        return;
      }
      try {
        await commands.executeCommand('editor.action.formatDocument');
      } catch {
        /* format errors are reported by the format command path */
      }
    }),
  );

  // Snapshot effective settings for the output channel (debug aid).
  const launch = resolveLspLaunch();
  const settings: Record<string, unknown> = {};
  for (const key of [
    'lsp.enabled',
    'lsp.command',
    'lsp.python',
    'formatting.enabled',
    'diagnostics.enabled',
    'completion.snippets',
    'formatOnSave.enabled',
    'hover.enabled',
    'signatureHelp.enabled',
    'semanticTokens.enabled',
    'documentHighlight.enabled',
    'linkedEditing.enabled',
    'selectionRange.enabled',
    'documentLink.enabled',
    'codeAction.enabled',
  ]) {
    settings[key] = cfg<unknown>(key);
  }
  log(`Effective settings: ${JSON.stringify(settings)}`);
  log(`Resolved LSP: ${launch.label} (found=${launch.found})`);
  log('Activation complete.');
}

export function deactivate(): Promise<void> | undefined {
  statusBar?.dispose();
  return withClientLock(() => stopClient());
}
