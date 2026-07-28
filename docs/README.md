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
