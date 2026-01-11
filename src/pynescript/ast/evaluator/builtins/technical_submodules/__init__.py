# Copyright 2024-2025 Yunseong Hwang, jango_blockchained
#
# Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.gnu.org/licenses/lgpl-3.0.en.html
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: LGPL-3.0-or-later

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
