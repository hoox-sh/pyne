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

import assert from 'node:assert/strict';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { describe, it } from 'node:test';

const EXT_ROOT = path.resolve(__dirname, '../../');
const PACKAGE_PATH = path.join(EXT_ROOT, 'package.json');
const SNIPPETS_PATH = path.join(EXT_ROOT, 'snippets', 'pine.code-snippets');

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
  'pynescript.selectSyntax',
];

interface CommandContribution {
  command: string;
  title?: string;
  category?: string;
  description?: string;
}

interface MenuEntry {
  command: string;
}

interface SnippetEntry {
  prefix?: string | string[];
}

describe('package identity', () => {
  it('has the Marketplace identity', () => {
    assert.equal(pkg.name, 'pyne');
    assert.equal(pkg.publisher, 'hoox-sh');
    assert.equal(pkg.displayName, 'PYNE Language Support');
    assert.ok(String(pkg.version).startsWith('0.5'), `unexpected version ${pkg.version}`);
  });
});

describe('commands', () => {
  const commands = pkg.contributes.commands as CommandContribution[];
  const commandIds = commands.map((c) => c.command);

  it('contributes every expected command id', () => {
    for (const id of EXPECTED_COMMANDS) {
      assert.ok(commandIds.includes(id), `missing command: ${id}`);
    }
    assert.ok(!commandIds.includes('pynescript.selectTheme'), 'selectTheme must not be contributed');
  });

  it('contributes selectSyntax', () => {
    const entry = commands.find((c) => c.command === 'pynescript.selectSyntax');
    assert.ok(entry, 'pynescript.selectSyntax is not in contributes.commands');
    assert.equal(entry.title, 'Select Syntax Highlighting');
    assert.equal(entry.category, 'PYNE');
    assert.equal(
      entry.description,
      'Choose AXIS Void, Hoox Signal, PYNE Volt, or inherit the active theme',
    );
  });

  it('has no duplicate command ids', () => {
    assert.equal(new Set(commandIds).size, commandIds.length, 'duplicate command id');
  });

  it('gives every command a real description', () => {
    for (const c of commands) {
      assert.ok(c.description && c.description.trim().length > 0, `${c.command} missing description`);
      assert.notEqual(
        c.description,
        `${c.title} command`,
        `${c.command} still has a generic description`,
      );
    }
  });

  it('lists every commandPalette entry in contributes.commands', () => {
    const palette = (pkg.contributes.menus?.commandPalette ?? []) as MenuEntry[];
    for (const entry of palette) {
      assert.ok(commandIds.includes(entry.command), `palette ${entry.command} is not contributed`);
    }
  });

  it('lists every editor/context command in contributes.commands', () => {
    const ctx = (pkg.contributes.menus?.['editor/context'] ?? []) as MenuEntry[];
    for (const entry of ctx) {
      assert.ok(commandIds.includes(entry.command), `context ${entry.command} is not contributed`);
    }
  });
});

describe('settings', () => {
  it('has no duplicate setting keys', () => {
    const configuration = Array.isArray(pkg.contributes.configuration)
      ? pkg.contributes.configuration
      : [pkg.contributes.configuration];
    const keys = configuration.flatMap((group: { properties?: Record<string, unknown> }) =>
      Object.keys(group.properties ?? {}),
    );
    assert.equal(new Set(keys).size, keys.length, 'duplicate setting key');
  });

  it('does not mention the removed pynescript.theme setting', () => {
    const appearance = (pkg.contributes.configuration as Array<{ properties?: Record<string, { markdownDescription?: string }> }>)
      .flatMap((group) => Object.values(group.properties ?? {}));
    for (const setting of appearance) {
      const text = setting.markdownDescription ?? '';
      assert.ok(!text.includes('pynescript.theme'), 'leftover pynescript.theme mention');
    }
  });
});

describe('snippets', () => {
  it('parses and includes indicator, strategy, and library', () => {
    const snippets = JSON.parse(fs.readFileSync(SNIPPETS_PATH, 'utf8')) as Record<string, SnippetEntry>;
    const prefixes = Object.values(snippets).flatMap((s) =>
      Array.isArray(s.prefix) ? s.prefix : s.prefix ? [s.prefix] : [],
    );
    assert.ok(prefixes.includes('indicator'), 'missing indicator snippet');
    assert.ok(prefixes.includes('strategy'), 'missing strategy snippet');
    assert.ok(prefixes.includes('library'), 'missing library snippet');
  });
});

describe('language', () => {
  it('maps the expected file extensions', () => {
    const lang = (pkg.contributes.languages as Array<{ id: string; extensions: string[] }>).find(
      (l) => l.id === 'pinescript',
    );
    assert.ok(lang, 'pinescript language contribution');
    for (const ext of ['.pyne', '.pine', '.pinev5', '.pinev6', '.pinescript']) {
      assert.ok(lang.extensions.includes(ext), `missing ${ext}`);
    }
  });

  it('activates on .pinescript workspaces', () => {
    assert.ok(
      (pkg.activationEvents as string[]).includes('workspaceContains:**/*.pinescript'),
      'missing workspaceContains:**/*.pinescript',
    );
  });
});

describe('grammar and themes', () => {
  it('ships a grammar file', () => {
    const grammar = pkg.contributes.grammars[0] as { path?: string };
    assert.ok(grammar?.path, 'missing grammar path');
    assert.ok(fs.existsSync(path.join(EXT_ROOT, grammar.path)), grammar.path);
  });

  it('ships three themes on disk', () => {
    const themes = pkg.contributes.themes as Array<{ path: string; label: string }>;
    assert.equal(themes.length, 3, `expected 3 themes, got ${themes.length}`);
    for (const theme of themes) {
      assert.ok(fs.existsSync(path.join(EXT_ROOT, theme.path)), theme.path);
    }
  });
});
