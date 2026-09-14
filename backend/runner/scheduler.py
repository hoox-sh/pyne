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

"""Bar-close tick for the optional Flask script runner.

Fetches OHLCV via ``pynescript.util.data.get_provider``, runs
``Runtime.run`` when the last bar time advanced, and forwards last-bar
alerts through :mod:`backend.alert_forwarder`. A flock keeps multi-worker
gunicorn from double-ticking.
"""

from __future__ import annotations

import logging
import os
import threading
import time

from typing import Any


logger = logging.getLogger(__name__)

_INTERVAL_MS: dict[str, int] = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "2h": 7_200_000,
    "4h": 14_400_000,
    "6h": 21_600_000,
    "8h": 28_800_000,
    "12h": 43_200_000,
    "1d": 86_400_000,
    "3d": 259_200_000,
    "1w": 604_800_000,
    "1M": 2_592_000_000,
}

_started_pid = 0
_start_lock = threading.Lock()


def _bars_from_columns(data: dict[str, Any], timeframe: str, max_bars: int) -> list[dict[str, Any]]:
    closes = list(data.get("close") or [])
    n = len(closes)
    if n == 0:
        return []
    opens = list(data.get("open") or closes)
    highs = list(data.get("high") or closes)
    lows = list(data.get("low") or closes)
    vols = list(data.get("volume") or [0] * n)
    times = data.get("time") or data.get("timestamp")
    interval = _INTERVAL_MS.get(timeframe, 86_400_000)
    # Deterministic origin so mock last_bar_time is stable across ticks.
    origin_ms = 1_700_000_000_000
    if not isinstance(times, list) or len(times) != n:
        times = [origin_ms + i * interval for i in range(n)]
    bars: list[dict[str, Any]] = []
    for i in range(n):
        try:
            t_raw = times[i]
            if hasattr(t_raw, "timestamp"):
                t_ms = int(t_raw.timestamp() * 1000)
            else:
                t_ms = int(t_raw)
                if t_ms < 10_000_000_000:
                    t_ms *= 1000
        except (TypeError, ValueError, OverflowError):
            t_ms = origin_ms + i * interval
        o = float(opens[i] if i < len(opens) else closes[i])
        c = float(closes[i])
        h = float(highs[i] if i < len(highs) else max(o, c))
        lo = float(lows[i] if i < len(lows) else min(o, c))
        v = float(vols[i] if i < len(vols) else 0.0)
        bars.append({"time": t_ms, "open": o, "high": h, "low": lo, "close": c, "volume": v})
    if max_bars > 0 and len(bars) > max_bars:
        return bars[-max_bars:]
    return bars


def fetch_ohlcv(script: dict[str, Any]) -> list[dict[str, Any]]:
    """Load bars for *script* from its ``data_source`` provider."""
    from pynescript.util.data import get_provider

    source = str(script.get("data_source") or "mock")
    opts = script.get("data_options") if isinstance(script.get("data_options"), dict) else {}
    symbol = str(script.get("symbol") or "TEST")
    timeframe = str(script.get("timeframe") or "1d")
    period = str(script.get("period") or "6mo")
    max_bars = int(script.get("max_bars") or 5000)
    kwargs: dict[str, Any] = {}
    if source == "ccxt":
        kwargs["exchange"] = opts.get("exchange") or "binance"
    elif source == "alphavantage":
        kwargs["api_key"] = opts.get("api_key") or os.environ.get("ALPHAVANTAGE_API_KEY") or "demo"
    elif source == "mock":
        if "seed" in opts:
            kwargs["seed"] = opts.get("seed")
    provider = get_provider(source, **kwargs)
    raw = provider.fetch(symbol, period=period, interval=timeframe)
    if source == "ccxt" and hasattr(provider, "fetch_ohlcv"):
        try:
            candles = provider.fetch_ohlcv(symbol, timeframe, limit=max_bars)
        except Exception:
            candles = None
        if candles:
            bars = [
                {
                    "time": int(c[0]),
                    "open": float(c[1]),
                    "high": float(c[2]),
                    "low": float(c[3]),
                    "close": float(c[4]),
                    "volume": float(c[5] if len(c) > 5 else 0.0),
                }
                for c in candles
                if isinstance(c, (list, tuple)) and len(c) >= 5
            ]
            if bars:
                return bars[-max_bars:]
    return _bars_from_columns(raw if isinstance(raw, dict) else {}, timeframe, max_bars)


def _eval_script(script: dict[str, Any], ohlcv: list[dict[str, Any]]) -> dict[str, Any]:
    from backend.runtime import Runtime

    runtime = Runtime(symbol=str(script.get("symbol") or "CHART"))
    libraries = script.get("libraries") if isinstance(script.get("libraries"), list) else None
    inputs = script.get("inputs") if isinstance(script.get("inputs"), dict) else None
    return runtime.run(
        str(script.get("script") or ""),
        ohlcv,
        mode=str(script.get("mode") or "auto"),
        inputs=inputs or None,
        libraries=libraries or None,
        timeout_seconds=25.0,
    )


