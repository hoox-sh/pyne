# Documentation writing rules (PYNE + AXIS)

Source of truth for agents authoring MDX under `docs/pyne/` and `docs/axis/`.
Hosted (Phase B) at `https://hoox.sh/pyne/docs` and `https://hoox.sh/axis/docs`.

## Products

| Tree | Public base | Brand pack (hoox.sh) |
|------|-------------|----------------------|
| `docs/pyne/**` | `/pyne/docs` | volt |
| `docs/axis/**` | `/axis/docs` | void |

Never put AXIS pages under `docs/pyne/` or PYNE language theory under `docs/axis/`
beyond short cross-links.

## Links

- PYNE internal: `/pyne/docs/enduser/getting-started/installation`
- AXIS internal: `/axis/docs/plugins/contracts`
- HOOX mesh: `/docs/...`
- Cross: always include product prefix

## Frontmatter

```yaml
---
title: "Clear title"
description: "One-sentence summary for SEO and sidebar."
---
```

## Page skeleton

1. Abstract
2. Conceptual model (Mermaid welcome)
3. Interface surface
4. Internals (repo paths)
5. Invariants & edge cases
6. Worked examples
7. Failure modes
8. See also

## Voice

Academic + nerdy-cool systems prose. Precise jargon. No empty marketing
("powerful", "seamless", "cutting-edge"). Open real source; mark
`{/* TODO: verify */}` when unsure. No Sphinx directives.

## Trademark

Pine Script™ / TradingView® disclaimer once per product `index.mdx` only.
