/**
 * Pure helpers for plugin capability labels (no Solid JSX — safe for bun:test).
 */

import type { PluginBase, PluginCapabilities } from '../plugins/types';

export type CapKey = keyof PluginCapabilities;

export const CAP_META: Record<
  CapKey,
  { label: string; class: string; title: string }
> = {
  offline: {
    label: 'offline',
    class: 'border-accent-2/40 text-accent-2',
    title: 'Works without network',
  },
  needsNetwork: {
    label: 'network',
    class: 'border-accent-3/40 text-accent-3',
    title: 'Requires network access',
  },
  needsAuth: {
    label: 'auth',
    class: 'border-orange/40 text-orange',
    title: 'Requires credentials / API key',
  },
  needsProxy: {
    label: 'proxy',
    class: 'border-text-faint/40 text-text-faint',
    title: 'May need CORS proxy',
  },
};

export function capabilityKeys(caps?: PluginCapabilities | null): CapKey[] {
  if (!caps) return [];
  return (Object.keys(CAP_META) as CapKey[]).filter((k) => caps[k]);
}

export function engineOptionLabel(p: PluginBase): string {
  const caps = capabilityKeys(p.capabilities);
  const tags = caps.length ? ` [${caps.join(', ')}]` : '';
  const extra = p.builtIn === false ? ' · plugin' : '';
  return `${p.name}${tags}${extra}`;
}
