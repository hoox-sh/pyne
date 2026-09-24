---
type: "Document"
title: "Configuration"
description: "Package extras, console scripts, Pro API environment variables, data providers, and editor LSP settings for PYNE."
resource: "docs/pyne/enduser/getting-started/configuration.mdx"
tags: [doc, docs, enduser, pyne]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:38:48Z
sources:
  - id: tree
    resource: "docs/pyne/enduser/getting-started/configuration.mdx"
    title: "docs/pyne/enduser/getting-started/configuration.mdx"
    author: process:git
okf_lock: generated
---

# Source

Repo path `docs/pyne/enduser/getting-started/configuration.mdx`.

# Outline

* Abstract
* Conceptual model
* Interface surface
  * Package extras (pyproject.toml)
  * Console scripts
  * CLI flags that act as “config”
  * Pro API environment variables
  * Runtime / evaluate environment variables
  * Data providers
  * Editor / LSP client settings
  * AXIS / frontend coupling (optional)
* Internals (repo paths)
* Invariants & edge cases
* Worked examples
  * Desk-only machine
  * Editor workstation
  * Local API + AXIS
  * Scripted Alpha Vantage fetch
* Failure modes
* See also

# Mentions

* [src/pynescript](/code/src/pynescript.md)
* [src/pynescript/runtime](/code/src/pynescript/runtime.md)
