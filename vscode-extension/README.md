# PYNE Language Support

<p align="center">
  <img src="media/icon-512.png" alt="PYNE" width="128" />
</p>

**VS Code language support** for **`.pyne`** / **`.pine`** sources — syntax highlighting, diagnostics, autocomplete, hover, signature help, semantic tokens, formatting, Convert to v6, document links, inlay hints, and more. Powered by **[PYNE](https://hoox.sh/pyne)** (`hoox-pyne`).

Part of the **[HOOX](https://hoox.sh) open trading stack** — sister products: **[AXIS](https://hoox.sh/axis)** (charting PWA) and **[HOOX](https://hoox.sh)** (edge execution).

> Independent, unofficial extension. **Not** affiliated with, endorsed by, or sponsored by TradingView, Inc.  
> Pine Script™ and TradingView® are trademarks of TradingView, Inc.

## What's new in 0.5.3

- **Pine syntax highlighting** — `pynescript.syntaxHighlighting` (`none` / `void` / `signal` / `volt`, default `void`) applies AXIS-style Pine token colors on top of any workbench theme. Switch it with **PYNE: Select Syntax Highlighting**. The three contributed themes (**AXIS Void**, **Hoox Signal**, **PYNE Volt**) are picked from VS Code's own Color Theme picker; the extension never switches your workbench theme.
- **Calm, AXIS-matched token roles** — keywords and functions → the theme accent, strings → a light accent tint, numbers → foreground, comments / punctuation / series builtins → neutral gray. Comments are always gray, in every theme.
- **Library annotation hover** — `//@function`, `//@param`, `//@returns`, `//@type`, `//@field`, `//@variable`, and `//@description` render as rich Markdown cards, including multi-line `//` continuation.
- **Auto-install** of `hoox-pyne[lsp]` (and the full backend extras) with pip, including automatic virtualenv creation for PEP 668 Python.
- **Backend integration** — `backend.url`, `backend.useHosted` (`pynescript.online`), plus **Install Backend**, **Start Backend**, and **Test Backend Connection** commands.

## Features

| Feature | Details |
|---------|---------|
| **File types** | **`.pyne`** (primary), `.pine`, `.pinev5`, `.pinev6`, `.pinescript` |
| **Syntax highlighting** | TextMate grammar — namespaces (`ta.`, `strategy.`, `color.`…), annotations (`//@version=`), colors, history refs, UDTs, multiline strings |
| **Snippets** | `indicator`, `strategy`, `library`, `type`, `enum`, `input.*`, `plot`, `ta.*`, `request.security`, `for`/`if`/`switch`, multiline string, … |
| **Language Server** | Diagnostics, autocomplete + docs, hover, signature help, document symbols, formatting (full/range/on-type), Convert to v6 (`pip install "hoox-pyne[lsp]"`) |
| **Semantic tokens** | Colorization by type: namespace, function, variable, keyword, operator, comment, … |
| **Inlay hints** | Assignment types, parameter-name hints on dotted builtin calls (`ta.sma(close, 14)` → `source:` / `length:`) |
| **Document links** | Clickable `http(s)` URLs in comments and string literals |
| **Document color** | `#hex` swatches with `colorPresentation` rewrite |
| **Library annotation hover** | `//@function` / `//@param` / `//@returns` / `//@type` / `//@field` / `//@variable` render as Markdown cards — headings, lists, code fences, blockquotes, tables, links, two-space line breaks |
| **Status bar** | `PYNE LSP` indicator (click → server output) |
| **Auto-detect LSP** | `pyne-lsp` (or alias `pynescript-lsp`) on `PATH`, or `python3 -m pynescript.langserver` |
| **Auto-install server** | Prompts (or auto-installs) `hoox-pyne[lsp]` with pip when the server is missing |
| **Pro API** | `PYNE: Run on Pro` — POST active script to your backend `/run` (local or hosted `pynescript.online`) |
| **Backend** | `PYNE: Install Backend (Pro API)`, `PYNE: Start Backend`, `PYNE: Test Backend Connection` |
| **Backend wheel** | `pip install hoox-pyne-backend` → `pyne-backend` / `python -m backend` |
| **Themes** | **AXIS Void / Hoox Signal / PYNE Volt** — AXIS-matched syntax highlighting + hover cards |

Every LSP feature above has a `pynescript.<feature>.enabled` setting and a `PYNE: Toggle <Feature>` palette command, so you can turn individual features off without restarting the server.

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

### Automatic install from the extension

When the server can't be found, the extension offers to install it for you:

- **Default:** a one-time prompt with **Install now** / **Later** / **Don't ask again**.
- **Silent:** set `pynescript.install.autoInstall` to `true` to install without prompting.
- **Manual:** run **PYNE: Install Language Server** any time.

It resolves a Python interpreter (`pynescript.install.python` → `pynescript.lsp.python` → `python3` → `python` → `py`), requires Python ≥ 3.10 and pip, then runs:

```bash
<python> -m pip install --upgrade --disable-pip-version-check "hoox-pyne[lsp]"
```

Output streams to the **PYNE Language Server** channel; on success the client restarts. On Debian/Ubuntu and other PEP 668 (externally managed) Python installs, the extension automatically creates an isolated virtualenv under its storage (or at `pynescript.install.venv`) and installs there, then remembers that interpreter via `pynescript.install.python`. Set `pynescript.install.createVenv` to `false` to install into the system Python instead.

## Install this extension

### From VSIX (local)

```bash
cd vscode-extension
npm install
npm run package
code --install-extension pyne-*.vsix
```

Site download: [https://hoox.sh/pyne-vscode.vsix](https://hoox.sh/pyne-vscode.vsix) (unversioned alias). Versioned `pyne-vscode-0.5.3.vsix` is built in this folder and on GitHub Releases.

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

### Appearance

| Setting | Default | Description |
| --- | --- | --- |
| `pynescript.syntaxHighlighting` | `void` | Pine token palette (TextMate + semantic tokens), independent of the workbench theme. `none` inherits the active theme. |

### Language server

| Setting | Default | Description |
| --- | --- | --- |
| `pynescript.lsp.enabled` | `true` | Start the language client |
| `pynescript.lsp.command` | `auto` | `auto` (PATH → module), an absolute binary path, or `docker` |
| `pynescript.lsp.python` | `python3` | Interpreter for `-m pynescript.langserver` |
| `pynescript.lsp.args` | `[]` | Extra server arguments (`docker run` arguments when `command` is `docker`) |

### Editor features

| Setting | Default | Description |
| --- | --- | --- |
| `pynescript.formatting.enabled` | `true` | Formatting — full document, selection, on-type |
| `pynescript.formatOnSave.enabled` | `false` | Format on save (requires `formatting.enabled`) |
| `pynescript.diagnostics.enabled` | `true` | Errors, warnings, and hints |
| `pynescript.diagnostics.severity` | `{}` | Remap severity by lint-code prefix, e.g. `{"W": "Hint"}` |
| `pynescript.completion.snippets` | `true` | Snippets for builtins and declarations |
| `pynescript.hover.enabled` | `true` | Hover cards (signature, docs, types) |
| `pynescript.signatureHelp.enabled` | `true` | Parameter hints while typing a call |
| `pynescript.semanticTokens.enabled` | `true` | Semantic token colorization |
| `pynescript.documentHighlight.enabled` | `true` | Highlight other occurrences of an identifier |
| `pynescript.linkedEditing.enabled` | `true` | Rename-as-you-type (needs `editor.linkedEditing`) |
| `pynescript.selectionRange.enabled` | `true` | Smart expand/shrink selection |
| `pynescript.documentLink.enabled` | `true` | Clickable `http(s)` URLs in comments and strings |
| `pynescript.codeAction.enabled` | `true` | Code actions (Convert to v6, `W001` quick fix) |

### Installation

| Setting | Default | Description |
| --- | --- | --- |
| `pynescript.install.autoInstall` | `false` | Install the server with pip when missing, without prompting |
| `pynescript.install.autoPrompt` | `true` | Ask once before installing a missing server |
| `pynescript.install.package` | `hoox-pyne[lsp]` | pip requirement installed by **PYNE: Install Language Server** |
| `pynescript.install.python` | `""` | Python for pip (empty = `lsp.python` → `python3` → `python` → `py`) |
| `pynescript.install.args` | `[]` | Extra pip arguments (e.g. `["--no-cache-dir"]`) |
| `pynescript.install.createVenv` | `true` | Isolated venv when the system Python is PEP 668 managed |
| `pynescript.install.venv` | `""` | Explicit venv directory (empty = extension storage) |

### Pro & backend

| Setting | Default | Description |
| --- | --- | --- |
| `pynescript.pro.enabled` | `false` | Enable PYNE Pro (`Run on Pro`) |
| `pynescript.pro.apiKey` | `""` | Pro API key, minted with `POST /auth/create_key`; stored in settings in plain text |
| `pynescript.backend.url` | `http://127.0.0.1:5002` | Self-hosted backend base URL (no `/run`) |
| `pynescript.backend.useHosted` | `false` | Use `pynescript.online` instead of `backend.url` |
| `pynescript.backend.hostedUrl` | `https://pynescript.online` | Hosted backend base URL |
| `pynescript.backend.package` | `hoox-pyne[pro,lsp]` | pip requirement installed by **PYNE: Install Backend (Pro API)** |
| `pynescript.backend.path` | `""` | PYNE checkout for **PYNE: Start Backend** (empty = first workspace folder) |

Palette toggles: **Toggle Diagnostics** / **Toggle Completion** / **Toggle Hover** / **Toggle Signature Help** / **Toggle Semantic Tokens** / **Toggle Document Highlight** / **Toggle Linked Editing** / **Toggle Selection Range** / **Toggle Document Links** / **Toggle Code Actions** / **Toggle Format on Save** flip the `pynescript.*` keys above.

**Toggle Inlay Hints**, **Toggle Folding**, and **Toggle Color Preview** flip `[pinescript]` editor settings (`editor.inlayHints.enabled`, `editor.folding`, `editor.colorDecorators`).

### Example — pin a venv binary:

```json
{
  "pynescript.lsp.command": "/home/you/project/.venv/bin/pyne-lsp"
}
```

### Example — force module launch:

```json
{
  "pynescript.lsp.command": "auto",
  "pynescript.lsp.python": "/home/you/project/.venv/bin/python"
}
```

### Example — local backend (Run on Pro):

```json
{
  "pynescript.pro.enabled": true,
  "pynescript.backend.url": "http://127.0.0.1:5002"
}
```

### Example — hosted PYNE Pro (`pynescript.online`):

```json
{
  "pynescript.pro.enabled": true,
  "pynescript.pro.apiKey": "pyn_…",
  "pynescript.backend.useHosted": true
}
```

`backend.useHosted` switches the effective URL to `backend.hostedUrl` (default `https://pynescript.online`). The key is minted once via `POST /auth/create_key` on your Pro instance and shown only then — store it in `pynescript.pro.apiKey`. Then use **PYNE: Run on Pro** to POST the active script to `{backend}/run`.

### Backend install / start / test

- **PYNE: Install Backend (Pro API)** — installs `pynescript.backend.package` (default `hoox-pyne[pro,lsp]`, the full Flask/gunicorn/gevent/numba stack plus the LSP).
- **PYNE: Start Backend** — runs `python -m backend.app` from `pynescript.backend.path` (or the workspace folder) in a terminal, with `PORT` taken from `backend.url`. Requires a PYNE checkout containing `backend/app.py`.
- **PYNE: Test Backend Connection** — GETs `{backend}/health` and reports the status.

You can also install the backend as its own wheel (no checkout needed):

```bash
pip install hoox-pyne-backend
pyne-backend          # or: python -m backend
```

For the hosted service you do not need to install or start anything — just enable `backend.useHosted` and set your Pro API key.

### Themes (AXIS Void / Hoox Signal / PYNE Volt)

The extension contributes three color themes. Pick one from the normal VS Code
**Preferences: Color Theme** picker — the extension never changes
`workbench.colorTheme` automatically, not on activation and not on install.

| Theme | Accent | Surfaces |
| --- | --- | --- |
| **AXIS Void** | periwinkle `#939FFF` | Near-black with a whisper of indigo; dark-grey panels |
| **Hoox Signal** | signal orange `#FE6A00` | Near-black, neutral surfaces |
| **PYNE Volt** | lime `#B7EF09` | Near-black with a whisper of lime |

Comments are always neutral gray in every theme. Keywords and functions take the accent, strings a light accent tint, numbers the foreground, and punctuation / series builtins gray — so a file stays calm even with a vivid accent.

Pine syntax highlighting is independent of the workbench theme:

| Option | Setting | Values | `none` means |
| --- | --- | --- | --- |
| **Syntax highlighting** | `pynescript.syntaxHighlighting` | `none` · `void` · `signal` · `volt` | Use the active theme's Pine colors |

It writes language-scoped `[pinescript]` token colors, so it composes with any workbench theme — including your own. Switch it with **PYNE: Select Syntax Highlighting** or set the key directly. Default: `void`.

## Docker (optional)

You do **not** need a local Python install if you run the language server from the **LSP image**. The VSIX is still installed in the editor; only the server process is containerized.

```bash
docker pull ghcr.io/hoox-sh/pyne/lsp:0.6.28
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
    "ghcr.io/hoox-sh/pyne/lsp:0.6.28"
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
| **PYNE: Convert to Pine v6** | `pynescript.convertToV6` | Rewrite older Pine (v1-v5) toward v6 |
| **PYNE: Toggle Diagnostics** | `pynescript.diagnosticsToggle` | Flip `pynescript.diagnostics.enabled` |
| **PYNE: Toggle Completion** | `pynescript.completionToggle` | Flip `pynescript.completion.snippets` |
| **PYNE: Toggle Inlay Hints** | `pynescript.inlayHintsToggle` | Flip `[pinescript].editor.inlayHints.enabled` |
| **PYNE: Toggle Folding** | `pynescript.foldingToggle` | Flip `[pinescript].editor.folding` |
| **PYNE: Toggle Color Preview** | `pynescript.colorPreviewToggle` | Flip `[pinescript].editor.colorDecorators` |
| **PYNE: Toggle Hover** | `pynescript.toggleHover` | Flip `pynescript.hover.enabled` |
| **PYNE: Toggle Signature Help** | `pynescript.toggleSignatureHelp` | Flip `pynescript.signatureHelp.enabled` |
| **PYNE: Toggle Semantic Tokens** | `pynescript.toggleSemanticTokens` | Flip `pynescript.semanticTokens.enabled` |
| **PYNE: Toggle Document Highlight** | `pynescript.toggleDocumentHighlight` | Flip `pynescript.documentHighlight.enabled` |
| **PYNE: Toggle Linked Editing** | `pynescript.toggleLinkedEditing` | Flip `pynescript.linkedEditing.enabled` |
| **PYNE: Toggle Selection Range** | `pynescript.toggleSelectionRange` | Flip `pynescript.selectionRange.enabled` |
| **PYNE: Toggle Document Links** | `pynescript.toggleDocumentLink` | Flip `pynescript.documentLink.enabled` |
| **PYNE: Toggle Code Actions** | `pynescript.toggleCodeAction` | Flip `pynescript.codeAction.enabled` |
| **PYNE: Toggle Format on Save** | `pynescript.toggleFormatOnSave` | Flip `pynescript.formatOnSave.enabled` |
| **PYNE: Open Document Link** | `pynescript.openDocumentLink` | Open the http(s) link under the cursor |
| **PYNE: Run on Pro** | `pynescript.runOnPro` | POST active script to Pro `/run` (requires `pynescript.pro.enabled`) |
| **PYNE: Install Language Server** | `pynescript.installLanguageServer` | `pip install --upgrade "hoox-pyne[lsp]"` into the resolved Python |
| **PYNE: Install Backend (Pro API)** | `pynescript.installBackend` | Install `hoox-pyne[pro,lsp]` (full backend extras) |
| **PYNE: Start Backend** | `pynescript.startBackend` | Run `python -m backend.app` from a checkout |
| **PYNE: Test Backend Connection** | `pynescript.testBackend` | GET `{backend}/health` |
| **PYNE: Select Syntax Highlighting** | `pynescript.selectSyntax` | None / AXIS Void / Hoox Signal / PYNE Volt |

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
|-------|-------|
| Extension id | `hoox-sh.pyne` |
| Package name | `pyne` |
| Display name | **PYNE Language Support** |
| Version | 0.5.3 |

## License

AGPL-3.0-or-later — see [LICENSE](./LICENSE).