def _forward_alerts(script: dict[str, Any], result: dict[str, Any], ohlcv: list[dict[str, Any]]) -> Any:
    from backend.alert_forwarder import maybe_forward_run_alerts

    return maybe_forward_run_alerts(
        alerts=result.get("alerts"),
        ohlcv=ohlcv,
        webhook_url=script.get("webhook_url") or None,
        enable_forward=bool(script.get("forward_alerts", True)),
        alert_last_bar=bool(script.get("alert_last_bar", True)),
        alert_batch=bool(script.get("alert_batch", True)),
        symbol=str(script.get("symbol") or "") or None,
    )


def _flock_path() -> str:
    from backend.runner import db_path

    path = db_path()
    if path == ":memory:":
        return os.path.join(os.environ.get("TMPDIR", "/tmp"), "pyne_runner.lock")
    return path + ".lock"


def tick(*, force: bool = False, script_id: str | None = None) -> dict[str, Any]:
    """Evaluate due deployed scripts. Safe under gunicorn (flock)."""
    from backend.runner import store

    lock_f = None
    try:
        lock_f = open(_flock_path(), "a+b")
        import fcntl

        fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        if lock_f is not None:
            try:
                lock_f.close()
            except Exception:
                pass
        return {"status": "skipped", "reason": "lock_held", "jobs": []}

    jobs: list[dict[str, Any]] = []
    try:
        scripts = store.list_enabled()
        if script_id:
            scripts = [s for s in scripts if s.get("id") == script_id]
        for rec in scripts:
            sid = str(rec["id"])
            item: dict[str, Any] = {"script_id": sid, "symbol": rec.get("symbol")}
            try:
                ohlcv = fetch_ohlcv(rec)
            except Exception as exc:
                logger.warning("runner fetch %s: %s", sid, exc)
                item.update({"status": "error", "reason": "fetch_failed"})
                store.put_cron_state(sid, {"last_status": "error", "last_error": "fetch_failed"})
                jobs.append(item)
                continue
            if not ohlcv:
                item.update({"status": "skipped", "reason": "no_data"})
                jobs.append(item)
                continue
            last_t = int(ohlcv[-1].get("time") or 0)
            prev = store.get_cron_state(sid)
            if not force and last_t > 0 and last_t <= int(prev.get("last_bar_time") or 0):
                item.update({"status": "skipped", "reason": "no_new_bar", "last_bar_time": last_t})
                jobs.append(item)
                continue
            result = _eval_script(rec, ohlcv)
            if "error" in result:
                item.update(
                    {
                        "status": "error",
                        "reason": str(result.get("error") or "run_failed")[:200],
                        "mode": result.get("mode"),
                    }
                )
                store.put_cron_state(
                    sid,
                    {
                        "last_bar_time": last_t,
                        "last_status": "error",
                        "last_error": str(result.get("error") or "")[:500],
                    },
                )
                jobs.append(item)
                continue
            alerts = result.get("alerts") or []
            events = result.get("events") or []
            fwd = None
            try:
                fwd = _forward_alerts(rec, result, ohlcv)
            except Exception as exc:
                logger.warning("runner webhook %s: %s", sid, exc)
            store.put_cron_state(
                sid,
                {
                    "last_bar_time": last_t,
                    "last_status": "ok",
                    "last_error": "",
                    "last_alerts": len(alerts) if isinstance(alerts, list) else 0,
                    "last_events": len(events) if isinstance(events, list) else 0,
                },
            )
            item.update(
                {
                    "status": "ok",
                    "last_bar_time": last_t,
                    "mode": result.get("mode"),
                    "alerts": len(alerts) if isinstance(alerts, list) else 0,
                    "events": len(events) if isinstance(events, list) else 0,
                    "count": result.get("count"),
                }
            )
            if fwd is not None:
                item["alert_forward"] = fwd
            jobs.append(item)
        ok = sum(1 for j in jobs if j.get("status") == "ok")
        return {"status": "success", "jobs": jobs, "ok": ok, "count": len(jobs)}
    finally:
        try:
            import fcntl

            fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        try:
            lock_f.close()
        except Exception:
            pass


def maybe_start_background() -> None:
    """Daemon poll loop when ``PYNE_RUNNER_SCHEDULER`` is on.

    Skips the Flask reloader parent. Gunicorn workers all start a thread;
    :func:`tick` serializes via flock.
    """
    global _started_pid
    from backend.runner import poll_seconds
    from backend.runner import scheduler_enabled

    if not scheduler_enabled():
        return
    if os.environ.get("WERKZEUG_RUN_MAIN") == "false":
        return
    pid = os.getpid()
    with _start_lock:
        if _started_pid == pid:
            return
        _started_pid = pid

    interval = poll_seconds()

    def _loop() -> None:
        # First tick after one interval so import/boot stays snappy.
        time.sleep(min(interval, 5.0))
        while True:
            try:
                tick()
            except Exception:
                logger.exception("pyne runner scheduler tick failed")
            time.sleep(interval)

    threading.Thread(target=_loop, name="pyne-runner", daemon=True).start()
    logger.info("pyne runner scheduler started (poll %.0fs)", interval)
