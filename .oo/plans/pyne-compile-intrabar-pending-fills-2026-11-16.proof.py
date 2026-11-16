# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Proof: compile object-mode intra-bar pending fills match interpret."""

from __future__ import annotations

# ruff: noqa: S101, T201
import sys

from pynescript.compiler.strategy_broker import CompileStrategyBroker
from pynescript.runtime import Runtime

sys.path.insert(0, "tests")
import test_realtime_datafeed_ticks as t  # noqa: E402


def _run(src: str, mode: str) -> dict[str, object]:
    out = Runtime(symbol="RT").run(
        src,
        t._bars(5),
        mode=mode,
        realtime_ticks=3,
        data_feed=t._compile_tick_feed(),
    )
    assert "error" not in out, (mode, out.get("error"))
    return out


def main() -> None:
    interp = _run(t._PENDING_LIMIT, "interpret")
    compiled = _run(t._PENDING_LIMIT, "compile")
    pos_i = [float(v) for v in interp["series"]["pos"]]  # type: ignore[index]
    pos_c = [float(v) for v in compiled["series"]["pos"]]  # type: ignore[index]
    assert pos_i[-1] == 1.0, pos_i
    assert pos_c == pos_i, (pos_c, pos_i)

    for mode in ("interpret", "compile"):
        out = _run(t._PARTIAL_FILL, mode)
        pos = [float(v) for v in out["series"]["pos"]]  # type: ignore[index]
        assert pos[-1] == 3.0, (mode, pos)

    real = CompileStrategyBroker.process_pending_orders

    def boom(self, open_=None, high=None, low=None, close=None):
        if low is not None and float(low) <= 94.0:
            raise RuntimeError("compile tick fill boom")
        return real(self, open_=open_, high=high, low=low, close=close)

    CompileStrategyBroker.process_pending_orders = boom
    try:
        out = Runtime(symbol="RT").run(
            t._PENDING_LIMIT,
            t._bars(5),
            mode="compile",
            realtime_ticks=3,
            data_feed=t._compile_tick_feed(),
        )
    finally:
        CompileStrategyBroker.process_pending_orders = real
    assert out.get("error_kind") == "order", out
    assert "compile tick fill boom" in str(out.get("error") or "")

    print("COMPILE_INTRABAR_OK fill=1.0 partial=3.0 err=order match=1")


if __name__ == "__main__":
    main()
