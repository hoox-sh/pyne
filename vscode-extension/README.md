# PYNE — Pine Script for VS Code

Language support for **TradingView® Pine Script™** via the **[PYNE](https://hoox.sh/pyne)** toolchain (`pynescript`).

Part of **[HOOX](https://hoox.sh)** · sister product: **[AXIS](https://hoox.sh/axis)** charting PWA.

## Features

- Syntax highlighting (TextMate)
- **LSP** diagnostics, autocomplete, hover, symbols, formatting
- Status bar: `PYNE LSP` (click → server output)
- Auto-detect language server:
  1. `pynescript.lsp.command` if not `auto`
  2. `pynescript-lsp` on `PATH`
  3. `python3 -m pynescript.langserver` (requires `pip install pynescript[lsp]`)

## Install language server (required)

```bash
pip install "pynescript[lsp]"
# or from a clone:
pip install -e ".[lsp]"
```

Confirm:

```bash
pynescript-lsp --help   # may just wait on stdio — use Ctrl+C
# or:
python3 -c "import pynescript.langserver; print('ok')"
```

## Install this extension

### From VSIX (local)

```bash
cd vscode-extension
npm install
npm run package
code --install-extension pyne-pinescript-1.1.0.vsix
```

### Development

```bash
cd vscode-extension
npm install
npm run compile
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

## Commands (palette)

- **PYNE: Restart Language Server**
- **PYNE: Show Language Server Output**
- **PYNE: Show Resolved LSP Launch Command**
- **PYNE: Format Document**

## AXIS note

The AXIS web editor uses the **Pro API** HTTP bridge (`POST /lsp/completion`, `/lsp/hover`) when engine=server — not this extension. VS Code uses **stdio** `pynescript-lsp`.

## License

AGPL-3.0-or-later · jango_blockchained
