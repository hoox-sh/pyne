---
type: "Playbook"
title: "How to read the PYNE bundle"
description: "Read the root index, open one concept, and follow its links instead of scanning the package."
tags: [pyne, playbook, okf]
status: stable
okf_lock: human
generated:
  by: human:jango_blockchained
  at: 2026-09-24T00:00:00Z
sources:
  - id: spec
    resource: https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md
    title: Open Knowledge Format v0.2
---

# What this bundle is

This directory is an [Open Knowledge Format](https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md) v0.2 bundle. It is a compiled cache of the PYNE repo: one concept per source directory and per document, with import links already resolved.

Start at [the root index](/index.md). Open one concept. Follow `# Depends on`, `# Used by`, and `# Nested` before opening source. The language map is [PYNE map](/playbooks/pyne-map.md).

# Commands

* `bun run okf:query evaluator builtins` finds concepts by path, title, and description.
* `bun run okf:context src/pynescript/compiler` prints that concept and one-line blurbs for its neighbors.
* `bun run okf:lint` checks the bundle.
* `bun run okf:enrich` drafts and relinks the bundle from the working tree.
* `bun run okf:check` fails when the committed bundle does not match the tree.

The draft records Python and TypeScript exports, imports, the first docstring, and the first non-license comment. It does not call a model. Generated ANTLR and ASDL trees, and the Pine corpora under `tests/data` and `tests/fixtures`, are not part of the map.

# What the hook does

`.githooks/pre-commit` runs this pipeline from the git index and stages the generated bundle. Enable it once with `git config core.hooksPath .githooks` (also done by `bun install` via `prepare`). A new curated file is staged with it. An unstaged edit to a curated playbook stays unstaged. `OKF_SKIP=1` skips the refresh.
