# AGENT 05 — Backend API, Runtime Host, Auth & Services

**Date:** 2026-08-10  
**Scope:** `backend/app.py`, `runtime.py`, `evaluator.py`, `series.py`, `alert_forwarder.py`, `backend/api/*`, `backend/middleware/*`, `backend/services/*`, `backend/requirements.txt`  
**Method:** Security-first deep read + targeted greps (`eval`/`exec`/`shell`/`pickle`/CORS/secrets/TODO). Read-only; no code changes.  
**Stack note:** Pro API is **Flask** (sync), not FastAPI — modernization notes reflect that reality.

---

## Executive summary

The Pro API has absorbed several solid fixes from the **2026-07-05 audit** (5 MB body cap, fail-closed admin minting, hash-only SQLite/Redis stores, restricted CORS defaults, hand-rolled request schemas on free `/run`). The **runtime host** (`Runtime` + `CustomEvaluator` + series cap policy) is the strongest subsystem: clear interpret/compile/auto boundary, JSON-safe export, structured `error_kind`, and thoughtful performance/correctness work (lazy calendar, OHLCV pack cache, plot columnar capture).

**Residual risk is concentrated on the free, unauthenticated compute surface and outbound HTTP.** Any client can `POST /run`, `/run/batch`, `/compile/prewarm`, open `/ws/run`, or supply a `webhook_url` that the server will POST to. There is **no per-IP rate limit, bar-count cap, concurrency gate, or SSRF denylist**. Auth protects only preview/backtest/usage; free-tier keys are effectively unlimited (`calls_limit=0` ⇒ infinite). JSON key store still persists **raw secrets**. Preview/backtest declare schemas but **do not validate** bodies; quick backtest **ignores the Pine script**.

Overall backend quality is good for a product demo/API host, but **production exposure of free `/run` + client webhooks is high risk**.

---

## Critical

### C1 — Unauthenticated compute DoS (free `/run`, batch, prewarm, WebSocket)

**Severity:** Critical (availability)  
**Evidence:**

```486:500:backend/app.py
@app.route("/run", methods=["POST"])
def run_pine_script():
    """Execute Pine Script with provided data. Free tier endpoint.
    ...
    """
    payload: dict[str, Any] = dict(request.get_json(silent=True) or {})
    ...
    body, status = execute_run_payload(payload)
```

```651:695:backend/app.py
@app.route("/run/batch", methods=["POST"])
def run_pine_script_batch():
    ...
    # max 8 scripts — no bar-count or script-size limits beyond MAX_CONTENT_LENGTH
```

```503:553:backend/app.py
@app.route("/compile/prewarm", methods=["POST"])
def compile_prewarm():
    ...
    for item in scripts_raw[:16]:  # hard cap on script count only
```

```556:648:backend/app.py
@sock.route("/ws/run")
def ws_run(ws):
    ...
    body, _status = execute_run_payload(payload)
```

**Why:** `MAX_CONTENT_LENGTH = 5 * 1024 * 1024` (`app.py:64–67`) stops multi-GB bodies but **not** pathological work: dense OHLCV near 5 MB, `mode=compile` Numba cold start, multi-script batch (×8), concurrent WebSocket runs, or prewarm with 16 sources. Sync Flask workers block end-to-end; one client can pin all gunicorn workers. No request timeout, no max bars, no queue, no IP throttle.

**Impact:** Full service outage / bill spike on Cloud Run.

**Remediation (priority):**

1. Cap bars (e.g. 5k–20k) and script chars; reject oversize with 413/400.
2. Per-IP / global concurrency + token-bucket rate limits on free paths.
3. Optional API key or CAPTCHA for public demos; separate internal compile prewarm from public.
4. Gunicorn/worker hard timeouts + circuit breaker.

---

### C2 — SSRF via client-controlled `webhook_url` on free `/run`

**Severity:** Critical (SSRF / internal network pivot)  
**Evidence:**

