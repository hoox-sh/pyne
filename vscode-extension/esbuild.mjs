#!/usr/bin/env node
/**
 * Bundle the VS Code extension so vscode-languageclient (and its deps) ship
 * inside out/extension.js. Packaging with --no-dependencies then works and
 * avoids "command not found" from a failed activate() when node_modules is
 * missing from the VSIX.
 */
import * as esbuild from 'esbuild';
import { mkdirSync } from 'fs';

const watch = process.argv.includes('--watch');

mkdirSync('out', { recursive: true });

const opts = {
  entryPoints: ['src/extension.ts'],
  bundle: true,
  outfile: 'out/extension.js',
  external: ['vscode'],
  format: 'cjs',
  platform: 'node',
  target: 'node18',
  sourcemap: true,
  sourcesContent: false,
  minify: false,
  logLevel: 'info',
  // Keep readable stack frames in Extension Host
  keepNames: true,
};

if (watch) {
  const ctx = await esbuild.context(opts);
  await ctx.watch();
  console.log('[esbuild] watching…');
} else {
  await esbuild.build(opts);
  console.log('[esbuild] bundled out/extension.js');
}
