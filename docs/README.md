# Copyright (C) 2024-2026 jango_blockchained
#
# This file is part of pynescript.
#
# pynescript is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pynescript is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# Documentation (PYNE + AXIS)

Self-hosted product manuals (HOOX-style MDX) for this monorepo.

| Product | Source tree | Intended public URL |
| --- | --- | --- |
| **PYNE** | [`docs/pyne/`](pyne/) | https://hoox.sh/pyne/docs |
| **AXIS** | [`docs/axis/`](axis/) | https://hoox.sh/axis/docs |

Authoring rules: [`WRITING.md`](WRITING.md).

## Layout

```
docs/
  WRITING.md          # voice, links, page skeleton
  pyne/
    docs.json         # navigation + SEO metadata
    index.mdx         # product hub
    enduser/ core/ runtime/ lsp/ api/ devops/ reference/ pine-worker/
  axis/
    docs.json
    index.mdx
    enduser/ architecture/ plugins/ ui/ worker/ devops/ reference/
```

Legacy Sphinx materials (`apidoc/`, `conf.py`, status `.md` files, `_build/`) remain
alongside these trees for historical/reference use. New product docs are MDX only.

## Host wiring (`hoox-landing-page`)

Live site: **https://hoox.sh/pyne/docs** and **https://hoox.sh/axis/docs**.

In the landing repo:

```bash
# refresh content from this monorepo (sibling path or PYNESCRIPT_ROOT)
pnpm run sync:docs
# full site build (prebuild runs sync + HOOX exports)
pnpm run build
```

- Source of truth: `pynescript/docs/{pyne,axis}`
- Published copy: `hoox-landing-page/content/{pyne-docs,axis-docs}`
- PDFs / agent packs: `public/exports/`, `public/{pyne,axis}/docs/llm.txt`
- MDX is sanitized on sync for Next MDX brace rules

## Exports (PDF + LLM packs)

HOOX-style auto-generation (DIN A4 track manuals + agent files):

```bash
bun run docs:exports          # PDFs + llm.txt + llms.txt for PYNE and AXIS
bun run docs:exports:agents   # llm.txt / llms.txt only
bun run docs:exports:pdfs     # PDFs only
bun run docs:exports:pyne     # one product
bun run docs:exports:axis
bun run docs:versions           # PyPI / npm / Open VSX / GitHub release → versions.json
```

| Artifact | Location |
| --- | --- |
| Track PDFs | [`exports/`](exports/) e.g. `pyne-enduser-manual.pdf`, `axis-plugins-manual.pdf` |
| Full-corpus LLM pack | [`pyne/llm.txt`](pyne/llm.txt), [`axis/llm.txt`](axis/llm.txt) |
| LLM site map | [`pyne/llms.txt`](pyne/llms.txt), [`axis/llms.txt`](axis/llms.txt) |
| Manifest | [`exports/manifest.json`](exports/manifest.json) |

Requires Chromium for PDFs (`/usr/bin/chromium` or `CHROME_PATH`). Intermediate HTML lands in `.cache/docs-exports/` (gitignored).

## Quick open

- PYNE hub: [`pyne/index.mdx`](pyne/index.mdx)
- AXIS hub: [`axis/index.mdx`](axis/index.mdx)
