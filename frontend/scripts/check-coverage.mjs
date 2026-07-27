#!/usr/bin/env bun
/**
 * Parse Bun lcov and enforce minimum line coverage on scoped paths.
 *
 * Usage:
 *   bun scripts/check-coverage.mjs [minPercent] [lcovPath]
 *
 * Scoped core gate (plugins, storage, store, results, worker auth/scripts, …).
 * Default min 70% if no arg; package.json uses 95% (ratchet: 70→80→87→90→95).
 */

import { readFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';

const min = Number(process.argv[2] || 70);
const lcovPath = resolve(process.argv[3] || 'coverage/lcov.info');

if (!existsSync(lcovPath)) {
  console.error(`check-coverage: missing ${lcovPath}`);
  console.error('Run: bun test --coverage --coverage-reporter=lcov --coverage-dir=coverage');
  process.exit(1);
}

const text = readFileSync(lcovPath, 'utf8');

/** Paths that count toward the Phase A gate (substring match on SF path). */
const INCLUDE = [
  'src/plugins/',
  'src/storage/',
  'src/store/',
  'src/results/',
  'src/sources/',
  'src/engines/catalog.ts',
  'src/streams/',
  'src/data/',
  'src/indicators/runner.ts',
  'src/chart/drawing-types.ts',
  'src/chart/pine-drawings.ts',
  'src/chart/series-factory.ts',
  'src/chart/manager-access.ts',
  'worker/src/auth.ts',
  'worker/src/scripts.ts',
  'worker/src/keys.ts',
  'worker/src/runtime.ts',
  'src/ui/plugin-badges-utils.ts',
];

// Still deferred (interactive / SVG / full chart apply)
const EXCLUDE = [
  'src/storage/idb.ts',
  'src/streams/binance.ts',
  'src/streams/index.js',
  'src/sources/index.js',
  'src/engines/index.js',
  'src/chart/drawing-layer.ts',
  'src/chart/pane-manager.ts', // covered by unit suite; resize/pointer paths need browser
  'src/indicators/runner.ts', // runAndApply overlay path needs live chart
  'src/engines/catalog.ts', // pyodide boot path
];

function included(file) {
  // Normalize windows paths
  const f = file.replace(/\\/g, '/');
  if (EXCLUDE.some((p) => f.includes(p))) return false;
  return INCLUDE.some((p) => f.includes(p));
}

let found = 0;
let hit = 0;
let currentFile = '';
let skip = true;
const perFile = [];
let fileFound = 0;
let fileHit = 0;

function flushFile() {
  if (currentFile && !skip && fileFound > 0) {
    perFile.push({ file: currentFile, found: fileFound, hit: fileHit });
  }
  fileFound = 0;
  fileHit = 0;
}

for (const line of text.split('\n')) {
  if (line.startsWith('SF:')) {
    flushFile();
    currentFile = line.slice(3).trim();
    skip = !included(currentFile);
    continue;
  }
  if (skip) continue;
  if (line.startsWith('DA:')) {
    const parts = line.slice(3).split(',');
    const n = Number(parts[1] || 0);
    found += 1;
    fileFound += 1;
    if (n > 0) {
      hit += 1;
      fileHit += 1;
    }
  }
}
flushFile();

if (found === 0) {
  console.error('check-coverage: no DA lines found in scoped core files');
  console.error('INCLUDE globs:', INCLUDE.join(', '));
  process.exit(1);
}

const pct = (100 * hit) / found;
console.log('check-coverage core packages:');
for (const row of perFile.sort((a, b) => a.file.localeCompare(b.file))) {
  const p = (100 * row.hit) / row.found;
  console.log(`  ${p.toFixed(1).padStart(6)}%  ${row.hit}/${row.found}  ${row.file.split('/src/').pop() || row.file.split('/worker/').pop()}`);
}
console.log(
  `check-coverage: ${hit}/${found} core lines hit = ${pct.toFixed(2)}% (min ${min}%)`,
);
if (pct + 1e-9 < min) {
  console.error(`check-coverage: FAIL below ${min}%`);
  process.exit(1);
}
console.log('check-coverage: OK');
