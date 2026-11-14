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

# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the

# GNU Affero General Public License for more details.

#

# You should have received a copy of the GNU Affero General Public License

# along with pynescript. If not, see <https://www.gnu.org/licenses/>.

#

# SPDX-License-Identifier: AGPL-3.0-or-later

# Documentation writing rules (PYNE + AXIS)

Source of truth for agents authoring MDX under `docs/pyne/` and `docs/axis/`.
Hosted (Phase B) at `https://hoox.sh/pyne/docs` and `https://hoox.sh/axis/docs`.

## Audience

`docs/pyne/**` and `docs/axis/**` are **public product docs** for end users and
external developers only.

Never document:

- Cost estimates, dollar amounts, monthly GCP bills, or free-tier spend planning
- Personal PyPI or GitHub accounts (e.g. `jango-blockchained` remotes)
- Trusted Publishing / API-token shipping, `PYPI_API_TOKEN`, or
  `gh secret set` for hoox-sh
- VPS / Hetzner / `deploy_vps.sh`, or machine-local paths like `/home/jango/...`

Operator and internal shipping belong in `AGENTS.md`, root `CONTRIBUTING.md`,
and `scripts/build/README.md` — not in Mintlify MDX.

Developer-facing internals (repo paths under `src/`, self-host Docker, env vars
the code reads) are in-scope.

Copyright headers with `jango_blockchained` stay (license). Public `hoox-sh/*`
GitHub orgs are fine.

## Products

| Tree           | Public base  | Brand pack (hoox.sh) |
| -------------- | ------------ | -------------------- |
| `docs/pyne/**` | `/pyne/docs` | volt                 |
| `docs/axis/**` | `/axis/docs` | void                 |

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
