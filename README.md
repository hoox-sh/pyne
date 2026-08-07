# pyne

> Parse, evaluate, and compile TradingView® Pine Script™ with a modern Python toolchain.
> Bar-loop runtime (interpret + Numba/object-mode compile), alerts, Pro API, and Language Server Protocol (LSP) for VS Code, Neovim, Zed, and Emacs.

**Version:** 0.3.0 · **PyPI (live):** [`hoox-pyne`](https://pypi.org/project/hoox-pyne/) · **Import / CLIs:** `pynescript` · `pynescript-lsp`

**Website:** [hoox.sh/pyne](https://hoox.sh/pyne) · **Docs:** [hoox.sh/pyne/docs](https://hoox.sh/pyne/docs) · **Repo:** [hoox-sh/pyne](https://github.com/hoox-sh/pyne)

_Pine Script™ and TradingView® are trademarks of TradingView, Inc. Cloudflare® is a trademark of Cloudflare, Inc. This project is an independent effort and is not affiliated with or endorsed by TradingView, Inc. or Cloudflare, Inc._

## Ecosystem

Part of the **[HOOX](https://hoox.sh)** open trading stack:

| Product | Role | Repo | Website |
|---------|------|------|---------|
| **HOOX** | Edge trading framework (Cloudflare® Workers) | [jango-blockchained/hoox](https://github.com/jango-blockchained/hoox) | [hoox.sh](https://hoox.sh) · [docs](https://docs.hoox.sh) |
| **PYNE** | Pine Script™ toolchain + Pro API (this repo) | [hoox-sh/pyne](https://github.com/hoox-sh/pyne) | [hoox.sh/pyne](https://hoox.sh/pyne) · [docs](https://hoox.sh/pyne/docs) |
| **AXIS** | Installable charting PWA | [jango-blockchained/axis](https://github.com/jango-blockchained/axis) | [hoox.sh/axis](https://hoox.sh/axis) · [docs](https://hoox.sh/axis/docs) |

Local clone layout (typical sibling checkouts):

```text
~/Git/hoox          # edge stack
~/Git/pynescript    # this repo (GitHub: pyne)
~/Git/axis          # charting PWA
```

## Table of Contents

- [Ecosystem](#ecosystem)
- [Overview](#overview)
- [Language Server (LSP)](#language-server-lsp)
- [Pro API](#pro-api)
- [AXIS charting UI](#axis-charting-ui)
- [Features](#features)
- [Installation](#installation)
- [Quickstart](#quickstart)
- [Tool Examples](#tool-examples)
- [CLI Reference](#cli-reference)
- [Library API](#library-api)
- [Project Structure](#project-structure)
- [Documentation](#documentation)
- [Compatibility note](#compatibility-note)

## Overview

**pyne** (Python package `pynescript`, distribution name **`hoox-pyne`**) is a toolchain for TradingView® Pine Script™ that provides:

- **Parser & AST** — Pine Script™ v5–v6 grammar (ANTLR4) into a navigable ASDL AST, with round-trip unparse
- **Bar-loop runtime** — Deterministic evaluate path for indicators and strategies on OHLCV
- **Compile modes** — `mode=auto|compile|interpret` with Numba nopython kernels and object-mode fallback; warm compile, disk IR cache, prewarm, corrupt-cache recovery
- **Interpret ↔ compile plot parity** — Harness and tests so plot series stay aligned across engines
- **Alert engine** — `alert()` / `alertcondition()` with TradingView-style frequency (`once_per_bar`, `once_per_bar_close`, `all`); exported on Pro `/run` and optional L2 webhooks
- **LSP server** — Diagnostics, completion, hover, navigation, formatting, semantic tokens for professional editors
- **Pro API** — HTTP evaluate (`/run`, `/run/batch`), chart previews, quick backtests, optional Git OAuth proxy for AXIS Connect
- **Linter** — Catch common issues before upload
- **Corpus runtime** — Large sanitized library corpus; set01–04 projects roughly **~94.3%+** runtime OK (not 100% TradingView® platform parity)

## Language Server (LSP)

Get professional IDE features in VS Code, Neovim, Zed, Emacs, and more:

```bash
pip install "hoox-pyne[lsp]"
pynescript-lsp
```

### Features

| Feature | Description |
|---------|-------------|
| **Diagnostics** | 9 lint rules (naming, deprecated, style) |
| **Autocomplete** | 800+ builtins across namespaces (`ta.*`, `strategy.*`, `array.*`, `matrix.*`, `math.*`, `str.*`, …) |
| **Hover** | Signature, docs, examples, see-also links |
| **Go-to-definition** | Jump to function/type/variable definitions |
| **Find references** | Find all usages of a symbol |
| **Document outline** | Hierarchical symbol tree |
| **Formatting** | Full document + range formatting |
| **Semantic tokens** | Rich highlighting via the language server |

### Editor Setup

**VS Code / compatible editors — PYNE extension:**

The **[PYNE — Pine Script™ for VS Code](./vscode-extension/)** extension (`pyne`) associates **`.pyne`** (first-class PYNE sources) and **`.pine`** (TradingView® exports), plus `.pinev5` / `.pinev6` / `.pinescript`.

1. Install the language server: `pip install "hoox-pyne[lsp]"`
2. Package or install the extension from `vscode-extension/` (see that folder’s README for VSIX packaging)
3. Open a `.pyne` or `.pine` file — the LSP activates automatically when `pynescript-lsp` is on `PATH` (or via `python3 -m pynescript.langserver`)

**Neovim (with nvim-lspconfig):**

```lua
require('lspconfig').pynescript.setup({})
```

**Zed:**

Add to `settings.json`:

```json
{
  "language_servers": {
    "pynescript": {
      "command": "pynescript-lsp",
      "arguments": ["--stdio"]
    }
  }
}
```

**Emacs (with lsp-mode):**

```elisp
(use-package lsp-mode
  :hook ((pinescript-mode . lsp))
  :config
  (lsp-register-client
   (make-lsp-client
    :new-connection (lsp-stdio-connection '("pynescript-lsp" "--stdio"))
    :major-modes '(pinescript-mode)
    :server-id 'pynescript)))
```

See `clients/` for full configuration guides.

## Pro API

Cloud / self-hosted API for live chart previews, strategy backtesting, and script evaluation:

| Endpoint | Description | Tier |
|----------|-------------|------|
| `POST /run` | Execute Pine Script (`mode` default **`auto`** = warm compile with interpret fallback); response includes **`alerts`**, plots, series, events, drawings | Free |
| `POST /run/batch` | Run multiple scripts on shared OHLCV (AXIS multi-indicator) | Free |
| `POST /compile/prewarm` | Warm Numba builtins / optional scripts | Free |
| `POST /preview/chart` | Generate chart thumbnail | Pro |
| `POST /preview/indicator` | Indicator chart (SMA, EMA, RSI, MACD) | Pro |
| `POST /backtest/quick` | Quick backtest with equity curve | Pro |
| Git OAuth proxy | Device-flow helpers for AXIS Connect (`/api/git/oauth/...`) | Optional |

### `/run` highlights

- **`mode`**: `"auto"` (default) \| `"compile"` \| `"interpret"`
- **`alerts`**: structured `alert()` / `alertcondition()` firings with TV-style frequency
- **L2 webhooks** (optional): per-request `webhook_url` or server `ALERT_WEBHOOK_URL`; last-bar batch POST of alert firings (`forward_alerts`, `alert_last_bar`, `alert_batch`)
- Structured errors: `error_kind` (`parse` \| `compile` \| `runtime` \| `data` \| `order` \| `mode`), `error_type`, `error_bar`

Product docs: [POST /run](https://hoox.sh/pyne/docs/api/endpoints/run) · [Alerts](https://hoox.sh/pyne/docs/runtime/alerts)

## AXIS charting UI

The installable charting PWA (**AXIS**) is a **sister repository**:

- Repo: [jango-blockchained/axis](https://github.com/jango-blockchained/axis)
- Product: [hoox.sh/axis](https://hoox.sh/axis)
- Docs: [hoox.sh/axis/docs](https://hoox.sh/axis/docs)

It talks to this repo’s Pro API in local dev:

```bash
# this repo (pyne)
make run              # Flask Pro API on :5002

# sibling clone
git clone https://github.com/jango-blockchained/axis.git ../axis
cd ../axis && bun install && bun run dev   # Vite on :3000
```

### Pricing

| Tier | Price | API Calls/mo | Features |
|------|-------|-------------|---------|
| Free | $0 | Unlimited (local) | All LSP features |
| Hobby | $9/mo | 5,000 | Live chart previews |
| Pro | $29/mo | 50,000 | + equity curves, backtests |
| Team | $99/mo | 200,000 | + multi-user |

Product site: [hoox.sh/pyne](https://hoox.sh/pyne).

### HTTP API (curl)

```bash
# Free run (no key) — default mode=auto; alerts returned in the payload
curl -s http://127.0.0.1:5002/run \
  -H 'Content-Type: application/json' \
  -d '{
    "script":"//@version=5\nindicator(\"demo\")\nplot(close)\nalert(close > open, alert.freq_once_per_bar)",
    "data":[{"open":1,"high":2,"low":0.5,"close":1.5,"time":1,"volume":1}],
    "mode":"auto"
  }'

# Optional L2 webhook (overrides ALERT_WEBHOOK_URL when set)
curl -s http://127.0.0.1:5002/run \
  -H 'Content-Type: application/json' \
  -d '{"script":"//@version=5\nindicator(\"a\")\nalert(\"ping\")","data":[{"open":1,"high":1,"low":1,"close":1,"time":1}],"webhook_url":"https://hooks.example.com/pine"}'

# Mint a Pro key (requires ADMIN_TOKEN env on the server)
curl -s -X POST http://127.0.0.1:5002/auth/create_key \
  -H "X-Admin-Token: $ADMIN_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"tier":"hobby"}'
```

## Features

- **Complete parsing** — Full Pine Script™ v5–v6 grammar via ANTLR4; sanitize helpers for real-world library corpora
- **Language Server** — Diagnostics, autocomplete (800+ builtins), hover, navigation, semantic tokens, formatting
- **`.pyne` + `.pine`** — First-class PYNE sources and TradingView® export associations in the PYNE VS Code extension
- **Dual-engine runtime** — Interpret AST bar-loop and Numba / object-mode compile (`mode=auto|compile|interpret`)
- **Warm compile path** — Disk IR cache, process prewarm, corrupt Numba-cache recovery, `time_arr` host plumbing
- **Interpret ↔ compile plot parity** — `scripts/compare_interp_compile.py`, `tests/test_interp_compile_parity.py`
- **Alert engine** — `alert()` / `alertcondition()` with `once_per_bar`, `once_per_bar_close`, `all`; Pro `/run` export + L2 webhooks
- **Pro API** — Live chart previews, equity curves, quick backtests, `/run` + `/run/batch`, optional Git OAuth proxy
- **Performance (Round 7)** — Series caps (`PYNE_SERIES_CAP`), incremental TA (bb / kama / cmo / stochrsi + SMA/EMA/RSI family), parse AST LRU cache
- **Drawing GC** — `max_lines_count` / `max_labels_count` / `max_boxes_count` / `max_polylines_count`
- **Plot bands** — `fill(plot1, plot2)` series export for AXIS charting
- **request.security policy** — Same-symbol simple OHLCV only; foreign / complex security → `na` (honest, no invented foreign closes)
- **Strategy fidelity** — Pending-fill VWAP when pyramiding ≤ 0; strategy events, commission/slippage paths
- **Corpus Runtime** — set01–04 ~**94.3%+** projected OK on sanitized library scripts (honest residual tail; not full TV platform parity)
- **AST manipulation** — Inspect and transform scripts with Python visitor patterns
- **Round-trip** — Parse and unparse without losing formatting intent
- **Linter** — 9 rules for catching issues before upload
- **Jupyter support** — Magic commands for notebook workflows
- **Data providers** — Yahoo Finance, Alpha Vantage, CCXT (100+ exchanges)
- **Modern tooling** — Ruff linting, pytest, Nuitka-compiled LSP binary option

## Installation

```bash
# From PyPI (distribution name hoox-pyne; import remains pynescript)
pip install hoox-pyne                 # live on PyPI · https://pypi.org/project/hoox-pyne/
pip install "hoox-pyne[lsp]"          # language server
pip install "hoox-pyne[compile]"      # Numba compile path
pip install "hoox-pyne[data]"         # ccxt market data
pip install "hoox-pyne[pro]"          # Flask Pro API stack

# From a git clone (development)
pip install -e ".[lsp,pro]"
pip install -e ".[dev-lsp]"        # + pytest-lsp
```

## Quickstart

```python
from pynescript.ast.helper import parse, unparse

script = """
//@version=5
indicator("My RSI")
rsi(close, 14)
"""

tree = parse(script)
regenerated = unparse(tree)
print(regenerated)
```

## Tool Examples

### Parsing and Inspecting AST

```bash
pynescript parse-and-dump examples/rsi_strategy.pine
```

### Round-Trip Formatting

```bash
pynescript parse-and-unparse messy_script.pine > clean_script.pine
```

### Linting

```bash
pynescript lint my_script.pine
pynescript lint --fail-on warnings my_script.pine
```

### Evaluating Expressions

```python
from pynescript.ast.helper import literal_eval

result = literal_eval("1 + 2 * 3")
print(result)  # 7

prices = [100, 102, 101, 103, 105]
rsi = literal_eval(f"ta.rsi({prices}, 9)")
print(rsi)  # ~81.25
```

### Fetching Market Data

```bash
pynescript data AAPL --provider yahoo --period 6mo
pynescript data BTC/USDT --provider ccxt --exchange binance
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `parse-and-dump <file>` | Parse and print AST |
| `parse-and-unparse <file>` | Normalize formatting |
| `lint <file>` | Check for issues |
| `lint --fail-on warnings` | Fail on warnings |
| `data <symbol>` | Fetch market data |
| `lsp` | Start LSP server |
| `prewarm [PATH…]` | Warm compile builtins / scripts (optional) |

## Library API

```python
# Parse
from pynescript.ast.helper import parse, unparse
tree = parse(source_code)

# Lint
from pynescript.ast.linter import lint_script
warnings = lint_script(source_code)

# Evaluate
from pynescript.ast.helper import literal_eval
result = literal_eval("ta.sma([100, 102, 101], 3)")

# Transform
from pynescript.ast.transformer import NodeTransformer
class Renamer(NodeTransformer):
    def visit_Name(self, node):
        if node.id == "close":
            node.id = "price"
        return node
```

## Project Structure

```
src/pynescript/     # Core: parser, AST, evaluator, compiler, linter
  ast/              # ANTLR grammar, ASDL nodes, evaluator builtins, helpers
  compiler/         # Numba / object-mode compile path
  langserver/       # LSP server (diagnostics, completion, hover)
  util/             # Data providers, helpers
backend/            # Pro API server
  api/              # REST endpoints (preview, LSP HTTP, git OAuth)
  services/         # Chart rendering, backtesting
  middleware/       # Auth, key stores, schemas
clients/            # Editor configs (Neovim, Zed, Emacs, Helix)
scripts/            # Build, metadata, interp↔compile parity harness
tests/              # Test suite (incl. parity, alerts, corpus residuals)
vscode-extension/   # PYNE VS Code extension (.pyne / .pine)
```

## Documentation

Product docs (canonical): **[hoox.sh/pyne/docs](https://hoox.sh/pyne/docs)**

| Topic | Link |
|-------|------|
| Getting started | [Installation](https://hoox.sh/pyne/docs/enduser/getting-started/installation) · [Quick start](https://hoox.sh/pyne/docs/enduser/getting-started/quick-start) |
| Evaluate scripts | [Evaluate guide](https://hoox.sh/pyne/docs/enduser/guides/evaluate-scripts) |
| Alerts & webhooks | [Runtime alerts](https://hoox.sh/pyne/docs/runtime/alerts) |
| Compiler & parity | [Compiler overview](https://hoox.sh/pyne/docs/runtime/compiler/overview) · [Interpret ↔ compile parity](https://hoox.sh/pyne/docs/runtime/compiler/parity) · [Numba path](https://hoox.sh/pyne/docs/runtime/compiler/numba) |
| Pro API | [API hub](https://hoox.sh/pyne/docs/api) · [POST /run](https://hoox.sh/pyne/docs/api/endpoints/run) · [Pro API usage](https://hoox.sh/pyne/docs/enduser/guides/pro-api-usage) |
| LSP | [LSP hub](https://hoox.sh/pyne/docs/lsp) · [VS Code extension](https://hoox.sh/pyne/docs/lsp/vscode-extension) |
| Compatibility | [Compatibility](https://hoox.sh/pyne/docs/reference/compatibility) · [Implementation status](https://hoox.sh/pyne/docs/reference/implementation-status) |

In-repo references:

- [Roadmap](./docs/ROADMAP.md)
- [Missing features](./docs/missing_features.md)
- [Compiler plan](./docs/COMPILER_PLAN.md)
- [GCP cost estimate](./docs/gcp_cost_estimate.md)
- [LSP implementation plan](./.opencode/plans/pynescript-lsp-implementation.md)

## Compatibility note

PYNE aims for practical runtime fidelity on a large library corpus (set01–04 ~**94.3%+** projected OK) with continuous residual fixes. It does **not** claim 100% TradingView® platform parity (chart host, data model, every edge-case builtin, or closed UI semantics). Prefer the [compatibility](https://hoox.sh/pyne/docs/reference/compatibility) and [implementation status](https://hoox.sh/pyne/docs/reference/implementation-status) pages for current surface coverage.
