/**
 * Copyright (c) 2026 HOOX · PYNE · hoox-sh
 * SPDX-License-Identifier: AGPL-3.0-or-later
 */

/**
 * OKF v0.2 conformance linter.
 *
 * Errors are the spec's hard rules plus malformed optional families (a present
 * `generated` / `sources` / `verified` block that cannot be read as specified).
 * Warnings are the producer conventions: recommended fields, resolvable links,
 * orphans, absolute links. Broken links stay warnings because the spec says
 * consumers must tolerate not-yet-written targets.
 */

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, posix } from 'node:path';
import { ACTOR, asList, type Frontmatter, isRecord, ISO_8601, parseYaml, splitFrontmatter } from './yaml';

export type Severity = 'error' | 'warning';

export type Finding = {
  path: string;
  line: number;
  rule: string;
  severity: Severity;
  message: string;
};

export type ConceptDoc = {
  path: string;
  id: string;
  frontmatter: Frontmatter;
  body: string;
  text: string;
};

export type BundleDocs = {
  files: Map<string, string>;
  concepts: ConceptDoc[];
  findings: Finding[];
};

const DATE_HEADING = /^## (\d{4}-\d{2}-\d{2})$/;

function push(
  findings: Finding[],
  path: string,
  rule: string,
  severity: Severity,
  message: string,
  line = 1,
): void {
  findings.push({ path, line, rule, severity, message });
}

function checkTimestamp(findings: Finding[], path: string, field: string, value: unknown): void {
  if (typeof value !== 'string' || !ISO_8601.test(value)) {
    push(findings, path, 'E007', 'error', `${field} must be an ISO 8601 datetime with a UTC offset`);
  }
}

function checkActor(findings: Finding[], path: string, field: string, value: unknown): void {
  if (typeof value !== 'string' || value.length === 0) {
    push(findings, path, 'E006', 'error', `${field} must be a non-empty actor`);
    return;
  }
  if (!ACTOR.test(value)) {
    push(
      findings,
      path,
      'W013',
      'warning',
      `${field} should use human:<id>, process:<id>, or <producer>/<version>`,
    );
  }
}

function checkGenerated(findings: Finding[], path: string, value: unknown): void {
  if (!isRecord(value)) {
    push(findings, path, 'E006', 'error', 'generated must be a mapping with by');
    return;
  }
  checkActor(findings, path, 'generated.by', value.by);
  if ('at' in value && value.at != null) checkTimestamp(findings, path, 'generated.at', value.at);
}

function checkVerified(findings: Finding[], path: string, value: unknown): void {
  if (!Array.isArray(value) && !isRecord(value)) {
    push(findings, path, 'E009', 'error', 'verified must be an event mapping or a list of events');
    return;
  }
  const events = asList(value);
  if (events.length === 0) {
    push(findings, path, 'E009', 'error', 'verified must contain at least one event');
    return;
  }
  for (const event of events) {
    if (!isRecord(event)) {
      push(findings, path, 'E009', 'error', 'each verified entry must be a mapping with by and at');
      continue;
    }
    checkActor(findings, path, 'verified.by', event.by);
    checkTimestamp(findings, path, 'verified.at', event.at);
  }
}

function checkSources(findings: Finding[], path: string, value: unknown): void {
  if (!Array.isArray(value)) {
    push(findings, path, 'E008', 'error', 'sources must be a list');
    return;
  }
  for (const entry of value) {
    if (!isRecord(entry) || typeof entry.resource !== 'string' || entry.resource.length === 0) {
      push(findings, path, 'E008', 'error', 'each sources entry needs a resource');
      continue;
    }
    if ('author' in entry && entry.author != null) checkActor(findings, path, 'sources.author', entry.author);
    if ('last_modified' in entry && entry.last_modified != null) {
      checkTimestamp(findings, path, 'sources.last_modified', entry.last_modified);
    }
    if ('usage_count' in entry && entry.usage_count != null && typeof entry.usage_count !== 'number') {
      push(findings, path, 'E008', 'error', 'sources.usage_count must be a number');
    }
    if ('id' in entry && entry.id != null && typeof entry.id !== 'string') {
      push(findings, path, 'E008', 'error', 'sources.id must be a string');
    }
  }
}

function checkUsageWindow(findings: Finding[], path: string, value: unknown): void {
  if (!isRecord(value)) {
    push(findings, path, 'E014', 'error', 'usage_window must be a { from, to } mapping');
    return;
  }
  checkTimestamp(findings, path, 'usage_window.from', value.from);
  checkTimestamp(findings, path, 'usage_window.to', value.to);
}

