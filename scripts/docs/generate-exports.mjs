#!/usr/bin/env node
/**
 * Copyright (c) 2026 HOOX · PYNE · jango-blockchained
 * SPDX-License-Identifier: AGPL-3.0-or-later
 */
/**
 * PYNE + AXIS documentation export pipeline (HOOX-style)
 *
 * Generates per product:
 *   1. Track manuals as DIN A4 PDFs → docs/exports/{product}-*-manual.pdf
 *   2. llms.txt  — machine-readable site map (llmstxt.org)
 *   3. llm.txt   — minified full-corpus text for LLM context windows
 *   4. manifest.json under docs/exports/
 *
 * Usage:
 *   node scripts/docs/generate-exports.mjs
 *   node scripts/docs/generate-exports.mjs --only=pyne
 *   node scripts/docs/generate-exports.mjs --only=axis
 *   node scripts/docs/generate-exports.mjs --only=agents
 *   node scripts/docs/generate-exports.mjs --only=pdfs
 *   node scripts/docs/generate-exports.mjs --product=pyne --only=enduser
 *   node scripts/docs/generate-exports.mjs --skip-pdf
 *
 * Requires Chromium for PDFs (/usr/bin/chromium or CHROME_PATH).
 * Wired as: bun run docs:exports
 */

import { createRequire } from "node:module"
import { execFile } from "node:child_process"
import { promisify } from "node:util"
import {
  mkdir,
  readFile,
  writeFile,
  readdir,
  unlink,
  copyFile,
} from "node:fs/promises"
import { existsSync, readFileSync } from "node:fs"
import path from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"

const execFileAsync = promisify(execFile)

const require = createRequire(import.meta.url)
const matter = require("gray-matter")
const { marked } = require("marked")

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(__dirname, "../..")
const DOCS = path.join(ROOT, "docs")
const OUT_DIR = path.join(DOCS, "exports")
const CACHE = path.join(ROOT, ".cache", "docs-exports")
const BRAND = path.join(DOCS, "assets", "brand")
const SITE = "https://hoox.sh"
const REPO = "https://github.com/hoox-sh/pyne"

const args = process.argv.slice(2)
const onlyArg = args.find((a) => a.startsWith("--only="))?.split("=")[1] ?? "all"
const productArg = args.find((a) => a.startsWith("--product="))?.split("=")[1] ?? null
const SKIP_PDF = args.includes("--skip-pdf")

/** data: URIs for HOOX logos (light = white mark for dark cover; dark = black mark for paper). */
function loadLogoDataUri(filename) {
  const candidates = [
    path.join(BRAND, filename),
    path.join(ROOT, "docs/assets/brand", filename),
    // sibling landing repo brand pack
    path.resolve(ROOT, "../hoox-landing-page/public/brand", filename),
    path.resolve("/home/jango/Git/hoox-landing-page/public/brand", filename),
  ]
  for (const p of candidates) {
    if (existsSync(p)) {
      const buf = readFileSync(p)
      return `data:image/svg+xml;base64,${buf.toString("base64")}`
    }
  }
  return null
}

const LOGO_LIGHT = loadLogoDataUri("hoox-logo-light.svg")
const LOGO_DARK = loadLogoDataUri("hoox-logo-dark.svg")

// ── Resolve product docs roots ──────────────────────────────────────────────
// AXIS MDX lives in the sister `axis` repo; `docs/axis` here is only a stub
// README pointing there. Prefer AXIS_DOCS, then sibling ../axis/docs, then the
// local stub if it ever gains a real docs.json.

function resolveAxisDocsRoot() {
  const candidates = [
    process.env.AXIS_DOCS,
    path.resolve(ROOT, "../axis/docs"),
    path.resolve(ROOT, "../../axis/docs"),
    "/home/jango/Git/axis/docs",
    path.join(DOCS, "axis"),
  ].filter(Boolean)
  for (const c of candidates) {
    if (existsSync(path.join(c, "docs.json"))) return c
  }
  return path.join(DOCS, "axis")
}

const AXIS_DOCS_ROOT = resolveAxisDocsRoot()

// ── Product definitions ─────────────────────────────────────────────────────

