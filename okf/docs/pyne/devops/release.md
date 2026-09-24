---
type: "Document"
title: "Release"
description: "Tag-driven CLI + LSP multi-platform Nuitka binaries, wheels, Docker CLI image, VSIX packaging, GitHub Releases, and Marketplace publish."
resource: "docs/pyne/devops/release.mdx"
tags: [devops, doc, docs, pyne]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/pyne/devops/release.mdx"
    title: "docs/pyne/devops/release.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/devops/release.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface
  * Triggers
  * Jobs
  * Environment
  * Local make-side packaging
* Internals
  * Release asset contract (from release body)
* Invariants & edge cases
* Worked examples
  * Cut a release
  * Smoke-test a downloaded binary
* Failure modes
* See also

# Mentions

* [scripts/build](/code/scripts/build.md)
* [src/pynescript](/code/src/pynescript.md)