function checkAttested(findings: Finding[], path: string, fm: Frontmatter): void {
  if (typeof fm.runtime !== 'string' || fm.runtime.trim() === '') {
    push(findings, path, 'E010', 'error', 'Attested Computation requires runtime');
  }
  if ('parameters' in fm && fm.parameters != null) {
    if (!Array.isArray(fm.parameters)) {
      push(findings, path, 'E012', 'error', 'parameters must be a list');
    } else {
      for (const param of fm.parameters) {
        if (!isRecord(param) || typeof param.name !== 'string' || param.name.length === 0) {
          push(findings, path, 'E012', 'error', 'each parameter needs a name');
        }
      }
    }
  }
  if ('computation' in fm && fm.computation != null && typeof fm.computation !== 'string') {
    push(findings, path, 'E015', 'error', 'computation must be a path string');
  }
  for (const key of ['executor', 'attester'] as const) {
    if (!(key in fm) || fm[key] == null) continue;
    const block = fm[key];
    if (!isRecord(block)) {
      push(findings, path, 'E015', 'error', `${key} must be a mapping`);
      continue;
    }
    if ('resource' in block && block.resource != null && typeof block.resource !== 'string') {
      push(findings, path, 'E015', 'error', `${key}.resource must be a string`);
    }
    if (key === 'executor' && 'receipt' in block && block.receipt != null) {
      const receipt = block.receipt;
      if (!Array.isArray(receipt) || receipt.some((item) => typeof item !== 'string')) {
        push(findings, path, 'E015', 'error', 'executor.receipt must be a list of strings');
      }
    }
  }
}

function checkConcept(findings: Finding[], path: string, fm: Frontmatter, body: string): void {
  if (typeof fm.type !== 'string' || fm.type.trim() === '') {
    push(findings, path, 'E003', 'error', 'type is required and must be a non-empty string');
  }
  if ('title' in fm && fm.title != null && typeof fm.title !== 'string') {
    push(findings, path, 'E016', 'error', 'title must be a string');
  } else if (!('title' in fm) || typeof fm.title !== 'string' || fm.title.trim() === '') {
    push(findings, path, 'W001', 'warning', 'missing recommended title');
  }
  if (!('description' in fm) || typeof fm.description !== 'string' || fm.description.trim() === '') {
    push(findings, path, 'W002', 'warning', 'missing recommended description');
  } else if (typeof fm.description === 'string') {
    if (fm.description.includes('\n')) {
      push(findings, path, 'W003', 'warning', 'description should be a single line');
    }
    if (fm.description.length > 280) {
      push(findings, path, 'W012', 'warning', 'description is longer than one sentence');
    }
  }
  if ('resource' in fm && fm.resource != null && typeof fm.resource !== 'string') {
    push(findings, path, 'E016', 'error', 'resource must be a string');
  }
  if ('tags' in fm && fm.tags != null) {
    if (!Array.isArray(fm.tags) || fm.tags.some((tag) => typeof tag !== 'string')) {
      push(findings, path, 'E013', 'error', 'tags must be a list of strings');
    } else {
      for (const tag of fm.tags) {
        if (typeof tag === 'string' && !/^[a-z0-9-]+$/.test(tag)) {
          push(findings, path, 'W011', 'warning', `tag "${tag}" should be lowercase words and hyphens`);
        }
      }
    }
  }
  if ('status' in fm && fm.status != null) {
    if (fm.status !== 'draft' && fm.status !== 'stable' && fm.status !== 'deprecated') {
      push(findings, path, 'E011', 'error', 'status must be draft, stable, or deprecated');
    }
  }
  if ('generated' in fm && fm.generated != null) checkGenerated(findings, path, fm.generated);
  if ('verified' in fm && fm.verified != null) checkVerified(findings, path, fm.verified);
  if ('sources' in fm && fm.sources != null) checkSources(findings, path, fm.sources);
  if ('usage_window' in fm && fm.usage_window != null) checkUsageWindow(findings, path, fm.usage_window);
  if ('stale_after' in fm && fm.stale_after != null) checkTimestamp(findings, path, 'stale_after', fm.stale_after);
  if (typeof fm.type === 'string' && fm.type.trim() === 'Attested Computation') checkAttested(findings, path, fm);
  if ('timestamp' in fm && !('generated' in fm)) {
    push(findings, path, 'W010', 'warning', 'timestamp is the v0.1 field; v0.2 uses generated.at');
  }
  if (body.trim() === '') push(findings, path, 'W007', 'warning', 'concept body is empty');
}

