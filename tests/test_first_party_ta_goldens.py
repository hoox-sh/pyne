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

"""First-party dual-host goldens for ATR / Supertrend / Keltner (Wave B).

Shipped fixtures under ``tests/fixtures/first_party/`` plus deterministic
synthetic OHLCV. Both ``mode=interpret`` and ``mode=compile`` must agree
(nan/None-aware allclose). ATR asserts Wilder RMA warmup (first finite
value after ``period`` TR samples → bar index ``>= period``). Supertrend
locks the simplified ``mid ± factor·ATR`` contract (na ATR → 0; direction
from close vs mid) — not the reference Pine band ratchet. Factor/period
pairs ``3.0/5`` and ``3.0/10`` assert interpret ≡ compile ≡ incremental ≡
numba; after ATR warmup ``st == mid ± factor * atr``. TV ratchet is out
of scope (not a residual hole).
"""

from __future__ import annotations

import math
import random
from pathlib import Path
from typing import Any

import pytest

from backend.runtime import Runtime

_ROOT = Path(__file__).resolve().parents[1]
_FIRST_PARTY = _ROOT / "tests" / "fixtures" / "first_party"

# Fixed seed for reproducible OHLCV (same spirit as fixtures/parity/ohlcv.py).
_SEED = 42
_N_BARS = 120

# Default dual-host tolerances (match scripts/compare_interp_compile.py).
_RTOL = 1e-5
_ATOL = 1e-6


