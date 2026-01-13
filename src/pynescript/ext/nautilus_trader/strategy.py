# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

from __future__ import annotations

from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import Bar
from nautilus_trader.model.data import BarType
from nautilus_trader.model.data import TradeTick
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.trading.strategy import Strategy


class PinescriptStrategyConfig(StrategyConfig):
    instrument_id: InstrumentId
    bar_type: BarType


class PinescriptStrategy(Strategy):
    def __init__(self, config: PinescriptStrategyConfig):
        super().__init__(config)
        self.instrument_id = config.instrument_id
        self.bar_type = config.bar_type
        self.instrument: Instrument | None = None

    def on_start(self):
        self.instrument = self.cache.instrument(self.instrument_id)
        self.request_bars(self.bar_type)
        self.subscribe_bars(self.bar_type)
        self.subscribe_trade_ticks(self.instrument_id)

    def on_bar(self, bar: Bar):
        pass

    def on_trade_tick(self, tick: TradeTick):
        pass

    def on_stop(self):
        self.cancel_all_orders(self.instrument_id)
        self.close_all_positions(self.instrument_id)
        self.unsubscribe_bars(self.bar_type)

    def on_reset(self):
        pass
