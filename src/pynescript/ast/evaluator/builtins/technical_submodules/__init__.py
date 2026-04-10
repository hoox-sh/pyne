# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

"""Technical Analysis Indicator Submodules.

This module was refactored from a single 5,142-line file into a modular structure:

Modules:
- core.py: Shared validation helpers and base utilities
- basic.py: Basic indicators (SMA, EMA, crossover, Bollinger, ATR, etc)
- common.py: Common indicators (statistics, trend, pivot, vwap)
- moving_averages.py: SMA, EMA, KAMA, DEMA, TEMA, HMA, VWMA, SWMA
- oscillators.py: RSI, STOCH, MACD, CCI, ROC, WPR, TSI, divergence detectors
- volatility.py: ATR, BB, Keltner Channels, StochRSI, linear regression, etc
- volume.py: OBV, MFI, CMF, WAD, WVAD indicators
- patterns.py: Engulfing, Hammer, Gap, Zigzag, Fractals, pivots
- economics.py: Market microstructure & advanced economics
- strategies.py: Advanced trading strategies & market timing
- synthesizer.py: Final capstone - intelligent strategy synthesizer
- advanced.py: Additional advanced indicators

Status: Fully modularized with 13 focused modules.
The TechnicalAnalysisMixin composes all modules for backward compatibility.
"""

from __future__ import annotations
