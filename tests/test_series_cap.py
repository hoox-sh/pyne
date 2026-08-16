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

"""T1 goldens: host ``current_series`` cap vs uncapped last-N plot values.

Flag ``PYNE_SERIES_CAP`` (default ON). Cap size = ``max(_SERIES_MAX,
max_bars_back)`` or ``PYNE_SERIES_MAX``. Window periods ≪ cap must match
the uncapped oracle on the last N bars.
"""

from __future__ import annotations

import math

import pytest

from backend.runtime import Runtime
from backend.series import (
    DEFAULT_PINESERIES_HISTORY,
    DEFAULT_SERIES_MAX,
    SERIES_CAP_SLACK,
    PineSeries,
    estimate_series_bytes,
    parse_max_bars_back_from_source,
    pineseries_history_length,
    resolve_series_cap,
    series_cap_enabled,
    series_cap_limit,
    trim_series_lists,
)


def _clear_parse_cache() -> None:
    """Round-7 parse LRU returns the same AST object; evaluators may mutate it.

    Clearing between Runtime runs avoids empty plot capture on the 2nd+ call
    with identical source (Agent 05 residual — not T1).
    """
    try:
        from pynescript.ast.helper import clear_parse_cache

        clear_parse_cache()
    except Exception:  # noqa: BLE001
        pass


def _run(src: str, bars: list[dict]) -> dict:
    _clear_parse_cache()
    return Runtime().run(src, bars)


def _bars(n: int = 500, seed: float = 100.0) -> list[dict]:
    out: list[dict] = []
    x = seed
    for i in range(n):
        x += math.sin(i / 7.0) * 1.5 + 0.05
        out.append(
            {
                "time": 1_700_000_000_000 + i * 86_400_000,
                "open": x - 0.2,
                "high": x + 1.0,
                "low": x - 1.0,
                "close": x,
                "volume": 100.0 + (i % 10),
            }
        )
    return out


def _plot_values(result: dict, name: str | None = None) -> list:
    assert "error" not in result, result.get("error")
    series = result.get("series") or {}
    if name and name in series:
        return list(series[name])
    if not series:
        plots = result.get("plots") or []
        return list(plots)
    # First named series
    key = next(iter(series))
    return list(series[key])


def _last_n_close(a: list, b: list, n: int = 50, *, tol: float = 1e-9) -> None:
    assert len(a) == len(b)
    assert len(a) >= n
    for i, (x, y) in enumerate(zip(a[-n:], b[-n:], strict=True)):
        if x is None and y is None:
            continue
        assert x is not None and y is not None, f"na mismatch at tail[{i}]: {x!r} vs {y!r}"
        assert abs(float(x) - float(y)) <= tol, f"tail[{i}]: {x} != {y}"


# ---------------------------------------------------------------------------
# Pure policy / trim helpers
# ---------------------------------------------------------------------------


def test_series_cap_enabled_default_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYNE_SERIES_CAP", raising=False)
    assert series_cap_enabled() is True
    monkeypatch.setenv("PYNE_SERIES_CAP", "1")
    assert series_cap_enabled() is True
    for off in ("0", "false", "no", "off", "FALSE"):
        monkeypatch.setenv("PYNE_SERIES_CAP", off)
        assert series_cap_enabled() is False, off


def test_resolve_series_cap_max_bars_back_and_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PYNE_SERIES_MAX", raising=False)
    assert resolve_series_cap() == DEFAULT_SERIES_MAX
    assert resolve_series_cap(series_max=256, max_bars_back=100) == 256
    assert resolve_series_cap(series_max=256, max_bars_back=500) == 500
    monkeypatch.setenv("PYNE_SERIES_MAX", "128")
    assert resolve_series_cap(max_bars_back=500) == 128  # env absolute


def test_parse_max_bars_back_from_source() -> None:
    assert parse_max_bars_back_from_source('indicator("t", max_bars_back=400)') == 400
    assert parse_max_bars_back_from_source("strategy('s', max_bars_back = 900)") == 900
    src = 'indicator("a", max_bars_back=100)\n// max_bars_back=999'
    # both match; take max
    assert parse_max_bars_back_from_source(src) == 999
    assert parse_max_bars_back_from_source("indicator('x')") is None


def test_trim_series_lists_keeps_newest_and_bound() -> None:
    keep = 256
    lists = [list(range(400)) for _ in range(4)]
    n = trim_series_lists(lists, keep=keep, length_hint=400)
    assert n == keep
    assert all(len(lst) == keep for lst in lists)
    # chronological oldest→newest: after drop, first kept is 400-keep
    assert lists[0][0] == 400 - keep
    assert lists[0][-1] == 399

    # Under limit: no-op
    short = [list(range(10))]
    assert trim_series_lists(short, keep=keep) == 10
    assert short[0] == list(range(10))

    # Slack amortization: grow past keep+slack then snap to keep
    lim = series_cap_limit(keep)
    assert lim == keep + SERIES_CAP_SLACK
    grow = [list(range(keep))]
    for i in range(keep, lim + 1):
        grow[0].append(i)
        if len(grow[0]) > lim:
            trim_series_lists(grow, keep=keep, length_hint=len(grow[0]))
    assert len(grow[0]) == keep
    assert grow[0][-1] == lim


