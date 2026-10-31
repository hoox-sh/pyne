import * as assert from 'assert';
import * as fs from 'fs';
import * as path from 'path';
import * as vscode from 'vscode';

// Mocha BDD globals provided by the VS Code test runner at runtime.
declare function suite(name: string, fn: () => void): void;
declare function test(name: string, fn: () => void | Promise<void>, opts?: { timeout?: number }): any;

const PACKAGE_PATH = path.resolve(__dirname, '../../package.json');
const SNIPPETS_PATH = path.resolve(__dirname, '../../snippets/pine.code-snippets');

const pkg = JSON.parse(fs.readFileSync(PACKAGE_PATH, 'utf8'));

const EXPECTED_COMMANDS = [
  'pynescript.restartServer',
  'pynescript.formatDocument',
  'pynescript.showLspOutput',
  'pynescript.showLspCommand',
  'pynescript.convertToV6',
  'pynescript.diagnosticsToggle',
  'pynescript.completionToggle',
  'pynescript.inlayHintsToggle',
  'pynescript.foldingToggle',
  'pynescript.colorPreviewToggle',
  'pynescript.toggleHover',
  'pynescript.toggleSignatureHelp',
  'pynescript.toggleSemanticTokens',
  'pynescript.toggleDocumentHighlight',
  'pynescript.toggleLinkedEditing',
  'pynescript.toggleSelectionRange',
  'pynescript.toggleDocumentLink',
  'pynescript.toggleCodeAction',
  'pynescript.toggleFormatOnSave',
  'pynescript.openDocumentLink',
  'pynescript.runOnPro',
  'pynescript.installLanguageServer',
  'pynescript.installBackend',
  'pynescript.startBackend',
  'pynescript.testBackend',
];

const EXPECTED_SETTINGS = [
  'pynescript.lsp.enabled',
  'pynescript.lsp.command',
  'pynescript.lsp.python',
  'pynescript.lsp.args',
  'pynescript.diagnostics.enabled',
  'pynescript.diagnostics.severity',
  'pynescript.formatting.enabled',
  'pynescript.completion.snippets',
  'pynescript.formatOnSave.enabled',
  'pynescript.hover.enabled',
  'pynescript.signatureHelp.enabled',
  'pynescript.semanticTokens.enabled',
  'pynescript.documentHighlight.enabled',
  'pynescript.linkedEditing.enabled',
  'pynescript.selectionRange.enabled',
  'pynescript.documentLink.enabled',
  'pynescript.codeAction.enabled',
  'pynescript.pro.enabled',
  'pynescript.pro.apiKey',
  'pynescript.backend.url',
  'pynescript.backend.useHosted',
  'pynescript.backend.hostedUrl',
  'pynescript.backend.package',
  'pynescript.backend.path',
  'pynescript.install.autoInstall',
  'pynescript.install.autoPrompt',
  'pynescript.install.package',
  'pynescript.install.python',
  'pynescript.install.args',
  'pynescript.install.createVenv',
  'pynescript.install.venv',
];

