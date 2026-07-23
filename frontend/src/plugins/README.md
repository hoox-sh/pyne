# frontend/src/plugins/ — Example plugins

This directory holds **example plugins** that you can load into the running
PWA via the **Manager → Plugins → Load from URL** dialog.  Each one is a
self-contained ES module that default-exports a plugin object matching the
registry contract.

## Loading examples

The simplest way to try an example:

1. Start the PWA: `make run-frontend`
2. Open `http://localhost:8081`
3. Click **📦 Manager** in the top bar → **Plugins** tab
4. Paste the URL of an example file, e.g.

   ```
   http://localhost:8081/src/plugins/example-coingecko-source.js
   ```

5. Click **Load**. The new plugin appears in the Source dropdown.

You can also host these files anywhere (GitHub, R2, your own server). The
PWA loads them via dynamic `import()`.

## Auto-loading on startup

The Manager tracks installed plugins in `localStorage` under
`pynescript.superchart.plugins.v1`. On startup, the PWA re-imports every
URL in that list, so once you've added an example it'll be there next time
you open the page.

Use **Manager → Export installed** to back up the list, and
**Import…** to restore it on another machine.

## Available examples

| File                              | Kind     | Description                                |
|-----------------------------------|----------|--------------------------------------------|
| `example-coingecko-source.js`     | source   | CoinGecko public market-chart API          |
| `example-tiny-pine-engine.js`     | engine   | In-browser "Tiny Pine" JS DSL              |
| `example-cf-do-stream.js`         | stream   | WebSocket relay via CF Durable Object      |

## Writing your own

A plugin is a JS object with `{ id, name, kind, description, configSchema, ... }`.
`kind` is one of `source`, `stream`, `engine`.

```js
// example-my-source.js
const mySource = {
    id: 'my-source',
    name: 'My Source',
    kind: 'source',
    description: 'A short description that shows up in the Manager.',
    configSchema: {
        apiKey: { type: 'string', default: '', label: 'API key' },
        baseUrl: { type: 'string', default: 'https://example.com', label: 'Base URL' },
    },
    async fetchHistorical({ symbol, interval, config }) {
        // `config` is the per-plugin config object from the Settings dialog.
        // Return an array of { time, open, high, low, close, volume? }.
        const res = await fetch(`${config.baseUrl}/bars?symbol=${symbol}&interval=${interval}`, {
            headers: { 'X-Api-Key': config.apiKey },
        });
        return res.json();
    },
};

export default mySource;
```

The other two plugin contracts:

```js
// Stream: start({ symbol, interval, onBar, onError, onStatus, config }) → stop()
const myStream = {
    id: 'my-stream', kind: 'stream', name: 'My Stream', configSchema: { ... },
    start(opts) {
        const ws = new WebSocket('wss://example.com/stream');
        ws.onmessage = (ev) => {
            const bar = JSON.parse(ev.data);
            opts.onBar({ time: bar.t, open: bar.o, high: bar.h, low: bar.l, close: bar.c, volume: bar.v });
        };
        return () => ws.close();
    },
};

// Engine: run({ script, bars, config }) → { status, plots, events, series?, error? }
const myEngine = {
    id: 'my-engine', kind: 'engine', name: 'My Engine', configSchema: { ... },
    async isReady() { return true; },
    async run({ script, bars }) {
        // do something with the script + bars, return a result
        return { status: 'success', plots: [], events: [], series: {}, meta: {} };
    },
};
```

After the user loads a plugin, the PWA emits a `plugin-loaded` window event.
Drop a file in `src/ui/`, `src/chart.js`, etc. that listens to that event
if you want to extend the UI when a particular plugin is added.

## CORS

If your plugin hits a third-party API that doesn't send CORS headers, the
browser will block the response. Workarounds:

1. **Same-origin proxy** — add a small endpoint to the CF Worker (`/api/proxy?url=…`).
2. **Request a key from the API provider** — most paid APIs allow CORS.
3. **Run offline** — for fully client-side plugins (engines, mock sources),
   this is a non-issue.
