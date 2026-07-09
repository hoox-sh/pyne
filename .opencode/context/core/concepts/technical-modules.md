# Technical Indicators Module Structure

**Core concept**: `technical.py` was refactored from a 5,142-line monolith into category-based submodules at `technical_submodules/`, with a shared core (`core.py`) and composition-inheritance pattern. The original `technical.py` is now 203 lines (composition wrapper).

## Key Points

- **Location**: `src/pynescript/ast/evaluator/builtins/technical_submodules/`
- **Architecture**: `TechnicalHelpers` base class in `core.py` inherited by all indicator modules
- **Scope**: ~150+ PineScript-compatible technical indicator functions across 10 modules
- **Constraint**: Zero breaking changes to public API — `technical.py` re-exports all symbols
- **Status**: ✅ Implemented and stable

## Module Breakdown

| Module | Focus | Size |
|--------|-------|------|
| `core.py` | Shared helpers, validation, base math | 228 lines |
| `basic.py` | Foundational indicators | ~700 lines |
| `common.py` | Common utility indicators | ~700 lines |
| `moving_averages.py` | KAMA, DEMA, TEMA, HMA, VWMA | ~300 lines |
| `oscillators.py` | RSI, STOCH, MACD, CCI, ROC, WPR | ~600 lines |
| `volatility.py` | ATR, Bollinger Bands, Keltner, StochRSI | ~500 lines |
| `volume.py` | OBV, MFI, CMF, WAD, WVAD, EMV | ~700 lines |
| `patterns.py` | Engulfing, Hammer, Gap, SAR | ~350 lines |
| `advanced.py` | Tiers 5-8 (regime detection, microstructure) | ~2K lines |
| `economics.py` | Economic indicators | ~600 lines |
| `strategies.py` | Strategy helpers | ~400 lines |
| `synthesizer.py` | Strategy synthesizer | ~200 lines |

## Architecture Pattern

```python
# core.py — shared base
class TechnicalHelpers:
    @staticmethod
    def validate_series(source, length): ...

# oscillators.py — inherits helpers
class Oscillators(TechnicalHelpers):
    def rsi(self, source, length): ...
```

## Reference

- Composition wrapper: `src/pynescript/ast/evaluator/builtins/technical.py` (203 lines)
- Submodules: `src/pynescript/ast/evaluator/builtins/technical_submodules/`