function checkIndex(findings: Finding[], path: string, yaml: string | null, body: string): void {
  const root = path === 'index.md';
  if (!root && yaml != null) {
    push(findings, path, 'E004', 'error', 'only the bundle-root index.md may carry frontmatter');
    return;
  }
  if (root && yaml != null) {
    let parsed: unknown;
    try {
      parsed = parseYaml(yaml);
    } catch {
      push(findings, path, 'E002', 'error', 'index frontmatter is not parseable YAML');
      return;
    }
    if (!isRecord(parsed)) {
      push(findings, path, 'E004', 'error', 'root index frontmatter must be a mapping');
      return;
    }
    const keys = Object.keys(parsed);
    if (keys.some((key) => key !== 'okf_version')) {
      push(findings, path, 'E004', 'error', 'root index frontmatter may only contain okf_version');
    }
    if ('okf_version' in parsed) {
      const version = parsed.okf_version;
      if (typeof version !== 'string' && typeof version !== 'number') {
        push(findings, path, 'E004', 'error', 'okf_version must be a scalar');
      } else if (String(version) !== '0.2') {
        push(findings, path, 'W014', 'warning', `okf_version ${String(version)} is not 0.2; checks still follow v0.2`);
      }
    }
  }
  if (!/\[[^\]]+\]\([^)]+\)/.test(body)) {
    push(findings, path, 'W008', 'warning', 'index lists no links');
  }
}

function checkLog(findings: Finding[], path: string, text: string): void {
  if (text.replace(/^\uFEFF/, '').startsWith('---\n')) {
    push(findings, path, 'E005', 'error', 'log.md must not carry frontmatter');
  }
  const dates: string[] = [];
  for (const line of text.split('\n')) {
    const match = DATE_HEADING.exec(line.trim());
    if (line.startsWith('## ') && !match) {
      push(findings, path, 'E005', 'error', `log heading "${line.slice(3)}" is not YYYY-MM-DD`);
      continue;
    }
    if (match?.[1]) dates.push(match[1]);
  }
  for (let i = 1; i < dates.length; i++) {
    const prev = dates[i - 1];
    const curr = dates[i];
    if (prev && curr && curr > prev) {
      push(findings, path, 'E005', 'error', 'log dates must be newest first');
      break;
    }
  }
}

export function markdownLinkTargets(text: string): string[] {
  const targets: string[] = [];
  const re = /(?:^|[^!])\[[^\]]*\]\((<[^>]+>|[^)\s]+)(?:\s+"[^"]*")?\)/g;
  for (const match of text.matchAll(re)) {
    const target = match[1];
    if (target) targets.push(target);
  }
  return targets;
}

export function resolveBundleLink(from: string, target: string, files: Set<string>): string | null {
  const raw = target.startsWith('<') && target.endsWith('>') ? target.slice(1, -1) : target;
  const bare = raw.split('#')[0]?.split('?')[0] ?? '';
  if (!bare || bare.startsWith('http://') || bare.startsWith('https://') || bare.startsWith('mailto:')) return null;
  let rel = bare.startsWith('/') ? bare.slice(1) : posix.normalize(posix.join(posix.dirname(from), bare));
  if (rel.endsWith('/')) rel += 'index.md';
  else if (!rel.endsWith('.md') && files.has(`${rel}.md`)) rel = `${rel}.md`;
  else if (!rel.endsWith('.md') && files.has(`${rel}/index.md`)) rel = `${rel}/index.md`;
  return rel;
}

function checkLinks(findings: Finding[], path: string, text: string, files: Set<string>, reserved: boolean): void {
  for (const target of markdownLinkTargets(text)) {
    const resolved = resolveBundleLink(path, target, files);
    if (resolved == null) continue;
    if (!files.has(resolved)) {
      push(findings, path, 'W004', 'warning', `broken bundle link ${target}`);
      continue;
    }
    if (!reserved && !target.startsWith('/')) {
      push(findings, path, 'W006', 'warning', `prefer a bundle-absolute link over ${target}`);
    }
  }
}