```390:401:backend/app.py
        wh = validated.get("webhook_url") or ""
        alert_fwd = maybe_forward_run_alerts(
            alerts=resp.get("alerts"),
            ohlcv=ohlcv if isinstance(ohlcv, list) else None,
            webhook_url=wh if isinstance(wh, str) else None,
            enable_forward=bool(validated.get("forward_alerts", True)),
```

```58:68:backend/alert_forwarder.py
def normalize_webhook_url(url: Any) -> str | None:
    ...
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return s
```

```134:149:backend/alert_forwarder.py
def http_post_json(url: str, body: dict[str, Any], *, timeout: float = 10.0) -> int:
    ...
        with urllib.request.urlopen(req, timeout=timeout) as resp:
```

**Why:** Any unauthenticated caller can force the API process to HTTP(S) POST to **arbitrary** hosts, including:

- Cloud metadata (`169.254.169.254`, `metadata.google.internal`)
- RFC1918 / link-local / localhost services
- Other tenants on the same VPC

Scheme check only; **no blocklist, no DNS rebinding guard, no allowlist**. Response meta echoes `"url": webhook_url` (`alert_forwarder.py:171`), confirming destination. Batch path also forwards (`app.py:800–813`). Default `forward_alerts=True` (`schemas.py:73`).

**Impact:** Cloud credential theft, internal port scanning, webhook spam amplification.

**Remediation:**

1. Disable client `webhook_url` in multi-tenant prod; allow only `ALERT_WEBHOOK_URL` env (server-side).
2. If client URLs must stay: strict allowlist (Discord/Slack host patterns) + block private/link-local/metadata IP ranges after DNS resolve; HTTPS-only.
3. Require auth for any outbound webhook feature.

---

## High

### H1 — JSON key store persists raw API secrets

**Evidence:** `backend/middleware/auth.py:150–151, 202–213` — JSON backend uses raw key as object key and writes it to disk. Docs admit “dev convenience only” (`auth.py:150–151`; `docs/pyne/devops/security.mdx`).

**Impact:** File leak / volume snapshot exposes all live keys. Default `STORE_BACKEND` is `json` (`auth.py:337`).

**Remediation:** Default prod to `sqlite` or `redis`; migrate JSON to hash-only; refuse raw-key persistence when `FLASK_ENV=production` / `ENV=prod`.

---

### H2 — Free tier is unlimited; monthly quota is soft and non-atomic

**Evidence:**

```108:114:backend/middleware/auth.py
_TIER_LIMITS = {
    "free": 0,
    "hobby": 5_000,
    ...
}
```

```72:80:backend/middleware/auth.py
    def calls_remaining(self) -> int | float:
        if self.calls_limit == 0 or self.calls_limit == float("inf"):
            return float("inf")
```

```99:105:backend/middleware/auth.py
    def increment_calls(self, count: int = 1) -> None:
        self.calls_used += count
        ...
        store.persist_usage(self)
```

SQLite/Redis `update_calls` is absolute SET of `calls_used`, not `HINCRBY` / atomic increment (`key_store_sqlite.py:147–153`, `key_store_redis.py:113–126`). Multi-worker race undercounts usage → **quota bypass**.

**Remediation:** Give free a real monthly/day limit; atomic increment; optional burst rate limit independent of monthly counters.

---

### H3 — API keys accepted via query string

**Evidence:** `auth.py:386` — `raw_key = request.args.get("api_key", "")` when `Authorization` is absent.

**Impact:** Keys land in access logs, CDN logs, browser history, `Referer` leaks.

**Remediation:** Header-only in prod; deprecate query param with warning then reject.

---

### H4 — No effective key revocation

**Evidence:** `APIKey.is_active()` always returns `True` (`auth.py:66–68`). `revoke_key` deletes rows but no API route uses it; no `revoked` flag.

**Impact:** Compromised keys live until manual DB edit.

**Remediation:** Admin revoke endpoint + `is_active`/`revoked_at`; short-lived keys or rotation.

---

### H5 — Git OAuth device-flow proxy is open and unauthenticated

