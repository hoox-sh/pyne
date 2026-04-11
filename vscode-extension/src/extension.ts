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

  const disposable = client.start();
  context.subscriptions.push(disposable);

  client.onReady().then(() => {
    client!.onNotification('window/showMessage', (params: { type: number; message: string }) => {
      window.showInformationMessage(params.message);
    });
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
