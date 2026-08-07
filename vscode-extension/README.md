# PYNE

<p align="center">
  <img src="media/icon-512.png" alt="PYNE" width="128" />
</p>

**VS Code language support** for **`.pyne`** / **`.pine`** sources, powered by the **[PYNE](https://hoox.sh/pyne)** toolchain (`pynescript` / `hoox-pyne`).

Part of the **[HOOX](https://hoox.sh) open trading stack** — sister products: **[AXIS](https://hoox.sh/axis)** (charting PWA) and **[HOOX](https://hoox.sh)** (edge execution).

> Independent, unofficial extension. **Not** affiliated with, endorsed by, or sponsored by TradingView, Inc.  
> Pine Script™ and TradingView® are trademarks of TradingView, Inc.

## Features

| Feature | Details |
|---------|---------|
| **File types** | **`.pyne`** (primary), `.pine`, `.pinev5`, `.pinev6`, `.pinescript` |
| **Syntax highlighting** | TextMate grammar — namespaces (`ta.`, `strategy.`, `color.`…), annotations (`//@version=`), colors, history refs, UDTs, multiline strings |
| **Language Server** | Diagnostics, autocomplete, hover docs, document symbols, formatting (`pip install "hoox-pyne[lsp]"`) |
| **Status bar** | `PYNE LSP` indicator (click → server output) |
| **Auto-detect LSP** | `pynescript-lsp` on `PATH`, or `python3 -m pynescript.langserver` |

### LSP discovery order

1. `pynescript.lsp.command` if not `auto`
2. `pynescript-lsp` on `PATH`
3. `python3 -m pynescript.langserver` (requires `pip install "hoox-pyne[lsp]"`)

## Install language server (required for LSP)

```bash
pip install "hoox-pyne[lsp]"
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
code --install-extension pyne-*.vsix
```

> The VSIX is **self-contained** (esbuild bundles `vscode-languageclient`). You still need the **language server** on the machine (`pip install "hoox-pyne[lsp]"`).

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

Search for **PYNE**:

- Restart Language Server  
- Format Document  
- Show Language Server Output  
- Show Resolved LSP Launch Command  

## Marketplace identity

| Field | Value |
|-------|--------|
| Extension id | `jango-blockchained.pyne` |
| Package name | `pyne` |
| Display name | **PYNE** |

## License

AGPL-3.0-or-later — see [LICENSE](./LICENSE).
