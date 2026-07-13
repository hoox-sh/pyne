# Pynescript Future Roadmap

**Last Updated:** 2026-07-13 (consolidation + v6 dynamic requests + datafeed complete) 
**Status:** Core + Strategy Events + pine-worker extra tool integrated. Many historical "remaining" items now implemented.

---

## Project Status Summary

| Component | Status |
|-----------|--------|
| Parser (ANTLR4) | 100% ✅ |
| Evaluator | 100% ✅ (incl. full var/varip, ReAssign) |
| Built-in Functions | 224+ ✅ |
| Technical Analysis | 178+ ✅ |
| Collections (array/matrix/map) | 100% ✅ |
| Strategy Events | ✅ (StrategyEvent, parity, long/short constants, full emission) |
| pine-worker (TS port + converter) | ✅ (extra tool colocated in repo) |
| Drawing/Strategy/Input/Request | 100% (plotting stubs intentional) |
| Linter | ✅ |
| Jupyter Integration | ✅ |
| Data Providers (Yahoo, AlphaVantage, CCXT) | ✅ (mocks + providers) |
| LSP (core) | Advanced (diagnostics, completion, hover, formatting, symbols, defs, refs) |
| Tests | 1000+ (core 381+ in recent run; parity + strategy events green) |

---

## Completed Features

### Quick Wins (All Done ✅)
1. **Better error messages** - Improved with type hints and module suggestions
2. **Code cleanup** - Removed backup files (evaluator_backup.py, technical_new.py)
3. **Type hint improvements** - Enhanced mypy configuration

### Short-term (All Done ✅)
4. **Jupyter support** - Added `pynescript/ext/jupyter.py`:
   - `%%pinescript` cell magic for running Pine Script
   - `create_sample_data()` - Generate OHLCV test data
   - `evaluate_indicator()` - Run indicators with data
   - `display_indicator_table()` - Display as pandas DataFrame

5. **Script validation/linting** - Added `pynescript/ast/linter.py`:
   - 7+ lint rules (version, deprecated patterns, naming, style)
   - CLI: `pynescript lint <file>`

### Medium-term (All Done ✅)
7. **Real data integration** - Added `pynescript/util/data.py`:
   - `MockDataProvider` - For testing
   - `YahooFinanceProvider` - Via yfinance
   - `AlphaVantageProvider` - Free API
   - `CCXTProvider` - 100+ crypto exchanges (historical)
   - Realtime datafeed: `pynescript/util/datafeed.py` using CCXT Pro (watch_ohlcv, trades, etc.) — integrated into evaluator (request.* via context), DataFeedBroker for exec/pos, Mock/Composite, backend/runtime support, tests (2026-07)

---

## Recent Additions (July 2026 consolidation)
- Full `strategy.*` event capture with `StrategyEvent` dataclass, parity test corpus, `var`/`varip` support.
- `pine-worker/` — TypeScript evaluator port + `scripts/convert-python-to-ts.py` converter, treated as extra tool of the main repo.
- See `.opencode/plans/2026-07-09-main-consolidation-remaining-work.md` for the full consolidation plan.

## Roadmap: Remaining Work

### Phase A: Enhancements (High Value)

#### A1. Performance Optimizations
- JIT compilation for critical paths
- Vectorized array operations
- Caching for repeated calculations

#### A2. Extended Analysis
- Machine learning indicator wrappers
- Advanced statistical functions
- Complex derivation functions

---

### Phase B: Developer Experience

#### B1. IDE Integration
- Language server protocol support
- Autocomplete for Pine Script
- Debugging tools and profiling

#### B2. Documentation
- Video tutorials
- Interactive examples
- Real-world trading examples

---

### Phase C: Integration

#### C1. API Server
- REST API for remote execution
- Webhook support for alerts
- Cloud deployment configs

---

### Phase D: New Features (Long-term)

#### D1. v5 ↔ v6 Converter (started per consolidation)
- Basic script skeleton for converting between versions.
- See scripts/ for related convert tools.
- (Small step as one concrete roadmap item from plan §6)

#### D1. Code Transformation
- Automatic script refactoring
- Code optimization suggestions
- Pine v5 ↔ v6 converter

#### D2. Advanced Features
- Parallel execution support
- Distributed computing
- Graph-based optimization

---

## Priority Recommendation

### Short-term (Next)
1. **API Server** - REST API for remote execution
2. **IDE Integration** - Language server protocol

### Medium-term
3. **Performance optimizations** - JIT, caching, vectorization
4. **ML wrappers** - Advanced statistical functions

### Long-term
5. **Pine v5 ↔ v6 converter** - Specific use case
6. **Parallel execution** - Performance scaling

---

## Usage Examples

### Jupyter
```python
from pynescript.ext.jupyter import load_ipython_extension, create_sample_data
load_ipython_extension(ipython)

# Then in a cell:
%%pinescript
//@version=5
indicator("SMA")
plot(ta.sma(close, 14))
```

### CLI Lint
```bash
pynescript lint script.pine
pynescript lint --fail-on warnings
```

### CLI Data
```bash
pynescript data AAPL --provider mock
pynescript data BTC/USDT --provider ccxt --exchange binance
pynescript data AAPL --provider yahoo --period 6mo
```

### Python API
```python
from pynescript.util.data import get_provider
provider = get_provider("ccxt", exchange="binance")
data = provider.fetch("BTC/USDT", "1y")
```

---

## Contributing

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for guidelines.

---

*This roadmap is a living document and will be updated as the project evolves.*