const PRODUCTS = {
  pyne: {
    id: "pyne",
    name: "PYNE",
    tagline: "Open-source Pine Script evaluation framework",
    blurb:
      "Grammar-driven parser, ASDL AST, bar-loop evaluator, LSP, Pro API, and edge workers. Self-host the runtime.",
    docsRoot: path.join(DOCS, "pyne"),
    publicBase: "/pyne/docs",
    publicUrl: `${SITE}/pyne/docs`,
    repoPath: "docs/pyne",
    accent: "#A3E635",
    accentDark: "#65A30D",
    brandPack: "volt",
    marketing: `${SITE}/pyne`,
    manuals: {
      enduser: {
        id: "enduser",
        title: "End User Manual",
        subtitle: "Install, CLI, library API, editors, and Pro API as a consumer",
        filename: "pyne-enduser-manual.pdf",
        audience: "Script authors · Library consumers · Editor users",
        tabMatch: /end\s*user/i,
        pathPrefixes: ["enduser/", "index"],
        includeProductIndex: true,
      },
      core: {
        id: "core",
        title: "Language Core Manual",
        subtitle: "ANTLR4 grammar, ASDL AST, builder, unparser, type system, linter",
        filename: "pyne-core-manual.pdf",
        audience: "Language implementers · Contributors",
        tabMatch: /^core$/i,
        pathPrefixes: ["core/"],
      },
      runtime: {
        id: "runtime",
        title: "Runtime Manual",
        subtitle: "Evaluator, series model, builtins, strategy, compiler",
        filename: "pyne-runtime-manual.pdf",
        audience: "Runtime engineers · Strategy authors",
        tabMatch: /runtime/i,
        pathPrefixes: ["runtime/"],
      },
      lsp: {
        id: "lsp",
        title: "Language Server Manual",
        subtitle: "LSP features, builtin metadata, VS Code, editor clients",
        filename: "pyne-lsp-manual.pdf",
        audience: "Editor integrators · IDE authors",
        tabMatch: /^lsp$/i,
        pathPrefixes: ["lsp/"],
      },
      api: {
        id: "api",
        title: "Pro API Manual",
        subtitle: "Flask Pro API, auth, /run contract, preview, backtest",
        filename: "pyne-api-manual.pdf",
        audience: "API clients · Backend operators",
        tabMatch: /^api$/i,
        pathPrefixes: ["api/"],
      },
      devops: {
        id: "devops",
        title: "DevOps Manual",
        subtitle: "CI, Docker, Nuitka, metadata crypto, GCP, security",
        filename: "pyne-devops-manual.pdf",
        audience: "Platform engineers · Release operators",
        tabMatch: /devops/i,
        pathPrefixes: ["devops/"],
      },
      reference: {
        id: "reference",
        title: "Reference Manual",
        subtitle: "Compatibility, status, gaps, numerical validation, pine-worker",
        filename: "pyne-reference-manual.pdf",
        audience: "Auditors · Contributors · Parity hunters",
        tabMatch: /reference/i,
        pathPrefixes: ["reference/", "pine-worker/", "contributing"],
      },
    },
  },
  axis: {
    id: "axis",
    name: "AXIS",
    tagline: "Open charting PWA — own the axes, swap the engine",
    blurb:
      "Installable AXIS for price and time. Orthogonal plugins: sources, streams, engines, storage. Full Pine surface via PYNE.",
    docsRoot: AXIS_DOCS_ROOT,
    publicBase: "/axis/docs",
    publicUrl: `${SITE}/axis/docs`,
    repoPath: path.relative(ROOT, AXIS_DOCS_ROOT).replace(/\\/g, "/") || "docs/axis",
    accent: "#A78BFA",
    accentDark: "#7C3AED",
    brandPack: "void",
    marketing: `${SITE}/axis`,
    manuals: {
      enduser: {
        id: "enduser",
        title: "End User Manual",
        subtitle: "Install the PWA, compose plugins, research workflows",
        filename: "axis-enduser-manual.pdf",
        audience: "Traders · Researchers · Self-hosters",
        tabMatch: /end\s*user/i,
        pathPrefixes: ["enduser/", "index"],
        includeProductIndex: true,
      },
      architecture: {
        id: "architecture",
        title: "Architecture Manual",
        subtitle: "ADRs, topologies, state namespaces, AXIS ≠ engine",
        filename: "axis-architecture-manual.pdf",
        audience: "Systems engineers · Contributors",
        tabMatch: /architecture/i,
        pathPrefixes: ["architecture/"],
      },
      plugins: {
        id: "plugins",
        title: "Plugins Manual",
        subtitle: "Contracts, registry, sources, streams, engines, storage",
        filename: "axis-plugins-manual.pdf",
        audience: "Plugin authors · Integrators",
        tabMatch: /plugins?/i,
        pathPrefixes: ["plugins/"],
      },
      ui: {
        id: "ui",
        title: "UI Manual",
        subtitle: "Chart, editor, UI shell, indicators, results, store",
        filename: "axis-ui-manual.pdf",
        audience: "Frontend engineers · UX contributors",
        tabMatch: /^ui$/i,
        pathPrefixes: ["ui/"],
      },
      worker: {
        id: "worker",
        title: "Worker Manual",
        subtitle: "Cloudflare Worker, Durable Objects, KV, D1, R2, auth",
        filename: "axis-worker-manual.pdf",
        audience: "Edge operators · Worker authors",
        tabMatch: /worker/i,
        pathPrefixes: ["worker/"],
      },
      devops: {
        id: "devops",
        title: "DevOps Manual",
        subtitle: "Local dev, build/serve, Cloudflare, VPS, CORS, CI",
        filename: "axis-devops-manual.pdf",
        audience: "Platform engineers · Deployers",
        tabMatch: /devops/i,
        pathPrefixes: ["devops/"],
      },
      reference: {
        id: "reference",
        title: "Reference Manual",
        subtitle: "Feature atlas, legacy shell, testing, plugin examples",
        filename: "axis-reference-manual.pdf",
        audience: "Auditors · QA · Contributors",
        tabMatch: /reference/i,
        pathPrefixes: ["reference/"],
      },
    },
  },
}

// ── CLI plan ────────────────────────────────────────────────────────────────

