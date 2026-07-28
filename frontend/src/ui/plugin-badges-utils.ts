// Copyright (C) 2024-2026 jango_blockchained
//
// This file is part of pynescript.
//
// pynescript is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// pynescript is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
//
// SPDX-License-Identifier: AGPL-3.0-or-later

/**
 * Pure helpers for plugin capability labels (no Solid JSX — safe for bun:test).
 */

import type { PluginBase, PluginCapabilities } from '../plugins/types';

/** Boolean capability flags shown as badges (excludes transport string). */
export type CapKey = 'offline' | 'needsNetwork' | 'needsAuth' | 'needsProxy';

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
  return (Object.keys(CAP_META) as CapKey[]).filter((k) => !!caps[k]);
}

export function engineOptionLabel(p: PluginBase): string {
  const caps = capabilityKeys(p.capabilities);
  const tags = caps.length ? ` [${caps.join(', ')}]` : '';
  const extra = p.builtIn === false ? ' · plugin' : '';
  return `${p.name}${tags}${extra}`;
}