def test_pineseries_oob_is_na_not_zero() -> None:
    s = PineSeries(history_length=5)
    for i in range(3):
        s.update(float(i + 1))
    assert s[0] == 3.0
    assert s[2] == 1.0
    assert s[3] is None  # na — never 0
    assert s[100] is None
    assert s[-1] is None
    # inf / NaN offsets are na (do not raise, do not invent 0)
    assert s[float("inf")] is None
    assert s[float("-inf")] is None
    assert s[float("nan")] is None
    assert s[None] is None
    # stored 0.0 is a real sample
    z = PineSeries()
    z.update(0.0)
    assert z[0] == 0.0
    assert z[1] is None


def test_pineseries_set_history_length_keeps_newest() -> None:
    s = PineSeries(history_length=10)
    for i in range(8):
        s.update(float(i))
    s.set_history_length(4)
    assert len(s.history) == 4
    assert s[0] == 7.0
    assert s[3] == 4.0
    assert s[4] is None


def test_pineseries_history_length_floor() -> None:
    assert pineseries_history_length(series_cap=256) == DEFAULT_PINESERIES_HISTORY
    assert pineseries_history_length(series_cap=2000) == 2000


def test_estimate_series_bytes_structural() -> None:
    # Structural proof: capped storage ≪ full-history for long charts
    full = estimate_series_bytes(50_000, n_lists=6)
    cap = estimate_series_bytes(DEFAULT_SERIES_MAX, n_lists=6)
    assert cap < full
    assert full // cap >= 100


# ---------------------------------------------------------------------------
# Runtime goldens: capped ≡ uncapped last N for periods ≪ cap
# ---------------------------------------------------------------------------


@pytest.fixture
def restore_series_env(monkeypatch: pytest.MonkeyPatch):
    """Isolate series-cap env for each test."""
    monkeypatch.delenv("PYNE_SERIES_CAP", raising=False)
    monkeypatch.delenv("PYNE_SERIES_MAX", raising=False)
    yield monkeypatch


def test_runtime_sma_last_n_matches_uncapped(restore_series_env: pytest.MonkeyPatch) -> None:
    """SMA(20) on 500 bars: last 80 values identical with cap on vs off."""
    monkeypatch = restore_series_env
    bars = _bars(500)
    src = """
//@version=5
indicator("sma cap")
plot(ta.sma(close, 20), "s")
"""
    monkeypatch.setenv("PYNE_SERIES_CAP", "0")
    uncapped = _plot_values(_run(src, bars), "s")
    monkeypatch.setenv("PYNE_SERIES_CAP", "1")
    capped = _plot_values(_run(src, bars), "s")
    assert len(uncapped) == 500
    _last_n_close(capped, uncapped, n=80)


def test_runtime_ema_rsi_last_n_matches_uncapped(restore_series_env: pytest.MonkeyPatch) -> None:
    """Recursive MAs under default incremental TA stay bit-stable with list cap."""
    monkeypatch = restore_series_env
    bars = _bars(600)
    src = """
//@version=5
indicator("ema rsi cap")
plot(ta.ema(close, 12), "e")
plot(ta.rsi(close, 14), "r")
"""
    monkeypatch.setenv("PYNE_SERIES_CAP", "0")
    r0 = _run(src, bars)
    monkeypatch.setenv("PYNE_SERIES_CAP", "1")
    r1 = _run(src, bars)
    assert "error" not in r0 and "error" not in r1
    _last_n_close(r1["series"]["e"], r0["series"]["e"], n=100)
    _last_n_close(r1["series"]["r"], r0["series"]["r"], n=100)


def test_runtime_combo_periods_within_cap(restore_series_env: pytest.MonkeyPatch) -> None:
    monkeypatch = restore_series_env
    bars = _bars(400)
    src = """
//@version=5
indicator("combo")
plot(ta.sma(close, 50), "s50")
plot(ta.ema(close, 26), "e26")
plot(ta.atr(14), "a14")
"""
    monkeypatch.setenv("PYNE_SERIES_CAP", "0")
    u = _run(src, bars)
    monkeypatch.setenv("PYNE_SERIES_CAP", "1")
    c = _run(src, bars)
    for name in ("s50", "e26", "a14"):
        _last_n_close(c["series"][name], u["series"][name], n=60)


