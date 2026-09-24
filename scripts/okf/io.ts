/**
 * Copyright (c) 2026 HOOX · PYNE · hoox-sh
 * SPDX-License-Identifier: AGPL-3.0-or-later
 */

import { execFileSync } from 'node:child_process';
import { mkdirSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, relative, sep } from 'node:path';

export type InputFile = {
  path: string;
  text: string;
  kind: 'code' | 'doc' | 'other';
};

export const CODE_ROOTS = [
  'src/pynescript',
  'backend',
  'tests',
  'scripts',
  'cf/src',
  'vscode-extension/src',
];

export const STANDALONE_DOCS = [
  'README.md',
  'CONTRIBUTING.md',
  'SECURITY.md',
  'DESIGN.md',
  'COMPATIBILITY.md',
];

/** Pine corpora and generated parsers are not the map. */
const SKIP_PREFIXES = [
  'docs/images',
  'tests/data',
  'tests/fixtures',
  'src/pynescript/ast/grammar/antlr4/generated',
  'src/pynescript/ast/grammar/asdl/generated',
];

const CODE_EXT = new Set(['.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.rs', '.py']);
const DOC_EXT = new Set(['.md', '.mdx']);
const SKIP_DIRS = new Set(['node_modules', 'dist', 'coverage', '__pycache__', 'target', 'pyodide', 'vendor']);
const MAX_PARSE_BYTES = 400_000;

function toPosix(path: string): string {
  return path.split(sep).join('/');
}

function extensionOf(path: string): string {
  const base = path.slice(path.lastIndexOf('/') + 1);
  const dot = base.lastIndexOf('.');
  return dot <= 0 ? '' : base.slice(dot);
}

export function classifyPath(path: string): InputFile['kind'] | null {
  if (path.startsWith('docs/images/') || path === 'docs/images') return null;
  const ext = extensionOf(path);
  if (path.startsWith('docs/') && DOC_EXT.has(ext)) return 'doc';
  if (STANDALONE_DOCS.includes(path)) return 'doc';
  if (CODE_EXT.has(ext) && CODE_ROOTS.some((root) => path === root || path.startsWith(`${root}/`))) return 'code';
  if (CODE_ROOTS.some((root) => path === root || path.startsWith(`${root}/`))) return 'other';
  return null;
}

function underSkipped(path: string): boolean {
  return path.split('/').some((part) => SKIP_DIRS.has(part) || part.startsWith('.'));
}

