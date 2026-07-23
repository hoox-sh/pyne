# frontend/worker/ — Cloudflare Worker for SuperChart Lite

This Worker provides the **production backend** for the PWA. It can:

- Proxy `POST /api/run` to an external Python backend (Flask) — works today.
- Run Pine scripts in-Worker via Pyodide (not yet implemented, see
  `RUNTIME.md` below).
- Hold **API keys in KV** (with admin-only `X-Admin-Token`).
- Meter usage in KV (per-key, 30-day TTL).
- Persist runs/scripts in **D1** (optional, off by default).
- Cache indicator bundles in **R2** (optional, off by default).
- Relay live datastreams to the browser via a **Durable Object** that opens
  one upstream WebSocket per session and fans it out to N clients.

## Local dev

```bash
cd frontend/worker
npm install
npm run dev      # starts wrangler dev on http://127.0.0.1:8787
```

The PWA's `endpoint` input can be pointed at this URL for an end-to-end
local stack.

## Bindings — provision once

```bash
# KV
wrangler kv namespace create API_KEYS
wrangler kv namespace create USAGE

# D1 (optional)
wrangler d1 create pynescript

# R2 (optional)
wrangler r2 bucket create indicator-bundles

# Durable Objects — migrations are declared in wrangler.toml, apply with:
wrangler deploy
```

Paste the returned IDs into `wrangler.toml`.

## Endpoints

| Path                | Method | Notes                                  |
|---------------------|--------|----------------------------------------|
| `/` or `/health`    | GET    | Health check                           |
| `/api/run`          | POST   | `{ script, data, mode? }` → plots+events |
| `/api/keys?action=create` | POST | `X-Admin-Token` required               |
| `/api/keys?action=validate` | GET | `Authorization: Bearer …` or `?key=` |
| `/api/usage`        | GET    | Per-key usage counter (KV)             |
| `/api/stream`       | WS     | `?session=…&symbol=…&interval=…` (DO)  |

WebSocket: open `wss://<worker>/api/stream?session=…&symbol=BTCUSDT&interval=1m`
and the Worker routes to a Durable Object instance that fans a single
upstream Binance kline stream to N clients.

## Deploy

```bash
# 1) Bindings (one time)
wrangler kv namespace create API_KEYS
wrangler kv namespace create USAGE
# (optional) wrangler d1 create pynescript
# (optional) wrangler r2 bucket create indicator-bundles

# 2) Deploy the Worker
cd frontend/worker
wrangler deploy

# 3) Deploy the PWA as a Pages site
cd ..
wrangler pages deploy . --project-name=pynescript-superchart
```

After deployment, the PWA's `Endpoint` field should be set to the
`*.workers.dev` URL or your custom domain.

## Caching strategy

- `Cache-Control: public, max-age=60` on `/api/run` for identical
  `(script, data_hash)` pairs (deferred — see `RUNTIME.md`).
- Live stream DO: no cache, always forwards.
- `/api/keys` and `/api/usage`: no cache.

## Implementation status

- [x] `/api/run` proxy to EXTERNAL_BACKEND
- [x] `/api/keys` admin endpoint
- [x] `/api/usage` (KV-backed)
- [x] `SessionDO` Durable Object for live streams
- [x] `/api/stream` → DO routing in `src/index.ts`
- [x] In-Worker Python scaffold (`src/pyodide_runtime.ts`, gated by
      `PYODIDE_IN_WORKER=enabled`)
- [ ] Pyodide wheel upload pipeline (see `RUNTIME.md`)
- [ ] Caching layer
- [ ] D1 schema + migrations

See `RUNTIME.md` for the in-Worker Python plan.