function reachable(files: Map<string, string>): Set<string> {
  const names = new Set(files.keys());
  const seen = new Set<string>();
  const queue = files.has('index.md') ? ['index.md'] : [];
  while (queue.length > 0) {
    const current = queue.pop();
    if (!current || seen.has(current)) continue;
    seen.add(current);
    const text = files.get(current);
    if (!text) continue;
    for (const target of markdownLinkTargets(text)) {
      const resolved = resolveBundleLink(current, target, names);
      if (resolved && names.has(resolved) && !seen.has(resolved)) queue.push(resolved);
    }
  }
  return seen;
}

export function lintFiles(files: Map<string, string>): Finding[] {
  const findings: Finding[] = [];
  if (!files.has('index.md')) push(findings, 'index.md', 'W009', 'warning', 'bundle has no root index.md');
  if (!files.has('log.md')) push(findings, 'log.md', 'W009', 'warning', 'bundle has no root log.md');

  const names = new Set(files.keys());
  for (const [path, text] of files) {
    if (!path.endsWith('.md')) continue;
    const base = posix.basename(path);
    if (base === 'log.md') {
      checkLog(findings, path, text);
      checkLinks(findings, path, text, names, true);
      continue;
    }
    const { yaml, body } = splitFrontmatter(text);
    if (base === 'index.md') {
      checkIndex(findings, path, yaml, body);
      checkLinks(findings, path, text, names, true);
      continue;
    }
    if (yaml == null) {
      push(findings, path, 'E001', 'error', 'concept is missing YAML frontmatter');
      continue;
    }
    let parsed: unknown;
    try {
      parsed = parseYaml(yaml);
    } catch {
      push(findings, path, 'E002', 'error', 'frontmatter is not parseable YAML');
      continue;
    }
    if (!isRecord(parsed)) {
      push(findings, path, 'E002', 'error', 'frontmatter must be a mapping');
      continue;
    }
    checkConcept(findings, path, parsed, body);
    checkLinks(findings, path, body, names, false);
  }

  const reached = reachable(files);
  for (const path of files.keys()) {
    if (!path.endsWith('.md')) continue;
    const base = posix.basename(path);
    if (base === 'index.md' || base === 'log.md') continue;
    if (!reached.has(path)) push(findings, path, 'W005', 'warning', 'concept is not reachable from the root index');
  }
  return findings.sort((a, b) => cmpFinding(a, b));
}

function cmpFinding(a: Finding, b: Finding): number {
  if (a.path !== b.path) return a.path < b.path ? -1 : 1;
  if (a.line !== b.line) return a.line - b.line;
  return a.rule < b.rule ? -1 : a.rule > b.rule ? 1 : 0;
}

function walkMarkdown(dir: string, root: string, into: Map<string, string>): void {
  let entries: ReturnType<typeof readdirSync>;
  try {
    entries = readdirSync(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const entry of entries) {
    if (entry.name.startsWith('.')) continue;
    const abs = join(dir, entry.name);
    if (entry.isSymbolicLink()) continue;
    if (entry.isDirectory()) {
      walkMarkdown(abs, root, into);
      continue;
    }
    if (!entry.name.endsWith('.md')) continue;
    const rel = posix.normalize(abs.slice(root.length + 1).split('\\').join('/'));
    into.set(rel, readFileSync(abs, 'utf8'));
  }
}

export function readMarkdownTree(dir: string): Map<string, string> {
  const files = new Map<string, string>();
  try {
    if (!statSync(dir).isDirectory()) return files;
  } catch {
    return files;
  }
  walkMarkdown(dir, dir, files);
  return files;
}

export function lintBundle(dir: string): Finding[] {
  return lintFiles(readMarkdownTree(dir));
}

export function loadConcepts(files: Map<string, string>): ConceptDoc[] {
  const concepts: ConceptDoc[] = [];
  for (const [path, text] of files) {
    if (!path.endsWith('.md')) continue;
    const base = posix.basename(path);
    if (base === 'index.md' || base === 'log.md') continue;
    const { yaml, body } = splitFrontmatter(text);
    if (yaml == null) continue;
    try {
      const parsed = parseYaml(yaml);
      if (!isRecord(parsed)) continue;
      concepts.push({ path, id: path.replace(/\.md$/, ''), frontmatter: parsed, body, text });
    } catch {
      // lint reports the parse error; query skips the file
    }
  }
  return concepts;
}

export function findingLine(finding: Finding): string {
  return `${finding.path}:${finding.line} ${finding.severity} ${finding.rule} ${finding.message}`;
}
