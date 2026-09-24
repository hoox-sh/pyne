---
type: "Document"
title: "Builtin Metadata"
description: "JSON catalog for LSP completion and hover; generation pipeline; Fernet encryption, CRYPTOKEY / METADATAKEY, and decrypt path."
resource: "docs/pyne/lsp/builtin-metadata.mdx"
tags: [doc, docs, lsp, pyne]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/pyne/lsp/builtin-metadata.mdx"
    title: "docs/pyne/lsp/builtin-metadata.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/lsp/builtin-metadata.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface (metadata record)
  * Loader API
  * Consumers
* Internals
  * Generation
  * Encryption (build)
  * Decrypt path
* Invariants and edge cases
* Worked example — local dev
* Worked example — encrypted binary path
* Failure modes
* See also

# Mentions

* [scripts](/code/scripts.md)
* [scripts/build](/code/scripts/build.md)
* [src/pynescript/langserver/providers](/code/src/pynescript/langserver/providers.md)
