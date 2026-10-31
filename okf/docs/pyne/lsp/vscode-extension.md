---
type: "Document"
title: "VS Code Extension"
description: "PYNE VS Code extension: LanguageClient host for pyne-lsp, TextMate grammar, snippets, settings, and VSIX 0.5.0."
resource: "docs/pyne/lsp/vscode-extension.mdx"
tags: [doc, docs, lsp, pyne]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-10-31T14:46:08Z
sources:
  - id: tree
    resource: "docs/pyne/lsp/vscode-extension.mdx"
    title: "docs/pyne/lsp/vscode-extension.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/lsp/vscode-extension.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface
  * Package identity
  * Language contribution
  * Hosted pyne-lsp methods (not reimplemented in TypeScript)
  * Activation
  * Settings (pynescript.)
  * Commands
  * Client options
* Internals
  * Automatic install
  * Build
  * Snippets
  * Backend and Pro (Run on Pro)
* Invariants and edge cases
* Worked example — extension development
* Failure modes
* See also

# Mentions

* [src/pynescript](/code/src/pynescript.md)
* [src/pynescript/langserver](/code/src/pynescript/langserver.md)