**Evidence:** `backend/api/git_oauth.py:202–278` — free `POST /api/git/oauth/device/start|poll`; accepts body `clientId`; returns `access_token` to caller.

**Impact:** Abuse as open OAuth poller; token traffic through your host; no rate limit; attacker can burn GitHub rate limits against a client id.

**Remediation:** Rate limit by IP; optional shared secret with AXIS; never log tokens; consider origin checks.

---

### H6 — Free `/run` can drive server-side market data with client credentials

**Evidence:** `schemas.py:64–65` (`data_source`, `data_options` with `api_key`); `app.py:299–306`; `pynescript/util/data.py:663–684` (ccxt/yahoo/alphavantage with `opts.get("api_key")`, `secret`, `password`).

**Impact:** Unauthenticated clients turn the API into an open proxy for third-party APIs (cost, ToS, credential laundering). Not classic SSRF but similar abuse class.

**Remediation:** Restrict `data_source` to chart/mock on free endpoints; require Pro key for external providers; never accept client exchange secrets on multi-tenant hosts.

---

### H7 — CORS “free path” reflects any browser Origin

**Evidence:**

```108:114:backend/app.py
_FREE_CORS_PATH_PREFIXES = (
    "/",
    "/run",
    "/compile",
    "/lsp/",
    "/ws/",
)
```

```160:168:backend/app.py
    if _path_is_free_cors(path) or _origin_allowed(origin):
        resp.headers["Access-Control-Allow-Origin"] = origin
```

**Impact:** Any website can call free endpoints from a victim’s browser (CSRF-style resource burn / webhook SSRF via browser). Intentional for AXIS VPS UX, dangerous if public internet-facing.

**Remediation:** Tight allowlist in prod; keep open reflection only for local-dev flag.

---

## Medium

### M1 — Preview / backtest schemas defined but unused

**Evidence:** `PREVIEW_*` / `BACKTEST_QUICK` / `CREATE` schemas in `schemas.py:98–121`; `preview.py` uses raw `request.get_json()` (`preview.py:71–75, 155–159, 308–314`).

**Impact:** Unknown fields, wrong types, unbounded `mock_bars` / array sizes (within body limit); inconsistent with `/run` S9 hardening.

**Remediation:** Route all Pro bodies through `validate(...)`.

---

### M2 — Quick backtest ignores Pine script (correctness / product honesty)

**Evidence:**

```134:165:backend/services/backtest.py
    try:
        tree = parse(script, mode="exec")
        _ = tree
    except Exception:
        pass
    ...
    # Hardcoded MA cross + pseudo-RSI signals — not evaluator/strategy engine
```

Docstring claims “full Pine Script evaluator would be used” in production (`backtest.py:112–113`) but API still sells “quick backtest” (`preview.py:277–307`).

**Impact:** Misleading Pro feature; users trust fake metrics.

**Remediation:** Wire `Runtime` + strategy events, or rename to “demo MA-cross simulator” and document clearly.

---

### M3 — Broken monthly reset timestamp

**Evidence:** `auth.py:92–97` — `_get_reset_time` builds a nonsensical `struct_time` from `now // (32 * 86400)` math; not calendar month start.

**Impact:** Clients show wrong `reset_at`; billing UX broken (not a direct auth bypass).

**Remediation:** Use `datetime` UTC first-of-next-month.

---

### M4 — `hmac.compare_digest` can raise on length mismatch

**Evidence:** `auth.py:472` — `hmac.compare_digest(provided, expected)` without equal-length precheck.

**Impact:** Wrong-length admin token may 500 instead of 403 (implementation-dependent); noisy logs / possible error-based oracle.

**Remediation:** Hash both sides to fixed length, or catch `ValueError` → 403.

---

### M5 — Private LAN + hardcoded demo IP always allowed in CORS

**Evidence:** `PRIVATE_HTTP_RE` always appended (`app.py:79–86, 100–101`) including `162.254.38.194`.

