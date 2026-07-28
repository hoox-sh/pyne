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
 * Transport classification + Connection HUD helpers.
 */

import type { ConnState, PlaneTelemetry, TransportClass } from '../store/types';
import type { PluginCapabilities } from '../plugins/types';

export function idlePlane(
  id: string,
  name: string,
  transport: TransportClass = 'none',
): PlaneTelemetry {
  return {
    id,
    name,
    transport,
    state: 'idle',
    latencyMs: null,
    lastEventAt: null,
    error: null,
  };
}

/** Infer transport from plugin id / capabilities when not declared. */
export function classifyTransport(
  kind: 'source' | 'stream' | 'engine' | 'storage',
  id: string,
  capabilities?: PluginCapabilities | null,
): TransportClass {
  const cap = capabilities as (PluginCapabilities & { transport?: TransportClass }) | null | undefined;
  if (cap?.transport) return cap.transport;
  if (cap?.needsProxy) return 'broker';
  if (cap?.offline && kind === 'engine') return 'local';
  if (cap?.offline && kind === 'stream') return 'local';
  if (cap?.offline && kind === 'source') return 'local';

  const lower = (id || '').toLowerCase();
  if (kind === 'stream') {
    if (lower.includes('mock') || lower.includes('poll')) return 'local';
    if (lower.includes('do') || lower.includes('cf-') || lower.includes('relay')) return 'broker';
    if (lower.endsWith('-ws') || lower.includes('websocket') || lower.includes('wss')) return 'ws';
    return 'ws';
  }
  if (kind === 'source') {
    if (lower.includes('mock') || lower.includes('csv') || lower.includes('upload')) return 'local';
    if (lower.includes('rest') || lower.includes('http')) return 'rest';
    return 'rest';
  }
  if (kind === 'engine') {
    if (lower.includes('pyodide') || lower.includes('local') || lower.includes('tiny')) return 'local';
    return 'rest';
  }
  if (kind === 'storage') {
    if (lower === 'local' || lower.includes('idb')) return 'local';
    if (lower.includes('git')) return 'rest';
    if (lower.includes('cloud')) return 'rest';
    return 'local';
  }
  return 'none';
}

export function transportLabel(t: TransportClass): string {
  switch (t) {
    case 'ws':
      return 'WS';
    case 'rest':
      return 'REST';
    case 'local':
      return 'LOCAL';
    case 'broker':
      return 'BROKER';
    default:
      return '—';
  }
}

export function connDotClass(state: ConnState): string {
  switch (state) {
    case 'open':
      return 'bg-accent-2 shadow-[0_0_6px_var(--color-accent-2)]';
    case 'connecting':
    case 'degraded':
      return 'bg-orange animate-pulse';
    case 'error':
      return 'bg-red';
    case 'closed':
      return 'bg-text-faint';
    default:
      return 'bg-border';
  }
}

export function formatLatency(ms: number | null | undefined): string {
  if (ms == null || !Number.isFinite(ms)) return '—';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function formatTickAge(at: number | null | undefined, now = Date.now()): string {
  if (at == null) return '—';
  const sec = Math.max(0, (now - at) / 1000);
  if (sec < 1.5) return 'now';
  if (sec < 60) return `${sec.toFixed(0)}s`;
  return `${Math.floor(sec / 60)}m`;
}

const MAX_SAMPLES = 24;

export function pushSample(samples: number[], ms: number): number[] {
  const next = samples.length >= MAX_SAMPLES ? samples.slice(samples.length - MAX_SAMPLES + 1) : samples.slice();
  next.push(ms);
  return next;
}
