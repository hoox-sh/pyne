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

// Registers the built-in sources/streams/engines with the registry. Adding
// a new built-in = one import + one registerSource / registerStream /
// registerEngine call here. Third-party plugins can be loaded later via
// `registry.loadPluginFromUrl(url)`.

import { registry } from './registry.js';
import { binanceRest, mockWalk, csvUpload } from './sources/index.js';
import { binanceWs, mockPoll, none } from './streams/index.js';
import { serverEngine, pyodideEngine } from './engines/index.js';

let registered = false;
export function registerBuiltins() {
    if (registered) return;
    registered = true;
    registry
        .registerSource(binanceRest)
        .registerSource(mockWalk)
        .registerSource(csvUpload)
        .registerStream(binanceWs)
        .registerStream(mockPoll)
        .registerStream(none)
        .registerEngine(serverEngine)
        .registerEngine(pyodideEngine);
}

registerBuiltins();
