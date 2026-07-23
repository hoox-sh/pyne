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
