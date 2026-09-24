---
type: "Document"
title: "Publish checklist"
description: "Publish hoox-pyne under personal PyPI account jango-blockchained from hoox-sh/pyne Actions."
resource: "docs/pyne/devops/publish-checklist.mdx"
tags: [devops, doc, docs, pyne]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/pyne/devops/publish-checklist.mdx"
    title: "docs/pyne/devops/publish-checklist.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/devops/publish-checklist.mdx`.

# Outline

* Abstract
* 0. Identity map
* 1. Confirm repo host (hoox-sh/pyne)
  * Automation secrets
* 2. PyPI under personal account jango-blockchained
  * Preferred — API token
  * Optional — Trusted Publishing
* 3. Local package smoke (no upload)
* 4. GitHub Actions dry-run
* 5. Cut v0.6.7
* 6. Post-publish verify
* Hardcoded owner map (repo automation)
* See also

# Mentions

* [scripts/build](/code/scripts/build.md)
* [src/pynescript](/code/src/pynescript.md)