**Impact:** Broader cross-origin attack surface than product hosts alone; demo IP should be env-only.

---

### M6 — No bar/schema validation on OHLCV payload

**Evidence:** `schemas.py:56–58` — “bar-list check loose”; `execute_run_payload` only checks non-empty (`app.py:289–294`).

**Impact:** Malformed bars waste CPU; non-dict rows padded to zeros (`runtime.py:506–513`); large responses OOM client/server.

**Remediation:** Max bars; optional per-bar keys; cap response series size.

---

### M7 — Dual CORS implementation (flask-cors + custom middleware)

**Evidence:** `CORS(...)` at `app.py:172–180` plus `_cors_preflight` / `_ensure_cors_headers` (`183–197`).

**Impact:** Divergent behavior; harder to reason about credentials/preflight; free-path override can surprise operators who only set `ALLOWED_ORIGINS`.

---

### M8 — Usage tracking incomplete for non-tuple responses

**Evidence:** `track_usage` (`auth.py:416–430`) increments always when result is not a `(response, status)` tuple — Flask `jsonify` returns `Response` with status 200 even on some error paths if handler returns bare Response with 4xx via second form inconsistently. Preview errors return tuples correctly; success paths return bare `jsonify` → always counted (OK). Failures that return only `jsonify(..., 500)` as single Response with status on Response object may still increment (depends on Flask return shape — preview uses `return jsonify(...), 500` tuples).

**Note:** Low practical impact today; fragile if handlers change.

---

### M9 — Health endpoint information disclosure

**Evidence:** `_health_payload` lists endpoints, compile cache dir, prewarm flags (`app.py:440–476`).

**Impact:** Low; helps attackers map free surfaces and disk layout. Prefer minimal public health; detailed readiness on internal path.

---

### M10 — Execution errors return exception text to clients

**Evidence:** `app.py:330–349` maps `result["error"]` into HTTP 500 JSON `message`.

**Impact:** Internal paths / stack-ish messages may leak (depends on Runtime formatting). Prefer generic client message + server log correlation id.

---

## Low

### L1 — `requirements.txt` is minimal Flask stack; no auth/rate-limit libs

**Evidence:** `backend/requirements.txt` — flask, flask-cors, flask-sock, numpy, numba, matplotlib, gunicorn, redis. No limits, pydantic, or OpenAPI.

### L2 — WebSocket `/ws/run` has no auth, frame size policy, or idle timeout in app code

Relies on underlying simple-websocket / reverse proxy.

### L3 — Matplotlib Agg used correctly with `plt.close` (good); still CPU-heavy on Pro preview under auth only

### L4 — Hardcoded product URLs in error messages (`pynescript.ai`) — fine, not security

### L5 — Process-global host compile / fail caches (`runtime.py:155–161`) unbounded only by MAX — OK; not multi-tenant isolated (same process is single tenant)

### L6 — `is_active` always true documented as “revocation hook” — incomplete feature, not a surprise bypass of missing revoke API

### L7 — LSP free endpoints unbounded source size (within 5 MB) — lighter than `/run` but still free CPU

---

## Documentation quality

| Area | Assessment |
|------|------------|
| Package / module docstrings | **Strong** — `backend/__init__.py`, `runtime.py`, `series.py`, `auth.py`, `alert_forwarder.py`, `git_oauth.py` explain purpose, env flags, backends |
| Runtime host contract | **Strong** — mode semantics, error kinds, packing contract, compile envelope parity comments |
| Prior audit breadcrumbs | **Good** — S1 body limit, S3 admin fail-closed, S7/S8 CORS, S9 schemas, S11 localhost bind |
| Security docs | **Good** at `docs/pyne/devops/security.mdx` but **incomplete** vs free `/run` DoS + webhook SSRF (diagram implies AUTH before `/run`; free run skips auth) |
| Pro services | **Weak** — backtest docs overclaim; preview endpoint docstrings OK but no schema enforcement |
| Inline comments in hot paths | **High density** in `runtime.py` / `evaluator.py` (performance rationale) |

