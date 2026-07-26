/**
 * Capability badge helpers.
 * Run: `bun test frontend/tests/plugin-badges.test.ts`
 */

import { describe, expect, it } from 'bun:test';
import { capabilityKeys, engineOptionLabel } from '../src/ui/plugin-badges-utils';
import type { PluginBase } from '../src/plugins/types';

describe('capabilityKeys', () => {
  it('returns empty for undefined', () => {
    expect(capabilityKeys(undefined)).toEqual([]);
  });

  it('filters true flags only', () => {
    expect(
      capabilityKeys({ offline: true, needsNetwork: true, needsAuth: false }),
    ).toEqual(['offline', 'needsNetwork']);
  });
});

describe('engineOptionLabel', () => {
  it('includes capability tags and plugin marker', () => {
    const p: PluginBase = {
      id: 'tiny',
      name: 'Tiny Pine',
      kind: 'engine',
      builtIn: false,
      capabilities: { offline: true },
    };
    const label = engineOptionLabel(p);
    expect(label).toContain('Tiny Pine');
    expect(label).toContain('offline');
    expect(label).toContain('plugin');
  });

  it('built-in without caps is just name', () => {
    const p: PluginBase = {
      id: 'server',
      name: 'Server-Side',
      kind: 'engine',
      builtIn: true,
    };
    expect(engineOptionLabel(p)).toBe('Server-Side');
  });
});
