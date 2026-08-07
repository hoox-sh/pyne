```
 ██╗  ██╗ ██████╗  ██████╗ ██╗  ██╗    ██████╗ ██╗   ██╗███╗   ██╗███████╗
 ██║  ██║██╔═══██╗██╔═══██╗╚██╗██╔╝    ██╔══██╗╚██╗ ██╔╝████╗  ██║██╔════╝
 ███████║██║   ██║██║   ██║ ╚███╔╝     ██████╔╝ ╚████╔╝ ██╔██╗ ██║█████╗
 ██╔══██║██║   ██║██║   ██║ ██╔██╗     ██╔═══╝   ╚██╔╝  ██║╚██╗██║██╔══╝
 ██║  ██║╚██████╔╝╚██████╔╝██╔╝ ██╗    ██║        ██║   ██║ ╚████║███████╗
 ╚═╝  ╚═╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═╝    ╚═╝        ╚═╝   ╚═╝  ╚═══╝╚══════╝
```

# HOOX · PYNE

```
> independent open toolchain for the Pine Script™ language
> grammar · AST · dual-engine bar-loop · LSP · HTTP evaluate
```

| key            | value                                                          |
|----------------|----------------------------------------------------------------|
| **version**    | `0.3.0`                                                        |
| **import**     | `pynescript`                                                   |
| **CLIs**       | `pynescript` · `pynescript-lsp`                                |
| **PyPI**       | [`hoox-pyne`](https://pypi.org/project/hoox-pyne/)             |
| **website**    | [hoox.sh/pyne](https://hoox.sh/pyne)                           |
| **docs**       | [hoox.sh/pyne/docs](https://hoox.sh/pyne/docs)                 |
| **source**     | [github.com/hoox-sh/pyne](https://github.com/hoox-sh/pyne)     |

<div align="center">

![FAILURE IS LOCAL. RESILIENCE IS GLOBAL.](brand/png/tagline-failure-is-local-github-1280x640-br-split-dark.png)

[![Python](https://shieldcn.dev/badge/Language-Python_3.10%2B-3776ab.png?size=sm&logo=python)](https://www.python.org/)
[![PyPI](https://shieldcn.dev/badge/PyPI-hoox--pyne-F97316.png?size=sm&logo=pypi)](https://pypi.org/project/hoox-pyne/)
[![License](https://shieldcn.dev/badge/License-AGPL_3.0-6b7280.png?size=sm)](LICENSE)
[![CI](https://shieldcn.dev/github/ci/hoox-sh/pyne.png?size=sm)](https://github.com/hoox-sh/pyne/actions/workflows/ci.yml)

</div>

```
/* trademark & affiliation ─────────────────────────────────────────────── */

  Pine Script™ / TradingView® → TradingView, Inc.
  Cloudflare®                 → Cloudflare, Inc.

  PYNE is independent and unofficial.
  NOT affiliated · NOT authorized · NOT sponsored · NOT endorsed
  by TradingView, Inc. or Cloudflare, Inc.
  NOT an official TradingView® product, service, or platform substitute.

  Language references are for interoperability / compatibility docs only.
  No redistribution of proprietary TV platform software or closed data services.
*/
```

---

## `//` abstract

Pine Script™ is commonly executed inside a host charting environment. PYNE models the language as an inspectable pipeline — source → parse → AST → deterministic bar-loop evaluation — so the same scripts can be analysed and run outside any particular UI.

```text
  ┌─ source (.pyne / .pine)
  │
  ├─► ANTLR4 lexer / parser
  ├─► ASDL AST
  ├─► bar-loop  { interpret | compile | auto }
  │      │
  │      ├─ plots · fills · drawings
  │      ├─ strategy events
  │      └─ alerts
  │
  └─► optional HTTP / edge / editor clients
```

Same pipeline → desk CLI · LSP binary · Pro API · AXIS (Pyodide) · Cloudflare® Workers (one evaluate contract).

Coverage: [compatibility](https://hoox.sh/pyne/docs/reference/compatibility) · [implementation status](https://hoox.sh/pyne/docs/reference/implementation-status).  
**No** third-party script corpora or TradingView® builtin downloads ship in-tree.

---

## `//` capabilities

### `./` language front-end

```
  [g4]  grammar     ≈ Pine Script™ v5–v6 surface (ANTLR4 resource grammars)
  [◇]   AST         ASDL nodes · visitor / transformer patterns
  [⇄]   round-trip  parse → unparse (formatting intent preserved)
  [✓]   linter      structural + style static checks
```

### `./` runtime

```
  [↻]   bar-loop       indicators + strategies on OHLCV
  [⚡]   dual engine    interpret AST | Numba nopython + object-mode fallback
                       mode ∈ { auto, compile, interpret }
  [♨]   warm compile   disk IR cache · prewarm · corrupt-cache recovery
  [≈]   plot parity    interpret ↔ compile series alignment (internal engines)
  [!]   alerts         alert() / alertcondition() · TV-style frequency
                       Pro /run export · optional L2 webhooks
  [$]   strategy       entries · exits · events · commission / slippage
  [⌫]   drawing GC     max_{lines,labels,boxes,polylines}_count
  [∅]   security       same-symbol simple OHLCV only; foreign → na
```

### `./` tooling surfaces

| surface | role |
|---------|------|
| `pynescript` CLI | check · format · lint · compile · run · data · prewarm |
| `pynescript-lsp` | diagnostics · completion (~800+ builtins) · hover · nav · tokens · format |
| VS Code extension **PYNE** | first-class `.pyne` / `.pine` (+ related) |
| Pro API | `/run` · batch · preview · backtest |
| `clients/` | Neovim · Zed · Emacs configs |

---

## `//` installation

```bash
pip install hoox-pyne                 # core library + CLI
pip install "hoox-pyne[lsp]"          # language server
pip install "hoox-pyne[compile]"      # Numba compile path
pip install "hoox-pyne[data]"         # market data providers
pip install "hoox-pyne[pro]"          # Flask Pro API stack

# from a git clone (dev)
pip install -e ".[lsp,pro]"
```

---

## `//` quickstart

### parse ⇄ unparse

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

### evaluate

```python
from pynescript.ast.helper import literal_eval

literal_eval("1 + 2 * 3")  # → 7
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

### language server

```bash
pip install "hoox-pyne[lsp]"
pynescript-lsp
```

Editors → [PYNE VS Code](./vscode-extension/) · [`clients/`](./clients/) (Neovim · Zed · Emacs)

---

## `//` Pro API

Self-hosted (or managed) HTTP evaluate surface:

| method | path | notes |
|--------|------|-------|
| `POST` | `/run` | `mode` default `auto` · plots · series · events · drawings · **alerts** |
| `POST` | `/run/batch` | multi-script · shared OHLCV |
| `POST` | `/compile/prewarm` | warm Numba / optional scripts |
| `POST` | `/preview/chart` | chart thumbnail |
| `POST` | `/preview/indicator` | SMA · EMA · RSI · MACD · … |
| `POST` | `/backtest/quick` | equity curve |

```
  mode        ∈ { auto, compile, interpret }
  errors      → error_kind · error_type · error_bar
  webhooks    → webhook_url | ALERT_WEBHOOK_URL  (last-bar alert batch)
```

```bash
make run   # :5002

curl -s http://127.0.0.1:5002/run \
  -H 'Content-Type: application/json' \
  -d '{
    "script": "//@version=5\nindicator(\"demo\")\nplot(close)\nalert(close > open, alert.freq_once_per_bar)",
    "data": [{"open":1,"high":2,"low":0.5,"close":1.5,"time":1,"volume":1}],
    "mode": "auto"
  }'
```

→ [POST /run](https://hoox.sh/pyne/docs/api/endpoints/run) · [alerts](https://hoox.sh/pyne/docs/runtime/alerts) · [API hub](https://hoox.sh/pyne/docs/api)

---

## `//` library API (sketch)

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

## `//` CLI reference

| command | purpose |
|---------|---------|
| `check <file>` | parse-only validation |
| `format <file>` | format via parse → unparse |
| `lint <file>` | static analysis |
| `parse-and-dump <file>` | print AST |
| `parse-and-unparse <file>` | normalize source |
| `compile <file>` | Numba host pipeline / emit |
| `run <file>` | execute on synthetic (or provided) OHLCV |
| `prewarm [PATH…]` | warm compile caches |
| `data <symbol>` | fetch market data |
| `info` | version + optional extras |

```
  language server entry →  pynescript-lsp   (separate console script)
```

---

## `//` documentation

Canonical docs → **[hoox.sh/pyne/docs](https://hoox.sh/pyne/docs)**

| topic | link |
|-------|------|
| install · quick start | [getting started](https://hoox.sh/pyne/docs/enduser/getting-started/installation) |
| evaluate | [evaluate guide](https://hoox.sh/pyne/docs/enduser/guides/evaluate-scripts) |
| alerts · webhooks | [runtime alerts](https://hoox.sh/pyne/docs/runtime/alerts) |
| compiler · parity | [compiler](https://hoox.sh/pyne/docs/runtime/compiler/overview) · [parity](https://hoox.sh/pyne/docs/runtime/compiler/parity) |
| Pro API | [API](https://hoox.sh/pyne/docs/api) · [usage](https://hoox.sh/pyne/docs/enduser/guides/pro-api-usage) |
| LSP | [LSP hub](https://hoox.sh/pyne/docs/lsp) · [VS Code](https://hoox.sh/pyne/docs/lsp/vscode-extension) |
| compatibility | [compatibility](https://hoox.sh/pyne/docs/reference/compatibility) · [status](https://hoox.sh/pyne/docs/reference/implementation-status) |

```
  in-repo →  docs/ROADMAP.md · docs/missing_features.md · CHANGELOG.md
```

---

## `//` compatibility

```
  claims     practical fidelity on first-party fixtures + unit tests
  NOT        official TV certification / endorsement
  NOT        complete platform parity (host · data model · every builtin · UI)
  NOT        bit-identical results on every script / bar
```

Prefer published [compatibility](https://hoox.sh/pyne/docs/reference/compatibility) and [implementation status](https://hoox.sh/pyne/docs/reference/implementation-status).

Results = research / development / self-hosted evaluation.  
**Not** financial advice. **Not** provided by TradingView, Inc.

---

## `//` contributing

```
  CONTRIBUTING.md · CODE_OF_CONDUCT.md · SECURITY.md
```

```bash
make install   # editable + LSP
make test      # pytest
make lint      # ruff
```

---

## `//` HOOX Open Trading Stack

**PYNE** ∈ **[HOOX Open Trading Stack](https://hoox.sh)** — three open projects, one site:

| product | role | repo | site |
|---------|------|------|------|
| **[HOOX](https://hoox.sh)** | edge trading framework (Cloudflare® Workers) | [hoox-sh/hoox](https://github.com/hoox-sh/hoox) | [hoox.sh](https://hoox.sh) · [docs](https://docs.hoox.sh) |
| **[PYNE](https://hoox.sh/pyne)** | language toolchain · LSP · Pro API · dual runtime (**this repo**) | [hoox-sh/pyne](https://github.com/hoox-sh/pyne) | [hoox.sh/pyne](https://hoox.sh/pyne) · [docs](https://hoox.sh/pyne/docs) |
| **[AXIS](https://hoox.sh/axis)** | installable charting PWA (Solid + Vite) | [hoox-sh/axis](https://github.com/hoox-sh/axis) | [hoox.sh/axis](https://hoox.sh/axis) · [docs](https://hoox.sh/axis/docs) |

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

```
  PYNE  →  language semantics · /run · alerts · strategy events
  AXIS  →  optional chart host (calls Pro API / workers)
  HOOX  →  optional execution mesh (consumes signals / webhooks)

  evaluate ∉ proprietary chart host
  AXIS ∧ HOOX = optional clients of one open evaluate contract
```

None of these projects is affiliated with or endorsed by TradingView, Inc.

---

## `//` license

```
  SPDX-License-Identifier: AGPL-3.0-or-later
  Copyright (C) 2024-2026 jango_blockchained
```

GNU Affero General Public License v3.0 or later — see [LICENSE](./LICENSE).

---

🔋 **Batteries included.**
