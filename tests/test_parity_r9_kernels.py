# Copyright (C) 2024-2026 jango_blockchained
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Round 9 residual parity: stoch slot stability + Heikin-Ashi security."""

from __future__ import annotations

from backend.runtime import Runtime


def _bars(n: int = 200) -> list[dict]:
    bars: list[dict] = []
    price = 100.0
    for i in range(n):
        o = round(price, 2)
        c = round(price + (1.0 if i % 3 else -0.5), 2)
        h = round(max(o, c) + 0.8, 2)
        lo = round(min(o, c) - 0.8, 2)
        bars.append(
            {
                "open": o,
                "high": h,
                "low": max(lo, 0.01),
                "close": c,
                "time": 1_000_000 + i * 86_400_000,
                "volume": 1000.0 + i,
            }
        )
        price = c
    return bars


class TestStochSlotDoesNotStealEmaSeed:
    def test_ema_after_stoch_on_rsi(self) -> None:
        """stoch must always consume a TA slot even when rsi is still na."""
        src = """//@version=4
study("t")
src = input(close)
rsi1 = rsi(src, 14)
k = stoch(rsi1, rsi1, rsi1, 14)
plot(ema(close, 200), "e")
plot(k, "k")
"""
        r = Runtime().run(src, _bars(200), mode="interpret")
        assert "error" not in r, r.get("error")
        e = r["series"]["e"]
        assert sum(1 for x in e if x is not None) >= 1
        assert e[-1] is not None
        assert abs(float(e[-1]) - 149.7475) < 1e-2


class TestHeikinAshiSecurityParity:
    def test_ha_security_tuple_interp_compile(self) -> None:
        src = """//@version=5
indicator("t")
[haopen, haclose, hahigh,halow] = request.security(
     ticker.heikinashi(syminfo.tickerid), timeframe.period, [open, close, high, low])
plot(haopen, "o")
plot(haclose, "c")
plot(hahigh, "h")
plot(halow, "l")
"""
        bars = _bars(40)
        ri = Runtime().run(src, bars, mode="interpret")
        rc = Runtime().run(src, bars, mode="compile")
        assert "error" not in ri and "error" not in rc
        for key in ("o", "c", "h", "l"):
            si, sc = ri["series"][key], rc["series"][key]
            assert len(si) == len(sc) == len(bars)
            for a, b in zip(si, sc, strict=True):
                assert a is not None and b == b  # not nan
                assert abs(float(a) - float(b)) < 1e-6

    def test_corpus_ha_ssl_strategy_parity(self) -> None:
        from pathlib import Path

        path = Path("tests/data/set01/strategies/045_str_ha_univlong_and_short_futures.pine")
        if not path.is_file():
            return
        import importlib.util
        from pathlib import Path as P

        root = P(".").resolve()
        spec = importlib.util.spec_from_file_location("h", root / "scripts" / "compare_interp_compile.py")
        assert spec and spec.loader
        h = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(h)
        r = h.run_one_script(str(path.resolve()), 200, ignore_hline_keys=True, ignore_fill_keys=True)
        assert r["status"] in ("OK", "fill_background_only", "both_error_same", "expected_error"), r


class TestStochRsiSupertrendCorpus:
    def test_strategy_073_parity(self) -> None:
        from pathlib import Path
        import importlib.util

        path = Path("tests/data/set01/strategies/073_str_stochrsi_plus_supertrend_strategy.pine")
        if not path.is_file():
            return
        root = Path(".").resolve()
        spec = importlib.util.spec_from_file_location("h", root / "scripts" / "compare_interp_compile.py")
        assert spec and spec.loader
        h = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(h)
        r = h.run_one_script(str(path.resolve()), 200, ignore_hline_keys=True, ignore_fill_keys=True)
        assert r["status"] in ("OK", "fill_background_only"), r
