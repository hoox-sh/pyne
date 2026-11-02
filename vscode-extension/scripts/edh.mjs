#!/usr/bin/env node
// Copyright (C) 2024-2026 jango_blockchained
// SPDX-License-Identifier: AGPL-3.0-or-later
/**
 * Launch the installed VS Code / Code - OSS as an Extension Development Host.
 *
 *   node scripts/edh.mjs           # open examples/rsi_strategy.pine
 *   node scripts/edh.mjs --test    # run mocha tests in the same host (--wait)
 *
 * Isolated --user-data-dir so this does not touch the interactive profile.
 */
import { spawn } from 'node:child_process';
import * as fs from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const extRoot = path.resolve(here, '..');
const repoRoot = path.resolve(extRoot, '..');
const runTests = process.argv.includes('--test');
const codeBin = process.env.VSCODE_EXECUTABLE || 'code';

const userData = fs.mkdtempSync(path.join(os.tmpdir(), 'pyne-edh-user-'));
const extDir = fs.mkdtempSync(path.join(os.tmpdir(), 'pyne-edh-ext-'));

const args = [
  '--new-window',
  '--disable-extensions',
  '--disable-workspace-trust',
  '--skip-release-notes',
  '--skip-welcome',
  `--user-data-dir=${userData}`,
  `--extensions-dir=${extDir}`,
  `--extensionDevelopmentPath=${extRoot}`,
];

if (runTests) {
  args.push('--wait');
  args.push(`--extensionTestsPath=${path.join(extRoot, 'out', 'test', 'index.js')}`);
} else {
  args.push(path.join(repoRoot, 'examples', 'rsi_strategy.pine'));
}

console.log(`[edh] ${codeBin} ${args.join(' ')}`);
console.log(`[edh] user-data-dir=${userData}`);

const child = spawn(codeBin, args, {
  stdio: 'inherit',
  env: { ...process.env, ELECTRON_NO_ATTACH_CONSOLE: '1' },
});

child.on('exit', (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});
