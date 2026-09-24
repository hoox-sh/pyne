---
type: "Document"
title: "Editors & LSP"
description: "Wire pyne-lsp into VS Code, Neovim, Zed, Emacs, Helix, and other LSP clients for diagnostics, completion, hover, and formatting."
resource: "docs/pyne/enduser/guides/editors.mdx"
tags: [doc, docs, enduser, pyne]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/pyne/enduser/guides/editors.mdx"
    title: "docs/pyne/enduser/guides/editors.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/enduser/guides/editors.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface
  * Install server
  * VS Code / Cursor / Antigravity
  * Neovim (nvim-lspconfig)
  * Zed
  * Emacs (lsp-mode)
  * Helix
  * Sublime Text (LSP package)
  * Generic
* Internals (repo paths)
* Invariants & edge cases
* Worked examples
  * Verify server starts (stdio smoke)
  * Neovim minimal init.lua fragment
  * Force a specific venv binary in VS Code
* Failure modes
* See also

# Mentions

* [scripts](/code/scripts.md)
* [src/pynescript/langserver](/code/src/pynescript/langserver.md)
