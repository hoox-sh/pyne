---
type: "Document"
title: "Nuitka build (LSP + CLI)"
description: "Compile pyne-lsp and pyne CLI with Nuitka — onefile vs standalone, CI build script, Anaconda quirks, and artifact layout."
resource: "docs/pyne/devops/nuitka-build.mdx"
tags: [devops, doc, docs, pyne]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/pyne/devops/nuitka-build.mdx"
    title: "docs/pyne/devops/nuitka-build.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/devops/nuitka-build.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface
  * Commands
  * Build modes (approx. wall time)
  * Expected layout
* Internals
  * Key Nuitka flags (compile.py)
  * Entry module
  * Metadata stage
  * Anaconda
* Invariants & edge cases
* Worked examples
  * Local onefile with explicit jobs
  * CI-shaped build
  * Verify without compile
* Failure modes
* See also

# Mentions

* [scripts](/code/scripts.md)
* [scripts/build](/code/scripts/build.md)
* [src/pynescript/langserver](/code/src/pynescript/langserver.md)
