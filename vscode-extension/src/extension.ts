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

import * as path from 'path';
import { ExtensionContext, workspace, commands, window } from 'vscode';
import {
  LanguageClient,
  LanguageClientOptions,
  ServerOptions,
  TransportKind,
} from 'vscode-languageclient/node';

let client: LanguageClient | undefined;

function getConfig(key: string): unknown {
  return workspace.getConfiguration('pynescript').get(key);
}

function getLspCommand(): string {
  const cmd = getConfig('lsp.command');
  return typeof cmd === 'string' ? cmd : 'pynescript-lsp';
}

export function activate(context: ExtensionContext): void {
  const enabled = getConfig('lsp.enabled');
  if (enabled === false) {
    return;
  }

  const lspCommand = getLspCommand();
  const scriptPath = context.asAbsolutePath(path.join('..', 'src', 'pynescript', 'langserver'));

  const serverOptions: ServerOptions = {
    command: lspCommand,
    args: ['--parent-dir', scriptPath],
    transport: TransportKind.stdio,
    options: {
      env: {
        ...process.env,
        PYTHONPATH: scriptPath,
      },
    },
  };

  const clientOptions: LanguageClientOptions = {
    documentSelector: [
      { language: 'pinescript', scheme: 'file' },
      { language: 'pinescript', scheme: 'untitled' },
    ],
    synchronize: {
      fileEvents: workspace.createFileSystemWatcher('**/*.pine'),
    },
    diagnosticCollectionName: 'pynescript',
    initializationOptions: {
      formattingEnabled: getConfig('formatting.enabled') !== false,
      snippetsEnabled: getConfig('completion.snippets') !== false,
      diagnosticsEnabled: getConfig('diagnostics.enabled') !== false,
    },
  };

  client = new LanguageClient(
    'pynescript-lsp',
    'Pine Script Language Server',
    serverOptions,
    clientOptions
  );

  client.start();

  client.onNotification('window/showMessage', (params: { type: number; message: string }) => {
    window.showInformationMessage(params.message);
  });

  context.subscriptions.push(
    commands.registerCommand('pynescript.restartServer', async () => {
      if (client) {
        await client.stop();
        client.start();
        window.showInformationMessage('Pine Script language server restarted.');
      }
    })
  );

  context.subscriptions.push(
    commands.registerCommand('pynescript.formatDocument', async () => {
      const editor = window.activeTextEditor;
      if (editor) {
        await commands.executeCommand('editor.action.formatDocument');
      }
    })
  );
}

export function deactivate(): Promise<void> | undefined {
  return client?.stop();
}
