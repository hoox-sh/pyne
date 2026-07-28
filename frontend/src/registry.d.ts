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

// Type declarations for the frontend modules. Keeps the JS sources
// loosely typed but gives test files and future plugin authors a
// discoverable contract.

export interface Bar {
    time: number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume?: number;
}

export interface FieldSchema {
    type: 'string' | 'number' | 'boolean' | 'select';
    default?: string | number | boolean;
    label?: string;
    description?: string;
    placeholder?: string;
    min?: number;
    max?: number;
    step?: number;
    options?: string[];
}

export type ConfigSchema = Record<string, FieldSchema>;

export interface SourceOpts {
    symbol: string;
    interval: string;
    limit?: number;
    config: Record<string, unknown>;
}
export interface Source {
    id: string;
    name: string;
    kind: 'source';
    description: string;
    configSchema: ConfigSchema;
    fetchHistorical(opts: SourceOpts): Promise<Bar[]>;
}

export interface StreamOpts {
    symbol: string;
    interval: string;
    config: Record<string, unknown>;
    lastBar?: Bar;
    onBar: (b: Bar) => void;
    onError: (e: Error) => void;
    onStatus: (s: { state: 'open' | 'closed'; url?: string }) => void;
}
export interface Stream {
    id: string;
    name: string;
    kind: 'stream';
    description: string;
    configSchema: ConfigSchema;
    start(opts: StreamOpts): () => void;
}

export interface RunResult {
    status: 'success' | 'error';
    plots: (number | null)[];
    series?: Record<string, (number | null)[]>;
    events: Array<{ time: number; type: string; id?: string; price?: number; dir?: string; [k: string]: unknown }>;
    error?: string;
    meta?: { mode?: string; script_id?: string; run_id?: string; ms?: number; count?: number; [k: string]: unknown };
}
export interface EngineOpts {
    script: string;
    bars: Bar[];
    config: Record<string, unknown>;
}
export interface Engine {
    id: string;
    name: string;
    kind: 'engine';
    description: string;
    configSchema: ConfigSchema;
    isReady(): Promise<boolean>;
    run(opts: EngineOpts): Promise<RunResult>;
}

export class Registry {
    registerSource(s: Source): this;
    getSource(id: string): Source | undefined;
    listSources(): Source[];
    registerStream(s: Stream): this;
    getStream(id: string): Stream | undefined;
    listStreams(): Stream[];
    registerEngine(e: Engine): this;
    getEngine(id: string): Engine | undefined;
    listEngines(): Engine[];
    clear(): void;
    summary(): { sources: Array<{ id: string; name: string; description: string }>; streams: Array<{ id: string; name: string; description: string }>; engines: Array<{ id: string; name: string; description: string }> };
}

export const registry: Registry;
export function loadPluginFromUrl(url: string): Promise<Source | Stream | Engine>;
