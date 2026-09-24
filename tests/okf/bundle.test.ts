/**
 * Copyright (c) 2026 HOOX · PYNE · hoox-sh
 * SPDX-License-Identifier: AGPL-3.0-or-later
 */

import { describe, expect, it } from 'bun:test';
import { mkdtempSync, rmSync, writeFileSync, mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { compileBundle } from '../../scripts/okf/compile';
import { extractNotes } from '../../scripts/okf/compile';
import type { InputFile } from '../../scripts/okf/io';
import { applyBundle, diffBundle } from '../../scripts/okf/io';
import { lintBundle, lintFiles } from '../../scripts/okf/lint';
import { renderContext, searchConcepts } from '../../scripts/okf/query';
import { loadConcepts } from '../../scripts/okf/lint';

const sample = (now: string, extra: InputFile[] = []) => {
  const files: InputFile[] = [
    {
      path: 'src/app.ts',
      kind: 'code',
      text: '/** Chart host entry. */\nimport { chart } from "./chart/view";\nexport function main() { chart(); }\n',
    },
    {
      path: 'src/chart/view.ts',
      kind: 'code',
      text: '/** Draws the visible range. */\nexport function chart() { return 1; }\n',
    },
    {
      path: 'docs/architecture/overview.mdx',
      kind: 'doc',
      text: '---\ntitle: Overview\ndescription: The composition host.\n---\n# Overview\n\n## Pieces\n\nThe chart lives in src/chart/view.ts.\n',
    },
    ...extra,
  ];
  return compileBundle({ files, existing: new Map(), now });
};

describe('OKF compile', () => {
  it('links an import to the dependency module and back', () => {
    const bundle = sample('2026-09-24T00:00:00Z');
    const app = bundle.get('code/src.md') ?? '';
    const chart = bundle.get('code/src/chart.md') ?? '';
    expect(app).toContain('](/code/src/chart.md)');
    expect(chart).toContain('](/code/src.md)');
    expect(app).toContain('type: "Code Module"');
    expect(bundle.get('docs/architecture/overview.md')).toContain('](/code/src/chart.md)');
  });

  it('keeps generated.at stable when the tree does not change', () => {
    const first = sample('2026-09-24T00:00:00Z');
    const second = compileBundle({
      files: [
        {
          path: 'src/app.ts',
          kind: 'code',
          text: '/** Chart host entry. */\nimport { chart } from "./chart/view";\nexport function main() { chart(); }\n',
        },
        {
          path: 'src/chart/view.ts',
          kind: 'code',
          text: '/** Draws the visible range. */\nexport function chart() { return 1; }\n',
        },
        {
          path: 'docs/architecture/overview.mdx',
          kind: 'doc',
          text: '---\ntitle: Overview\ndescription: The composition host.\n---\n# Overview\n\n## Pieces\n\nThe chart lives in src/chart/view.ts.\n',
        },
      ],
      existing: first,
      now: '2026-10-01T12:00:00Z',
    });
    expect(second.get('code/src.md')).toBe(first.get('code/src.md'));
    expect(second.get('log.md')).toBe(first.get('log.md'));
  });

  it('restamps and logs when a module changes', () => {
    const first = sample('2026-09-24T00:00:00Z');
    const second = compileBundle({
      files: [
        {
          path: 'src/app.ts',
          kind: 'code',
          text: '/** Chart host entry, now with alerts. */\nexport function main() {}\n',
        },
      ],
      existing: first,
      now: '2026-10-01T12:00:00Z',
    });
    expect(second.get('code/src.md')).toContain('at: 2026-10-01T12:00:00Z');
    expect(second.get('code/src/chart.md')).toBeUndefined();
    expect(second.get('log.md')).toContain('## 2026-10-01');
    expect(second.get('log.md')).toContain('## 2026-09-24');
    const log = second.get('log.md') ?? '';
    expect(log.indexOf('## 2026-10-01')).toBeLessThan(log.indexOf('## 2026-09-24'));
  });

  it('does not overwrite a human-locked concept', () => {
    const locked = [
      '---',
      'type: "Playbook"',
      'title: "Keep me"',
      'description: "Hand written."',
      'okf_lock: human',
      'generated:',
      '  by: human:jango_blockchained',
      '  at: 2026-09-01T00:00:00Z',
      '---',
      '',
      'Do not replace this body.',
      '',
    ].join('\n');
    const bundle = compileBundle({
      files: [{ path: 'src/app.ts', kind: 'code', text: 'export function main() {}\n' }],
      existing: new Map([['playbooks/keep.md', locked]]),
      now: '2026-09-24T00:00:00Z',
    });
    expect(bundle.get('playbooks/keep.md')).toBe(locked);
    expect(bundle.get('playbooks/index.md')).toContain('](keep.md)');
    expect(bundle.get('index.md')).toContain('okf_version: "0.2"');
    expect(bundle.get('index.md')).toContain('(playbooks/)');
  });

  it('skips license banners and keeps the module sentence', () => {
    const notes = extractNotes(
      ['// Copyright (C) 2026', '// SPDX-License-Identifier: AGPL-3.0-or-later', '', '/** Background backfill for OHLCV. */', '', 'export const x = 1;'].join('\n'),
      '.ts',
    );
    expect(notes[0]).toContain('Background backfill');
  });
});

describe('OKF lint', () => {
  it('accepts a compiled bundle with no errors', () => {
    const findings = lintFiles(sample('2026-09-24T00:00:00Z'));
    expect(findings.filter((finding) => finding.severity === 'error')).toEqual([]);
  });

  it('errors on a missing type, a bad log, and an attested computation without runtime', () => {
    const files = new Map<string, string>([
      ['index.md', '---\nokf_version: "0.2"\ntitle: no\n---\n\n* [A](a.md)\n'],
      ['log.md', '# Log\n\n## March\n* **Update**: late\n\n## 2026-01-02\n* **Update**: newer\n\n## 2026-01-01\n* **Update**: older\n'],
      ['a.md', '---\ntitle: "A"\n---\n\nBody.\n'],
      [
        'computations/revenue.md',
        '---\ntype: "Attested Computation"\ntitle: "Revenue"\ndescription: "Revenue for a year."\nparameters:\n  - { name: year, type: integer, required: true }\nverified: { by: human:ada, at: 2026-06-25T09:00:00Z }\n---\n\n# Computation\n\n    select 1\n',
      ],
    ]);
    const rules = new Set(lintFiles(files).filter((finding) => finding.severity === 'error').map((finding) => finding.rule));
    expect(rules.has('E003')).toBe(true);
    expect(rules.has('E004')).toBe(true);
    expect(rules.has('E005')).toBe(true);
    expect(rules.has('E010')).toBe(true);
    expect(lintFiles(files).some((finding) => finding.path === 'computations/revenue.md' && finding.rule === 'E009')).toBe(false);
  });

  it('warns on a broken link and an orphan without failing conformance of the type', () => {
    const files = new Map<string, string>([
      ['index.md', '---\nokf_version: "0.2"\n---\n\n* [A](a.md)\n'],
      ['log.md', '# Bundle update log\n\n## 2026-09-24\n* **Initialization**: Created.\n'],
      ['a.md', '---\ntype: "Reference"\ntitle: "A"\ndescription: "Points nowhere."\n---\n\nSee [missing](/missing.md) and [rel](./b.md).\n'],
      ['b.md', '---\ntype: "Reference"\ntitle: "B"\ndescription: "Linked relatively."\n---\n\nAlone.\n'],
      ['c.md', '---\ntype: "Reference"\ntitle: "C"\ndescription: "Unlinked."\n---\n\nAlone.\n'],
    ]);
    const findings = lintFiles(files);
    expect(findings.some((finding) => finding.severity === 'error')).toBe(false);
    expect(findings.some((finding) => finding.rule === 'W004')).toBe(true);
    expect(findings.some((finding) => finding.rule === 'W005' && finding.path === 'c.md')).toBe(true);
    expect(findings.some((finding) => finding.rule === 'W006')).toBe(true);
  });
});

describe('OKF query', () => {
  it('finds a module and renders its context', () => {
    const bundle = sample('2026-09-24T00:00:00Z');
    const hits = searchConcepts(loadConcepts(bundle), ['chart']);
    expect(hits[0]?.id).toBe('code/src/chart');
    const context = renderContext(bundle, 'src/chart', 1, 6000);
    expect(context).toContain('Draws the visible range');
    expect(context).toContain('code/src.md');
  });
});

describe('OKF apply', () => {
  it('writes the bundle and reports drift', () => {
    const dir = mkdtempSync(join(tmpdir(), 'axis-okf-'));
    try {
      const next = sample('2026-09-24T00:00:00Z');
      expect(diffBundle(dir, next).length).toBeGreaterThan(0);
      const applied = applyBundle(dir, next);
      expect(applied.wrote).toBe(next.size);
      expect(diffBundle(dir, next)).toEqual([]);
      expect(lintBundle(dir).filter((finding) => finding.severity === 'error')).toEqual([]);
      writeFileSync(join(dir, 'stray.md'), '---\ntype: "Note"\n---\n\n');
      mkdirSync(join(dir, 'nested'), { recursive: true });
      const pruned = applyBundle(dir, next);
      expect(pruned.deleted).toBe(1);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });
});
