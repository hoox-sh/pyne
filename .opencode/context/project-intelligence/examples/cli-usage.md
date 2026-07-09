<!-- Context: project-intelligence/examples/cli-usage | Priority: high | Version: 1.0 | Updated: 2026-07-05 -->

# CLI Usage

Two console scripts are installed from `pyproject.toml [project.scripts]`:

| Command | Module | What |
| --- | --- | --- |
| `pynescript` | `pynescript.__main__:cli` | Click group: parse, lint, data, lsp |
| `pynescript-lsp` | `pynescript.langserver.__main__:main` | pygls LSP server (STDIO) |

## `pynescript` Subcommands

```bash
pynescript parse-and-dump <file.pine> [--indent 2] [--output-file -]
pynescript parse-and-unparse <file.pine> [--encoding utf-8]
pynescript lint <file.pine> [--fix] [--fail-on errors|warnings|all]
pynescript data <symbol> [--provider mock|yahoo|alphavantage|ccxt]
                        [--period 1y] [--interval 1d]
                        [--api-key ...] [--secret ...] [--exchange binance]
pynescript download-builtin-scripts --script-dir <dir>
pynescript lsp [--tcp --port 8765]
```

## `pynescript-lsp`

```bash
# STDIO (default — what editors expect):
pynescript-lsp
pynescript-lsp --stdio

# Or via the group:
pynescript lsp
```

The LSP transport is STDIO for VS Code / Neovim / Zed / Emacs (see `clients/`).

## Quick Recipes

```bash
# Round-trip a script:
pynescript parse-and-unparse examples/rsi_strategy.pine > /tmp/clean.pine

# Lint with fail-on-warnings in CI:
pynescript lint --fail-on warnings my_script.pine

# Pull the official builtin .pine corpus (powers the LSP completion set):
pynescript download-builtin-scripts --script-dir tests/data/builtin_scripts
```

## Pipeline Equivalents

```bash
# Same as `pynescript parse-and-dump`:
python -m pynescript parse-and-dump file.pine

# Same as `pynescript-lsp`:
python -m pynescript.langserver
```

## 📂 Codebase References

- **Implementation**: `src/pynescript/__main__.py` — `cli` Click group.
- **Implementation**: `src/pynescript/langserver/__main__.py` — `main()`.
- **Reference**: `pyproject.toml` — `[project.scripts]` entries.
- **Reference**: `clients/` — Neovim/Zed/Emacs/Helix launch configs.
