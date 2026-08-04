# PYNE — Pine Script™ for VS Code

<p align="center">
  <img src="media/icon-512.png" alt="HOOX / PYNE" width="128" />
</p>

**Language support for [TradingView®](https://www.tradingview.com/) Pine Script™**, powered by the **[PYNE](https://hoox.sh/pyne)** toolchain (`pynescript`).

Part of the **[HOOX](https://hoox.sh) open trading stack** — sister products: **[AXIS](https://hoox.sh/axis)** (charting PWA) and **[HOOX](https://hoox.sh)** (edge execution).

> Pine Script™ and TradingView® are trademarks of TradingView, Inc.  
> This extension is an independent open-source project and is **not affiliated with, endorsed by, or sponsored by TradingView, Inc.**

## Features

| Feature | Details |
|---------|---------|
| **File types** | **`.pyne`** (primary), `.pine`, `.pinev5`, `.pinev6`, `.pinescript` |
| **Syntax highlighting** | TextMate grammar for Pine™ v5/v6 — namespaces (`ta.`, `strategy.`, `color.`…), annotations (`//@version=`), colors (`#RRGGBB`), history refs, UDTs, multiline strings |
| **Language Server** | Diagnostics, autocomplete, hover docs, document symbols, formatting (`pip install "pyne[lsp]"`) |
| **Status bar** | `PYNE LSP` indicator (click → server output) |
| **Auto-detect LSP** | `pynescript-lsp` on `PATH`, or `python3 -m pynescript.langserver` |

### LSP discovery order

1. `pynescript.lsp.command` if not `auto`
2. `pynescript-lsp` on `PATH`
3. `python3 -m pynescript.langserver` (requires `pip install "pyne[lsp]"`)

## Install language server (required for LSP)

```bash
pip install "pyne[lsp]"
# or from a clone of pyne:
pip install -e ".[lsp]"
```

Confirm:

```bash
python3 -c "import pynescript.langserver; print('ok')"
```

## Install this extension

### From VSIX (local)

```bash
cd vscode-extension
npm install
npm run package
code --install-extension pyne-0.2.2.vsix
```

> The VSIX is **self-contained** (esbuild bundles `vscode-languageclient`). You still need the **language server** on the machine (`pip install "pyne[lsp]"`).

### Development

```bash
cd vscode-extension
npm install
npm run compile   # esbuild bundle → out/extension.js
# F5 in VS Code with this folder open, or:
code --extensionDevelopmentPath=.
```

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `pynescript.lsp.enabled` | `true` | Master switch |
| `pynescript.lsp.command` | `auto` | Binary path, or `auto` |
| `pynescript.lsp.python` | `python3` | Interpreter for `-m pynescript.langserver` |
| `pynescript.lsp.args` | `[]` | Extra server args |
| `pynescript.diagnostics.enabled` | `true` | Squiggles |
| `pynescript.formatting.enabled` | `true` | Format document |
| `pynescript.completion.snippets` | `true` | Snippet inserts |

## Commands (Command Palette)

| Command | ID | Notes |
|---------|-----|--------|
| **PYNE: Restart Language Server** | `pynescript.restartServer` | Always available after install |
| **PYNE: Show Language Server Output** | `pynescript.showLspOutput` | Also status-bar click |
| **PYNE: Show Resolved LSP Launch Command** | `pynescript.showLspCommand` | Copy / debug launch path |
| **PYNE: Format Document** | `pynescript.formatDocument` | Pine files only; needs running LSP |

If a command says **“not found”**, reinstall the VSIX (0.2.2+ bundles the language client). Older packages omitted `node_modules` and failed to activate.

## Ecosystem

| Product | Role |
|---------|------|
| **[HOOX](https://hoox.sh)** | Edge trading framework |
| **[PYNE](https://hoox.sh/pyne)** | Pine Script™ toolchain + Pro API + this extension |
| **[AXIS](https://hoox.sh/axis)** | Installable charting PWA |

The AXIS web editor uses the **Pro API** HTTP bridge (`POST /lsp/completion`, `/lsp/hover`) when engine=server — not this extension. VS Code uses **stdio** `pynescript-lsp`.

## Trademark notice

Pine Script™ and TradingView® are trademarks of TradingView, Inc.  
PYNE / HOOX are independent open-source software and are not affiliated with, endorsed by, or sponsored by TradingView, Inc.

## License

AGPL-3.0-or-later · jango_blockchained · [hoox.sh](https://hoox.sh)