function productsToRun() {
  if (productArg) {
    if (!PRODUCTS[productArg]) {
      throw new Error(`Unknown --product=${productArg} (pyne|axis)`)
    }
    return [productArg]
  }
  if (onlyArg === "pyne" || onlyArg === "axis") return [onlyArg]
  return ["pyne", "axis"]
}

function planForProduct(productId) {
  const product = PRODUCTS[productId]
  const manualIds = Object.keys(product.manuals)

  switch (onlyArg) {
    case "agents":
      return { manuals: [], agents: true }
    case "pdfs":
      return { manuals: manualIds, agents: false }
    case "pyne":
    case "axis":
    case "all":
      return { manuals: manualIds, agents: true }
    default:
      // track id for a single product
      if (product.manuals[onlyArg]) {
        return { manuals: [onlyArg], agents: false }
      }
      return { manuals: manualIds, agents: true }
  }
}

// ── Docs JSON / filesystem ──────────────────────────────────────────────────

function flattenPages(pages, out = []) {
  for (const p of pages) {
    if (typeof p === "string") out.push(p)
    else if (p?.pages) flattenPages(p.pages, out)
  }
  return out
}

function loadDocsJson(docsRoot) {
  return JSON.parse(
    require("fs").readFileSync(path.join(docsRoot, "docs.json"), "utf8"),
  )
}

function pagesForManual(product, manual, docsJson) {
  const tabs = docsJson.navigation?.tabs ?? []
  const tab = tabs.find((t) => manual.tabMatch.test(String(t.tab ?? "")))
  let pages = []
  if (tab?.groups?.length) {
    for (const g of tab.groups) flattenPages(g.pages ?? [], pages)
  }

  pages = pages.filter((p) => {
    if (manual.includeProductIndex && (p === "index" || p === "docs/index")) {
      return true
    }
    return manual.pathPrefixes.some((pref) => {
      if (pref.endsWith("/")) return p === pref.slice(0, -1) || p.startsWith(pref)
      return p === pref || p.startsWith(pref + "/")
    })
  })

  // Deduplicate while preserving order
  const seen = new Set()
  pages = pages.filter((p) => {
    if (seen.has(p)) return false
    seen.add(p)
    return true
  })

  if (pages.length) return pages

  // Fallback: walk filesystem under prefixes
  return null
}

async function walkMdx(dir, acc = []) {
  let entries
  try {
    entries = await readdir(dir, { withFileTypes: true })
  } catch {
    return acc
  }
  for (const e of entries) {
    const full = path.join(dir, e.name)
    if (e.isDirectory()) await walkMdx(full, acc)
    else if (e.name.endsWith(".mdx") || e.name.endsWith(".md")) acc.push(full)
  }
  return acc
}

