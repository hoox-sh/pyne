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

// Type definitions for the plugin modules. The plugins themselves are
// `.js` so we declare their shapes here for TypeScript consumers
// (registry, tests, future plugin authors).

declare module '../src/sources/index.js' {
    export const binanceRest: import('../src/registry.js').Source;
    export const mockWalk: import('../src/registry.js').Source;
    export const csvUpload: import('../src/registry.js').Source;
}

declare module '../src/streams/index.js' {
    export const binanceWs: import('../src/registry.js').Stream;
    export const mockPoll: import('../src/registry.js').Stream;
    export const none: import('../src/registry.js').Stream;
}

declare module '../src/engines/index.js' {
    export const serverEngine: import('../src/registry.js').Engine;
    export const pyodideEngine: import('../src/registry.js').Engine;
}
