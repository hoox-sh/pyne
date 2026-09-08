# PYNE

**Independent open toolchain for the Pine Script™ language** — formal grammar, algebraic AST, dual-engine bar-loop runtime, language server, and HTTP evaluation surface. Part of the [HOOX](https://hoox.sh) open trading stack.

**0.4.4** · PyPI [`hoox-pyne`](https://pypi.org/project/hoox-pyne/) · import `pynescript` · CLIs `pyne` · `pyne-lsp` (aliases: `pynescript` · `pynescript-lsp`)

<div align="center">

![FAILURE IS LOCAL. RESILIENCE IS GLOBAL.](brand/png/tagline-failure-is-local-github-1280x640-br-split-dark.png)

[![CI](https://img.shields.io/github/actions/workflow/status/hoox-sh/pyne/ci.yml?branch=main&style=flat-square&label=CI)](https://github.com/hoox-sh/pyne/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/hoox-sh/pyne/graph/badge.svg)](https://codecov.io/gh/hoox-sh/pyne)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![PyPI](https://img.shields.io/pypi/v/hoox-pyne?style=flat-square&logo=pypi&logoColor=white)](https://pypi.org/project/hoox-pyne/)
[![License](https://img.shields.io/github/license/hoox-sh/pyne?style=flat-square)](LICENSE)

**Website:** [hoox.sh/pyne](https://hoox.sh/pyne) · **Docs:** [hoox.sh/pyne/docs](https://hoox.sh/pyne/docs) · **Source:** [github.com/hoox-sh/pyne](https://github.com/hoox-sh/pyne)

**Stack:** ⚡ [HOOX](https://github.com/hoox-sh/hoox) · 🐍 [**PYNE**](https://github.com/hoox-sh/pyne) *(this repo)* · 📊 [AXIS](https://github.com/hoox-sh/axis)

</div>

> **Pine Script™** and **TradingView®** are trademarks of [TradingView, Inc.](https://www.tradingview.com/). **Cloudflare®** is a trademark of Cloudflare, Inc.  
> PYNE is an **independent, unofficial** implementation. It is not affiliated with, authorized by, sponsored by, or endorsed by TradingView, Inc. or Cloudflare, Inc., and is not an official TradingView® product, service, or platform substitute.  
> Language references are for interoperability and compatibility documentation only. PYNE does not redistribute proprietary TradingView® platform software, charting UI, or closed data services.

## Ecosystem

Part of the **[HOOX](https://hoox.sh)** open trading stack:

| Product | Role | Repo | Website |
|---------|------|------|---------|
| **HOOX** | Edge trading framework (Cloudflare® Workers) | [hoox-sh/hoox](https://github.com/hoox-sh/hoox) | [hoox.sh](https://hoox.sh) · [docs](https://docs.hoox.sh) |
| **PYNE** | Pine Script™ toolchain + Pro API (**this repo**) | [hoox-sh/pyne](https://github.com/hoox-sh/pyne) | [hoox.sh/pyne](https://hoox.sh/pyne) · [docs](https://hoox.sh/pyne/docs) |
| **pyne-worker** | Python Cloudflare® Worker — edge evaluate | [hoox-sh/pyne-worker](https://github.com/hoox-sh/pyne-worker) | [hoox.sh/pyne](https://hoox.sh/pyne) |
| **pyne-agent-worker** | NL → PYNE scripts (Workers AI™) | [hoox-sh/pyne-agent-worker](https://github.com/hoox-sh/pyne-agent-worker) | [PYNE agent](https://hoox.sh/pyne/docs/agent) |
| **AXIS** | Charting PWA | [hoox-sh/axis](https://github.com/hoox-sh/axis) | [hoox.sh/axis](https://hoox.sh/axis) · [docs](https://hoox.sh/axis/docs) |

**Edge evaluate** (one-click, not this repo):

[![Deploy to Cloudflare](https://deploy.workers.cloudflare.com/button)](https://deploy.workers.cloudflare.com/?url=https://github.com/hoox-sh/pyne-worker)

That button deploys **[pyne-worker](https://github.com/hoox-sh/pyne-worker)** — a thin Workers host for `POST /run`. CLI, LSP, compile, Flask Pro API, and the language source of truth stay **here**. See [pyne-worker limitations](https://github.com/hoox-sh/pyne-worker#limitations-read-before-you-click-deploy).

## Abstract

Pine Script™ is commonly executed inside a host charting environment. PYNE models the language as an inspectable pipeline — source text through parse, AST construction, and deterministic bar-loop evaluation — so the same scripts can be analysed and run outside any particular UI.

```text
Source (.pyne / .pine)
  → ANTLR4 lexer / parser
  → ASDL AST
  → bar-loop  (interpret | compile | auto)
  → plots · fills · drawings · strategy events · alerts
  → optional HTTP / edge / editor clients
```

The same pipeline underlies the desk CLI, the Language Server Protocol (LSP) binary, the Pro API, browser Pyodide evaluation (via AXIS), and Cloudflare® Workers that share one evaluate contract.

Coverage and known gaps are documented under [compatibility](https://hoox.sh/pyne/docs/reference/compatibility) and [implementation status](https://hoox.sh/pyne/docs/reference/implementation-status). This repository does **not** ship third-party script corpora or TradingView® builtin downloads.

### Corpus snapshot (set01–04 · local measurement · 2026-08-09)

Open-source Pine regression sets (**2477** scripts; not shipped in git) under parse+unparse and Runtime interpret (50 bars, 12s timeout):

| Suite | Rate | Detail |
| --- | ---: | --- |
| **Parse + unparse** | **99.96%** | 2476 / 2477 OK — residual is one intentional invalid line-wrap docs demo |
| **Runtime interpret** | **100%** excl. EXPECTED | 2466 OK + **11** intentional demos (`runtime.error` guards, lower-TF security, pathological loops) |
| set01 Runtime | **100%** | **249 / 249** OK |

Not a claim of TradingView® platform parity. Intentional demos are classified so OK% stays honest.

## Capabilities

### Language front-end

- **Grammar.** Approximate Pine Script™ v5–v6 language surface via ANTLR4 resource grammars.
- **AST.** ASDL-generated nodes with visitor and transformer patterns.
- **Round-trip.** `parse → unparse` with preservation of formatting intent.
- **Linter.** Static checks for common structural and style issues.

### Runtime

- **Bar-loop evaluation.** Deterministic indicator and strategy execution on OHLCV. Interpret (0.3.10) inlines Assign/Call after bar 0, skips unused derived series, and incrementally updates volume TA (`obv` / `wad` / `cmf` / `klinger`). `PYNE_SERIES_RING` default **off**.
- **Dual engine.** Interpret (AST walk) and compile (Numba nopython kernels with object-mode fallback); `mode` ∈ {`auto`, `compile`, `interpret`}. Object-mode recovers UDT/switch/map/matrix/drawing scripts that previously leaked `TypingError` or stored objects into float64 series.
- **Warm compile.** Disk IR cache, process prewarm, and recovery from corrupt cache state.
- **Plot parity.** Interpret ↔ compile series alignment verified by harness and tests (internal engine consistency, not platform certification).
- **Alerts.** `alert()` / `alertcondition()` with documented frequency semantics (`once_per_bar`, `once_per_bar_close`, `all`); structured export on Pro `/run` and optional L2 webhooks.
- **Strategy surface.** Entries, exits, events, commission/slippage paths, pending-fill behaviour under pyramiding constraints.
- **Drawing GC.** Honour of `max_lines_count`, `max_labels_count`, `max_boxes_count`, `max_polylines_count`.
- **UDT collections.** `array.sort` / `array.sort_indices` / `matrix.sort` and `array.binary_search*` take `sort_field` (const int index, default 0, or const string name) on arrays of user-defined types.
- **Security policy.** Same-symbol simple OHLCV for `request.security`; foreign or complex security resolves to `na` (no invented foreign closes).

### Surfaces

| Surface | Role |
|---------|------|
| **CLI** (`pyne`, alias `pynescript`) | Check, format, lint, compile, run, data fetch, prewarm |
| **LSP** (`pyne-lsp`) | Diagnostics, completion (~800+ builtins), hover, navigation, semantic tokens, formatting |
| **VS Code extension** | First-class `.pyne` / `.pine` (and related) associations |
| **Pro API** | HTTP evaluate, batch run, chart preview, quick backtest |
| **Editors** | Configurations for Neovim, Zed, Emacs (see `clients/`) |
| **PyneTS** | TypeScript / Bun library (`@hoox/pynets`) — [standalone repo](https://github.com/hoox-sh/pynets), consumed here only as the `pynets/` git submodule |

## Installation

```bash
pip install hoox-pyne                 # core library + CLI
pip install "hoox-pyne[lsp]"          # language server
pip install "hoox-pyne[compile]"      # Numba compile path
pip install "hoox-pyne[data]"         # market data providers
pip install "hoox-pyne[pro]"          # Flask Pro API stack

# Development install from a clone
git clone --recurse-submodules https://github.com/hoox-sh/pyne.git
cd pyne
git submodule update --init --recursive   # pynets/; needed after a plain clone
pip install -e ".[lsp,pro]"
```

### Container images (GHCR)

Multi-arch (`linux/amd64`, `linux/arm64`) images publish to GitHub Container Registry on `v*` tags (and via Actions → **GHCR** → Run workflow):

```bash
# CLI
docker pull ghcr.io/hoox-sh/pyne/cli:0.4.4
docker run --rm -v "$PWD:/work" -w /work ghcr.io/hoox-sh/pyne/cli:0.4.4 check script.pine

# Language server (stdio; -i required)
docker pull ghcr.io/hoox-sh/pyne/lsp:0.4.4
docker run --rm -i -v "$PWD:/work" -w /work ghcr.io/hoox-sh/pyne/lsp:0.4.4

# Pro API
docker pull ghcr.io/hoox-sh/pyne/api:0.4.4
docker run --rm -p 5002:8080 -e ADMIN_TOKEN=… ghcr.io/hoox-sh/pyne/api:0.4.4
```

Packages: [ghcr.io/hoox-sh/pyne](https://github.com/hoox-sh/pyne/pkgs/container/pyne%2Fcli). Local: `make docker-build-lsp`.
## Quickstart

### Parse and unparse

```python
from pynescript.ast.helper import parse, unparse

source = """
//@version=6
indicator("My RSI")
plot(ta.rsi(close, 14))
"""

tree = parse(source)
print(unparse(tree))
```

### Evaluate an expression

```python
from pynescript.ast.helper import literal_eval

literal_eval("1 + 2 * 3")  # 7
literal_eval("ta.rsi([100, 102, 101, 103, 105], 9)")
```

### CLI

```bash
pyne check script.pine
pyne format script.pine -w
pyne lint script.pine
pyne run script.pine --bars 100
pyne compile script.pine --emit
pyne data AAPL --provider yahoo --period 6mo
pyne info
# aliases still work: pynescript check …
```

### Language server

```bash
pip install "hoox-pyne[lsp]"
pyne-lsp
# alias: pynescript-lsp
```

Editor integration: [PYNE for VS Code](./vscode-extension/); Neovim, Zed, and Emacs configs under [`clients/`](./clients/).

## Pro API

Self-hosted (or managed) HTTP surface for script evaluation and previews:

| Endpoint | Description |
|----------|-------------|
| `POST /run` | Execute script (`mode` default `auto`); returns plots, series, events, drawings, **alerts** |
| `POST /run/batch` | Multiple scripts on shared OHLCV |
| `POST /compile/prewarm` | Warm Numba builtins / optional scripts |
| `POST /preview/chart` | Chart thumbnail |
| `POST /preview/indicator` | Indicator chart (SMA, EMA, RSI, MACD, …) |
| `POST /backtest/quick` | Quick backtest with equity curve |

`/run` accepts `mode` ∈ {`auto`, `compile`, `interpret`}, returns structured errors (`error_kind`, `error_type`, `error_bar`), and can forward last-bar alert firings to an optional webhook (`webhook_url` or server `ALERT_WEBHOOK_URL`).

```bash
make run   # :5002

curl -s http://127.0.0.1:5002/run \
  -H 'Content-Type: application/json' \
  -d '{
    "script": "//@version=6\nindicator(\"demo\")\nplot(close)\nalert(close > open, alert.freq_once_per_bar)",
    "data": [{"open":1,"high":2,"low":0.5,"close":1.5,"time":1,"volume":1}],
    "mode": "auto"
  }'
```

Documentation: [POST /run](https://hoox.sh/pyne/docs/api/endpoints/run) · [Alerts](https://hoox.sh/pyne/docs/runtime/alerts) · [API hub](https://hoox.sh/pyne/docs/api)

## Library API (sketch)

```python
from pynescript.ast.helper import parse, unparse, literal_eval
from pynescript.ast.linter import lint_script
from pynescript.ast.transformer import NodeTransformer

tree = parse(source_code)
warnings = lint_script(source_code)
value = literal_eval("ta.sma([100, 102, 101], 3)")

class Renamer(NodeTransformer):
    def visit_Name(self, node):
        if node.id == "close":
            node.id = "price"
        return node
```

## CLI reference

| Command | Purpose |
|---------|---------|
| `check <file>` | Parse-only validation |
| `format <file>` | Format via parse → unparse |
| `lint <file>` | Static analysis |
| `parse-and-dump <file>` | Print AST |
| `parse-and-unparse <file>` | Normalize source |
| `compile <file>` | Numba host pipeline / emit |
| `run <file>` | Execute on synthetic (or provided) OHLCV |
| `prewarm [PATH…]` | Warm compile caches |
| `data <symbol>` | Fetch market data |
| `info` | Version and optional extras |

Language server entry point: **`pyne-lsp`** (alias **`pynescript-lsp`**; separate console script).

## Documentation

Canonical product documentation: **[hoox.sh/pyne/docs](https://hoox.sh/pyne/docs)**

| Topic | Link |
|-------|------|
| Installation · quick start | [Getting started](https://hoox.sh/pyne/docs/enduser/getting-started/installation) |
| Evaluate scripts | [Evaluate guide](https://hoox.sh/pyne/docs/enduser/guides/evaluate-scripts) |
| Alerts & webhooks | [Runtime alerts](https://hoox.sh/pyne/docs/runtime/alerts) |
| Compiler & parity | [Compiler](https://hoox.sh/pyne/docs/runtime/compiler/overview) · [Parity](https://hoox.sh/pyne/docs/runtime/compiler/parity) |
| Pro API | [API](https://hoox.sh/pyne/docs/api) · [Usage](https://hoox.sh/pyne/docs/enduser/guides/pro-api-usage) |
| LSP | [LSP hub](https://hoox.sh/pyne/docs/lsp) · [VS Code](https://hoox.sh/pyne/docs/lsp/vscode-extension) |
| Compatibility | [Compatibility](https://hoox.sh/pyne/docs/reference/compatibility) · [Status](https://hoox.sh/pyne/docs/reference/implementation-status) |

In-repository notes: [Roadmap](./docs/ROADMAP.md) · [Missing features](./docs/missing_features.md) · [Changelog](./CHANGELOG.md)

## Compatibility

PYNE targets practical runtime fidelity verified with first-party fixtures, unit tests, and (when present locally) open-source corpus sets. Latest local corpus snapshot (set01–04, 2026-08-09): **parse 99.96%**, **Runtime interpret 100% excl. intentional demos** — see the table under Abstract. It does **not** claim:

- official TradingView® certification or endorsement  
- complete platform parity (chart host, data model, every edge-case builtin, or closed UI behaviour)  
- that results will match the TradingView® platform on every script or bar  

Prefer the published [compatibility](https://hoox.sh/pyne/docs/reference/compatibility) and [implementation status](https://hoox.sh/pyne/docs/reference/implementation-status) pages for current surface coverage.

Results obtained with PYNE are for research, development, and self-hosted evaluation. They are **not** financial advice and are **not** provided by TradingView, Inc.

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md). Code of conduct: [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md). Security reports: [SECURITY.md](./SECURITY.md).

```bash
make install   # editable install with LSP
make test      # pytest
make lint      # ruff
```

---

## The HOOX Stack — all products & sister projects

Everything under [github.com/hoox-sh](https://github.com/hoox-sh) — one open trading stack on [hoox.sh](https://hoox.sh):

```text
                    https://hoox.sh
           ┌──────────────┼──────────────┐
           ▼              ▼              ▼
         HOOX            PYNE           AXIS
    (edge execution)  (Pine engine)  (charting UI)
           │              │              │
           └──────────────┴──────────────┘
                    trade signals / eval API
```

**How they relate**

- **PYNE** *(this repo)* owns language semantics: parse, evaluate/compile, alerts, strategy events, and the HTTP evaluate surface (`/run`, batch, previews).
- **[AXIS](https://github.com/hoox-sh/axis)** is an optional chart host. It can call PYNE's Pro API (or edge workers) to plot series, fills, and drawings — evaluation does not require AXIS.
- **[HOOX](https://github.com/hoox-sh/hoox)** is an optional execution mesh. Strategy events and alert webhooks from PYNE can feed edge trade paths; HOOX does not replace the PYNE runtime.

**Main products**

| Product | Role | Repository | Website |
|---------|------|------------|---------|
| **HOOX** | Edge trading framework — signal validation & execution on Cloudflare® Workers | [hoox-sh/hoox](https://github.com/hoox-sh/hoox) | [hoox.sh](https://hoox.sh) · [docs](https://docs.hoox.sh) |
| **PYNE** *(this repo)* | Pine Script™ toolchain — grammar, AST, dual-engine runtime, LSP, Pro API | [hoox-sh/pyne](https://github.com/hoox-sh/pyne) | [hoox.sh/pyne](https://hoox.sh/pyne) · [docs](https://hoox.sh/pyne/docs) |
| **AXIS** | Installable charting PWA — CEX OHLCV, drawings, on-chain overlays | [hoox-sh/axis](https://github.com/hoox-sh/axis) | [hoox.sh/axis](https://hoox.sh/axis) · [docs](https://hoox.sh/axis/docs) |

**PYNE satellites**

| Project | Role | Repository |
|---------|------|------------|
| **PyneTS** | TypeScript / Bun library (`@hoox-sh/pynets`) — parse, unparse, interpret | [hoox-sh/pynets](https://github.com/hoox-sh/pynets) |
| **pyne-worker** | Python Cloudflare® Worker — edge `POST /run`, cron, R2, alerts | [hoox-sh/pyne-worker](https://github.com/hoox-sh/pyne-worker) · [docs](https://hoox.sh/pyne/docs/pyne-worker) |
| **pyne-agent-worker** | Workers AI Pine agent — RAG + validate loop | [hoox-sh/pyne-agent-worker](https://github.com/hoox-sh/pyne-agent-worker) · [docs](https://hoox.sh/pyne/docs/agent) |
| **pyne-lsp** | Language server `pyne-lsp` / `pynescript-lsp` — extras `[lsp]`, Nuitka binaries, GHCR image (in the PYNE tree) | [hoox-sh/pyne](https://github.com/hoox-sh/pyne) · [docs](https://hoox.sh/pyne/docs/lsp) · [GHCR](https://github.com/hoox-sh/pyne/pkgs/container/pyne%2Flsp) |
| **pyne-vscode** | VS Code / Open VSX extension `hoox-sh.pyne` (in the PYNE tree) | [vscode-extension](https://github.com/hoox-sh/pyne/tree/main/vscode-extension) · [Marketplace](https://marketplace.visualstudio.com/items?itemName=hoox-sh.pyne) |

**AXIS satellites**

| Project | Role | Repository |
|---------|------|------------|
| **axis-plugin-boilerplate** | Starter for source / stream / engine / dataset / component plugins | [hoox-sh/axis-plugin-boilerplate](https://github.com/hoox-sh/axis-plugin-boilerplate) |

**HOOX execution & ops plane**

| Worker | Role | Repository |
|--------|------|------------|
| **hoox-worker** | Public gateway — webhooks, WAF, DO idempotency, dispatch | [hoox-sh/hoox-worker](https://github.com/hoox-sh/hoox-worker) |
| **trade-worker** | Multi-exchange execution — Binance, Bybit, MEXC | [hoox-sh/trade-worker](https://github.com/hoox-sh/trade-worker) |
| **agent-worker** | AI risk manager — cron, trailing stops, kill switch | [hoox-sh/agent-worker](https://github.com/hoox-sh/agent-worker) |
| **d1-worker** | D1 SQL proxy — balances, positions, settings | [hoox-sh/d1-worker](https://github.com/hoox-sh/d1-worker) |
| **telegram-worker** | Telegram alerts + RAG copilot | [hoox-sh/telegram-worker](https://github.com/hoox-sh/telegram-worker) |
| **web3-wallet-worker** | On-chain wallet identity (ethers.js) | [hoox-sh/web3-wallet-worker](https://github.com/hoox-sh/web3-wallet-worker) |
| **email-worker** | Mailgun ingress — natural language → trade signals | [hoox-sh/email-worker](https://github.com/hoox-sh/email-worker) |
| **analytics-worker** | Analytics Engine fan-in — trades, signals, latency | [hoox-sh/analytics-worker](https://github.com/hoox-sh/analytics-worker) |
| **report-worker** | Browser Rendering PDFs → R2, cron delivery | [hoox-sh/report-worker](https://github.com/hoox-sh/report-worker) |
| **dashboard** | Next.js ops console (in the HOOX tree) | [hoox-sh/hoox](https://github.com/hoox-sh/hoox) |
| **pine-worker** | Pine evaluator → trade events (private) | [hoox-sh/pine-worker](https://github.com/hoox-sh/pine-worker) |

**Web**

| Project | Role | Repository |
|---------|------|------------|
| **hoox-landing-page** | Marketing site source for [hoox.sh](https://hoox.sh) | [hoox-sh/hoox-landing-page](https://github.com/hoox-sh/hoox-landing-page) |

### Clone the stack

```bash
git clone --recurse-submodules https://github.com/hoox-sh/pyne.git   # PYNE + pynets/ submodule (pyne-lsp is in-tree)
git submodule update --init --recursive                              # after a plain clone
pip install -e ".[lsp,pro]"                                          # CLI + LSP + Pro API
git clone https://github.com/hoox-sh/pynets.git                      # TypeScript library
git clone https://github.com/hoox-sh/pyne-worker.git                 # edge POST /run
git clone https://github.com/hoox-sh/pyne-agent-worker.git           # NL authoring
git clone https://github.com/hoox-sh/axis.git
```

## Ethos

- **Independent & open** — no proprietary chart host, no closed data services; evaluation never depends on TradingView®.
- **Edge-first** — compute colocated with exchanges on Cloudflare's global network.
- **Local-first** — AXIS runs fully offline (Pyodide); PYNE runs on your machine; HOOX self-hosts on the free tier.
- **No vendor lock-in** — open core, self-hostable, exportable.
- **Batteries included** — CLIs, LSP, dashboards, docs, and one-click deploy buttons ship in the box.

> **Disclaimer.** *Pine Script™* and *TradingView®* are trademarks of [TradingView, Inc.](https://www.tradingview.com/); *Cloudflare®* is a trademark of Cloudflare, Inc. The HOOX stack is **independent** and is not affiliated with, authorized by, sponsored by, or endorsed by either company. Educational and research use; trading involves substantial risk of loss — this is not financial advice.

⚡ **Powered by Cloudflare** — Workers · D1 · R2 · KV · Queues · Analytics Engine · Workers AI · Browser Rendering

## License

**SPDX:** `AGPL-3.0-or-later` · **Copyright (C) 2024–2026** jango_blockchained

GNU Affero General Public License v3.0 or later — see [LICENSE](./LICENSE).

🔋 Batteries included.
