# Prod pro-key mint — BLOCKED, no key created (2026-11-19)

Requested (via Chief, from operator): mint ONE `pro`-tier API key in the production
key store on Azure VM `172.174.232.254` (`/home/azureuser/pynescript`), expected store:
"the same sqlite the API uses". Do not touch anything else.

Result: **not minted. No key was created. No production state was modified.**

## What was run (read-only except one failed mint)

1. `ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new azureuser@172.174.232.254` — OK.
2. `sudo -n docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T api sh -c 'command -v pyne && pyne --version'`
   → `/usr/local/bin/pyne`, `0.7.2`. (Used `sudo -n` so it fails fast instead of hanging on a password prompt.)
3. `... exec -T api pyne key create --tier pro` → **FAILED** before any write:
   `redis.exceptions.ConnectionError: Error 111 connecting to 127.0.0.1:6379. Connection refused`
   (traceback via `backend/middleware/auth.py get_key_store → key_store_redis.py create → pipe.execute`).
   Nothing was written to any store; redis was never reached.
4. Diagnosis (read-only):
   - Container env (names + safe values only): `STORE_BACKEND=redis`,
     `API_KEY_STORE=/data/api_keys.json`, `API_KEY_STORE_SQLITE=/data/api_keys.db`,
     `REDIS_URL` = set (value is `redis://:<redacted>@127.0.0.1:6379/0` — password never printed),
     `ADMIN_TOKEN` = set.
   - Host `.env` key names: contains `REDIS_URL`, `STORE_BACKEND`, `REDIS_PASSWORD` (values not printed; REDIS_URL host = 127.0.0.1 per the container traceback).
   - `docker compose ps`: redis up 3h (healthy), api/datafeed/lsp/mcp up ~1h (api/datafeed/mcp healthy).
   - `/data` inside api container: `cache/ compile-cache/ runner.db* series/ sessions.db*` — **no `api_keys.db`, no `api_keys.json`** (the sqlite store the task named does not exist here).
   - `docker-compose.prod.yml`: api and redis both `network_mode: !reset` onto the `pynescript` bridge; api publishes `127.0.0.1:5002->8080`; redis has **no published ports**, `--protected-mode no`, requirepass from `REDIS_PASSWORD`, and the compose comment says "api reaches it as `redis:6379` over the internal network".
   - `getent hosts redis` inside api container → `172.18.0.5` (resolves fine; only the URL host is wrong).
   - Prod redis healthcheck runs *inside* the redis container, so "healthy" is consistent with being unreachable from the api.

## Root cause

Host `.env` still carries the dev-era `REDIS_URL=redis://:…@127.0.0.1:6379/0` (127.0.0.1 = the api
container's own loopback after the 2026-11 bridge-network rework, card "Fix 3d7d0092"). The prod
compose intends `redis://…@redis:6379/0`. `STORE_BACKEND=redis` in `.env` also overrides the prod
default (`sqlite`), and the sqlite file was never created. The mint failed closed; the API's own
key validation would hit the same refused connection.

## Not done / not changed

- No `.env` edit, no container recreate/restart, no config change, no key minted, no sqlite file created.
- No HTTP request was sent to the production API (auth state unverified — suspected broken, not confirmed).

## Needs (operator decision)

Either
A) set `REDIS_URL=redis://:<REDIS_PASSWORD>@redis:6379/0` in `.env` and recreate the api container
   (`docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d api`), then mint; or
B) set `STORE_BACKEND=sqlite` (prod default; `API_KEY_STORE_SQLITE=/data/api_keys.db`) and recreate api, then mint; or
C) explicitly authorize minting into a non-API-backed target (not recommended).

Note: `POST /auth/*` behaviour until the store is reachable is unverified; worth checking right after the fix.

Approval `7b99d3d6-555e-42a4-ac44-1901dead9ef4` (action=create, resource=production/api-key,
decidedBy=policy "allow") covers the mint once a reachable, API-backing store is chosen.