suite('PYNE Extension Structure', () => {
  test('package.json is valid JSON with expected identity', () => {
    assert.strictEqual(pkg.name, 'pyne');
    assert.strictEqual(pkg.publisher, 'hoox-sh');
    assert.strictEqual(pkg.displayName, 'PYNE Language Support');
    assert.ok(pkg.version.startsWith('0.5'));
  });

  test('contributes all expected commands', () => {
    const commandIds = pkg.contributes.commands.map((c: { command: string }) => c.command);
    for (const id of EXPECTED_COMMANDS) {
      assert.ok(commandIds.includes(id), `Missing command: ${id}`);
    }
  });

  test('contributes all expected settings', () => {
    const settings = Object.keys(pkg.contributes.configuration.properties);
    for (const key of EXPECTED_SETTINGS) {
      assert.ok(settings.includes(key), `Missing setting: ${key}`);
    }
  });

  test('snippets file is valid JSON', () => {
    const snippets = JSON.parse(fs.readFileSync(SNIPPETS_PATH, 'utf8'));
    assert.ok(Object.keys(snippets).length > 0, 'Snippets file should not be empty');
  });

  test('registers snippets contribution for pinescript', () => {
    const snippets = pkg.contributes.snippets || [];
    assert.ok(
      snippets.some((s: any) => s.language === 'pinescript' && s.path === './snippets/pine.code-snippets'),
      'Missing pinescript snippets contribution',
    );
  });

  test('language id is pinescript with expected extensions', () => {
    const lang = pkg.contributes.languages.find((l: any) => l.id === 'pinescript');
    assert.ok(lang, 'pinescript language contribution');
    assert.ok(lang.extensions.includes('.pyne'));
    assert.ok(lang.extensions.includes('.pine'));
    assert.ok(lang.extensions.includes('.pinev5'));
    assert.ok(lang.extensions.includes('.pinev6'));
    assert.ok(lang.extensions.includes('.pinescript'));
  });
});

suite('PYNE Extension Activation', () => {
  test('activates without error', async () => {
    // Extension activates on onLanguage:pinescript; open a document to trigger it
    const doc = await vscode.workspace.openTextDocument({
      content: '//@version=6\nindicator("test", overlay=true)\nplot(close)\n',
      language: 'pinescript',
    });
    assert.ok(doc, 'Document opened');
    assert.strictEqual(doc.languageId, 'pinescript');
    await vscode.window.showTextDocument(doc);
    // Give activation a moment
    await new Promise((r) => setTimeout(r, 1000));
  }).timeout(30000);

  test('registers PYNE commands with the command palette', async () => {
    const commands = await vscode.commands.getCommands();
    for (const id of EXPECTED_COMMANDS) {
      assert.ok(commands.includes(id), `Command not registered: ${id}`);
    }
  }).timeout(15000);

  test('default settings are present', async () => {
    const config = vscode.workspace.getConfiguration('pynescript');
    assert.strictEqual(config.get('diagnostics.enabled'), true);
    assert.strictEqual(config.get('formatting.enabled'), true);
    assert.strictEqual(config.get('completion.snippets'), true);
    assert.strictEqual(config.get('hover.enabled'), true);
    assert.strictEqual(config.get('semanticTokens.enabled'), true);
    assert.strictEqual(config.get('formatOnSave.enabled'), false);
    assert.strictEqual(config.get('pro.enabled'), false);
    assert.strictEqual(config.get('backend.url'), 'http://127.0.0.1:5002');
    assert.strictEqual(config.get('backend.useHosted'), false);
    assert.strictEqual(config.get('backend.hostedUrl'), 'https://pynescript.online');
    assert.strictEqual(config.get('backend.package'), 'hoox-pyne[pro,lsp]');
    assert.strictEqual(config.get('install.autoInstall'), false);
    assert.strictEqual(config.get('install.autoPrompt'), true);
    assert.strictEqual(config.get('install.package'), 'hoox-pyne[lsp]');
    assert.strictEqual(config.get('install.createVenv'), true);
  });

  test('toggle commands change their settings', async () => {
    const before = vscode.workspace.getConfiguration('pynescript').get('hover.enabled');
    await vscode.commands.executeCommand('pynescript.toggleHover');
    const after = vscode.workspace.getConfiguration('pynescript').get('hover.enabled');
    assert.strictEqual(after, !before);
    // Restore
    await vscode.commands.executeCommand('pynescript.toggleHover');
  }).timeout(15000);

  test('openDocumentLink reports no link when none present', async () => {
    const doc = await vscode.workspace.openTextDocument({
      content: '//@version=6\nindicator("test", overlay=true)\nplot(close)\n',
      language: 'pinescript',
    });
    await vscode.window.showTextDocument(doc);
    await new Promise((r) => setTimeout(r, 500));
    // Should not throw; reports "No link under the cursor."
    await vscode.commands.executeCommand('pynescript.openDocumentLink');
  }).timeout(15000);
});
