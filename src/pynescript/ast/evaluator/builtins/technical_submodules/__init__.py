# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

"""Technical Analysis Indicator Submodules.

This module was refactored from a single 5,142-line file into a modular structure:

Modules:
- core.py: Shared validation helpers and base utilities
- moving_averages.py: SMA, EMA, KAMA, DEMA, TEMA, HMA, VWMA, SWMA
- oscillators.py: RSI, STOCH, MACD, CCI, ROC, WPR, TSI, divergence detectors
- volatility.py: ATR, BB, Keltner Channels, StochRSI, linear regression, etc
- volume.py: OBV, MFI, CMF, WAD, WAD indicators
- patterns.py: Engulfing, Hammer, Gap, Zigzag, Fractals, pivots
- advanced.py: Market microstructure, regime detection, strategy synthesis (Tiers 5-8)

Status: Core helpers created. Individual modules will be composed dynamically.
The original TechnicalAnalysisMixin remains functional with backward compatibility.
"""

from __future__ import annotations
