# Azure VM deploy — PYNE stack (2026-11-18)

Seat: oo-spec-2 (Deploy). Target: fresh Azure VM `azureuser@172.174.232.254`
(Ubuntu 24.04.5 LTS, 2 vCPU, 7.7 GB RAM, 29 GB disk, 26 GB avail).
Runbook: steps A (inspect/prep) + B (ship stack) as routed by the Chief.
Not done, by design: nginx install/reload, certbot, DNS changes — parked
pending the operator's DNS decision. Nothing is public; all service ports
are loopback-only.

## Step A — VM prep (all commands over ssh as azureuser, sudo -n)

| Check | Result |
|---|---|
| OS | Ubuntu 24.04.5 LTS (noble) |
| Passwordless sudo | `sudo -n true` → SUDO_OK (exit 0) |
| Packages installed | `docker.io` 29.1.3, `docker-compose-v2` 2.40.3 (found in archive; `docker-compose-plugin` fallback NOT needed), `nginx` 1.24.0, `git` 2.43.0, `rsync` 3.2.7, `certbot` 2.9.0, `ca-certificates`, `curl`, `python3-certbot-nginx` |
| `docker compose version` | Docker Compose version 2.40.3+ds1-0ubuntu1~24.04.1 |
| `nginx -v` | nginx/1.24.0 |
| Service | `sudo systemctl enable --now docker` OK; `azureuser` added to `docker` group (effective on next login; `sudo docker` used until then) |

## Step B — Ship

1. rsync (exit 0): workstation → VM `/home/azureuser/pynescript/`,
   `--delete`, excludes `.git node_modules .venv tests/data/set0* tests/data/library .env .pytest_cache /dist`.
   Remote tree present (66 entries incl. Dockerfile, compose files, backend/, docs/).
2. `.env` copied with scp (NOT via rsync). Local and remote both 4327 bytes.
   Key NAMES verified present (values never printed): ADMIN_TOKEN, ALLOWED_ORIGINS,
   API_CPUS, API_KEY_STORE, API_KEY_STORE_SQLITE, API_MEM_LIMIT, API_PORT, FLASK_DEBUG,
   GIT_SHA, GUNICORN_*, PYNE_*, REDIS_*, STORE_BACKEND, SESSION_*, TAG.
   Remote perms: `-rw------- azureuser:azureuser` (600). No secret values in this file or logs.
3. Build (VM): `sudo docker compose --profile redis --profile lsp --profile cli -f docker-compose.yml -f docker-compose.prod.yml build`
   → BUILD_EXIT=0. All five images named: `pynescript-api`, `pynescript-cli`,
   `pynescript-mcp`, `pynescript-lsp` (from api target / respective targets) — log at `/tmp/pyne-build.log` (1995 lines).
4. `up -d` (same profiles/files) → all containers created/started; redis reported Healthy before api started (depends_on honored).
5. Health wait loop (15 s polls, all settled at t≈30 s):
   `api` healthy, `datafeed` healthy, `mcp` healthy, `redis` healthy, `lsp` Up (stdio, no healthcheck by design), `cli` Exited(0) (one-shot by design).

## Sanity curls FROM THE VM (127.0.0.1 only)

| URL | Code | Note |
|---|---|---|
| `http://127.0.0.1:5002/` | 200 | API root |
| `http://127.0.0.1:5002/health` | 200 | body: `status: "healthy"`, `version: 0.7.2`, `service: pynescript-pro-api`, `git_sha: "dev"` |
| `http://127.0.0.1:5004/datafeed/health` | 200 | datafeed gateway |
| `http://127.0.0.1:5003/mcp` | 400 | expected nonzero; MCP endpoint rejects bare GET (400/405/406 all acceptable) |

Listen check (`sudo ss -ltn`): 5002, 5003, 5004 bound to **127.0.0.1 only**. Nothing on public NICs.

## Notes / findings

- `/health` reports `git_sha: "dev"` — the build did not pick up a VCS sha
  (GIT_SHA build-arg not propagated into the image metadata). Cosmetic for now;
  pass `GIT_SHA=$(git rev-parse --short HEAD)` at build time next deploy if it matters.
- `pynescript-cli-1` exiting 0 is expected (one-shot container, no long-running process).
- nginx config `deploy/nginx-pynescript.conf` was READ and reported, NOT installed.
  It references domains `pynescript.online` / `www.pynescript.online`, TLS cert paths
  `/etc/letsencrypt/live/pynescript.online/fullchain.pem` and `privkey.pem`, port 80
  (ACME HTTP-01 + 301→https) and 443 ssl. Nothing was installed, reloaded, or renewed;
  no DNS records were touched; no certbot run.

## What remains (not this card)

- nginx install + reload — blocked on operator's DNS decision.
- certbot issuance for pynescript.online — blocked on DNS + nginx :80 ACME path live.
- Public exposure decision (currently loopback-only, nothing public).
- Board card -> Ready for Review; Done is the Checker's call.

## Proof commands (re-checkable)

```bash
ssh -i ~/.ssh/id_rsa azureuser@172.174.232.254 \
  'sudo docker compose --profile redis --profile lsp --profile cli \
     -f /home/azureuser/pynescript/docker-compose.yml \
     -f /home/azureuser/pynescript/docker-compose.prod.yml ps -a'
ssh -i ~/.ssh/id_rsa azureuser@172.174.232.254 \
  'curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5002/health'
```