**Doc gaps to fix:**

1. Explicit threat model: free vs Pro surfaces.
2. Document `webhook_url` SSRF risk and prod recommendations.
3. Document default JSON store raw-key danger.
4. Align security.mdx flowchart with unauthenticated `/run`.

---

## Modernization

| Topic | Current | Recommendation |
|-------|---------|----------------|
| Framework | Sync Flask + flask-sock | Accept for now, **or** FastAPI + Starlette WS with async workers for I/O-bound webhooks |
| Lifespan | Module-level app + optional prewarm | Explicit app factory + gunicorn post-fork prewarm hook |
| Validation | Hand-rolled schemas (good discipline) | Pydantic v2 models for OpenAPI + nested OHLCV validation |
| Streaming | Single JSON blob for large series | Optional NDJSON / chunked WS progress frames |
| Rate limits | Monthly counters only | Redis token bucket + concurrency semaphore |
| Outbound HTTP | `urllib` sync | `httpx` with SSRF-safe transport + timeouts |
| Typed errors | Runtime `error_kind` good | Shared API error envelope + request_id |
| Metrics | Minimal logging | Prometheus: run latency, bars, mode, webhook failures |
| Auth | Custom API keys | Optional OIDC later; keep keys for machine clients |

---

## Design quality — API / runtime boundary

**Strengths**

- Clear split: HTTP (`app.py` / blueprints) → `execute_run_payload` → `Runtime.run` → interpret/compile.
- Runtime is library-usable outside Flask (CLI/showcase).
- Structured errors (`ERROR_KIND_*`, `error_bar`) preserve backward-compatible `error` string.
- OHLCV packing contract shared between interpret and compile (`_pack_ohlcv_columns` docstring at `runtime.py:473–485`).
- Alert forwarding isolated in `alert_forwarder.py` with injectable `http_post` (testable).
- Pluggable key stores with protocol (`_HashBackend`).

**Weaknesses**

- Free product policy (no auth on heavy endpoints) is a **product/security boundary leak**, not a layering bug.
- `preview.py` reimplements indicator TA instead of Runtime.
- `backtest.py` is a parallel toy engine, not the strategy broker.
- Global mutable caches and DrawingRegistry reset in-process — fine for single-tenant workers, weak for multi-tenant isolation.
- No job abstraction (timeout, cancel, progress) around `Runtime.run`.

**Boundary score: 7.5/10** (runtime host excellent; HTTP policy and Pro service honesty drag the overall design).

---

## Scorecard

| Dimension | Score (1–10) | Notes |
|-----------|-------------:|-------|
| Security (auth, SSRF, secrets) | **4.5** | Good admin fail-closed + body cap; free compute + webhook SSRF dominate |
| Correctness (runtime host) | **8.0** | Solid packing, error kinds, plot capture; backtest service not correct |
| Correctness (API services) | **5.0** | Preview partial; backtest ignores script; schemas inconsistently applied |
| Design (API ↔ runtime) | **7.5** | Clean host; free/pro policy muddies threat model |
| Code quality / maintainability | **7.5** | Typed-ish modern Python, good structure; large `runtime.py` |
| Modern techniques | **5.5** | Sync Flask, hand schemas, no streaming/rate-limit stack |
| Inline documentation | **8.0** | Excellent runtime/auth docs; security product docs lag reality |
| **Overall (scoped backend)** | **6.5** | Ready for controlled/self-host demos; harden before public multi-tenant |

---

## Prioritized recommendations

### P0 (before public multi-tenant)

1. **C2** — Disable or allowlist `webhook_url`; block private/metadata IPs.
2. **C1** — Bar caps + IP rate limits + worker timeouts on `/run`, `/run/batch`, `/ws/run`, `/compile/prewarm`.
3. **H1** — Default `STORE_BACKEND=sqlite` (or redis) in prod images; never persist raw keys.
4. **H6** — Free path: chart/mock data only.

### P1 (short term)

