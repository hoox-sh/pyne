#!/usr/bin/env node
/**
 * Copyright (C) 2024-2026 jango_blockchained
 * SPDX-License-Identifier: AGPL-3.0-or-later
 *
 * Fetch published package versions and write docs/pyne/versions.json.
 * Also rewrites the FALLBACK object in docs/pyne/snippets/package-versions.jsx
 * so Mintlify pages stay current without hand-editing stamps.
 *
 *   node scripts/docs/fetch_versions.mjs
 *   bun run docs:versions
 */
import { readFile, writeFile } from "node:fs/promises"
import path from "node:path"
import { fileURLToPath } from "node:url"

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..")
const OUT_JSON = path.join(ROOT, "docs/pyne/versions.json")
const SNIPPET = path.join(ROOT, "docs/pyne/snippets/package-versions.jsx")

const START = "/* VERSIONS_FALLBACK_START */"
const END = "/* VERSIONS_FALLBACK_END */"

async function getJson(url, init = {}) {
  const res = await fetch(url, {
    headers: { Accept: "application/json", ...init.headers },
    ...init,
  })
  if (!res.ok) {
    throw new Error(`${url} → ${res.status}`)
  }
  return res.json()
}

function stripV(tag) {
  if (typeof tag !== "string") return null
  return tag.startsWith("v") ? tag.slice(1) : tag
}

async function one(label, fn) {
  try {
    return { ok: true, value: await fn() }
  } catch (err) {
    console.warn(`!! ${label}: ${err instanceof Error ? err.message : err}`)
    return { ok: false, value: null }
  }
}

async function fetchAll() {
  const pypi = await one("pypi hoox-pyne", async () => {
    const j = await getJson("https://pypi.org/pypi/hoox-pyne/json")
    return String(j.info.version)
  })
  const npm = await one("npm @hoox-sh/pynets", async () => {
    const j = await getJson("https://registry.npmjs.org/@hoox-sh/pynets/latest")
    return String(j.version)
  })
  const release = await one("github release hoox-sh/pyne", async () => {
    const j = await getJson("https://api.github.com/repos/hoox-sh/pyne/releases/latest", {
      headers: { "User-Agent": "hoox-pyne-docs-versions" },
    })
    return stripV(j.tag_name)
  })
  const vsix = await one("open-vsx hoox-sh.pyne", async () => {
    const j = await getJson("https://open-vsx.org/api/hoox-sh/pyne")
    return String(j.version)
  })
  return {
    fetched_at: new Date().toISOString(),
    packages: {
      "hoox-pyne": pypi.value,
      "@hoox-sh/pynets": npm.value,
      "hoox-sh.pyne": vsix.value,
      "ghcr.io/hoox-sh/pyne": release.value,
    },
    sources: {
      pypi: "https://pypi.org/pypi/hoox-pyne/json",
      npm: "https://registry.npmjs.org/@hoox-sh/pynets/latest",
      github_release: "https://api.github.com/repos/hoox-sh/pyne/releases/latest",
      openvsx: "https://open-vsx.org/api/hoox-sh/pyne",
    },
  }
}

function fallbackLiteral(packages) {
  const body = Object.entries(packages)
    .map(([k, v]) => `  ${JSON.stringify(k)}: ${JSON.stringify(v)}`)
    .join(",\n")
  return `${START}\nconst FALLBACK = {\n${body}\n}\n${END}`
}

async function patchSnippet(packages) {
  let src
  try {
    src = await readFile(SNIPPET, "utf8")
  } catch {
    return false
  }
  const i = src.indexOf(START)
  const j = src.indexOf(END)
  if (i < 0 || j < 0 || j <= i) {
    console.warn("!! snippet missing FALLBACK markers; skip rewrite")
    return false
  }
  const next = src.slice(0, i) + fallbackLiteral(packages) + src.slice(j + END.length)
  if (next === src) return false
  await writeFile(SNIPPET, next)
  return true
}

function publicPackages(payload) {
  return Object.fromEntries(
    Object.entries(payload.packages).filter(([, v]) => typeof v === "string" && v.length > 0),
  )
}

async function main() {
  const payload = await fetchAll()
  const pkgs = publicPackages(payload)
  if (Object.keys(pkgs).length === 0) {
    console.error("no versions fetched")
    process.exit(1)
  }
  payload.packages = {
    "hoox-pyne": pkgs["hoox-pyne"] ?? null,
    "@hoox-sh/pynets": pkgs["@hoox-sh/pynets"] ?? null,
    "hoox-sh.pyne": pkgs["hoox-sh.pyne"] ?? null,
    "ghcr.io/hoox-sh/pyne": pkgs["ghcr.io/hoox-sh/pyne"] ?? null,
  }
  const json = `${JSON.stringify(payload, null, 2)}\n`
  let prev = ""
  try {
    prev = await readFile(OUT_JSON, "utf8")
  } catch {
    prev = ""
  }
  const jsonChanged = json !== prev
  if (jsonChanged) {
    await writeFile(OUT_JSON, json)
  }
  const snippetChanged = await patchSnippet(payload.packages)
  console.log(JSON.stringify(payload.packages, null, 2))
  console.log(`json ${jsonChanged ? "updated" : "unchanged"}  snippet ${snippetChanged ? "updated" : "unchanged"}`)
  if (!jsonChanged && !snippetChanged) {
    process.exit(0)
  }
}

await main()