def _is_na(v: object) -> bool:
    if v is None:
        return True
    if isinstance(v, float):
        return math.isnan(v)
    try:
        if hasattr(v, "dtype") and hasattr(v, "item"):
            return bool(math.isnan(float(v)))  # type: ignore[arg-type]
        return bool(math.isnan(float(v)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False


def _to_float_or_none(v: object) -> float | None:
    if _is_na(v):
        return None
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def series_allclose(
    a: list[Any],
    b: list[Any],
    *,
    rtol: float = _RTOL,
    atol: float = _ATOL,
) -> tuple[bool, str]:
    """Nan/None-aware series comparison (interp vs compile)."""
    if len(a) != len(b):
        return False, f"length {len(a)} != {len(b)}"
    n_bad = 0
    first_i = -1
    first_detail = ""
    max_abs = 0.0
    for i, (x, y) in enumerate(zip(a, b, strict=True)):
        if _is_na(x) and _is_na(y):
            continue
        fx, fy = _to_float_or_none(x), _to_float_or_none(y)
        if fx is None or fy is None:
            n_bad += 1
            if first_i < 0:
                first_i = i
                first_detail = f"type/na interp={x!r} compile={y!r}"
            continue
        diff = abs(fx - fy)
        tol = atol + rtol * abs(fy)
        if diff > tol:
            n_bad += 1
            max_abs = max(max_abs, diff)
            if first_i < 0:
                first_i = i
                first_detail = f"interp={fx!r} compile={fy!r}"
    if n_bad == 0:
        return True, ""
    return (
        False,
        f"index {first_i}: {first_detail} n_bad={n_bad} max_abs={max_abs:.6g}",
    )


def make_ohlcv(n: int = _N_BARS, seed: int = _SEED) -> list[dict[str, Any]]:
    """Deterministic synthetic OHLCV (sine trend + gaussian noise)."""
    rng = random.Random(seed)
    bars: list[dict[str, Any]] = []
    price = 100.0
    for i in range(n):
        trend = 15.0 * math.sin(2.0 * math.pi * i / max(n * 0.7, 1.0))
        noise = rng.gauss(0, 2.0)
        open_ = round(price + noise, 2)
        close_ = round(open_ + trend * 0.3 + rng.gauss(0, 1.0), 2)
        high_ = round(max(open_, close_) + abs(rng.gauss(0, 1.0)), 2)
        low_ = round(min(open_, close_) - abs(rng.gauss(0, 1.0)), 2)
        high_ = max(high_, low_ + 0.01)
        low_ = max(low_, 0.01)
        bars.append(
            {
                "open": open_,
                "high": high_,
                "low": low_,
                "close": close_,
                "time": 1_000_000 + i * 86_400_000,
                "volume": 1000.0 + i,
            }
        )
        price = close_
    return bars


def _run_dual(
    source: str,
    bars: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run interpret + compile; skip only if compile hard-fails on optional dep."""
    rt = Runtime(symbol="GOLDEN")
    interp = rt.run(source, bars, mode="interpret")
    try:
        compiled = rt.run(source, bars, mode="compile")
    except Exception as exc:  # pragma: no cover - optional dep / host edge
        msg = str(exc).lower()
        if "numba" in msg or "no module named" in msg:
            pytest.skip(f"compile path unavailable: {exc}")
        raise
    return interp, compiled


def _assert_no_error(result: dict[str, Any], mode: str) -> None:
    err = result.get("error")
    assert not err, f"{mode} error: {err}"


def _assert_series_present(result: dict[str, Any], keys: tuple[str, ...], n: int) -> None:
    series = result.get("series") or {}
    for key in keys:
        assert key in series, f"missing series key {key!r}; have {list(series)}"
        assert len(series[key]) == n, f"{key}: len {len(series[key])} != {n}"


def _assert_dual_parity(
    interp: dict[str, Any],
    compiled: dict[str, Any],
    keys: tuple[str, ...],
) -> None:
    si = interp["series"]
    sc = compiled["series"]
    for key in keys:
        ok, detail = series_allclose(si[key], sc[key])
        assert ok, f"{key}: {detail}"


def _first_finite_index(values: list[Any]) -> int | None:
    for i, v in enumerate(values):
        if not _is_na(v):
            return i
    return None


def _all_finite_after(values: list[Any], start: int) -> bool:
    for v in values[start:]:
        if _is_na(v):
            return False
        try:
            fv = float(v)
        except (TypeError, ValueError):
            return False
        if not math.isfinite(fv):
            return False
    return True


@pytest.fixture(scope="module")
def bars() -> list[dict[str, Any]]:
    return make_ohlcv()


def test_fixture_files_shipped() -> None:
    for name in ("atr.pine", "supertrend.pine", "keltner.pine"):
        path = _FIRST_PARTY / name
        assert path.is_file(), f"first-party fixture must ship: {path}"


def test_atr_wilder_dual_host(bars: list[dict[str, Any]]) -> None:
    """``ta.atr(14)``: RMA-of-TR warmup + interpret≈compile."""
    path = _FIRST_PARTY / "atr.pine"
    src = path.read_text(encoding="utf-8")
    period = 14
    interp, compiled = _run_dual(src, bars)
    _assert_no_error(interp, "interpret")
    _assert_no_error(compiled, "compile")
    _assert_series_present(interp, ("atr",), len(bars))
    _assert_series_present(compiled, ("atr",), len(bars))
    _assert_dual_parity(interp, compiled, ("atr",))

    atr = interp["series"]["atr"]
    first = _first_finite_index(atr)
    assert first is not None, "ATR never becomes valid"
    # Wilder ATR: first valid after ``period`` TR samples → index ``>= period``
    # (bar 0 has no TR; seed uses TR bars 1..period → first value at index period).
    assert first >= period, f"ATR first valid at {first}, expected >= {period}"
    assert _all_finite_after(atr, first), f"ATR non-finite after warmup bar {first}"
    # Compile path same warmup
    c_first = _first_finite_index(compiled["series"]["atr"])
    assert c_first == first


_ST_FACTOR = 3.0
_ST_ATR_PERIOD = 10
_ST_PAIRS = ((3.0, 5), (3.0, 10))


def _supertrend_inline_src(factor: float, period: int, tag: str = "") -> str:
    name = f"fp_st_{factor}_{period}{tag}"
    return f"""//@version=5
indicator("{name}")
// Simplified mid±factor·ATR Supertrend (not TV band ratchet).
[st, dir] = ta.supertrend({factor}, {period})
plot(st, title="st")
plot(dir, title="dir")
plot(ta.atr({period}), title="atr")
plot(hl2, title="mid")
plot(close, title="c")
"""


def _ohlc_from_bars(bars: list[dict[str, Any]]) -> tuple[list[float], list[float], list[float]]:
    return (
        [float(b["high"]) for b in bars],
        [float(b["low"]) for b in bars],
        [float(b["close"]) for b in bars],
    )


def _assert_simplified_supertrend_contract(
    st: list[Any],
    direction: list[Any],
    atr: list[Any],
    mid: list[Any],
    close: list[Any],
    *,
    factor: float = _ST_FACTOR,
    atr_period: int = _ST_ATR_PERIOD,
    host: str = "interpret",
) -> None:
    """Lock mid ± factor·ATR (na ATR → 0); dir from close vs mid. Not TV ratchet."""
    n = len(st)
    assert n == len(direction) == len(atr) == len(mid) == len(close)
    first = _first_finite_index(st)
    assert first == 0, f"{host}: warmup st should be finite (na ATR→0 → st==mid), first={first}"
    assert _all_finite_after(st, 0), f"{host}: st non-finite after bar 0"
    assert _all_finite_after(direction, 0), f"{host}: dir non-finite after bar 0"
    n_up = n_down = 0
    for i in range(n):
        mid_f = float(mid[i])
        close_f = float(close[i])
        st_f = float(st[i])
        dir_f = float(direction[i])
        atr_raw = atr[i]
        atr_f = 0.0 if _is_na(atr_raw) else float(atr_raw)
        exp_dir = -1.0 if close_f >= mid_f else 1.0
        exp_st = mid_f - factor * atr_f if exp_dir < 0 else mid_f + factor * atr_f
        assert dir_f == exp_dir, f"{host} bar {i}: dir {dir_f} != {exp_dir} (close={close_f} mid={mid_f})"
        assert abs(st_f - exp_st) <= _ATOL + _RTOL * abs(exp_st), (
            f"{host} bar {i}: st {st_f} != mid±factor·ATR {exp_st} (atr={atr_f})"
        )
        if dir_f < 0:
            n_up += 1
        else:
            n_down += 1
        if i < atr_period:
            assert _is_na(atr_raw), f"{host} bar {i}: ATR should still be na"
            assert abs(st_f - mid_f) <= _ATOL + _RTOL * abs(mid_f), f"{host} bar {i}: warmup st {st_f} != mid {mid_f}"
        elif not _is_na(atr_raw) and atr_f > 0:
            assert abs(abs(st_f - mid_f) - factor * atr_f) <= _ATOL + _RTOL * factor * atr_f
    assert n_up >= 1 and n_down >= 1, f"{host}: expected both directions, up={n_up} down={n_down}"


def _assert_formula_after_atr_warmup(  # noqa: PLR0913
    st: list[Any],
    direction: list[Any],
    atr: list[Any],
    mid: list[Any],
    close: list[Any],
    *,
    factor: float,
    atr_period: int,
    host: str,
) -> None:
    """Explicit golden: after ATR warmup, ``st == mid ± factor * atr``."""
    first_atr = _first_finite_index(atr)
    assert first_atr is not None, f"{host}: ATR never becomes valid"
    assert first_atr >= atr_period, f"{host}: ATR first valid at {first_atr}, expected >= {atr_period}"
    n_checked = 0
    for i in range(first_atr, len(st)):
        assert not _is_na(atr[i]), f"{host} bar {i}: ATR na after warmup"
        mid_f = float(mid[i])
        close_f = float(close[i])
        atr_f = float(atr[i])
        st_f = float(st[i])
        dir_f = float(direction[i])
        exp_dir = -1.0 if close_f >= mid_f else 1.0
        exp_st = mid_f - factor * atr_f if exp_dir < 0 else mid_f + factor * atr_f
        assert dir_f == exp_dir, f"{host} bar {i}: dir {dir_f} != {exp_dir} (close={close_f} mid={mid_f})"
        assert abs(st_f - exp_st) <= _ATOL + _RTOL * abs(exp_st), (
            f"{host} bar {i}: st {st_f} != mid±factor·ATR {exp_st} (mid={mid_f} factor={factor} atr={atr_f})"
        )
        n_checked += 1
    assert n_checked >= 10, f"{host}: too few post-warmup bars ({n_checked})"


def _walk_eval_supertrend(
    bars: list[dict[str, Any]],
    factor: float,
    period: int,
    *,
    incremental: bool,
) -> tuple[list[float], list[int]]:
    from pynescript.ast.evaluator import NodeLiteralEvaluator

    class _Ev(NodeLiteralEvaluator):
        def __init__(self) -> None:
            super().__init__()
            if incremental:
                self._pine_bar_mode = True
                self._pine_ta_incremental = True
                self._ta_inc_state: dict = {}
                self._ta_call_i = 0

    ev = _Ev()
    highs, lows, closes = _ohlc_from_bars(bars)
    st: list[float] = []
    direction: list[int] = []
    for i in range(len(closes)):
        ev.current_series = {
            "high": highs[: i + 1],
            "low": lows[: i + 1],
            "close": closes[: i + 1],
        }
        if incremental:
            ev._ta_call_i = 0
            val, dir_ = ev._supertrend_inc_update(highs[: i + 1], lows[: i + 1], closes[: i + 1], factor, period)
        else:
            val, dir_ = ev._builtin_ta_supertrend([factor, period])
        st.append(float(val))
        direction.append(int(dir_))
    return st, direction


def _walk_numba_supertrend(
    bars: list[dict[str, Any]],
    factor: float,
    period: int,
    *,
    incremental: bool,
) -> tuple[list[float], list[int]]:
    import numpy as np

    from pynescript.compiler import numba_builtins as nb

    highs, lows, closes = _ohlc_from_bars(bars)
    high_a = np.asarray(highs, dtype=np.float64)
    low_a = np.asarray(lows, dtype=np.float64)
    close_a = np.asarray(closes, dtype=np.float64)
    st_state = np.full(2, np.nan)
    st: list[float] = []
    direction: list[int] = []
    for i in range(len(closes)):
        if incremental:
            val, dir_ = nb.numba_supertrend_inc(high_a, low_a, close_a, factor, period, i, st_state)
        else:
            val, dir_ = nb.numba_supertrend(high_a, low_a, close_a, factor, period, i)
        st.append(float(val))
        direction.append(int(dir_))
    return st, direction


def _maybe_clear_parse_cache() -> None:
    try:
        from pynescript.ast.helper import clear_parse_cache
    except ImportError:  # pragma: no cover
        return
    clear_parse_cache()


def _assert_hosts_match(
    hosts: list[tuple[str, list[Any], list[Any]]],
) -> None:
    ref_name, ref_st, ref_dir = hosts[0]
    for name, st, direction in hosts[1:]:
        ok, detail = series_allclose(ref_st, st)
        assert ok, f"{ref_name} vs {name} st: {detail}"
        ok, detail = series_allclose(ref_dir, direction)
        assert ok, f"{ref_name} vs {name} dir: {detail}"


def test_supertrend_dual_host(bars: list[dict[str, Any]]) -> None:
    """Supertrend ATR consumer: simplified mid±factor·ATR, interpret≈compile."""
    path = _FIRST_PARTY / "supertrend.pine"
    src = path.read_text(encoding="utf-8")
    interp, compiled = _run_dual(src, bars)
    _assert_no_error(interp, "interpret")
    _assert_no_error(compiled, "compile")
    keys = ("st", "dir", "atr", "mid", "c")
    _assert_series_present(interp, keys, len(bars))
    _assert_series_present(compiled, keys, len(bars))
    _assert_dual_parity(interp, compiled, keys)

    si = interp["series"]
    sc = compiled["series"]
    _assert_simplified_supertrend_contract(si["st"], si["dir"], si["atr"], si["mid"], si["c"], host="interpret")
    _assert_simplified_supertrend_contract(sc["st"], sc["dir"], sc["atr"], sc["mid"], sc["c"], host="compile")
    _assert_formula_after_atr_warmup(
        si["st"],
        si["dir"],
        si["atr"],
        si["mid"],
        si["c"],
        factor=_ST_FACTOR,
        atr_period=_ST_ATR_PERIOD,
        host="interpret",
    )
    _assert_formula_after_atr_warmup(
        sc["st"],
        sc["dir"],
        sc["atr"],
        sc["mid"],
        sc["c"],
        factor=_ST_FACTOR,
        atr_period=_ST_ATR_PERIOD,
        host="compile",
    )


@pytest.mark.parametrize("factor,period", _ST_PAIRS)
def test_supertrend_dual_host_factor_period(
    bars: list[dict[str, Any]],
    factor: float,
    period: int,
) -> None:
    """Dual-host goldens for factor/period 3.0/5 and 3.0/10."""
    src = _supertrend_inline_src(factor, period)
    interp, compiled = _run_dual(src, bars)
    _assert_no_error(interp, "interpret")
    _assert_no_error(compiled, "compile")
    keys = ("st", "dir", "atr", "mid", "c")
    _assert_series_present(interp, keys, len(bars))
    _assert_series_present(compiled, keys, len(bars))
    _assert_dual_parity(interp, compiled, keys)
    si = interp["series"]
    sc = compiled["series"]
    _assert_simplified_supertrend_contract(
        si["st"],
        si["dir"],
        si["atr"],
        si["mid"],
        si["c"],
        factor=factor,
        atr_period=period,
        host="interpret",
    )
    _assert_simplified_supertrend_contract(
        sc["st"],
        sc["dir"],
        sc["atr"],
        sc["mid"],
        sc["c"],
        factor=factor,
        atr_period=period,
        host="compile",
    )


@pytest.mark.parametrize("factor,period", _ST_PAIRS)
def test_supertrend_formula_after_atr_warmup(
    bars: list[dict[str, Any]],
    factor: float,
    period: int,
) -> None:
    """After ATR warmup, ``st == mid ± factor * atr`` on interpret and compile."""
    src = _supertrend_inline_src(factor, period, tag="_formula")
    interp, compiled = _run_dual(src, bars)
    _assert_no_error(interp, "interpret")
    _assert_no_error(compiled, "compile")
    keys = ("st", "dir", "atr", "mid", "c")
    _assert_series_present(interp, keys, len(bars))
    _assert_series_present(compiled, keys, len(bars))
    si = interp["series"]
    sc = compiled["series"]
    _assert_formula_after_atr_warmup(
        si["st"],
        si["dir"],
        si["atr"],
        si["mid"],
        si["c"],
        factor=factor,
        atr_period=period,
        host="interpret",
    )
    _assert_formula_after_atr_warmup(
        sc["st"],
        sc["dir"],
        sc["atr"],
        sc["mid"],
        sc["c"],
        factor=factor,
        atr_period=period,
        host="compile",
    )


@pytest.mark.parametrize("factor,period", _ST_PAIRS)
def test_supertrend_interpret_compile_inc_numba(
    bars: list[dict[str, Any]],
    factor: float,
    period: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """interpret-full ≡ interpret-inc ≡ compile ≡ numba (full + inc)."""
    src = _supertrend_inline_src(factor, period, tag="_4host")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)
    _maybe_clear_parse_cache()
    interp_inc = Runtime(symbol="GOLDEN").run(src, bars, mode="interpret")
    _assert_no_error(interp_inc, "interpret-inc")

    monkeypatch.setenv("PYNE_TA_INCREMENTAL", "0")
    _maybe_clear_parse_cache()
    interp_full = Runtime(symbol="GOLDEN").run(src, bars, mode="interpret")
    _assert_no_error(interp_full, "interpret-full")
    monkeypatch.delenv("PYNE_TA_INCREMENTAL", raising=False)

    _maybe_clear_parse_cache()
    try:
        compiled = Runtime(symbol="GOLDEN").run(src, bars, mode="compile")
    except Exception as exc:  # pragma: no cover - optional dep
        msg = str(exc).lower()
        if "numba" in msg or "no module named" in msg:
            pytest.skip(f"compile path unavailable: {exc}")
        raise
    _assert_no_error(compiled, "compile")
    assert compiled.get("object_mode") is False, "compile Supertrend must stay nopython"

    try:
        nb_full_st, nb_full_dir = _walk_numba_supertrend(bars, factor, period, incremental=False)
        nb_inc_st, nb_inc_dir = _walk_numba_supertrend(bars, factor, period, incremental=True)
    except Exception as exc:  # pragma: no cover
        msg = str(exc).lower()
        if "numba" in msg or "no module named" in msg:
            pytest.skip(f"numba kernels unavailable: {exc}")
        raise

    ev_full_st, ev_full_dir = _walk_eval_supertrend(bars, factor, period, incremental=False)
    ev_inc_st, ev_inc_dir = _walk_eval_supertrend(bars, factor, period, incremental=True)
    keys = ("st", "dir")
    _assert_series_present(interp_inc, keys, len(bars))
    _assert_series_present(interp_full, keys, len(bars))
    _assert_series_present(compiled, keys, len(bars))
    hosts: list[tuple[str, list[Any], list[Any]]] = [
        ("interpret-inc", interp_inc["series"]["st"], interp_inc["series"]["dir"]),
        ("interpret-full", interp_full["series"]["st"], interp_full["series"]["dir"]),
        ("compile", compiled["series"]["st"], compiled["series"]["dir"]),
        ("numba", nb_full_st, nb_full_dir),
        ("numba-inc", nb_inc_st, nb_inc_dir),
        ("eval-full", ev_full_st, ev_full_dir),
        ("eval-inc", ev_inc_st, ev_inc_dir),
    ]
    _assert_hosts_match(hosts)
    mid = interp_inc["series"]["mid"]
    close = interp_inc["series"]["c"]
    atr = interp_inc["series"]["atr"]
    for name, st, direction in hosts:
        _assert_formula_after_atr_warmup(
            st,
            direction,
            atr,
            mid,
            close,
            factor=factor,
            atr_period=period,
            host=name,
        )


def test_keltner_dual_host(bars: list[dict[str, Any]]) -> None:
    """Keltner channels (EMA ± mult×ATR): dual-host mid/up/lo parity."""
    path = _FIRST_PARTY / "keltner.pine"
    src = path.read_text(encoding="utf-8")
    interp, compiled = _run_dual(src, bars)
    _assert_no_error(interp, "interpret")
    _assert_no_error(compiled, "compile")
    keys = ("mid", "up", "lo")
    _assert_series_present(interp, keys, len(bars))
    _assert_series_present(compiled, keys, len(bars))
    _assert_dual_parity(interp, compiled, keys)

    mid = interp["series"]["mid"]
    up = interp["series"]["up"]
    lo = interp["series"]["lo"]
    first = _first_finite_index(mid)
    assert first is not None
    # EMA length 20 → first mid at index 19; bands track mid/ATR after that
    assert first >= 19
    assert _all_finite_after(mid, first)
    # Band ordering when ATR > 0
    checked = 0
    for i in range(first, len(bars)):
        if _is_na(up[i]) or _is_na(lo[i]) or _is_na(mid[i]):
            continue
        u, m, l = float(up[i]), float(mid[i]), float(lo[i])
        assert u >= m - 1e-9, f"bar {i}: upper {u} < mid {m}"
        assert l <= m + 1e-9, f"bar {i}: lower {l} > mid {m}"
        checked += 1
    assert checked >= 10


def test_inline_atr_compile_object_mode_ok(bars: list[dict[str, Any]]) -> None:
    """Inline ATR script still dual-hosts (object mode allowed if no Numba)."""
    src = """//@version=5
indicator("inline_atr")
plot(ta.atr(10), title="atr")
"""
    interp, compiled = _run_dual(src, bars)
    _assert_no_error(interp, "interpret")
    _assert_no_error(compiled, "compile")
    _assert_series_present(interp, ("atr",), len(bars))
    _assert_series_present(compiled, ("atr",), len(bars))
    _assert_dual_parity(interp, compiled, ("atr",))
    first = _first_finite_index(interp["series"]["atr"])
    assert first is not None and first >= 10
