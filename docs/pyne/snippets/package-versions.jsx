/**
 * Copyright (C) 2024-2026 jango_blockchained
 * SPDX-License-Identifier: AGPL-3.0-or-later
 *
 * Static version table. A 5-minute GitHub cron rewrites FALLBACK — no
 * browser fetches, no extra pageload.
 */

/* VERSIONS_FALLBACK_START */
const FALLBACK = {
  "hoox-pyne": "0.3.16",
  "@hoox-sh/pynets": "0.2.0",
  "hoox-sh.pyne": "0.3.16",
  "ghcr.io/hoox-sh/pyne": "0.3.14"
}
/* VERSIONS_FALLBACK_END */

const ROWS = [
  {
    key: "hoox-pyne",
    label: "hoox-pyne",
    via: "PyPI",
    href: "https://pypi.org/project/hoox-pyne/",
  },
  {
    key: "@hoox-sh/pynets",
    label: "@hoox-sh/pynets",
    via: "npm",
    href: "https://www.npmjs.com/package/@hoox-sh/pynets",
  },
  {
    key: "hoox-sh.pyne",
    label: "hoox-sh.pyne",
    via: "VS Code / Open VSX",
    href: "https://marketplace.visualstudio.com/items?itemName=hoox-sh.pyne",
  },
  {
    key: "ghcr.io/hoox-sh/pyne",
    label: "ghcr.io/hoox-sh/pyne/{api,cli,lsp}",
    via: "GHCR",
    href: "https://github.com/orgs/hoox-sh/packages?repo_name=pyne",
  },
]

export const PackageVersions = () => {
  return (
    <div className="not-prose my-4 overflow-x-auto rounded-xl border border-zinc-950/10 dark:border-white/10">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-zinc-950/10 text-left dark:border-white/10">
            <th className="px-3 py-2 font-medium">Package</th>
            <th className="px-3 py-2 font-medium">Latest</th>
            <th className="px-3 py-2 font-medium">Registry</th>
          </tr>
        </thead>
        <tbody>
          {ROWS.map((row) => (
            <tr key={row.key} className="border-b border-zinc-950/5 last:border-0 dark:border-white/5">
              <td className="px-3 py-2 font-mono">
                <a href={row.href}>{row.label}</a>
              </td>
              <td className="px-3 py-2 font-mono">{FALLBACK[row.key] || "—"}</td>
              <td className="px-3 py-2 text-zinc-950/70 dark:text-white/70">{row.via}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