5. **H2/H4** — Real free quotas, atomic increments, revoke API.
6. **H3** — Header-only API keys.
7. **H5** — Rate-limit git OAuth proxy.
8. **H7** — Prod CORS allowlist only (no free-path Origin reflection).
9. **M1** — Enforce schemas on preview/backtest.

### P2 (product integrity)

10. **M2** — Real Runtime-backed backtest or honest rename.
11. **M3/M4** — Fix reset time + constant-time admin compare.
12. OpenAPI + request IDs + metrics.
13. Align `docs/pyne/devops/security.mdx` with free-run threat model.

### P3 (modernization)

14. Optional FastAPI migration or keep Flask and add `flask-limiter` + redis.
15. Nested Pydantic models for OHLCV; streaming results for large charts.
16. Split `runtime.py` into pack / interpret / compile modules for maintainability.

---

## Evidence index (key files)

| Path | Role |
|------|------|
| `/mnt/data/home/jango/Git/pynescript/backend/app.py` | Flask app, CORS, free `/run`, WS, auth routes, body limit |
| `/mnt/data/home/jango/Git/pynescript/backend/runtime.py` | Runtime host (interpret/compile/auto) |
| `/mnt/data/home/jango/Git/pynescript/backend/evaluator.py` | Plot-capturing evaluator |
| `/mnt/data/home/jango/Git/pynescript/backend/series.py` | PineSeries + list cap policy |
| `/mnt/data/home/jango/Git/pynescript/backend/alert_forwarder.py` | Webhook delivery (SSRF surface) |
| `/mnt/data/home/jango/Git/pynescript/backend/middleware/auth.py` | Keys, tiers, decorators |
| `/mnt/data/home/jango/Git/pynescript/backend/middleware/key_store_sqlite.py` | Hash-only SQLite |
| `/mnt/data/home/jango/Git/pynescript/backend/middleware/key_store_redis.py` | Hash-only Redis |
| `/mnt/data/home/jango/Git/pynescript/backend/middleware/schemas.py` | Request validation |
| `/mnt/data/home/jango/Git/pynescript/backend/api/preview.py` | Pro chart/backtest (auth) |
| `/mnt/data/home/jango/Git/pynescript/backend/api/lsp_http.py` | Free LSP bridge |
| `/mnt/data/home/jango/Git/pynescript/backend/api/git_oauth.py` | Free OAuth device proxy |
| `/mnt/data/home/jango/Git/pynescript/backend/services/backtest.py` | Simplified (non-Pine) backtest |
| `/mnt/data/home/jango/Git/pynescript/backend/services/chart_renderer.py` | Matplotlib PNG base64 |
| `/mnt/data/home/jango/Git/pynescript/backend/requirements.txt` | Flask stack deps |

---

## Grep summary (security-relevant)

| Pattern | Result in `backend/` |
|---------|----------------------|
| `eval(` / `exec(` / `pickle` / `shell=True` | **None** in backend package (Pine via AST evaluator, not Python `eval`) |
| `urlopen` | `alert_forwarder.py`, `git_oauth.py` (outbound) |
| CORS `*` | Supported via `ALLOWED_ORIGINS=*`; free paths reflect any Origin |
| Secrets handling | `secrets.token_urlsafe`, SHA-256 key hash, admin `hmac.compare_digest` |
| TODO/FIXME | Essentially none; audit comments reference 2026-07-05 findings |

---

## Conclusion

Treat the **runtime host** as production-capable library code with good documentation and solid engineering. Treat the **public Flask surface** as intentionally open for AXIS demos: that openness creates **Critical** DoS and SSRF issues if the same process is multi-tenant on the public internet. Auth middleware is well-designed for Pro routes but **does not gate the expensive free surface**, and free-tier economics (`calls_limit=0`) undermine metering even when keys are used.

**Recommended posture:** self-host / private network for free compile UX; harden webhooks and quotas before SaaS; keep Runtime as the single execution engine and retire the toy backtest path or rebind it.
