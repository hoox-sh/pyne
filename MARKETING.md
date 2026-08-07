# Marketing & Strategy

> *"Leave the barbed wire to those who still believe in fences."*
> — jango_blockchained

---

## The Pine Script monopoly

TradingView owns Pine Script™. 10+ years, 500+ builtins, millions of users —
and almost no open-source runtimes that execute real strategies end-to-end.
Historically the practical options were:

1. Inside TradingView's browser (20k bar limit, $200/mo Premium)
2. Via webhooks → 3commas/Cryptohopper ($30-150/mo, Pine conversion required)
3. Rewrite everything in Python (Freqtrade, Backtrader)

**PYNE** ([hoox-sh/pyne](https://github.com/hoox-sh/pyne), PyPI **[`hoox-pyne`](https://pypi.org/project/hoox-pyne/)**, import
`pynescript`) is a full open toolchain: parse → evaluate/compile → strategy
events → alerts/webhooks → Pro API / edge workers / AXIS charting. Corpus Runtime
on open-source set01–04 is ~**94.3%** OK — strong real-world coverage, **not** a
claim of bit-identical 100% TradingView platform parity.

---

## What people actually want

| # | Request | Frequency |
|---|---|---|
| 1 | "Run my Pine strategy **outside** TradingView" | 🔥 Daily ask |
| 2 | "Backtest with **more than 20k bars**" | 🔥🔥🔥 |
| 3 | "Webhook Pine signals → exchange **without 3commas**" | 🔥🔥 |
| 4 | "Open-source Pine Script runtime" | 🔥🔥🔥 |
| 5 | "Faster backtesting (TV is slow on complex scripts)" | 🔥🔥 |
| 6 | "Custom data feeds (not just TV's)" | 🔥 |
| 7 | "Strategy tester metrics **programmatically**" | 🔥🔥 |
| 8 | "Free/cheap alternative to TV Premium ($200/mo)" | 🔥🔥🔥🔥 |

Source: Reddit r/algotrading, TradingView forums, GitHub issues, Discord.

---

## The current landscape

```
TradingView (walled garden)
├── Best Pine editor + charts
├── Strategy tester (20k bar limit unless Premium)
├── Webhook out → 3commas/Wundertrading/etc ($20-50/mo extra)
└── ❌ Can't run Pine outside the browser

Open source alternatives
├── Freqtrade — Python, NOT Pine Script (rewrite everything)
├── Backtrader — Python, NOT Pine Script
├── Jesse — Python, NOT Pine Script
└── Full Pine toolchains — rare; **PYNE** is the open stack (parse/eval/compile/LSP/API)

Bridge solutions
├── 3commas / Cryptohopper — expensive, Pine conversion required
├── TradingView webhooks → Zapier → ??? — hacky, unreliable
└── AlgoTest — proprietary, limited Pine support
```

---

## What we built

### PYNE — Python toolchain (this repo: [hoox-sh/pyne](https://github.com/hoox-sh/pyne))
- **Product:** PYNE · **PyPI:** `pip install "hoox-pyne[lsp]"` · **import:** `pynescript`
- Full ANTLR4 grammar for Pine™ v5 + v6 (multiline strings, `export const`, soft keywords)
- ASDL-generated AST + evaluator with broad builtin surface (`ta.*`, strategy, drawing, request, …)
- **Strategy events** (entry/exit/close/cancel/order) + broker depth (OCA, commission, risk)
- **Alert engine** + **L2 webhooks** (`ALERT_WEBHOOK_URL` / `webhook_url` on Pro API + pyne-worker)
- **Numba compile path**: `mode=auto` / interpret / compile, warm-compile + IR cache, disk recovery
- **Interpret ↔ compile plot parity** harness (`scripts/compare_interp_compile.py` + goldens)
- **Series caps** (`PYNE_SERIES_CAP`) + **incremental TA** (sma/ema/rsi/macd/atr/bb/… hot path)
- **Drawing GC** (`max_*_count` on line/box/label/…; package + Pro API + AXIS Pyodide)
- **`fill()` export** for AXIS charting (plot registry + host series metadata)
- CLI (repl, lint, format), **LSP** (`pynescript-lsp`), Flask **Pro API**, Docker
- **VS Code extension PYNE** — `.pyne` / `.pine` / `.pinev5` / `.pinev6` associations
- Corpus Runtime set01–04 ~**94.3%** OK (honest residual: scrape stubs, `runtime.error` demos, foreign `request.*`)

### pine-worker (TypeScript edge port — extra tool in-repo)
- ANTLR4 TS parser (same grammar lineage)
- Zod AST schemas + visitor evaluator
- Builtin modules ported (technical, numeric, strategy, strings, arrays, drawing, plotting, input, alerts, utility)
- R2 + local data providers; chart CSV export
- Parity fixtures against the Python reference
- Wrangler service binding + observability

### pyne-worker (Python CF Worker) — production-grade ✅
- API key auth, rate limits, payload validation, structured logging, 30s wall timeout
- Bar-loop runtime on **pynescript** (aligns with Pro API host surface: inputs, alerts, series export)
- R2 data provider + ingest; trade-worker event forwarding
- Dual-host alert export + outbound webhooks
- Parity / smoke tests green; AGPL on sources

---

## Competitive comparison

| | TradingView | Freqtrade | 3commas | **PYNE / pyne-worker** |
|---|---|---|---|---|
| Run Pine outside TV | ❌ (browser) | ❌ rewrite | ❌ convert | **✅ high corpus OK** |
| Open source | ❌ | ✅ | ❌ | **✅ AGPL** |
| Free to self-host | ❌ ($50-200/mo) | ✅ (your VPS) | ❌ ($30-150/mo) | **✅ (CF free tier / your box)** |
| Edge infra | ❌ | ❌ | ❌ | **✅** |
| Backtest >20k bars | ❌ | ✅ | ❌ | **✅** |
| Programmatic API | ❌ (limited webhooks) | ✅ | ✅ | **✅ Pro API + workers** |
| Alerts → webhooks | ✅ TV alerts | custom | ✅ | **✅ L2 productized** |
| Strategy events → trade | ❌ (manual) | ✅ (custom) | ✅ | **✅ built-in events** |
| Self-hostable | ❌ | ✅ | ❌ | **✅** |
| Multi-strategy batch | ❌ (1 per chart) | ✅ | ✅ | **✅** |

---

## Pricing strategy

### Free (always)
| Component | License |
|---|---|
| **PYNE** (`pyne` / `pynescript`) — full toolchain | AGPL |
| `pine-worker` — TypeScript port | AGPL |
| `pyne-worker` — CF Worker | AGPL |
| ANTLR grammar + ASDL definitions | AGPL |
| All tests, fixtures, parity harness | AGPL |
| CLI + LSP + VS Code extension | AGPL |

### Paid SaaS (managed hosting)
| Tier | Price | Limits |
|---|---|---|
| **Starter** | $9/mo | 1 strategy, 1 symbol, daily backtest |
| **Pro** | $29/mo | 5 strategies, 10 symbols, real-time |
| **Unlimited** | $99/mo | Unlimited, multi-user, priority support |
| **Enterprise** | Custom | SLA, dedicated infra, on-prem |

### Commercial license
Companies that can't use AGPL (legal/compliance) buy a commercial license.
Standard OSS dual-license model (MongoDB, MySQL, Grafana).

### Donations
GitHub Sponsors, ETH tips. Pure cypherpunk patronage.

---

## Why this works financially

| Metric | Estimate |
|---|---|
| Monthly costs (self-hosted SaaS) | ~$20-50 (CF Workers free tier + small DB) |
| Break-even users (Pro tier) | 2 users |
| Ramen profitable ($3k/mo) | ~100 Pro users |
| Full-time sustainable ($6k/mo) | ~200 Pro users |
| Competitive alternative to | TradingView ($200/mo) + 3commas ($30/mo) = **$230/mo** |

**Key insight:** You only need ~100 paid users at $29/mo to hit $35k/yr.
Most solo devs globally can live on that. 500 users and you're comfortable.

---

## The fork risk

> *"Could a team fork my repo and build a bigger SaaS in a quarter?"*

**Realistic assessment:** A team of 2-3 devs could fork `pynescript` + `pyne-worker`,
wrap it in a dashboard, and launch a competing SaaS in **2-4 weeks** (not a quarter).

**Why it won't beat you:**

| Reason | Explanation |
|---|---|
| **AGPL teeth** | Section 13 closes the ASP loophole — forks must open-source their changes |
| **80/20 rule** | Evaluator is 20% of the work. Data pipeline, exchange hooks, billing, dashboard, docs, support, monitoring — that's 80%. You're already building it. |
| **Gravity** | You're the reference. Parity tests run against your Python evaluator. Forks that diverge lose compatibility. |
| **Nobody forks trading infra** | Running reliable trade execution is stressful and thankless. The people who can do it are already building their own stuff. |
| **Cypherpunk win** | If someone builds a better service on top of your code, that's a win for the ethos. The code is free. People use the best service. |

**Real risks (not forks):**

| Risk | Mitigation |
|---|---|
| `workers-py` deprecated by Cloudflare | Port to TS `pine-worker` (already started) |
| Grammar falls out of sync with TV updates | Automate via `hatch run lint:gen-parser` |
| Burnout maintaining it alone | AGPL means community can take over |
| Nobody pays for the SaaS | Keep lean — solo-operable, $9/mo entry |

**The code IS the moat. The evaluator IS the hard part. You already built it.**

---

## The dream stack (self-hosted quant)

```
AXIS (charting PWA)  or  TradingView (chart + alert webhook)
        │
        ▼
  PYNE Pro API / pyne-worker / pine-worker  ← self-host or CF Workers
  (parse · interpret/compile · events · alerts/webhooks)
        │
        ▼
  HOOX trade path / trade-worker  ← CF Workers (free)
  (executes on Binance/Coinbase/…)
        │
        ▼
  Portfolio dashboard  ← CF Pages (free)
```

Self-host the stack or run edge pieces on Cloudflare free tier.
**Infrastructure can be near-zero.** That's something neither TradingView Premium
($200/mo) nor 3commas ($30/mo) can touch.

---

## The ethos

> *"Cypherpunks write code. We know that software can't be destroyed
> and that a widely dispersed system can't be shut down."*
> — Eric Hughes, **A Cypherpunk's Manifesto** (1993)

Pine Script evaluation has been a walled-garden monopoly since TradingView
launched. The grammar was proprietary. The runtime was proprietary. If you
wanted to run Pine outside their browser, you couldn't. Full stop.

This project breaks that. The ANTLR grammar, the ASDL AST, the evaluator
with 500+ builtins, the parity test harness, the CF Worker deployment —
that's real cypherpunk work. Code that decentralizes access to financial
infrastructure.

### The line

| ❌ Wrong (rent-seeking) | ✅ Right (value-add) |
|---|---|
| Closed-source the evaluator | Open-source the evaluator (AGPL) |
| Paywall the core runtime | Free self-host + free basic SaaS |
| API keys that expire monthly | Charge for **managed hosting, not software** |
| Obscure the grammar/parser | Publish everything, let anyone fork |

### The fence metaphor

Most crypto projects build **moats** (proprietary, closed, VCs, tokens).
This project builds **bridges** — anyone can use the software, deploy it
themselves, verify the code, fork it if you disappear. That's the opposite
of a fence.

The barbed wire is what TradingView built around Pine Script.
You're cutting it. Let people run. That's the whole point.

---

## Rating: 9/10

```
┌──────────────────────────────────────────────────────────────────────┐
│  What this fills: the #1 unfilled gap in crypto trading:            │
│  "Run my Pine Script strategies without TradingView or 3commas"    │
│                                                                     │
│  Open toolchain + edge/self-host path + strategy events + alerts. │
│  Corpus Runtime ~94.3% set01–04 — honest, not bit-identical TV.    │
│                                                                     │
│  Rating: 9/10 — docking 1 point for:                               │
│    • Dual-host package Runtime unify residual                       │
│    • Interpret↔compile plot MISMATCH tail + foreign request data    │
│    • Non-dev onboarding still thinner than the engine               │
└──────────────────────────────────────────────────────────────────────┘
```

---

---

## Product portfolio

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   HOOX       │  │    PYNE      │  │    AXIS      │
│              │  │              │  │              │
│ Edge trading │  │ Pine™        │  │ Charting PWA │
│ framework    │  │ toolchain    │  │ (open source)│
│ (TS, AGPL)   │  │ (Py, AGPL)   │  │ (TS, AGPL)   │
└──────────────┘  └──────────────┘  └──────────────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           │
              All open source. All free.
              Charge for managed hosting only.
```

Site: [hoox.sh](https://hoox.sh) · product docs at [hoox.sh/pyne](https://hoox.sh/pyne) /
[hoox.sh/axis](https://hoox.sh/axis).

### HOOX
- Edge-native trading framework on Cloudflare Workers
- Execution, intelligence, security, data, DeFi, tooling modules
- Published at [hoox.sh](https://hoox.sh)

### PYNE (this repo — [hoox-sh/pyne](https://github.com/hoox-sh/pyne))
- Pine Script™ Python toolchain: parser, evaluator, Numba compile, LSP, Pro API
- PyPI **[`hoox-pyne`](https://pypi.org/project/hoox-pyne/)** (live · 0.3.0), import **`pynescript`**, VS Code extension **PYNE** (`.pyne` files)
- pyne-worker (Python CF Worker) + pine-worker (TS edge port, extra tool)
- Product surface: [hoox.sh/pyne](https://hoox.sh/pyne)

### AXIS (sister repo — not in this tree)
- Open-source charting PWA ([jango-blockchained/axis](https://github.com/jango-blockchained/axis))
- Pine integration via PYNE Pro API / Pyodide; `fill()` + drawing export from runtime
- Free to self-host; product surface: [hoox.sh/axis](https://hoox.sh/axis)

### Design consistency
HOOX / PYNE / AXIS share stack DNA and brand language on [hoox.sh](https://hoox.sh)
(layout, components, typography; product accent colors differ).

---

## Action items

- [x] Write `MARKETING.md` (this file)
- [x] Public GitHub repo: [hoox-sh/pyne](https://github.com/hoox-sh/pyne)
- [x] Product docs surface: [hoox.sh/pyne](https://hoox.sh/pyne)
- [ ] Deploy guide: "Deploy pyne-worker in 5 minutes"
- [ ] Honest parity badge (corpus % + what is *not* TV platform parity)
- [ ] SaaS landing page + Stripe checkout (managed PYNE/workers)
- [ ] Commercial license page (email inquiry)
- [ ] GitHub Sponsors profile
- [ ] Reddit/X announcement post
- [ ] Benchmark page: interpret vs compile vs TV oracle (scoped scripts)
- [ ] Portfolio page linking HOOX · PYNE · AXIS
