---
type: "Document"
title: "Metadata encryption"
description: "Fernet-encrypted LSP builtinmetadata.json — key lifecycle, CI secrets, integrity hashes, and runtime decrypt."
resource: "docs/pyne/devops/metadata-crypto.mdx"
tags: [devops, doc, docs, pyne]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/pyne/devops/metadata-crypto.mdx"
    title: "docs/pyne/devops/metadata-crypto.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/devops/metadata-crypto.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface
  * Files
  * Environment variables
  * Code entrypoints
* Internals
  * Generation (always code-derived)
  * Encrypt (local sketch)
  * Decrypt integrity check
  * Dev vs binary
* Invariants & edge cases
* Worked examples
  * Regenerate + local encrypt
  * CI snippet
  * Runtime with env key
* Failure modes
* See also

# Mentions

* [scripts](/code/scripts.md)
* [scripts/build](/code/scripts/build.md)
* [src/pynescript/langserver/providers](/code/src/pynescript/langserver/providers.md)
