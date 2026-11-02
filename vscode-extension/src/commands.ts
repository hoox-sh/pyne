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
  selectSyntax: 'pynescript.selectSyntax',
} as const;
