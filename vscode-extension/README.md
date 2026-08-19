# PYNE Language Support

<p align="center">
  <img src="media/icon-512.png" alt="PYNE" width="128" />
</p>

**VS Code language support** for **`.pyne`** / **`.pine`** sources — syntax highlighting, diagnostics, autocomplete, hover, and formatting. Powered by **[PYNE](https://hoox.sh/pyne)** (`hoox-pyne`).

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
| **Auto-detect LSP** | `pyne-lsp` (or alias `pynescript-lsp`) on `PATH`, or `python3 -m pynescript.langserver` |

### LSP discovery order

1. `pynescript.lsp.command` if not `auto`
2. `pyne-lsp` on `PATH`
3. `pynescript-lsp` on `PATH` (backward-compatible alias)
4. `python3 -m pynescript.langserver` (requires `pip install "hoox-pyne[lsp]"`)

## Install language server (required for LSP)

```bash
pip install "hoox-pyne[lsp]"
# or from a clone of this repo:
pip install -e ".[lsp]"
```

Confirm the preferred console script:

```bash
pyne-lsp --help
# alias still works: pynescript-lsp --help
# module form: python3 -m pynescript.langserver
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

**Example — pin a venv binary:**

```json
{
  "pynescript.lsp.command": "/home/you/project/.venv/bin/pyne-lsp"
}
```

**Example — force module launch:**

```json
{
  "pynescript.lsp.command": "auto",
  "pynescript.lsp.python": "/home/you/project/.venv/bin/python"
}
```

## Docker (optional)

You do **not** need a local Python install if you run the language server from the **LSP image**. The VSIX is still installed in the editor; only the server process is containerized.

```bash
docker pull ghcr.io/hoox-sh/pyne/lsp:0.3.15
# local bake:  make docker-build-lsp
```

Pin the extension to Docker (`-i` keeps stdio open). `${workspaceFolder}` is expanded by the extension:

```json
{
  "pynescript.lsp.command": "docker",
  "pynescript.lsp.args": [
    "run", "-i", "--rm",
    "-v", "${workspaceFolder}:/work",
    "-w", "/work",
    "ghcr.io/hoox-sh/pyne/lsp:0.3.15"
  ]
}
```

Compose (from a PYNE clone):

```bash
docker compose --profile lsp run --rm -i lsp
```

The image `ENTRYPOINT` is `pyne-lsp`. Extra `pynescript.lsp.args` after the image name are passed through to the server.

## Commands (Command Palette)

Search for **PYNE**:

| Command palette | ID | Notes |
|-----------------|-----|--------|
| **PYNE: Restart Language Server** | `pynescript.restartServer` | Always available after install |
| **PYNE: Format Document** | `pynescript.formatDocument` | `.pyne` / `.pine` only; needs running LSP |
| **PYNE: Show Language Server Output** | `pynescript.showLspOutput` | Also status-bar click |
| **PYNE: Show Resolved LSP Launch Command** | `pynescript.showLspCommand` | Copy / debug launch path |

From the CLI / developer host you can also run:

```bash
# show what the extension would launch (Command Palette)
#   PYNE: Show Resolved LSP Launch Command
# typical resolved values:
pyne-lsp
# or: pynescript-lsp
# or: python3 -m pynescript.langserver
```

## Marketplace identity

| Field | Value |
|-------|--------|
| Extension id | `hoox-sh.pyne` |
| Package name | `pyne` |
| Display name | **PYNE Language Support** |

## License

AGPL-3.0-or-later — see [LICENSE](./LICENSE).