function pageKeyToFile(docsRoot, pageKey) {
  const rel = pageKey.replace(/^docs\//, "")
  const base = path.join(docsRoot, rel)
  for (const ext of [".mdx", ".md"]) {
    if (existsSync(base + ext)) return base + ext
  }
  if (existsSync(path.join(base, "index.mdx"))) return path.join(base, "index.mdx")
  if (rel === "index" && existsSync(path.join(docsRoot, "index.mdx"))) {
    return path.join(docsRoot, "index.mdx")
  }
  return null
}

async function resolvePageKeys(product, manual, docsJson) {
  let pageKeys = pagesForManual(product, manual, docsJson)
  if (pageKeys?.length) return pageKeys

  const keys = []
  for (const pref of manual.pathPrefixes) {
    if (pref === "index") {
      if (existsSync(path.join(product.docsRoot, "index.mdx"))) keys.push("index")
      continue
    }
    const dir = path.join(
      product.docsRoot,
      pref.endsWith("/") ? pref.slice(0, -1) : pref,
    )
    if (pref.endsWith("/") || existsSync(dir + ".mdx") === false) {
      if (existsSync(dir) && require("fs").statSync(dir).isDirectory()) {
        const files = await walkMdx(dir)
        for (const f of files) {
          const rel = path.relative(product.docsRoot, f).replace(/\\/g, "/")
          keys.push(rel.replace(/\.mdx?$/, ""))
        }
      } else if (existsSync(dir + ".mdx")) {
        keys.push(pref.replace(/\/$/, ""))
      }
    } else if (existsSync(path.join(product.docsRoot, pref + ".mdx"))) {
      keys.push(pref)
    }
  }
  return [...new Set(keys)].sort()
}

// ── MDX transforms ──────────────────────────────────────────────────────────

function mdxToMarkdown(raw, product) {
  const { data, content } = matter(raw)
  let body = content
    .replace(/^import\s+.+;?\s*$/gm, "")
    .replace(/^export\s+.+;?\s*$/gm, "")
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, "")
    .replace(/<([A-Z][A-Za-z0-9.]*)[^>]*\/>/g, "")
    .replace(/<([A-Z][A-Za-z0-9.]*)[^>]*>[\s\S]*?<\/\1>/g, (m) =>
      m.replace(/<[^>]+>/g, ""),
    )
    .replace(/<(?:br|hr)\s*\/?>/gi, "\n\n")
    .replace(/\]\((?!https?:|\/|#|mailto:)([^)]+)\)/g, (m, p1) => {
      const clean = p1.replace(/^\.\//, "").replace(/\.mdx?$/, "")
      return `](${SITE}${product.publicBase}/${clean})`
    })
    .replace(/\n{3,}/g, "\n\n")
    .trim()

  return {
    title: data.title || null,
    description: data.description || null,
    body,
  }
}

function titleFromKey(pageKey) {
  const last = pageKey.replace(/^docs\//, "").split("/").pop()
  if (last === "index") return "Overview"
  return last
    .split("-")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ")
}

function pageKeyToHref(product, pageKey) {
  if (pageKey === "index" || pageKey === "docs/index") return product.publicBase
  const without = pageKey.replace(/^docs\//, "")
  if (without.endsWith("/index")) {
    const base = without.replace(/\/index$/, "")
    return base ? `${product.publicBase}/${base}` : product.publicBase
  }
  return `${product.publicBase}/${without}`
}

/** Minified full-corpus text (hoox-setup llm.txt style). */
function minifyLlmText(content) {
  let text = content.replace(/^---[\s\S]*?---/, "")
  text = text.replace(/```mermaid[\s\S]*?```/g, "")
  text = text.replace(/\{\/\*[\s\S]*?\*\/\}/g, "")
  text = text.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
  text = text.replace(/<svg[\s\S]*?<\/svg>/g, "")
  text = text.replace(/<[^>]+>/g, "")
  text = text.replace(/^#+\s+/gm, "")
  text = text.replace(/\*\*([^*]+)\*\*/g, "$1")
  text = text.replace(/\*([^*]+)\*/g, "$1")
  text = text.replace(/__([^_]+)__/g, "$1")
  text = text.replace(/_([^_]+)_/g, "$1")
  text = text.replace(/`([^`]+)`/g, "$1")
  text = text.replace(/^\s*[-*+]\s+/gm, "")
  text = text.replace(/^\s*>\s+/gm, "")
  text = text.replace(/```[a-zA-Z0-9]*\n([\s\S]*?)```/g, "$1")
  try {
    text = text.replace(/\p{Emoji}/gu, "")
  } catch {
    /* ignore if unicode props unavailable */
  }
  const compressedLines = text
    .split("\n")
    .map((line) => line.trim().replace(/\s+/g, " "))
    .filter((line) => line.length > 0)
  return compressedLines.join("\n")
}

// ── Print CSS (product-accent) ──────────────────────────────────────────────

function printCss(accent) {
  return `
@page { size: A4; margin: 16mm 14mm 18mm 14mm; }
@page :first { margin: 0; }
* { box-sizing: border-box; }
html, body {
  margin: 0; padding: 0;
  font-family: "IBM Plex Sans", "Segoe UI", system-ui, sans-serif;
  font-size: 10pt; line-height: 1.55; color: #1a1a1a; background: #fff;
  -webkit-print-color-adjust: exact; print-color-adjust: exact;
}
/* Cover — full-bleed dark plate (no Playwright chrome on page 1; see htmlToPdf) */
.cover {
  page-break-after: always;
  /* Exactly one A4 portrait frame when @page :first has margin 0 */
  width: 210mm; min-height: 297mm; height: 297mm;
  padding: 22mm 20mm 18mm;
  box-sizing: border-box;
  display: flex; flex-direction: column;
  background: #0c0c0c; color: #f2f2f2;
  position: relative; overflow: hidden;
}
.cover-brand-row {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 16px; flex-shrink: 0;
}
.cover-top {
  display: flex; align-items: center; gap: 10px;
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 9pt; letter-spacing: 0.28em; text-transform: uppercase;
  color: ${accent};
  max-width: 70%;
}
.cover-logo {
  /* Top-right of the cover plate — white mark on dark */
  width: 36mm; height: auto; max-height: 32mm;
  object-fit: contain; object-position: top right;
  flex-shrink: 0; opacity: 0.98;
  /* Avoid SVG preserveAspectRatio=none distorting the mark */
  image-rendering: auto;
}
.cover-dot { width: 6px; height: 6px; background: ${accent}; border-radius: 50%; flex-shrink: 0; }
.cover-mid {
  flex: 1 1 auto;
  display: flex; flex-direction: column; justify-content: center;
  margin: 0; padding: 12mm 0 18mm;
  min-height: 0;
}
.cover-kicker {
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 8.5pt; letter-spacing: 0.22em; text-transform: uppercase;
  color: #888; margin-bottom: 14px;
}
.cover h1 {
  font-family: "Bebas Neue", "Arial Narrow", Impact, sans-serif;
  font-weight: 400; font-size: 42pt; line-height: 0.95;
  letter-spacing: 0.02em; margin: 0 0 12px; color: #fff;
  max-width: 160mm;
}
.cover-rule { width: 48px; height: 2px; background: ${accent}; margin: 14px 0 18px; }
.cover-sub { max-width: 420px; font-size: 11pt; line-height: 1.5; color: #b5b5b5; margin: 0; }
.cover-tagline {
  max-width: 420px; font-size: 9.5pt; line-height: 1.45; color: #777;
  margin: 14px 0 0; font-family: "IBM Plex Sans", system-ui, sans-serif;
}
.cover-foot {
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 8pt; letter-spacing: 0.12em; text-transform: uppercase;
  color: #666; border-top: 1px solid #2a2a2a; padding-top: 14px;
  display: flex; justify-content: space-between; gap: 16px; flex-shrink: 0;
  flex-wrap: wrap;
}
.toc { page-break-after: always; padding-top: 2mm; }
.toc h2 {
  font-family: "Bebas Neue", "Arial Narrow", Impact, sans-serif;
  font-size: 22pt; font-weight: 400; letter-spacing: 0.04em; margin: 0 0 12px;
}
.toc ol { list-style: none; padding: 0; margin: 0; }
.toc li {
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 8.5pt; padding: 5px 0; border-bottom: 1px solid #eee;
  display: flex; justify-content: space-between; gap: 12px;
}
.toc .num { color: ${accent}; margin-right: 8px; }
.toc .t { color: #222; flex: 1; }
.chapter { page-break-before: always; }
.chapter:first-of-type { page-break-before: auto; }
.chapter-head { border-bottom: 1px solid #e8e8e8; padding-bottom: 10px; margin-bottom: 16px; }
.chapter-meta {
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 8pt; letter-spacing: 0.2em; text-transform: uppercase;
  color: ${accent}; margin-bottom: 6px;
}
.chapter h1 {
  font-family: "Bebas Neue", "Arial Narrow", Impact, sans-serif;
  font-size: 22pt; font-weight: 400; letter-spacing: 0.03em; margin: 0; line-height: 1.05;
}
.chapter .desc { margin: 8px 0 0; color: #555; font-size: 9.5pt; }
.content h2 { font-size: 13pt; margin: 1.4em 0 0.5em; page-break-after: avoid; }
.content h3 { font-size: 11pt; margin: 1.2em 0 0.4em; page-break-after: avoid; }
.content h4 { font-size: 10pt; margin: 1em 0 0.35em; color: #333; }
.content p { margin: 0.55em 0; orphans: 3; widows: 3; }
.content ul, .content ol { margin: 0.5em 0; padding-left: 1.25em; }
.content li { margin: 0.25em 0; }
.content blockquote {
  margin: 0.9em 0; padding: 8px 14px; border-left: 2px solid ${accent};
  background: #f7f7f7; color: #333;
}
/* Inline code — soft grey chip */
.content code {
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 8.5pt;
  background: #eceff1;
  color: #263238;
  padding: 0.12em 0.35em;
  border-radius: 2px;
}
/* Fenced code — light grey plate (no black terminal look) */
.content pre {
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 7.8pt; line-height: 1.45;
  background: #eceff1;
  color: #1a1a1a;
  padding: 12px 14px;
  overflow-x: auto;
  page-break-inside: avoid;
  border: 1px solid #d0d5d9;
  border-left: 3px solid ${accent};
  border-radius: 2px;
}
.content pre code {
  background: transparent;
  color: inherit;
  padding: 0;
  border-radius: 0;
}
.content table {
  width: 100%; border-collapse: collapse; font-size: 8.5pt;
  margin: 0.8em 0; page-break-inside: avoid;
}
.content th, .content td {
  border: 1px solid #ddd; padding: 5px 7px; text-align: left; vertical-align: top;
}
.content th { background: #f0f2f4; font-weight: 600; }
.content a { color: ${accentDark(accent)}; text-decoration: none; }
.content hr { border: none; border-top: 1px solid #e5e5e5; margin: 1.4em 0; }
`
}

function accentDark(accent) {
  if (accent === "#A3E635") return "#4d7c0f"
  if (accent === "#A78BFA") return "#6d28d9"
  if (accent === "#F97316") return "#c2410c"
  return "#333"
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
}

function wrapHtml({ product, title, subtitle, audience, chapters, dateIso }) {
  const tocItems = chapters
    .map(
      (c, i) =>
        `<li><span><span class="num">${String(i + 1).padStart(2, "0")}</span><span class="t">${escapeHtml(c.title)}</span></span></li>`,
    )
    .join("\n")

  const body = chapters
    .map((c, i) => {
      const num = String(i + 1).padStart(2, "0")
      return `
<section class="chapter">
  <header class="chapter-head">
    <div class="chapter-meta">${num} · ${escapeHtml(c.section || "Chapter")}</div>
    <h1>${escapeHtml(c.title)}</h1>
    ${c.description ? `<p class="desc">${escapeHtml(c.description)}</p>` : ""}
  </header>
  <div class="content">${c.html}</div>
</section>`
    })
    .join("\n")

  const coverLogo = LOGO_LIGHT
    ? `<img class="cover-logo" src="${LOGO_LIGHT}" alt="HOOX" />`
    : ""
  const tagline = product.tagline
    ? `<p class="cover-tagline">${escapeHtml(product.tagline)}</p>`
    : ""

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>${escapeHtml(title)} — ${escapeHtml(product.name)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet" />
<style>${printCss(product.accent)}</style>
</head>
<body>
  <section class="cover">
    <div class="cover-brand-row">
      <div class="cover-top">
        <span class="cover-dot"></span>
        <span>HOOX · ${escapeHtml(product.name)} · Documentation</span>
      </div>
      ${coverLogo}
    </div>
    <div class="cover-mid">
      <div class="cover-kicker">${escapeHtml(audience)}</div>
      <h1>${escapeHtml(title)}</h1>
      <div class="cover-rule"></div>
      <p class="cover-sub">${escapeHtml(subtitle)}</p>
      ${tagline}
    </div>
    <div class="cover-foot">
      <span>${escapeHtml(dateIso)}</span>
      <span>DIN A4 · ${escapeHtml(product.publicUrl)}</span>
      <span>Open Source</span>
    </div>
  </section>

  <section class="toc">
    <h2>Contents</h2>
    <ol>${tocItems}</ol>
  </section>

  ${body}
</body>
</html>`
}

// ── Playwright PDF (logo header + page numbers) ─────────────────────────────

function findChrome() {
  if (process.env.CHROME_PATH && existsSync(process.env.CHROME_PATH)) {
    return process.env.CHROME_PATH
  }
  for (const p of [
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/snap/bin/chromium",
  ]) {
    if (existsSync(p)) return p
  }
  return null
}

async function loadPlaywright() {
  const candidates = [
    path.join(ROOT, "../axis/node_modules/playwright-core/index.js"),
    path.join(ROOT, "node_modules/playwright-core/index.js"),
    path.join(ROOT, "node_modules/playwright-core/index.js"),
    path.resolve("/home/jango/Git/axis/node_modules/playwright-core/index.js"),
  ]
  for (const p of candidates) {
    if (existsSync(p)) {
      return import(pathToFileURL(p).href)
    }
  }
  throw new Error(
    "playwright-core not found (expected under ../axis/node_modules or root). Install axis deps for PDF exports.",
  )
}

/** Playwright header: small HOOX mark, top-right of every page. */
function headerTemplate() {
  const logo = LOGO_DARK
    ? `<img src="${LOGO_DARK}" style="height:11px;width:auto;display:block;opacity:0.85;" />`
    : `<span style="font-family:monospace;font-size:8px;color:#666;">HOOX</span>`
  return `<div style="width:100%;box-sizing:border-box;padding:0 14mm;display:flex;justify-content:flex-end;align-items:center;font-size:8px;">${logo}</div>`
}

/** Playwright footer: centered page number. */
function footerTemplate() {
  return `<div style="width:100%;box-sizing:border-box;padding:0 14mm;display:flex;justify-content:center;align-items:center;font-family:'IBM Plex Mono',ui-monospace,monospace;font-size:8px;color:#6b7280;letter-spacing:0.08em;">
    <span class="pageNumber"></span>
    <span style="margin:0 4px;opacity:0.5;">/</span>
    <span class="totalPages"></span>
  </div>`
}

/**
 * Render HTML → PDF with a clean full-bleed cover.
 *
 * Playwright applies header/footer to *every* page, which polluted the dark
 * cover (stray logo mark + ``1 / N``). We render:
 *   1) full document with running logo + page numbers
 *   2) page 1 only, no chrome, zero margins (true full-bleed cover)
 * then stitch cover + body (pages 2–end) with qpdf.
 */
async function htmlToPdf(htmlPath, pdfPath) {
  const chrome = findChrome()
  if (!chrome) {
    throw new Error(
      "No Chromium/Chrome found. Install chromium or set CHROME_PATH.",
    )
  }
  await mkdir(path.dirname(pdfPath), { recursive: true })
  const pw = await loadPlaywright()
  const chromium = pw.chromium ?? pw.default?.chromium
  if (!chromium?.launch) {
    throw new Error("playwright-core loaded but chromium.launch is unavailable")
  }
  const browser = await chromium.launch({
    executablePath: chrome,
    headless: true,
    args: ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
  })
  const tmpFull = `${pdfPath}.full.tmp.pdf`
  const tmpCover = `${pdfPath}.cover.tmp.pdf`
  const tmpBody = `${pdfPath}.body.tmp.pdf`
  try {
    const page = await browser.newPage()
    await page.goto(pathToFileURL(htmlPath).href, {
      waitUntil: "networkidle",
      timeout: 120_000,
    })
    // Give webfonts a beat
    await new Promise((r) => setTimeout(r, 500))

    const contentMargins = {
      top: "16mm",
      bottom: "14mm",
      left: "14mm",
      right: "14mm",
    }

    // Full doc with chrome (page numbers / running logo on body pages)
    await page.pdf({
      path: tmpFull,
      format: "A4",
      printBackground: true,
      preferCSSPageSize: false,
      displayHeaderFooter: true,
      headerTemplate: headerTemplate(),
      footerTemplate: footerTemplate(),
      margin: contentMargins,
    })

    // Cover only: no header/footer, zero margin so the dark plate is full-bleed
    await page.pdf({
      path: tmpCover,
      format: "A4",
      printBackground: true,
      preferCSSPageSize: false,
      displayHeaderFooter: false,
      pageRanges: "1",
      margin: { top: "0", bottom: "0", left: "0", right: "0" },
    })

    // Body = pages 2–end of the chrome PDF (if any)
    let pageCount = 1
    try {
      const { stdout } = await execFileAsync("qpdf", ["--show-npages", tmpFull], {
        timeout: 30_000,
      })
      pageCount = Math.max(1, parseInt(String(stdout).trim(), 10) || 1)
    } catch {
      pageCount = 1
    }

    if (pageCount <= 1) {
      // Single-page manual (cover only)
      await copyFile(tmpCover, pdfPath)
    } else if (existsSync("/usr/bin/qpdf")) {
      await execFileAsync(
        "qpdf",
        ["--empty", "--pages", tmpFull, "2-z", "--", tmpBody],
        { timeout: 60_000 },
      )
      await execFileAsync(
        "qpdf",
        ["--empty", "--pages", tmpCover, "1", tmpBody, "1-z", "--", pdfPath],
        { timeout: 60_000 },
      )
    } else {
      console.warn(
        "  WARN: qpdf missing — cover may still show page chrome",
      )
      await copyFile(tmpFull, pdfPath)
    }
  } finally {
    await browser.close()
    for (const p of [tmpFull, tmpCover, tmpBody]) {
      try {
        if (existsSync(p)) await unlink(p)
      } catch {
        /* ignore */
      }
    }
  }
}

// ── Manual build ────────────────────────────────────────────────────────────

async function buildManual(product, manual, docsJson) {
  console.log(`\n→ [${product.name}] Manual: ${manual.title}`)
  const pageKeys = await resolvePageKeys(product, manual, docsJson)
  const chapters = []

  for (const key of pageKeys) {
    const file = pageKeyToFile(product.docsRoot, key)
    if (!file) {
      console.warn(`  skip missing: ${key}`)
      continue
    }
    const raw = await readFile(file, "utf8")
    const { title, description, body } = mdxToMarkdown(raw, product)
    const html = marked.parse(body, { gfm: true, breaks: false })
    const parts = key
      .replace(/^docs\//, "")
      .split("/")
      .slice(0, -1)
      .filter((s) => !manual.pathPrefixes.some((p) => p.replace(/\/$/, "") === s))
    const section =
      parts
        .map((s) =>
          s
            .split("-")
            .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
            .join(" "),
        )
        .join(" / ") || manual.title

    chapters.push({
      title: title || titleFromKey(key),
      description,
      section,
      html,
      key,
    })
    console.log(`  + ${key}`)
  }

  if (!chapters.length) {
    console.warn(`  WARN: no chapters for ${product.id}/${manual.id}`)
    return { htmlPath: null, pdfPath: null, chapters: [] }
  }

  const dateIso = new Date().toISOString().slice(0, 10)
  const html = wrapHtml({
    product,
    title: manual.title,
    subtitle: manual.subtitle,
    audience: manual.audience,
    chapters,
    dateIso,
  })

  await mkdir(CACHE, { recursive: true })
  await mkdir(OUT_DIR, { recursive: true })
  const htmlPath = path.join(CACHE, `${product.id}-${manual.id}.html`)
  const pdfPath = path.join(OUT_DIR, manual.filename)
  await writeFile(htmlPath, html, "utf8")
  console.log(`  wrote ${path.relative(ROOT, htmlPath)}`)

  if (SKIP_PDF) {
    console.log("  skip PDF (--skip-pdf)")
    return { htmlPath, pdfPath: null, chapters }
  }
  if (!findChrome()) {
    console.warn(
      "  WARN: no Chromium — HTML written, PDF skipped (set CHROME_PATH)",
    )
    return { htmlPath, pdfPath: null, chapters }
  }

  await htmlToPdf(htmlPath, pdfPath)
  console.log(`  wrote ${path.relative(ROOT, pdfPath)}`)
  return { htmlPath, pdfPath, chapters }
}

// ── Agent files: llms.txt + llm.txt ─────────────────────────────────────────

async function buildAgentFiles(product, docsJson) {
  console.log(`\n→ [${product.name}] Agent files: llms.txt + llm.txt`)
  const dateIso = new Date().toISOString().slice(0, 10)
  const tabs = docsJson.navigation?.tabs ?? []

  // ── llms.txt (index map) ──
  const linesLlms = [
    `# ${product.name} — llms.txt`,
    `# https://llmstxt.org/ — machine-readable project map for LLMs`,
    `# Generated ${dateIso}`,
    ``,
    `# ${product.name}`,
    `> ${product.tagline}`,
    ``,
    product.blurb,
    ``,
    `## Primary`,
    ``,
    `- [Marketing](${product.marketing}): Product landing`,
    `- [Docs](${product.publicUrl}): Full documentation hub`,
    `- [Repository](${REPO}): Source monorepo`,
    `- [Docs tree](${REPO}/tree/main/${product.repoPath}): MDX source of truth`,
    `- [llm.txt](${product.publicUrl}/llm.txt): Full-corpus minified context`,
    `- [llms.txt](${product.publicUrl}/llms.txt): This file`,
    product.id === "pyne"
      ? `- [AXIS docs](${SITE}/axis/docs): Charting PWA (separate product)`
      : `- [PYNE docs](${SITE}/pyne/docs): Language runtime (separate product)`,
    `- [HOOX docs](${SITE}/docs): Edge trade mesh`,
    ``,
    `## Documentation tracks`,
    ``,
  ]

  for (const tab of tabs) {
    const name = String(tab.tab ?? "")
    if (!tab.groups?.length) continue
    linesLlms.push(`### ${name}`, ``)
    const pages = []
    for (const g of tab.groups) flattenPages(g.pages ?? [], pages)
    const seen = new Set()
    for (const p of pages) {
      if (seen.has(p)) continue
      seen.add(p)
      const href = pageKeyToHref(product, p)
      const label = titleFromKey(p)
      linesLlms.push(`- [${label}](${SITE}${href})`)
    }
    linesLlms.push(``)
  }

  linesLlms.push(`## PDF manuals`, ``)
  for (const manual of Object.values(product.manuals)) {
    linesLlms.push(
      `- [${manual.title} (A4 PDF)](${SITE}/exports/${manual.filename})`,
    )
  }
  linesLlms.push(
    ``,
    `## Optional`,
    ``,
    `- [HOOX llms.txt](${SITE}/llms.txt)`,
    `- [HOOX ai.txt](${SITE}/ai.txt)`,
    `- [Exports manifest](${SITE}/exports/manifest.json)`,
    ``,
  )

  const llmsPath = path.join(product.docsRoot, "llms.txt")
  await writeFile(llmsPath, linesLlms.join("\n"), "utf8")
  console.log(`  wrote ${path.relative(ROOT, llmsPath)}`)

  // Also mirror under exports for hosting convenience
  await mkdir(OUT_DIR, { recursive: true })
  await writeFile(
    path.join(OUT_DIR, `${product.id}-llms.txt`),
    linesLlms.join("\n"),
    "utf8",
  )

  // ── llm.txt (full minified corpus) ──
  const allFiles = await walkMdx(product.docsRoot)
  allFiles.sort()
  const chunks = [
    `${product.name} CONSOLIDATED DOCUMENTATION — LLM CONTEXT PACK`,
    `Generated: ${dateIso}`,
    `Source: ${product.repoPath}`,
    `Public: ${product.publicUrl}`,
    `Repository: ${REPO}`,
    ``,
  ]

  for (const file of allFiles) {
    const rel = path.relative(product.docsRoot, file).replace(/\\/g, "/")
    if (rel === "llm.txt" || rel === "llms.txt") continue
    const raw = await readFile(file, "utf8")
    const body = minifyLlmText(raw)
    if (!body.trim()) continue
    chunks.push(`FILE: ${product.repoPath}/${rel}`)
    chunks.push(body)
    chunks.push("---")
  }

  const llmText = chunks.join("\n") + "\n"
  const llmPath = path.join(product.docsRoot, "llm.txt")
  await writeFile(llmPath, llmText, "utf8")
  console.log(
    `  wrote ${path.relative(ROOT, llmPath)} (${(llmText.length / 1024).toFixed(1)} KB)`,
  )
  await writeFile(path.join(OUT_DIR, `${product.id}-llm.txt`), llmText, "utf8")

  return {
    llms: path.relative(ROOT, llmsPath),
    llm: path.relative(ROOT, llmPath),
    bytes: llmText.length,
  }
}

// ── Main ────────────────────────────────────────────────────────────────────

async function main() {
  const t0 = Date.now()
  console.log("PYNE + AXIS docs export pipeline")
  console.log(`  only=${onlyArg}  product=${productArg || "both"}  skipPdf=${SKIP_PDF}`)
  console.log(`  chrome=${findChrome() || "(none)"}`)
  console.log(`  axis docsRoot=${AXIS_DOCS_ROOT}`)

  await mkdir(OUT_DIR, { recursive: true })
  await mkdir(CACHE, { recursive: true })

  const manifest = {
    generatedAt: new Date().toISOString(),
    site: SITE,
    repository: REPO,
    products: {},
  }

  for (const productId of productsToRun()) {
    const product = PRODUCTS[productId]
    if (!existsSync(path.join(product.docsRoot, "docs.json"))) {
      console.warn(`skip ${productId}: missing docs.json`)
      continue
    }
    const docsJson = loadDocsJson(product.docsRoot)
    const plan = planForProduct(productId)
    const pdfs = {}

    for (const mid of plan.manuals) {
      const manual = product.manuals[mid]
      const result = await buildManual(product, manual, docsJson)
      if (result.pdfPath) {
        pdfs[mid] = `/exports/${manual.filename}`
      }
    }

    let agents = null
    if (plan.agents) {
      agents = await buildAgentFiles(product, docsJson)
    }

    manifest.products[productId] = {
      name: product.name,
      docs: product.publicUrl,
      marketing: product.marketing,
      pdfs,
      llm: `/${product.repoPath}/llm.txt`,
      llms: `/${product.repoPath}/llms.txt`,
      exportLlm: `/exports/${productId}-llm.txt`,
      exportLlms: `/exports/${productId}-llms.txt`,
      agents,
    }
  }

  await writeFile(
    path.join(OUT_DIR, "manifest.json"),
    JSON.stringify(manifest, null, 2) + "\n",
    "utf8",
  )
  console.log(`\n  wrote ${path.relative(ROOT, path.join(OUT_DIR, "manifest.json"))}`)
  console.log(`\nDone in ${((Date.now() - t0) / 1000).toFixed(1)}s`)
  console.log(`Artifacts → ${path.relative(ROOT, OUT_DIR)}/ + docs/{pyne,axis}/llm(s).txt`)
}

main().catch((err) => {
  console.error("\nExport failed:", err)
  process.exit(1)
})
