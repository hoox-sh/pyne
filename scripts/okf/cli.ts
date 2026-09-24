/**
 * Copyright (c) 2026 HOOX · PYNE · hoox-sh
 * SPDX-License-Identifier: AGPL-3.0-or-later
 */

/**
 * OKF bundle pipeline.
 *
 *   bun scripts/okf/cli.ts enrich [--check] [--stage] [--from-index]
 *   bun scripts/okf/cli.ts lint [--strict] [--format text|json]
 *   bun scripts/okf/cli.ts query <terms...>
 *   bun scripts/okf/cli.ts context <path-or-id> [--depth 1]
 */

import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { compileBundle, isHumanConcept } from './compile';
import { applyBundle, collectInputs, diffBundle, readBundleFiles, readBundleFromIndex } from './io';
import { findingLine, lintBundle, lintFiles, loadConcepts } from './lint';
import { formatHits, renderContext, searchConcepts } from './query';

const ROOT = join(import.meta.dir, '../..');
const BUNDLE = join(ROOT, 'okf');

type Flags = {
  check: boolean;
  stage: boolean;
  fromIndex: boolean;
  strict: boolean;
  format: string;
  depth: number;
  help: boolean;
  positional: string[];
};

function parseArgs(argv: string[]): Flags {
  const flags: Flags = {
    check: false,
    stage: false,
    fromIndex: false,
    strict: false,
    format: 'text',
    depth: 1,
    help: false,
    positional: [],
  };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--check') flags.check = true;
    else if (arg === '--stage') flags.stage = true;
    else if (arg === '--from-index') flags.fromIndex = true;
    else if (arg === '--strict') flags.strict = true;
    else if (arg === '--help' || arg === '-h') flags.help = true;
    else if (arg === '--format') flags.format = argv[++i] ?? 'text';
    else if (arg === '--depth') flags.depth = Number(argv[++i] ?? '1');
    else if (arg) flags.positional.push(arg);
  }
  return flags;
}

function usage(): string {
  return [
    'usage: bun scripts/okf/cli.ts <enrich|lint|query|context> [options]',
    '',
    '  enrich [--check] [--stage] [--from-index]   draft, link, and lint the bundle',
    '  lint [--strict] [--format text|json]        conformance plus producer warnings',
    '  query <terms...>                            search titles, paths, and descriptions',
    '  context <path-or-id> [--depth N]            one concept plus neighbor blurbs',
    '',
    'OKF_SKIP=1 skips the pre-commit refresh.',
  ].join('\n');
}

function stamp(): string {
  return new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
}

function reportLint(findings: ReturnType<typeof lintFiles>, strict: boolean, format: string): number {
  const errors = findings.filter((finding) => finding.severity === 'error');
  const warnings = findings.filter((finding) => finding.severity === 'warning');
  if (format === 'json') {
    console.log(JSON.stringify({ ok: errors.length === 0 && (!strict || warnings.length === 0), errors: errors.length, warnings: warnings.length, findings }));
  } else {
    for (const finding of findings) console.log(findingLine(finding));
    console.log(`okf lint: ${errors.length} error(s), ${warnings.length} warning(s)`);
  }
  if (errors.length > 0) return 1;
  if (strict && warnings.length > 0) return 1;
  return 0;
}

function enrich(flags: Flags): number {
  const inputs = collectInputs(ROOT, flags.fromIndex);
  const existing = flags.fromIndex ? readBundleFromIndex(ROOT) : readBundleFiles(BUNDLE);
  if (flags.fromIndex) {
    for (const [rel, text] of readBundleFiles(BUNDLE)) {
      if (!existing.has(rel) && isHumanConcept(text)) existing.set(rel, text);
    }
  }
  const next = compileBundle({ files: inputs, existing, now: stamp() });
  const findings = lintFiles(next);
  if (flags.check) {
    const changes = diffBundle(BUNDLE, next);
    if (changes.length > 0) {
      console.error(`okf: bundle is stale (${changes.length} file(s))`);
      for (const change of changes.slice(0, 40)) console.error(`  ${change}`);
      if (changes.length > 40) console.error(`  … ${changes.length - 40} more`);
      return 1;
    }
    console.log('okf: bundle matches the tree');
    return reportLint(findings, true, flags.format);
  }
  // Dirty curated files stay on disk. The commit's bundle is built from the index.
  const skip = new Set<string>();
  if (flags.fromIndex) {
    for (const [rel, text] of next) {
      if (!isHumanConcept(text)) continue;
      try {
        if (readFileSync(join(BUNDLE, rel), 'utf8') !== text) skip.add(rel);
      } catch {
        skip.add(rel);
      }
    }
  }
  const applied = applyBundle(BUNDLE, next, skip);
  if (flags.stage) stageGenerated(next);
  console.log(`okf: ${applied.wrote} written, ${applied.deleted} removed`);
  return reportLint(findings, false, flags.format);
}

function stageGenerated(next: Map<string, string>): void {
  let listed: string[];
  try {
    listed = execFileSync('git', ['ls-files', '-z', '--', 'okf'], { cwd: ROOT, encoding: 'utf8' }).split('\0');
  } catch {
    listed = [];
  }
  const tracked = new Set(listed.filter((path) => path.length > 0));
  const paths: string[] = [];
  for (const [rel, text] of next) {
    const path = `okf/${rel}`;
    if (isHumanConcept(text)) {
      if (!tracked.has(path)) paths.push(path);
      continue;
    }
    paths.push(path);
  }
  for (const path of listed) {
    if (!path.endsWith('.md')) continue;
    const rel = path.slice('okf/'.length);
    if (!next.has(rel)) paths.push(path);
  }
  if (paths.length === 0) return;
  execFileSync('git', ['add', '-A', '--', ...paths], { cwd: ROOT, stdio: 'inherit' });
}

function main(): number {
  const [command, ...rest] = process.argv.slice(2);
  const flags = parseArgs(rest);
  if (!command || flags.help || command === 'help') {
    console.log(usage());
    return command ? 0 : 1;
  }
  if (command === 'enrich') return enrich(flags);
  if (command === 'lint') return reportLint(lintBundle(BUNDLE), flags.strict, flags.format);
  if (command === 'query') {
    const concepts = loadConcepts(readBundleFiles(BUNDLE));
    console.log(formatHits(searchConcepts(concepts, flags.positional)));
    return 0;
  }
  if (command === 'context') {
    const start = flags.positional.join(' ');
    if (!start) {
      console.error('context needs a concept id or repo path');
      return 1;
    }
    console.log(renderContext(readBundleFiles(BUNDLE), start, Number.isFinite(flags.depth) ? flags.depth : 1, 6000));
    return 0;
  }
  console.error(usage());
  return 1;
}

process.exit(main());
