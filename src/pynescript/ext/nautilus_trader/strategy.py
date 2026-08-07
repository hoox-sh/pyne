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

"""Experimental Nautilus Trader strategy shell for Pine Script integration.

Requires the optional ``nautilus_trader`` dependency. Subclass and implement
:meth:`PinescriptStrategy.on_bar` to drive Pine evaluation on live bars.
"""

from __future__ import annotations

from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import Bar
from nautilus_trader.model.data import BarType
from nautilus_trader.model.data import TradeTick
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.trading.strategy import Strategy


class PinescriptStrategyConfig(StrategyConfig):
    """Config for :class:`PinescriptStrategy` (instrument + bar type)."""

    instrument_id: InstrumentId
    bar_type: BarType


class PinescriptStrategy(Strategy):
    """Minimal Nautilus strategy that subscribes to bars and trade ticks.

    Lifecycle hooks are stubs except subscription setup / teardown. Wire a
    Pyne Runtime or compiled script in :meth:`on_bar` for production use.
    """

    def __init__(self, config: PinescriptStrategyConfig):
        """Store instrument identifiers from *config*."""
        super().__init__(config)
        self.instrument_id = config.instrument_id
        self.bar_type = config.bar_type
        self.instrument: Instrument | None = None

    def on_start(self):
        """Resolve instrument and subscribe to bars + trade ticks."""
        self.instrument = self.cache.instrument(self.instrument_id)
        self.request_bars(self.bar_type)
        self.subscribe_bars(self.bar_type)
        self.subscribe_trade_ticks(self.instrument_id)

    def on_bar(self, bar: Bar):
        """Handle a new bar (override to run Pine)."""
        pass

    def on_trade_tick(self, tick: TradeTick):
        """Handle a trade tick (optional override)."""
        pass

    def on_stop(self):
        """Cancel orders, close positions, and unsubscribe streams."""
        self.cancel_all_orders(self.instrument_id)
        self.close_all_positions(self.instrument_id)
        self.unsubscribe_bars(self.bar_type)

    def on_reset(self):
        """Reset strategy state (no-op stub)."""
        pass
