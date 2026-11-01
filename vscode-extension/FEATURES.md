# PYNE VS Code Extension — Feature Support Matrix

Extension `hoox-sh.pyne` (this repo: `vscode-extension/`). The extension has two
independent subsystems:

1. **Language server (`pyne-lsp`)** — a local stdio process spawned from your
   Python environment (`pip install "hoox-pyne[lsp]"`). It never calls a backend.
2. **Pro API client** — plain `fetch` calls against a configurable backend
   (`PYNE: Run on Pro` → `POST /run`, `PYNE: Test Backend` → `GET /health`).

Deployment modes:

| Mode | How | Auth |
| --- | --- | --- |
| **Hosted Pro (remote)** | `pynescript.backend.useHosted=true` → `https://pynescript.online` | Pro API key required (`pynescript.pro.apiKey`) |
| **Self-hosted local** | Flask Pro API on `http://127.0.0.1:5002` (`make run`, `make docker-up`, or `PYNE: Start Backend`) | No key for `POST /run` (free-tier endpoint); key accepted if set |
| **Self-hosted remote** | Same Flask Pro API on your own host (`pynescript.backend.url`) | Same as local (key optional; recommended if exposed) |
| **Self-hosted edge** | [`pyne-worker`](https://github.com/jango-blockchained/pyne-worker) on Cloudflare — `POST /run`, `/health`, `/scripts`, `/cron/*` | Tenant `Bearer hx_live_…` key when auth is enabled on the worker |
| **None** | No backend configured | — |

Legend: ✅ supported · ⚠️ partial / conditional · ❌ not available · — not applicable (the extension never calls it)

## Feature matrix

| Functionality | Hosted Pro (key) | Self-hosted local | Self-hosted remote | Self-hosted edge | No backend |
| --- | --- | --- | --- | --- | --- |
| Pine grammar highlighting (`.pyne` / `.pine`) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Color themes (`pyne-volt`, `hoox-signal`, `axis-void`) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Snippets (declaration + builtin) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Diagnostics — parse + lint (pull + push) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Diagnostics — style / semantic (opt-in) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Completion (+ resolve, snippets, user symbols) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Hover cards (builtin metadata, user symbols) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Signature help while typing | ✅ | ✅ | ✅ | ✅ | ✅ |
| Definition / references / rename (+ prepare) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Document + workspace symbols | ✅ | ✅ | ✅ | ✅ | ✅ |
| Document highlight / linked editing | ✅ | ✅ | ✅ | ✅ | ✅ |
| Semantic tokens (full + range) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Folding / selection range | ✅ | ✅ | ✅ | ✅ | ✅ |
| Document color swatches (`#hex`) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Document links (+ resolve) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Inlay hints — parameter names | ✅ | ✅ | ✅ | ✅ | ✅ |
| Inlay hints — inferred types | ❌ removed | ❌ removed | ❌ removed | ❌ removed | ❌ removed |
| Formatting (document / range / on-type / format-on-save) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Convert to v6 (code action + command) | ✅ | ✅ | ✅ | ✅ | ✅ |
| PYNE: Restart Server / Show LSP Output / Show LSP Command | ✅ | ✅ | ✅ | ✅ | ✅ |
| PYNE: Install Language Server (`hoox-pyne[lsp]`) | ✅ | ✅ | ✅ | ✅ | ✅ |
| **PYNE: Run on Pro** (`POST /run`, mode `auto`) | ✅ key required | ✅ no key needed | ✅ key optional | ✅ tenant key when auth on | ❌ |
| **PYNE: Test Backend** (`GET /health`) | ✅ | ✅ | ✅ | ✅ (worker `/health`) | ❌ |
| PYNE: Install Backend (`hoox-pyne[pro,lsp]`) | — not needed | ✅ | ⚠️ installs into the local env only | ⚠️ installs into the local env only | ⚠️ installs, but nothing to start automatically |
| PYNE: Start Backend (`python -m backend.app`) | ❌ blocked by `useHosted` | ✅ | ❌ backend runs elsewhere | ❌ backend runs elsewhere | ✅ (this is how you get one) |
| Real market data, live sessions (`/data/*`)¹ | ✅ key | ✅ key | ✅ key | ❌ no `/data` on worker | ❌ |
| Optimize / backtest / preview endpoints¹ | ✅ key | ✅ | ✅ | ❌ | ❌ |
| Hosted runner (`/scripts`, `/cron/*`)¹ | ✅ key | ✅ admin token to mint | ✅ | ✅ (worker native) | ❌ |

¹ **Not exposed by the extension today** — reachable from the Pro API directly
(AXIS, agents, `curl`) and via PYNE MCP runner/data tools. Listed for completeness
because availability differs per deployment.

### Notes

- All LSP features run **inside the editor** against `pyne-lsp`; no column
  changes for them. The only requirement is a Python env with `hoox-pyne[lsp]`.
- Inferred-type inlay hints were removed entirely (v0.5.3 server, extension
  0.5.3+): the server never annotates declarations. Parameter-name hints remain.
- `PYNE: Run on Pro` sends the full script plus a single synthetic OHLCV bar
  (`mode: auto`) to the configured backend — hosted, local, remote, or edge.
- The hosted backend fronts `/run` with the Pro API key; self-hosted Flask
  `/run` is an open free-tier endpoint. If you expose a self-hosted instance
  publicly, put auth in front of it.
