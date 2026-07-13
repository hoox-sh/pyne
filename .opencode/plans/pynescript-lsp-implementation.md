# Pine Script Language Server — Implementation Plan

**Last Updated:** 2026-07-13 (consolidation baseline + integration; core LSP complete, remaining semantic/inlay per plan) 
**Author:** jango-blockchained  
**Status:** Core LSP features implemented on main (diagnostics, completion, hover, formatting, symbols, definitions, references, workspace). pine-worker extra tool + strategy events integrated. Many early-phase checkboxes below are now historical. See 2026-07-09 consolidation plan for remaining real work (semanticTokens, advanced inlay, polish, publishing). 

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [What Exists vs What Needs Building](#3-what-exists-vs-what-needs-building)
4. [Phase-by-Phase Implementation](#4-phase-by-phase-implementation)
5. [Project Structure](#5-project-structure)
6. [Builtin Metadata Schema](#6-builtin-metadata-schema)
7. [LSP Method Specifications](#7-lsp-method-specifications)
8. [Target IDEs & Client Configurations](#8-target-ides--client-configurations)
9. [Closed Source Strategy](#9-closed-source-strategy)
10. [Monetization via LSP](#10-monetization-via-lsp)
11. [Risks & Mitigations](#11-risks--mitigations)
12. [Timeline](#12-timeline)

---

## 1. Overview

**Goal:** Build a Language Server Protocol (LSP) implementation for Pine Script that provides professional-grade IDE integration — diagnostics, autocomplete, hover documentation, code navigation, and formatting — directly inside VS Code, Neovim, Zed, Cursor, and Emacs.

**Why this matters:**
- Pine Script has 482+ builtins (`ta.sma`, `request.security()`, etc.) — autocomplete is essential
- TradingView's browser editor lacks offline access, CI/CD integration, and proper tooling
- The LSP becomes the **distribution channel** for the closed-source evaluation engine
- Every developer who installs the LSP gets exposed to live previews (paid feature) as they code

**Stack:**
- Framework: `pygls` v2 + `lsprotocol` (community standard for Python LSP)
- Transport: STDIO (all editors), TCP / WebSocket (optional)
- Language: Python 3.10+
- Distribution: compiled binary via Nuitka + VS Code extension

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      IDE / Editor                           │
│         (VS Code · Neovim · Zed · Cursor · Emacs)           │
│                  ↕ LSP over STDIO / TCP                     │
├─────────────────────────────────────────────────────────────┤
│             Pynescript Language Server                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  pygls v2 + lsprotocol                              │   │
│  ├────────────┬────────────┬────────────┬──────────────┤   │
│  │ diagnostics│ completion │   hover    │ formatting   │   │
│  │ (lint→LSP) │ (482 fns)  │ (docstr)  │  (unparse)  │   │
│  ├────────────┴────────────┴────────────┴──────────────┤   │
│  │         Document Workspace + Symbol Index            │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │         Pynescript Core (Parser · Linter · AST)      │   │
│  └─────────────────────────────────────────────────────┘   │
│                           ↕                                 │
│         (Optional) Remote Evaluation API                    │
│              api.pynescript.ai/eval                         │
│         ↕ Shows live chart previews on hover ↕             │
│         ↕ Shows equity curve previews on strategy ↕         │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. What Exists vs What Needs Building

### 3.1 Direct Mapping (Already Done)

| LSP Feature | Pynescript Component | Work Needed |
|-------------|---------------------|-------------|
| `textDocument/publishDiagnostics` | `PineLinter.lint()` → 9 rules | Convert `LintWarning(line, col)` → LSP `Range` |
| `textDocument/formatting` | `unparse()` in `ast/unparser.py` | Wire with indent options, max line length |
| Parser (syntax validation) | ANTLR4 grammar | None — already works |
| AST traversal | `NodeVisitor`, `NodeTransformer` | None — already works |

### 3.2 Needs Structured Data

| LSP Feature | Pynescript State | Work Needed |
|-------------|-----------------|-------------|
| `textDocument/completion` | `BuiltinEvaluator` has 482 builtins but **no structured metadata** | Extract to `builtin_metadata.json` |
| `textDocument/hover` | Docstrings exist but **not machine-readable** | Convert to structured schema |
| `completionItem/resolve` | Not implemented | Wire metadata to completion items |

### 3.3 Needs New Code

| LSP Feature | Effort | Description |
|-------------|--------|-------------|
| `textDocument/definition` | Medium | Walk AST → find `FunctionDef`, `TypeDef`, UDT field defs |
| `textDocument/references` | Medium | Collect all `Name` nodes referencing a symbol |
| `textDocument/documentSymbol` | Medium | Build tree: script → functions → local vars |
| `textDocument/workspaceSymbol` | Small | Search across all open files |
| `textDocument/semanticTokens` | Medium | Color: builtins (blue), user fns (green), types (orange) |
| `textDocument/inlayHints` | Small | Show inferred types |
| Document workspace manager | Medium | Track open files, cache ASTs, parse on change |

### 3.4 Evaluation Engine (Closed Source, Paid)

| Feature | Description |
|---------|-------------|
| Live chart preview on hover | Send `ta.sma(close, 14)` to API → return chart thumbnail |
| Equity curve preview | Send `strategy.entry(...)` to API → return backtest chart |
| Real-time data integration | Wire `request.security()` to live market data API |

---

## 4. Phase-by-Phase Implementation

### Phase 1: Foundation — *Week 1*

**Goal:** LSP server boots, diagnostics work in VS Code / Neovim.

#### Step 1.1 — Project Setup
- [ ] Create `src/pynescript/langserver/` directory
- [ ] Add to `pyproject.toml`: `pygls>=2.0`, `lsprotocol`
- [ ] Create `src/pynescript/langserver/__init__.py`
- [ ] Create `src/pynescript/langserver/server.py` — pygls boilerplate
- [ ] Register server capabilities (completion, hover, diagnostics, formatting)
- [ ] Add CLI entry point: `pynescript lsp` → starts the server

#### Step 1.2 — Document Workspace Manager
- [ ] `src/pynescript/langserver/workspace.py`
- [ ] Track open documents (`DidOpenTextDocument`, `DidChangeTextDocument`, `DidCloseTextDocument`)
- [ ] Cache parsed ASTs per document (invalidate on change)
- [ ] Store source text + parsed tree + linter warnings
- [ ] Debounce diagnostics (wait 300ms after last keystroke)

#### Step 1.3 — Diagnostics (Lint → LSP)
- [ ] `src/pynescript/langserver/features/diagnostics.py`
- [ ] Convert `LintWarning(line, column)` to LSP `Diagnostic(range, severity, message)`
- [ ] Map lint codes to LSP severities: `E*` → Error, `W*` → Warning, `C*` → Information
- [ ] Implement `textDocument/didChange` → re-lint → `publishDiagnostics` notification
- [ ] Add `textDocument/diagnostic` (pull model, for LSP 3.16+)

#### Step 1.4 — Test with VS Code
- [ ] Clone VS Code `lsp-sample` extension
- [ ] Point to local server via `pynescript lsp --stdio`
- [ ] Verify red squiggles appear on save
- [ ] Verify errors disappear after fixing code

#### Step 1.5 — Test with Neovim
- [ ] Write `nvim-lspconfig` snippet for pynescript
- [ ] Verify diagnostics via `lua <<EOF` config

**Phase 1 Deliverable:** Live diagnostics in VS Code + Neovim. User sees red squiggles as they type.

---

### Phase 2: Completions & Hover — *Week 1–2*

**Goal:** Autocomplete for all 482 builtins with signatures, snippets, and hover docs.

#### Step 2.1 — Extract Builtin Metadata

This is the most important data structure. Two options:

**Option A: Generate from code** (recommended)
- [ ] Write a script that introspects `BuiltinEvaluator._builtin_dispatch`
- [ ] Extract function names + signatures from docstrings
- [ ] Generate `src/pynescript/langserver/providers/builtin_metadata.json`

**Option B: Manual from TradingView docs**
- [ ] Scrape TradingView Pine Script reference
- [ ] Structure into JSON

**Metadata schema (see Section 6 for full detail):**
```json
{
  "ta.sma": {
    "label": "ta.sma",
    "detail": "ta.sma(series, length) → series float",
    "documentation": "Simple Moving Average...",
    "params": [
      {"name": "series", "type": "series int/float"},
      {"name": "length", "type": "const int"}
    ],
    "snippet": "ta.sma(${1:series}, ${2:length})",
    "category": "ta.moving_averages"
  }
}
```

#### Step 2.2 — Completion Provider
- [ ] `src/pynescript/langserver/features/completion.py`
- [ ] `completion` feature: return all builtin names + user-defined functions/types
- [ ] `completionItem/resolve`: enrich with full doc + params on selection
- [ ] Snippet support with tab stops (`${1:series}`, `${2:length}`)

#### Step 2.3 — Completion Categories

Organize by category for better UX:

| Category | Items |
|----------|-------|
| `ta.*` | All 150+ technical analysis functions |
| `request.*` | `request.security`, `request.currency`, etc. |
| `strategy.*` | Strategy trading functions |
| `array.*`, `matrix.*`, `map.*` | Collection operations |
| `math.*`, `str.*` | Math and string functions |
| `plot.*`, `line.*`, `box.*`, `label.*`, `table.*` | Drawing |
| `input.*` | Input parameters |
| Built-in variables | `close`, `open`, `high`, `low`, `volume`, `time`, `na` |

#### Step 2.4 — Hover Provider
- [ ] `src/pynescript/langserver/features/hover.py`
- [ ] `textDocument/hover`: look up symbol in builtin metadata
- [ ] Show: signature, brief doc, link to TradingView docs
- [ ] Fallback: show raw docstring if metadata not available
- [ ] Support user-defined functions (walk AST to find definition)

#### Step 2.5 — Fuzzy Matching
- [ ] Integrate `rapidfuzz` or `thefuzz` for typo-tolerant completion
- [ ] Match `sma` → `ta.sma`, `math.sma`, `ta.alma`, `ta.swma`

**Phase 2 Deliverable:** Autocomplete shows 482 builtins with signatures. Hover shows docs. Typo-tolerant fuzzy search.

---

### Phase 3: Navigation & Symbols — *Week 2*

**Goal:** Go-to-definition, find references, document outline.

#### Step 3.1 — Go-to-Definition
- [ ] `src/pynescript/langserver/features/definitions.py`
- [ ] Walk AST to find `FunctionDef`, `TypeDef`, UDT field definitions
- [ ] Return `Location` (file path + `Range`) for the definition
- [ ] Handle: user-defined functions, types, UDT fields, variables

#### Step 3.2 — Find References
- [ ] `src/pynescript/langserver/features/references.py`
- [ ] Collect all `Name` nodes that reference the target symbol
- [ ] Return list of `Location` objects
- [ ] Filter: exclude comments and string literals

#### Step 3.3 — Document Symbols
- [ ] `src/pynescript/langserver/features/symbols.py`
- [ ] Build hierarchical tree: script → functions → local variables
- [ ] Return `DocumentSymbol[]` with children
- [ ] Display in IDE "Outline" / "Document Symbol" panel

#### Step 3.4 — Workspace Symbols
- [ ] Search across all open workspace files
- [ ] Support: function names, type names, variable names
- [ ] Fast index: build on `DidOpen`, update on `DidChange`

**Phase 3 Deliverable:** Outline panel, Ctrl+Click to navigate, Find All References.

---

### Phase 4: Formatting & Polish — *Week 2*

**Goal:** Professional code formatting + semantic highlighting.

#### Step 4.1 — Full Document Formatting
- [ ] `src/pynescript/langserver/features/formatting.py`
- [ ] Wire `unparse()` with options: indent size, max line length
- [ ] Implement `textDocument/formatting` → return `TextEdit[]`

#### Step 4.2 — Range Formatting
- [ ] Format selection only
- [ ] Format on paste (via `paste` event + auto-format config)

#### Step 4.3 — Semantic Tokens (Optional — Phase 4b)
- [ ] `textDocument/semanticTokens/full`
- [ ] Token types: `function` (green), `type` (orange), `builtin` (blue), `variable` (default)
- [ ] Map Pine Script constructs to token types via AST visitor

#### Step 4.4 — Inlay Hints (Optional — Phase 4b)
- [ ] Show inferred types inline: `length = 14` → `length: const int = 14`
- [ ] Use type inference from evaluator context

**Phase 4 Deliverable:** Shift+Alt+F formats entire file. Format on save option.

---

### Phase 5: Client Configurations — *Week 2–3*

**Goal:** One-click install for all major editors.

#### Step 5.1 — VS Code Extension
- [ ] Create `vscode-extension/` directory
- [ ] `package.json`: language ID `pinescript`, contributes LSP client
- [ ] Bundle compiled LSP server binary inside extension
- [ ] Add: icon, syntax highlighting (reuse Pygments lexer), keybindings
- [ ] Publish to VS Code Marketplace
- [ ] Revenue: paid extension ($5–$10) or freemium (basic free, pro features locked)

#### Step 5.2 — Neovim Configuration
- [ ] Write `nvim-lspconfig` snippet:
```lua
lua <<EOF
require('lspconfig').pynescript.setup({
  cmd = {'pynescript', 'lsp'},
  filetypes = {'pinescript'},
})
EOF
```
- [ ] Add to project README

#### Step 5.3 — Zed Configuration
- [ ] JSON LSP config in `zed_extension.json`:
```json
{
  "name": "pynescript",
  "languages": [{"id": "pinescript", "name": "Pine Script"}],
  "language_server": {
    "name": "pynescript",
    "capabilities": ["completion", "hover", "diagnostics"]
  }
}
```

#### Step 5.4 — Other Editors
- [ ] **Emacs**: `eglot` / `lsp-mode` (auto-discovers via `.lspconfig`)
- [ ] **Cursor**: VS Code extension compatibility (same extension works)
- [ ] **Helix**: `languages.toml` LSP config

**Phase 5 Deliverable:** One-click install in VS Code marketplace. Neovim config in README.

---

## 5. Project Structure

```
src/pynescript/langserver/
├── __init__.py
├── __main__.py                    # CLI: python -m pynescript.langserver
├── server.py                     # pygls LanguageServer entry point
├── config.py                     # Server capabilities registration
├── workspace.py                   # Document tracking, AST cache
│
├── features/                      # LSP method implementations
│   ├── __init__.py
│   ├── diagnostics.py             # publishDiagnostics, pull diagnostics
│   ├── completion.py              # completion, completionItem/resolve
│   ├── hover.py                   # textDocument/hover
│   ├── definitions.py             # textDocument/definition
│   ├── references.py              # textDocument/references
│   ├── symbols.py                 # documentSymbol, workspaceSymbol
│   └── formatting.py              # textDocument/formatting, rangeFormatting
│
├── providers/                     # Data providers for features
│   ├── __init__.py
│   ├── builtin_metadata.py        # Load/serve builtin function metadata
│   └── completion_items.py        # Build CompletionItem objects
│
└── protocol/                      # Protocol utilities
    ├── __init__.py
    ├── utils.py                   # Range ↔ (line, col) conversion
    └── constants.py               # Token types, severity maps

vscode-extension/                  # VS Code extension (separate repo or here)
├── package.json
├── src/
│   └── extension.ts               # LSP client, language activation
├── syntaxes/
│   └── pinescript.tmLanguage.json # TextMate grammar (from Pygments)
└── README.md
```

---

## 6. Builtin Metadata Schema

### 6.1 Full Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "patternProperties": {
    "^([a-zA-Z_][a-zA-Z0-9_]*\\.)*[a-zA-Z_][a-zA-Z0-9_]*$": {
      "type": "object",
      "required": ["label", "detail"],
      "properties": {
        "label": {
          "type": "string",
          "description": "Display label in autocomplete"
        },
        "detail": {
          "type": "string",
          "description": "Signature: 'ta.sma(series, length) → float'"
        },
        "documentation": {
          "type": "string",
          "description": "Full docstring from TradingView"
        },
        "brief": {
          "type": "string",
          "description": "One-line summary for hover tooltip"
        },
        "params": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["name", "type"],
            "properties": {
              "name": {"type": "string"},
              "type": {"type": "string"},
              "doc": {"type": "string"},
              "optional": {"type": "boolean"},
              "default": {"type": "string"}
            }
          }
        },
        "returns": {
          "type": "object",
          "properties": {
            "type": {"type": "string"},
            "doc": {"type": "string"}
          }
        },
        "snippet": {
          "type": "string",
          "description": "VS Code snippet with ${1:placeholder} tab stops"
        },
        "category": {
          "type": "string",
          "description": "Completion group: ta.moving_averages, strategy.*, etc."
        },
        "example": {
          "type": "string",
          "description": "Usage example code"
        },
        "since": {
          "type": "string",
          "description": "Pine Script version when introduced: '5', '6'"
        },
        "tradingviewUrl": {
          "type": "string",
          "description": "Link to TradingView docs page"
        }
      }
    }
  }
}
```

### 6.2 Example Entry

```json
{
  "ta.sma": {
    "label": "ta.sma",
    "detail": "ta.sma(series, length) → series float",
    "brief": "Simple Moving Average",
    "documentation": "Simple Moving Average (SMA) is the arithmetic mean of the source series over a specified number of bars. It is commonly used to smooth price data and identify trend direction.",
    "params": [
      {
        "name": "series",
        "type": "series int/float",
        "doc": "Source data (e.g., close, open, high)"
      },
      {
        "name": "length",
        "type": "const int",
        "doc": "Number of bars for the averaging window",
        "default": "14"
      }
    ],
    "returns": {
      "type": "series float",
      "doc": "The smoothed moving average series"
    },
    "snippet": "ta.sma(${1:series}, ${2:length})",
    "category": "ta.moving_averages",
    "example": "// Plot SMA with default length\nplot(ta.sma(close, 14))",
    "since": "5",
    "tradingviewUrl": "https://www.tradingview.com/pine-script-reference/v5/#fun_ta%7Bdot%7Dsma"
  }
}
```

### 6.3 Generation Script

```python
# scripts/generate_builtin_metadata.py
"""Introspect BuiltinEvaluator and generate builtin_metadata.json"""

import json
from pathlib import Path
from pynescript.ast.evaluator import BuiltinEvaluator

def generate_metadata():
    evaluator = BuiltinEvaluator()
    dispatch = evaluator._builtin_dispatch
    
    metadata = {}
    for name, handler in dispatch.items():
        doc = handler.__doc__ or ""
        brief = doc.strip().split('\n')[0] if doc else name
        
        metadata[name] = {
            "label": name,
            "detail": f"{name}(...)",  # Would extract params from signature
            "brief": brief,
            "documentation": doc,
            "category": _infer_category(name),
        }
    
    output_path = Path(__file__).parent.parent / "src/pynescript/langserver/providers/builtin_metadata.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(metadata, indent=2))
    print(f"Generated {len(metadata)} entries → {output_path}")

if __name__ == "__main__":
    generate_metadata()
```

---

## 7. LSP Method Specifications

### 7.1 Diagnostics

**Trigger:** `textDocument/didChange` (debounced 300ms)

**Input:** `DidChangeTextDocumentParams`  
```
{ textDocument: { uri, version }, contentChanges: [{ text }] }
```

**Process:**
```
source text
  → parse(source)                  # from pynescript.ast.helper
  → lint_script(source)            # from pynescript.ast.linter
  → for each LintWarning:
       convert to Diagnostic:
         range: (warning.line - 1, warning.column, warning.line - 1, warning.column + 10)
         severity: ERROR if code.startswith('E') else WARNING or INFO
         message: warning.message
         code: warning.code
```

**Output:** `publishDiagnostics` notification  
```
{ uri, diagnostics: [Diagnostic] }
```

### 7.2 Completion

**Trigger:** `textDocument/completion` (on typing `.` or Ctrl+Space)

**Input:** `TextDocumentPositionParams`  
```
{ textDocument: { uri }, position: { line, character } }
```

**Process:**
```
1. Get document at uri
2. Get text before cursor
3. If last char is '.': filter by prefix (e.g., 'ta.' → all ta.* functions)
4. If inside identifier: fuzzy match against all builtins + user symbols
5. Return CompletionList with items from builtin_metadata + user-defined
```

**Output:** `CompletionList`
```python
CompletionList(
    isIncomplete=False,
    items=[
        CompletionItem(
            label="ta.sma",
            kind=CompletionItemKind.Function,
            detail="ta.sma(series, length) → series float",
            documentation=MarkupContent(kind=Markdown, value="Simple Moving Average..."),
            insertText="ta.sma(${1:series}, ${2:length})",
            insertTextFormat=InsertTextFormat.Snippet,
            filterText="sma ta simple moving",
        ),
        ...
    ]
)
```

### 7.3 Hover

**Trigger:** `textDocument/hover` (mouse over symbol)

**Input:** `TextDocumentPositionParams`

**Process:**
```
1. Get symbol at cursor position (walk AST Name nodes)
2. If builtin: lookup in builtin_metadata → return docs
3. If user-defined: walk AST to find definition → return signature + docstring
4. If not found: return None
```

**Output:** `Hover`
```python
Hover(
    contents=MarkupContent(
        kind=Markdown,
        value="""```pinescript
ta.sma(series, length) → series float
```
Simple Moving Average...

📖 [TradingView docs](https://...)
"""
    ),
    range=Range(start=Position(line, col), end=Position(line, col_end))
)
```

### 7.4 Go-to-Definition

**Trigger:** `textDocument/definition` (Ctrl+Click or F12)

**Input:** `TextDocumentPositionParams`

**Process:**
```
1. Get symbol name at cursor
2. Walk document AST:
     - Find FunctionDef nodes where name matches → return def start
     - Find TypeDef nodes where name matches → return def start
     - Find Assign nodes where target matches → return assignment location
3. Return Location or None
```

### 7.5 Find References

**Trigger:** `textDocument/references` (Ctrl+Shift+F or Find All References)

**Input:** `ReferenceParams` (includes `textDocument`, `position`, `context.includeDeclaration`)

**Process:**
```
1. Get symbol name at cursor
2. Walk entire document AST:
     - Collect all Name nodes where id == symbol
     - Exclude if inside comments or string literals
3. Return list of Location objects
```

### 7.6 Document Symbols

**Trigger:** `textDocument/documentSymbol` (Outline panel)

**Input:** `DocumentSymbolParams`

**Process:**
```
Walk AST → build tree:
  Script
  ├── @version=5 annotation
  ├── strategy("RSI Strategy")  [SymbolKind.Function]
  │   ├── length [SymbolKind.Variable]
  │   └── vrsi [SymbolKind.Variable]
  ├── ta.rsi() [SymbolKind.Function]  ← from builtin, skip or mark
  └── myFunction() [SymbolKind.Function]
      └── param1 [SymbolKind.Variable]
```

### 7.7 Formatting

**Trigger:** `textDocument/formatting` (Shift+Alt+F)

**Input:** `DocumentFormattingParams`
```
{ textDocument: { uri }, options: { tabSize, insertSpaces, maxLineLength } }
```

**Process:**
```
1. Get document source
2. parse(source) → AST
3. unparse(AST, options) → formatted source
4. Compute diff → TextEdit[Range(0,0 → end), formatted]
```

---

## 8. Target IDEs & Client Configurations

### 8.1 VS Code Extension

**Repository:** `vscode-extension/` (bundled or separate repo)

**package.json key fields:**
```json
{
  "name": "pynescript",
  "displayName": "Pine Script",
  "description": "Pine Script language support with LSP",
  "version": "1.0.0",
  "languages": [{
    "id": "pinescript",
    "aliases": ["Pine Script", "pinescript"],
    "extensions": [".pine", ".pinev5", ".pinev6"],
    "configuration": "./language-configuration.json"
  }],
  "contributes": {
    "languageServer": [{
      "id": "pynescript-lsp",
      "label": "Pine Script Language Server",
      "entrypoint": "./out/extension.js"
    }]
  },
  "extensionDependencies": []
}
```

**Distribution strategy:**
- Free: diagnostics, autocomplete, hover (local, no API)
- Pro ($9.99/mo): live chart previews, equity curve on hover (requires API key)
- Bundle compiled LSP binary inside `.vsix`

### 8.2 Neovim

**Quick config (for README):**
```lua
-- ~/.config/nvim/lua/lsp/pynescript.lua
return {
  cmd = { 'pynescript', 'lsp' },
  filetypes = { 'pinescript' },
  root_dir = function(fname)
    return vim.fs.root(fname, { '.git', '*.pine' }) or vim.fn.getcwd()
  end,
  settings = {},
}
```

**Community package:** Submit to `nvim-lspconfig` for auto-discovery

### 8.3 Zed

```json
// ~/.config/zed/settings.json (user-level)
{
  "languages": {
    "Pine Script": {
      "language_servers": ["pynescript"]
    }
  },
  "language_servers": {
    "pynescript": {
      "command": ["pynescript", "lsp"],
      "settings": {}
    }
  }
}
```

### 8.4 Emacs

```elisp
;; ~/.emacs.d/init.el
(use-package lsp-mode
  :hook (pinescript-mode . lsp)
  :config
  (lsp-register-client
   (make-lsp-client
    :new-connection (lsp-stdio-connection '("pynescript" "lsp"))
    :major-modes '(pinescript-mode)
    :server-id 'pynescript)))
```

---

## 9. Closed Source Strategy

### 9.1 What to Close

| Component | Method | Rationale |
|-----------|--------|-----------|
| Evaluator + builtins (224+ functions) | **Nuitka compile** to `.so` | Ships inside LSP binary; extremely hard to reverse |
| LSP server business logic | **Nuitka compile** | No Python source exposed |
| Builtin metadata JSON | **Encrypted JSON** (Fernet) + API key | Decrypt at runtime; keys embedded in compiled binary |
| VS Code extension source | **Closed repo** | Only compiled bundle in marketplace |
| SaaS / API backend | **Already server-side** | Pure cloud |

### 9.2 What Stays (Partially) Open

| Component | Status | Why |
|-----------|--------|-----|
| ANTLR4 grammar files | Open (LGPL) | Required for parser; competitors can build their own |
| LSP protocol wiring | Open (MIT) | pygls is open source; no IP here |
| Pygments lexer | Open (BSD) | Syntax highlighting is commodity |
| CLI parsing | Open | `pynescript parse-and-dump` is free tool |

### 9.3 Build Pipeline

```bash
# 1. Generate builtin metadata
python scripts/generate_builtin_metadata.py

# 2. Encrypt metadata
python scripts/encrypt_metadata.py

# 3. Compile with Nuitka
nuitka --standalone \
       --onefile \
       --enable-plugin=cli \
       --noinclude-pytest-mode=noforce \
       --output-dir=dist/ \
       src/pynescript/langserver/__main__.py

# 4. Bundle into VS Code extension
vsce package --no-sudo

# 5. Publish to marketplace
vsce publish --token $VSCE_TOKEN
```

---

## 10. Monetization via LSP

The LSP is a **free distribution channel** that funnel users into paid products.

### 10.1 Freemium Model

| Feature | Free (Local) | Pro (API Key Required) |
|---------|-------------|----------------------|
| Diagnostics (lint) | ✅ | ✅ |
| Autocomplete (builtins) | ✅ | ✅ |
| Hover (docs only) | ✅ | ✅ |
| Go-to-definition | ✅ | ✅ |
| Formatting | ✅ | ✅ |
| **Live chart preview on hover** | ❌ | ✅ |
| **Equity curve preview** | ❌ | ✅ |
| **Real-time data indicators** | ❌ | ✅ |
| **Strategy backtest on save** | ❌ | ✅ |

### 10.2 How Live Previews Work

**On hover over `ta.sma(close, 14)`:**
```
1. LSP captures: file + cursor position + expression
2. If user has API key → POST /preview/chart to api.pynescript.ai
3. API returns: base64 PNG chart thumbnail
4. LSP renders: markdown image in hover popup
```

**On save of strategy file:**
```
1. File watcher detects strategy script
2. POST /backtest/quick to api.pynescript.ai
3. API runs 1-year backtest (mock data, fast)
4. Returns: equity curve + key metrics
5. VS Code notification: "Quick backtest: +23.4% (Sharpe 1.8)"
6. Click notification → full report on web dashboard
```

### 10.3 Conversion Flow

```
User installs VS Code extension (free)
    ↓
Uses autocomplete + diagnostics (free, no account)
    ↓
Hovers on indicator → sees "Get live preview (Pro)" button
    ↓
Signs up for free trial (7 days Pro)
    ↓
Gets API key → live previews activate
    ↓
Pro trial ends → user pays $9.99/mo to continue
```

### 10.4 Pricing Tiers

| Tier | Price | API Calls/mo | Features |
|------|-------|-------------|---------|
| Free | $0 | 0 (local only) | All LSP features |
| Hobby | $9/mo | 5,000 | Live previews, chart thumbnails |
| Pro | $29/mo | 50,000 | + equity curves, backtest on save |
| Team | $99/mo | 200,000 | + multi-user, workspace analytics |
| Enterprise | $499/mo | Unlimited | + on-prem server, SLA, SSO |

---

## 11. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| TradingView updates Pine Script grammar | Medium | High | Monitor release notes; update grammar + metadata monthly |
| pygls performance on large scripts | Low | Medium | Cache ASTs; debounce diagnostics; async evaluation |
| VS Code marketplace rejection | Low | High | Clearly mark as third-party; don't use TradingView branding in marketplace listing |
| Nuitka compilation errors | Medium | Low | CI/CD pipeline with regression tests on compiled binary |
| Competitors build competing LSP | Low | Medium | First-mover advantage; close evaluator = moat |
| Users bypass API with local evaluator | Medium | Low | Most users won't bother; premium features (live data) require API anyway |
| ANTLR4 grammar legally problematic | Low | High | Grammar is derived from public docs; MIT/BSD grammar tools are standard |
| LSP binary crashes in editor | Low | High | Ship with crash reporting (Sentry); auto-update mechanism |

---

## 12. Timeline

```
Week 1
  ├── Day 1–2:  Project setup, pygls server bootstrap, STDIO transport
  ├── Day 3–4:  Document workspace manager, diagnostics (lint → LSP)
  └── Day 5:    Test in VS Code + Neovim, fix edge cases

Week 2
  ├── Day 1–2:  Builtin metadata generation script
  ├── Day 3–4:  Completion provider (482 builtins + snippets)
  └── Day 5:    Hover provider, fuzzy matching

Week 3
  ├── Day 1–2:  Go-to-definition, find references, document symbols
  ├── Day 3:    Formatting (full document + range)
  ├── Day 4:    Semantic tokens (optional)
  └── Day 5:    Workspace symbols, polish

Week 4
  ├── Day 1–2:  VS Code extension (bundle + publish)
  ├── Day 3:    Neovim / Zed / Emacs configs
  ├── Day 4:    Nuitka compilation pipeline
  └── Day 5:    Encrypted metadata, release v1.0

Post-Launch
  ├── Monitor user feedback, fix bugs
  ├── Add Pro features: live chart previews via API
  ├── Submit to nvim-lspconfig community
  └── Iterate on autocomplete quality
```

**Total: ~4 weeks to MVP (diagnostics + autocomplete + hover)**

---

## Appendix A: File Inventory

| File | Created By | LOC Est. |
|------|-----------|---------|
| `src/pynescript/langserver/__init__.py` | New | 10 |
| `src/pynescript/langserver/__main__.py` | New | 20 |
| `src/pynescript/langserver/server.py` | New | 80 |
| `src/pynescript/langserver/config.py` | New | 30 |
| `src/pynescript/langserver/workspace.py` | New | 120 |
| `src/pynescript/langserver/features/diagnostics.py` | New | 60 |
| `src/pynescript/langserver/features/completion.py` | New | 100 |
| `src/pynescript/langserver/features/hover.py` | New | 60 |
| `src/pynescript/langserver/features/definitions.py` | New | 50 |
| `src/pynescript/langserver/features/references.py` | New | 50 |
| `src/pynescript/langserver/features/symbols.py` | New | 60 |
| `src/pynescript/langserver/features/formatting.py` | New | 40 |
| `src/pynescript/langserver/providers/builtin_metadata.py` | New | 40 |
| `src/pynescript/langserver/providers/completion_items.py` | New | 60 |
| `src/pynescript/langserver/protocol/utils.py` | New | 40 |
| `scripts/generate_builtin_metadata.py` | New | 60 |
| `scripts/encrypt_metadata.py` | New | 30 |
| **Total new Python** | | **~910 LOC** |
| `builtin_metadata.json` | Generated | ~50K chars |
| `vscode-extension/` | New | ~500 LOC TS/JSON |
| **Grand Total** | | **~1,500 LOC + generated data** |

---

## Appendix B: Dependencies to Add

```toml
# pyproject.toml additions

[project.optional-dependencies]
lsp = [
    "pygls>=2.0.0",
    "lsprotocol>=2024.0.0",
    "rapidfuzz>=3.0.0",
]
vscode = [
    "pygls>=2.0.0",
    "lsprotocol>=2024.0.0",
]
dev = [
    "pytest-lsp>=0.1.0",
]

[project.scripts]
pynescript-lsp = "pynescript.langserver.__main__:main"
```

---

## Appendix C: Testing Strategy

| Test Type | Tool | What to Test |
|-----------|------|-------------|
| Unit tests | pytest | Each feature: diagnostics conversion, completion filtering, hover lookup |
| LSP protocol tests | `pytest-lsp` | Full protocol: send request → verify response shape |
| Integration tests | VS Code + Neovim | Manual end-to-end: type code → see squiggles → get completions |
| Fixture regression | TradingView built-in scripts | Parse 100+ real scripts → ensure no crashes |
| Metadata coverage | Script | Ensure all 482 builtins have metadata entries |
| Performance | pytest-benchmark | LSP response time < 100ms for 1000-line script |

---

*Document status: Draft — ready for review and implementation.*
