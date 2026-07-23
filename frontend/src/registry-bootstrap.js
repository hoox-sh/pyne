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
