<p align="center">
  <img src="brand/png/github-social-1280x640-dark.png" alt="PYNE — parse the language, own the AST" width="720" />
</p>

# PYNE

**Independent open toolchain for the Pine Script™ language** — formal grammar, algebraic AST, dual-engine bar-loop runtime, language server, and HTTP evaluation surface.

| | |
|---|---|
| **Version** | 0.3.0 |
| **PyPI** | [`hoox-pyne`](https://pypi.org/project/hoox-pyne/) |
| **Import / CLIs** | `pynescript` · `pynescript-lsp` |
| **Website** | [hoox.sh/pyne](https://hoox.sh/pyne) |
| **Docs** | [hoox.sh/pyne/docs](https://hoox.sh/pyne/docs) |
| **Source** | [github.com/hoox-sh/pyne](https://github.com/hoox-sh/pyne) |
| **License** | AGPL-3.0-or-later |

### Trademark & affiliation notice

**Pine Script™** and **TradingView®** are trademarks of [TradingView, Inc.](https://www.tradingview.com/). **Cloudflare®** is a trademark of Cloudflare, Inc. All such marks remain the property of their respective owners.

PYNE (this project) is an **independent, unofficial** implementation effort. It is **not** affiliated with, associated with, authorized by, sponsored by, or endorsed by TradingView, Inc. or Cloudflare, Inc. It is **not** an official TradingView® product, service, or platform substitute.

References to Pine Script™ syntax, builtins, and behaviour are for **interoperability and compatibility documentation only**. PYNE does not redistribute TradingView® proprietary platform software, charting UI, or closed data services.

---

## Abstract

Pine Script™ is commonly executed inside a host charting environment. PYNE models the language as an inspectable pipeline — source text through parse, AST construction, and deterministic bar-loop evaluation — so the same scripts can be analysed and run outside any particular UI.

```
Source (.pyne / .pine)
  → ANTLR4 lexer / parser
  → ASDL AST
  → bar-loop  (interpret | compile | auto)
  → plots · fills · drawings · strategy events · alerts
  → optional HTTP / edge / editor clients
```

The same pipeline underlies the desk CLI, the Language Server Protocol (LSP) binary, the Pro API, browser Pyodide evaluation (via AXIS), and Cloudflare® Workers that share one evaluate contract.

Coverage and known gaps are documented in [compatibility](https://hoox.sh/pyne/docs/reference/compatibility) and [implementation status](https://hoox.sh/pyne/docs/reference/implementation-status). The repository does **not** ship third-party script corpora or TradingView® builtin downloads.

---

## Ecosystem

PYNE is one component of the [HOOX](https://hoox.sh) open trading stack:

| Component | Role | Repository |
|-----------|------|------------|
| **HOOX** | Edge execution mesh (Cloudflare® Workers) | [jango-blockchained/hoox](https://github.com/jango-blockchained/hoox) |
| **PYNE** | Independent Pine Script™-oriented toolchain + Pro API (this repository) | [hoox-sh/pyne](https://github.com/hoox-sh/pyne) |
| **AXIS** | Installable charting PWA | [jango-blockchained/axis](https://github.com/jango-blockchained/axis) |

AXIS is an optional visualization surface; HOOX is an optional execution mesh. Neither replaces the TradingView® platform.

---

## Capabilities

### Language front-end

- **Grammar** — Approximate Pine Script™ v5–v6 language surface via ANTLR4 resource grammars
- **AST** — ASDL-generated nodes with visitor and transformer patterns
- **Round-trip** — `parse → unparse` with preservation of formatting intent
- **Linter** — Static checks for common structural and style issues

### Runtime

- **Bar-loop evaluation** — Deterministic indicator and strategy execution on OHLCV
- **Dual engine** — Interpret (AST walk) and compile (Numba nopython kernels with object-mode fallback); `mode=auto|compile|interpret`
- **Warm compile** — Disk IR cache, process prewarm, and recovery from corrupt cache state
- **Plot parity** — Interpret ↔ compile series alignment verified by harness and tests (internal engine consistency, not platform certification)
- **Alerts** — `alert()` / `alertcondition()` with documented frequency semantics (`once_per_bar`, `once_per_bar_close`, `all`); structured export on Pro `/run` and optional L2 webhooks
- **Strategy surface** — Entries, exits, events, commission/slippage paths, pending-fill behavior under pyramiding constraints
- **Drawing GC** — Honor of `max_lines_count`, `max_labels_count`, `max_boxes_count`, `max_polylines_count`
- **Security policy** — Same-symbol simple OHLCV for `request.security`; foreign or complex security resolves to `na` (no invented foreign closes)

### Tooling surfaces

| Surface | Role |
|---------|------|
| **CLI** (`pynescript`) | Check, format, lint, compile, run, data fetch, prewarm |
| **LSP** (`pynescript-lsp`) | Diagnostics, completion (~800+ builtins), hover, navigation, semantic tokens, formatting |
| **VS Code extension** | First-class `.pyne` / `.pine` (and related) associations |
| **Pro API** | HTTP evaluate, batch run, chart preview, quick backtest |
| **Editors** | Configurations for Neovim, Zed, Emacs (see `clients/`) |

---

## Installation

```bash
pip install hoox-pyne                 # core library + CLI
pip install "hoox-pyne[lsp]"          # language server
pip install "hoox-pyne[compile]"      # Numba compile path
pip install "hoox-pyne[data]"         # market data providers
pip install "hoox-pyne[pro]"          # Flask Pro API stack
```

Development install from a clone:

```bash
pip install -e ".[lsp,pro]"
```

---

## Quickstart

### Parse and unparse

```python
from pynescript.ast.helper import parse, unparse

source = """
//@version=5
indicator("My RSI")
plot(ta.rsi(close, 14))
"""

tree = parse(source)
print(unparse(tree))
```

### Evaluate an expression

```python
from pynescript.ast.helper import literal_eval

literal_eval("1 + 2 * 3")                    # 7
literal_eval("ta.rsi([100, 102, 101, 103, 105], 9)")
```

### CLI

```bash
pynescript check script.pine
pynescript format script.pine -w
pynescript lint script.pine
pynescript run script.pine --bars 100
pynescript compile script.pine --emit
pynescript data AAPL --provider yahoo --period 6mo
pynescript info
```

### Language server

```bash
pip install "hoox-pyne[lsp]"
pynescript-lsp
```

Editor integration: VS Code via the [PYNE extension](./vscode-extension/); Neovim, Zed, and Emacs configs under [`clients/`](./clients/).

---

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
# Local server
make run   # :5002

curl -s http://127.0.0.1:5002/run \
  -H 'Content-Type: application/json' \
  -d '{
    "script": "//@version=5\nindicator(\"demo\")\nplot(close)\nalert(close > open, alert.freq_once_per_bar)",
    "data": [{"open":1,"high":2,"low":0.5,"close":1.5,"time":1,"volume":1}],
    "mode": "auto"
  }'
```

Documentation: [POST /run](https://hoox.sh/pyne/docs/api/endpoints/run) · [Alerts](https://hoox.sh/pyne/docs/runtime/alerts) · [API hub](https://hoox.sh/pyne/docs/api)

---

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

---

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

Language server entry point: **`pynescript-lsp`** (separate console script).

---

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

---

## Compatibility

PYNE targets practical runtime fidelity verified with first-party fixtures and unit tests. It does **not** claim:

- official TradingView® certification or endorsement  
- complete platform parity (chart host, data model, every edge-case builtin, or closed UI behaviour)  
- that results will match the TradingView® platform on every script or bar  

Prefer the published [compatibility](https://hoox.sh/pyne/docs/reference/compatibility) and [implementation status](https://hoox.sh/pyne/docs/reference/implementation-status) pages for current surface coverage.

Results obtained with PYNE are for research, development, and self-hosted evaluation. They are **not** financial advice and are **not** provided by TradingView, Inc.

---

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md). Code of conduct: [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md). Security reports: [SECURITY.md](./SECURITY.md).

```bash
make install   # editable install with LSP
make test      # pytest
make lint      # ruff
```

---

## License

GNU Affero General Public License v3.0 or later — see [LICENSE](./LICENSE).
