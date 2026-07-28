# Copyright (C) 2024-2026 jango_blockchained
#
# This file is part of pynescript.
#
# pynescript is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pynescript is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with pynescript.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: AGPL-3.0-or-later

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
