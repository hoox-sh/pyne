# Pine Script LSP — Client Configurations

This directory contains LSP client configurations for popular editors.

## VS Code

Extension lives in [`../vscode-extension`](../vscode-extension) (**PYNE — Pine Script™ for VS Code**, part of the HOOX open trading stack).

**Prerequisite:** language server installed:

```bash
pip install "pyne[lsp]"
```

**Build & install VSIX:**

```bash
cd vscode-extension
npm install
npm run package
code --install-extension pyne-*.vsix   # 0.2.2+ is self-contained (bundled language client)
```

**Dev:**

```bash
cd vscode-extension && npm run compile
code --extensionDevelopmentPath=.
```

**Features:**
- File associations: **`.pyne`**, `.pine`, `.pinev5`, `.pinev6`, `.pinescript`
- Syntax highlighting (TextMate grammar)
- LSP diagnostics, autocomplete, hover, symbols, formatting
- Status bar + auto-detect `pynescript-lsp` or `python -m pynescript.langserver`
- Install language server: `pip install "pyne[lsp]"` (import package remains `pynescript`)

**Configuration:**
- `pynescript.lsp.enabled` — Toggle LSP (default: true)
- `pynescript.lsp.command` — `auto` (default) or path to binary
- `pynescript.lsp.python` — Python for module launch (default: `python3`)
- `pynescript.lsp.args` — Extra args
- `pynescript.formatting.enabled` / `diagnostics.enabled` / `completion.snippets`

## Neovim

Requires `nvim-lspconfig`:

```bash
# Install nvim-lspconfig if not already installed
git clone https://github.com/neovim/nvim-lspconfig ~/.config/nvim/pack/vendor/start/nvim-lspconfig
```

Add to your `init.lua`:

```lua
-- Option 1: With nvim-lspconfig (recommended)
require('lspconfig').pynescript.setup({})

-- Option 2: Manual setup (no nvim-lspconfig needed)
-- Copy clients/neovim.lua to ~/.config/nvim/lua/lsp/pynescript.lua
local pynescript = require('lsp.pynescript')
require('lspconfig').pynescript.setup(pynescript)
```

**Keybindings (when using on_attach):**
- `gd` — Go to definition
- `gr` — Find references
- `K` — Hover documentation
- `<leader>lf` — Format document

## Zed

Add to your Zed settings (`~/.config/zed/settings.json`):

```json
{
  "languages": {
    "Pine Script": {
      "language_servers": ["pynescript"]
    }
  },
  "language_servers": {
    "pynescript": {
      "command": "pynescript-lsp",
      "arguments": ["--stdio"]
    }
  }
}
```

Or use the provided config snippet in `clients/zed.json`:
```bash
cat clients/zed.json >> ~/.config/zed/settings.json
```

## Emacs

Add to `~/.emacs.d/init.el`:

```elisp
;; Option 1: Using use-package (recommended)
(use-package lsp-mode
  :ensure t
  :hook ((pinescript-mode . lsp))
  :config
  (lsp-register-client
   (make-lsp-client
    :new-connection (lsp-stdio-connection '("pynescript-lsp" "--stdio"))
    :major-modes '(pinescript-mode)
    :server-id 'pynescript)))

;; Option 2: Direct load
(load-file "clients/emacs.el")
```

**Keybindings:**
- `C-c C-c` — Format document
- `M-.` — Go to definition
- `M-?` — Find references

## Cursor / Other Editors

Any LSP-compatible editor can use the Pine Script LSP:

```
pynescript-lsp --stdio
```

### Helix

Add to `~/.config/helix/languages.toml`:

```toml
[[language]]
name = "pinescript"
scope = "source.pinescript"
file-types = ["pyne", "pine", "pinev5", "pinev6"]
roots = ["pyproject.toml"]
command = "pynescript-lsp"
args = ["--stdio"]
```

### Sublime Text (LSP package)

1. Install "LSP" package via Package Control
2. Add to `LSP.sublime-settings`:

```json
{
  "clients": {
    "pynescript": {
      "command": ["pynescript-lsp", "--stdio"],
      "selector": "source.pinescript",
      "initializationOptions": {}
    }
  }
}
```

## Requirements

- Python 3.10+
- `pynescript-lsp` installed and in PATH

```bash
pip install "pyne[lsp]"
# or for development:
pip install -e ".[lsp]"
```