function walk(dir: string, root: string, out: string[]): void {
  let entries: ReturnType<typeof readdirSync>;
  try {
    entries = readdirSync(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const entry of entries) {
    if (entry.name.startsWith('.') || SKIP_DIRS.has(entry.name)) continue;
    if (entry.isSymbolicLink()) continue;
    const abs = join(dir, entry.name);
    const rel = toPosix(relative(root, abs));
    if (SKIP_PREFIXES.some((prefix) => rel === prefix || rel.startsWith(`${prefix}/`))) continue;
    if (entry.isDirectory()) walk(abs, root, out);
    else out.push(rel);
  }
}

function git(root: string, args: string[]): string {
  return execFileSync('git', args, {
    cwd: root,
    encoding: 'utf8',
    maxBuffer: 64 * 1024 * 1024,
  });
}

function nulSplit(text: string): string[] {
  return text.split('\0').filter((part) => part.length > 0);
}

function readText(root: string, path: string, fromIndex: boolean, unstaged: Set<string>): string {
  if (fromIndex && unstaged.has(path)) {
    return git(root, ['show', `:${path}`]);
  }
  return readFileSync(join(root, path), 'utf8');
}

function trackedPaths(root: string): string[] {
  const pathspecs = [...CODE_ROOTS, 'docs', ...STANDALONE_DOCS];
  return nulSplit(git(root, ['ls-files', '-z', '--', ...pathspecs]));
}

export function collectInputs(root: string, fromIndex: boolean): InputFile[] {
  const paths = fromIndex ? trackedPaths(root) : [];
  if (!fromIndex) {
    for (const codeRoot of CODE_ROOTS) walk(join(root, codeRoot), root, paths);
    walk(join(root, 'docs'), root, paths);
    for (const doc of STANDALONE_DOCS) {
      try {
        if (statSync(join(root, doc)).isFile()) paths.push(doc);
      } catch {
        // optional companion doc
      }
    }
  }
  const unstaged = fromIndex ? new Set(nulSplit(git(root, ['diff', '-z', '--name-only']))) : new Set<string>();
  const files: InputFile[] = [];
  const seen = new Set<string>();
  for (const path of paths.sort()) {
    if (seen.has(path) || underSkipped(path)) continue;
    seen.add(path);
    const kind = classifyPath(path);
    if (!kind) continue;
    let text = '';
    if (kind !== 'other') {
      try {
        const abs = join(root, path);
        const size = fromIndex && unstaged.has(path) ? MAX_PARSE_BYTES : statSync(abs).size;
        if (size <= MAX_PARSE_BYTES) text = readText(root, path, fromIndex, unstaged);
      } catch {
        text = '';
      }
      if (text.includes('\0')) {
        files.push({ path, text: '', kind: 'other' });
        continue;
      }
    }
    files.push({ path, text, kind: text === '' && kind !== 'other' ? 'other' : kind });
  }
  return files;
}

export function applyBundle(
  dir: string,
  next: Map<string, string>,
  skip: ReadonlySet<string> = new Set(),
): { wrote: number; deleted: number } {
  const previous = markdownPaths(dir);
  let wrote = 0;
  let deleted = 0;
  for (const [rel, text] of next) {
    if (skip.has(rel)) continue;
    const abs = join(dir, rel);
    let current: string;
    try {
      current = readFileSync(abs, 'utf8');
    } catch {
      current = '';
    }
    if (current === text) continue;
    mkdirSync(dirname(abs), { recursive: true });
    writeFileSync(abs, text);
    wrote += 1;
  }
  for (const rel of previous) {
    if (next.has(rel)) continue;
    rmSync(join(dir, rel), { force: true });
    deleted += 1;
  }
  pruneEmpty(dir);
  return { wrote, deleted };
}

export function diffBundle(dir: string, next: Map<string, string>): string[] {
  const previous = readExisting(dir);
  const changes: string[] = [];
  for (const [rel, text] of next) {
    if (previous.get(rel) !== text) changes.push(rel);
  }
  for (const rel of previous.keys()) {
    if (!next.has(rel)) changes.push(rel);
  }
  return changes.sort();
}

function markdownPaths(dir: string): string[] {
  return [...readExisting(dir).keys()];
}

function readExisting(dir: string): Map<string, string> {
  const files = new Map<string, string>();
  walkMd(dir, dir, files);
  return files;
}

function walkMd(dir: string, root: string, into: Map<string, string>): void {
  let entries: ReturnType<typeof readdirSync>;
  try {
    entries = readdirSync(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const entry of entries) {
    if (entry.name.startsWith('.') || entry.isSymbolicLink()) continue;
    const abs = join(dir, entry.name);
    if (entry.isDirectory()) {
      walkMd(abs, root, into);
      continue;
    }
    if (!entry.name.endsWith('.md')) continue;
    into.set(toPosix(relative(root, abs)), readFileSync(abs, 'utf8'));
  }
}

export function readBundleFiles(dir: string): Map<string, string> {
  return readExisting(dir);
}

/** Bundle markdown as the index will commit it. Unstaged edits are read from the index; clean files are read from disk. */
export function readBundleFromIndex(root: string, bundleRel = 'okf'): Map<string, string> {
  const files = readBundleFiles(join(root, bundleRel));
  let dirty: string[];
  try {
    dirty = nulSplit(git(root, ['diff', '-z', '--name-only', '--', bundleRel]));
  } catch {
    return files;
  }
  const prefix = `${bundleRel}/`;
  for (const path of dirty) {
    if (!path.startsWith(prefix) || !path.endsWith('.md')) continue;
    const rel = path.slice(prefix.length);
    try {
      files.set(rel, git(root, ['show', `:${path}`]));
    } catch {
      files.delete(rel);
    }
  }
  return files;
}

function pruneEmpty(dir: string): void {
  let entries: ReturnType<typeof readdirSync>;
  try {
    entries = readdirSync(dir, { withFileTypes: true });
  } catch {
    return;
  }
  for (const entry of entries) {
    if (!entry.isDirectory() || entry.name.startsWith('.') || entry.isSymbolicLink()) continue;
    const abs = join(dir, entry.name);
    pruneEmpty(abs);
    try {
      if (readdirSync(abs).length === 0) rmSync(abs, { recursive: true });
    } catch {
      // already gone
    }
  }
}
