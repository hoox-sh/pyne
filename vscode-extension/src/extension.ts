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
 * Unofficial independent project. Not affiliated with or endorsed by TradingView, Inc.
 * Pine Script™ and TradingView® are trademarks of TradingView, Inc.
 */

import {
  commands,
  ConfigurationTarget,
  env,
  ExtensionContext,
  Range,
  StatusBarAlignment,
  TextEdit,
  Uri,
  window,
  workspace,
} from 'vscode';
import { ExecuteCommandRequest } from 'vscode-languageclient/node';
import { runOnPro, startBackend, testBackend } from './backend';
import { COMMANDS } from './commands';
import {
  cfg,
  PINESCRIPT,
  serverSettings,
  togglePinescriptEditor,
  togglePyneBool,
} from './config';
import { convertViaPython } from './convert';
import { installBackend, installLanguageServer, setLanguageServerRestarter } from './install';
import { log, setStatus } from './log';
import {
  getClient,
  isClientRunning,
  resolveLspLaunch,
  startClient,
  stopClient,
  withClientLock,
} from './lsp';
import { state } from './state';
import { applyPyneSyntax, themeChoices } from './syntax';

export { COMMANDS } from './commands';
export { resolveLspLaunch } from './lsp';

function registerCommands(context: ExtensionContext): void {
  context.subscriptions.push(
    commands.registerCommand(COMMANDS.showLspOutput, () => {
      if (!state.output) {
        void window.showWarningMessage('PYNE output channel is not available.');
        return;
      }
      state.output.show(true);
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
        state.output?.show(true);
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
      const client = getClient();
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
        getClient()?.diagnostics?.clear();
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
      // Also flip [pinescript] editor.linkedEditing so rename-as-you-type
      // actually runs; the LSP gate alone is not enough.
      const next = await togglePyneBool('linkedEditing.enabled', 'linked editing');
      await workspace
        .getConfiguration('editor', PINESCRIPT)
        .update('linkedEditing', next, ConfigurationTarget.Global, true);
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
      await runOnPro();
    }),
  );
}

export async function activate(context: ExtensionContext): Promise<void> {
  state.globalStorageDir = context.globalStorageUri.fsPath;
  state.extensionPath = context.extensionPath;
  setLanguageServerRestarter(() => withClientLock(() => startClient()));
  state.output = window.createOutputChannel('PYNE Language Server', { log: true });
  context.subscriptions.push(state.output);
  log('Activating PYNE extension…');

  state.statusBar = window.createStatusBarItem(StatusBarAlignment.Right, 100);
  state.statusBar.name = 'PYNE LSP';
  state.statusBar.command = COMMANDS.showLspOutput;
  context.subscriptions.push(state.statusBar);
  setStatus('$(sync~spin) PYNE…', 'Activating');

  // Register commands first so palette never shows "command not found"
  // even if the language server fails to start.
  registerCommands(context);

  context.subscriptions.push(
    workspace.onDidChangeConfiguration(async (e) => {
      if (e.affectsConfiguration('pynescript.syntaxHighlighting')) {
        await applyPyneSyntax();
      }
      if (e.affectsConfiguration('pynescript.lsp')) {
        log('LSP launch configuration changed — restarting client.');
        try {
          await withClientLock(() => startClient());
        } catch {
          /* shown */
        }
      } else if (
        e.affectsConfiguration('pynescript.formatting') ||
        e.affectsConfiguration('pynescript.diagnostics') ||
        e.affectsConfiguration('pynescript.completion') ||
        e.affectsConfiguration('pynescript.inlayHints')
      ) {
        log('Feature configuration changed — sending workspace/didChangeConfiguration.');
        getClient()?.sendNotification('workspace/didChangeConfiguration', {
          settings: serverSettings(),
        });
      }
    }),
  );

  await applyPyneSyntax();

  try {
    await withClientLock(() => startClient());
  } catch {
    /* already reported */
  }

  // Format on save: resolve the LSP edits before the file is written. Using
  // the provider directly (rather than `editor.action.formatDocument` after
  // save) means the saved bytes are already formatted.
  context.subscriptions.push(
    workspace.onWillSaveTextDocument((event) => {
      const { document } = event;
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
      event.waitUntil(
        (async () => {
          try {
            const edits = await commands.executeCommand<TextEdit[]>(
              'vscode.executeFormatDocumentProvider',
              document.uri,
              { tabSize: 4, insertSpaces: true },
            );
            return edits ?? [];
          } catch (err) {
            log(`formatOnSave failed: ${err instanceof Error ? err.message : String(err)}`);
            return [];
          }
        })(),
      );
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
    'diagnostics.style',
    'diagnostics.semantic',
    'completion.snippets',
    'inlayHints.parameters',
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
  state.statusBar?.dispose();
  return withClientLock(() => stopClient());
}
