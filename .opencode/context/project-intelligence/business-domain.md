<!-- Context: project-intelligence/business | Priority: high | Version: 1.0 | Updated: 2026-06-03 -->

# Business Domain

**Core concept**: Modern Python toolchain for TradingView Pine Script — parse, analyze, execute, and provide IDE support outside TradingView's native editor.

## Problem & Solution

| Aspect | Description |
|--------|-------------|
| **Problem** | Pine Script has no offline tooling, no IDE support (LSP) outside TradingView, no programmatic execution for backtesting/analysis |
| **Solution** | Python library with parser (ANTLR4), full LSP server, CLI tools, and a Flask Pro API for cloud execution |
| **Users** | Traders, quantitative analysts, strategy developers |
| **Status** | v0.2.0 — Pre-Alpha |

## Domain Vocabulary

| Term | Definition |
|------|-----------|
| Pine Script | TradingView's proprietary scripting language for indicators/strategies |
| Bar / Series | OHLCV market data — open, high, low, close, volume |
| Indicator | Visual overlay on charts (moving averages, oscillators, etc.) |
| Strategy | Automated trading logic with entry/exit signals |
| Builtin | 482 native functions (`ta.*`, `strategy.*`, `array.*`, etc.) |
| LSP | Language Server Protocol — IDE features in VS Code, Neovim, etc. |
| Pro API | Paid cloud service for chart previews and backtests |

## Business Model

| Tier | Features |
|------|----------|
| **Free** | Open-source library, CLI tools, LSP server |
| **Pro API** | Cloud execution, chart previews, backtesting (hobby/pro/team/enterprise) |

## Key Capabilities

- Parse Pine Script v6 (latest TradingView features)
- Full LSP: diagnostics, completion, hover, definitions, references, symbols, formatting
- 150+ technical indicators modularized (SMA, RSI, MACD, Bollinger, etc.)
- Execute scripts with real market data (Yahoo, CCXT, Alpha Vantage)
- CLI: parse/dump, lint, normalize formatting, data fetching
- Docker deployment with optional Redis caching

## 📂 Codebase References

- CLI entry: `src/pynescript/__main__.py`
- LSP server: `src/pynescript/langserver/`
- Pro API: `backend/app.py`
- Evaluator: `src/pynescript/ast/evaluator/`
- License: LGPL-3.0

## Related Files

- `technical-domain.md` — Tech stack and implementation patterns
- `decisions-log.md` — Architecture decisions