def test_runtime_max_bars_back_raises_cap(
    restore_series_env: pytest.MonkeyPatch,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Declaration max_bars_back=400 must raise host list cap above 256."""
    # Capture evaluator after run via monkeypatch of CustomEvaluator init path
    from backend import runtime as runtime_mod

    captured: dict = {}
    Real = runtime_mod.CustomEvaluator

    class Spy(Real):  # type: ignore[misc, valid-type]
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            captured["ev"] = self

    monkeypatch.setattr(runtime_mod, "CustomEvaluator", Spy)
    restore_series_env.setenv("PYNE_SERIES_CAP", "1")
    src = """
//@version=5
indicator("mbb", max_bars_back=400)
plot(ta.sma(close, 20), "s")
"""
    r = _run(src, _bars(500))
    assert "error" not in r, r.get("error")
    ev = captured.get("ev")
    assert ev is not None
    assert getattr(ev, "_pine_series_cap_enabled", None) is True
    assert getattr(ev, "_pine_series_cap", None) == 400


def test_runtime_cap_off_allows_full_length_growth(
    restore_series_env: pytest.MonkeyPatch,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend import runtime as runtime_mod

    captured: dict = {}
    Real = runtime_mod.CustomEvaluator

    class Spy(Real):  # type: ignore[misc, valid-type]
        def visit(self, node):  # type: ignore[override]
            # After appends, mid-run length can exceed _SERIES_MAX when cap off
            return super().visit(node)

        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            captured["ev"] = self

    monkeypatch.setattr(runtime_mod, "CustomEvaluator", Spy)
    restore_series_env.setenv("PYNE_SERIES_CAP", "0")
    n_bars = 400
    src = """
//@version=5
indicator("uncapped")
plot(close, "c")
"""
    r = _run(src, _bars(n_bars))
    assert "error" not in r
    ev = captured["ev"]
    close_list = (ev.current_series or {}).get("close") or []
    assert len(close_list) == n_bars
    assert getattr(ev, "_pine_series_cap_enabled", True) is False


def test_runtime_cap_on_bounds_current_series(
    restore_series_env: pytest.MonkeyPatch,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend import runtime as runtime_mod

    captured: dict = {}
    Real = runtime_mod.CustomEvaluator

    class Spy(Real):  # type: ignore[misc, valid-type]
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            captured["ev"] = self

    monkeypatch.setattr(runtime_mod, "CustomEvaluator", Spy)
    restore_series_env.setenv("PYNE_SERIES_CAP", "1")
    restore_series_env.delenv("PYNE_SERIES_MAX", raising=False)
    n_bars = 500
    src = """
//@version=5
indicator("capped")
plot(close, "c")
"""
    r = _run(src, _bars(n_bars))
    assert "error" not in r
    ev = captured["ev"]
    cap = int(getattr(ev, "_pine_series_cap", DEFAULT_SERIES_MAX) or DEFAULT_SERIES_MAX)
    close_list = (ev.current_series or {}).get("close") or []
    # After last bar: length is in [keep, keep+slack]; never above keep+slack.
    assert len(close_list) <= cap + SERIES_CAP_SLACK
    assert len(close_list) <= n_bars
    # With 500 bars and cap 256, must have trimmed.
    assert len(close_list) < n_bars
    assert cap <= len(close_list) <= cap + SERIES_CAP_SLACK


def test_runtime_pyne_series_max_override(
    restore_series_env: pytest.MonkeyPatch,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend import runtime as runtime_mod

    captured: dict = {}
    Real = runtime_mod.CustomEvaluator

    class Spy(Real):  # type: ignore[misc, valid-type]
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            captured["ev"] = self

    monkeypatch.setattr(runtime_mod, "CustomEvaluator", Spy)
    restore_series_env.setenv("PYNE_SERIES_CAP", "1")
    restore_series_env.setenv("PYNE_SERIES_MAX", "64")
    r = _run(
        '//@version=5\nindicator("x")\nplot(ta.sma(close, 10), "s")',
        _bars(200),
    )
    assert "error" not in r
    assert captured["ev"]._pine_series_cap == 64
    close_list = captured["ev"].current_series["close"]
    assert len(close_list) <= 64 + SERIES_CAP_SLACK


def test_apply_bar_sample_writes_wrapper_and_optional_list() -> None:
    from backend.series import apply_bar_sample

    s = PineSeries(history_length=8)
    dest: list[float] = []
    apply_bar_sample(s, 1.0, dest)
    apply_bar_sample(s, 2.0, dest)
    apply_bar_sample(s, 3.0, dest)
    assert s.current == 3.0
    assert s[0] == 3.0
    assert s[1] == 2.0
    assert dest == [1.0, 2.0, 3.0]
    apply_bar_sample(s, 4.0, dest=None)
    assert s[0] == 4.0
    assert dest == [1.0, 2.0, 3.0]


def test_unused_derived_lists_stay_empty_when_not_named(
    restore_series_env: pytest.MonkeyPatch,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend import runtime as runtime_mod

    captured: dict = {}
    Real = runtime_mod.CustomEvaluator

    class Spy(Real):  # type: ignore[misc, valid-type]
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            captured["ev"] = self

    monkeypatch.setattr(runtime_mod, "CustomEvaluator", Spy)
    r = _run('//@version=5\nindicator("x")\nplot(close, "c")\n', _bars(20))
    assert "error" not in r
    cs = captured["ev"].current_series
    assert len(cs["close"]) == 20
    assert len(cs.get("hl2") or []) == 0
    assert len(cs.get("tr") or []) == 0
