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

Per-job scheduling and resilience:

- **Timeframe due gate** — a script is only fetched once its next bar
  can have closed (``last_bar_time + timeframe interval``), so a ``1w``
  job is not hammered every poll.
- **Exponential backoff** — fetch / run failures delay the next attempt
  (60s doubling, capped at 30min) via ``cron_state.next_due_at``;
  ``force`` bypasses it.
- **Run history** — every ok / error run is appended to ``run_history``
  for auditing (``GET /cron/history``).
- **Worker pool** — ``PYNE_RUNNER_WORKERS`` job threads isolate slow
  scripts instead of serializing the whole tick.
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


# Exponential backoff after fetch / run failures: 60s, 120s, 240s ... capped.
_BACKOFF_BASE_SECONDS = 60.0
_BACKOFF_MAX_SECONDS = 1800.0


def _now_ms() -> int:
    return int(time.time() * 1000)


def _backoff_delay_ms(consecutive_errors: int) -> int:
    if consecutive_errors <= 0:
        return 0
    return int(min(_BACKOFF_BASE_SECONDS * (2 ** (consecutive_errors - 1)), _BACKOFF_MAX_SECONDS) * 1000)


def _fetch_due(state: dict[str, Any], timeframe: str) -> tuple[bool, int]:
    """Timeframe-aware due gate: fetch only when the next bar can have closed.

    Returns ``(due, next_due_ms)``. Scripts that never ran are always due.
    A ``1w`` script is fetched at most once per week instead of every poll.
    """
    last_bar = int(state.get("last_bar_time") or 0)
    if last_bar <= 0:
        return True, 0
    interval = _INTERVAL_MS.get(timeframe, 86_400_000)
    next_due = last_bar + interval
    return next_due <= _now_ms(), next_due


def _record(sid: str, **fields: Any) -> None:
    from backend.runner import store

    try:
        store.record_run({"script_id": sid, "ts": _now_ms(), **fields})
    except Exception:
        logger.exception("runner history write failed for %s", sid)


def _run_job(rec: dict[str, Any], *, force: bool) -> dict[str, Any]:
    """Fetch + evaluate one script and persist cron state / history."""
    from backend.runner import store

    sid = str(rec["id"])
    item: dict[str, Any] = {"script_id": sid, "symbol": rec.get("symbol")}
    now = _now_ms()
    prev = store.get_cron_state(sid)

    # Backoff gate: failed scripts wait out their exponential delay.
    next_due_at = int(prev.get("next_due_at") or 0)
    if not force and next_due_at > now:
        item.update({"status": "skipped", "reason": "backoff", "next_due_at": next_due_at})
        return item

    # Timeframe gate: skip the fetch entirely while the current bar is still forming.
    due, next_due = _fetch_due(prev, str(rec.get("timeframe") or "1d"))
    if not force and not due:
        item.update({"status": "skipped", "reason": "not_due", "next_due_at": next_due})
        return item

    try:
        ohlcv = fetch_ohlcv(rec)
    except Exception as exc:
        logger.warning("runner fetch %s: %s", sid, exc)
        errors = int(prev.get("consecutive_errors") or 0) + 1
        due_at = now + _backoff_delay_ms(errors)
        store.put_cron_state(
            sid,
            {"last_status": "error", "last_error": "fetch_failed", "consecutive_errors": errors, "next_due_at": due_at},
        )
        item.update({"status": "error", "reason": "fetch_failed", "next_due_at": due_at})
        _record(sid, status="error", reason="fetch_failed", error="fetch_failed")
        return item
    if not ohlcv:
        item.update({"status": "skipped", "reason": "no_data"})
        return item
    last_t = int(ohlcv[-1].get("time") or 0)
    if not force and last_t > 0 and last_t <= int(prev.get("last_bar_time") or 0):
        # Fetch succeeded — clear backoff, keep the bar time for the due gate.
        store.put_cron_state(sid, {"last_bar_time": last_t, "consecutive_errors": 0, "next_due_at": 0})
        item.update({"status": "skipped", "reason": "no_new_bar", "last_bar_time": last_t})
        return item
    result = _eval_script(rec, ohlcv)
    if "error" in result:
        errors = int(prev.get("consecutive_errors") or 0) + 1
        err_text = str(result.get("error") or "run_failed")[:500]
        due_at = now + _backoff_delay_ms(errors)
        store.put_cron_state(
            sid,
            {
                "last_bar_time": last_t,
                "last_status": "error",
                "last_error": err_text,
                "consecutive_errors": errors,
                "next_due_at": due_at,
            },
        )
        item.update({"status": "error", "reason": err_text[:200], "mode": result.get("mode"), "next_due_at": due_at})
        _record(
            sid,
            status="error",
            reason="run_failed",
            last_bar_time=last_t,
            mode=str(result.get("mode") or ""),
            error=err_text,
        )
        return item
    alerts = result.get("alerts") or []
    events = result.get("events") or []
    n_alerts = len(alerts) if isinstance(alerts, list) else 0
    n_events = len(events) if isinstance(events, list) else 0
    fwd = None
    forward_status = ""
    try:
        fwd = _forward_alerts(rec, result, ohlcv)
        if fwd is not None:
            forward_status = "ok"
    except Exception as exc:
        logger.warning("runner webhook %s: %s", sid, exc)
        forward_status = f"error: {exc}"[:200]
    store.put_cron_state(
        sid,
        {
            "last_bar_time": last_t,
            "last_status": "ok",
            "last_error": "",
            "last_alerts": n_alerts,
            "last_events": n_events,
            "consecutive_errors": 0,
            "next_due_at": 0,
            "last_forward_status": forward_status,
        },
    )
    item.update(
        {
            "status": "ok",
            "last_bar_time": last_t,
            "mode": result.get("mode"),
            "alerts": n_alerts,
            "events": n_events,
            "count": result.get("count"),
        }
    )
    if fwd is not None:
        item["alert_forward"] = fwd
    if forward_status:
        item["alert_forward_status"] = forward_status
    _record(
        sid,
        status="ok",
        last_bar_time=last_t,
        mode=str(result.get("mode") or ""),
        alerts=n_alerts,
        events=n_events,
        forward_status=forward_status,
    )
    return item


def tick(*, force: bool = False, script_id: str | None = None) -> dict[str, Any]:
    """Evaluate due deployed scripts.

    Serialized across gunicorn workers / replicas by :func:`store.acquire_tick_lock`
    (flock for the SQLite backend, ``SET NX`` token for Redis).
    """
    from backend.runner import runner_workers
    from backend.runner import store

    lock = store.acquire_tick_lock()
    if lock is None:
        return {"status": "skipped", "reason": "lock_held", "jobs": []}

    try:
        scripts = store.list_enabled()
        if script_id:
            scripts = [s for s in scripts if s.get("id") == script_id]
        if not scripts:
            return {"status": "success", "jobs": [], "ok": 0, "count": 0}
        # Worker pool so one slow script (up to the 25s run timeout) cannot
        # serialize the rest of the fleet. DB access is serialized by the
        # store lock, so threads only overlap fetch + evaluation.
        workers = runner_workers()
        if workers > 1 and len(scripts) > 1:
            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(max_workers=min(workers, len(scripts)), thread_name_prefix="pyne-runner-job") as ex:
                jobs = [f.result() for f in [ex.submit(_run_job, rec, force=force) for rec in scripts]]
        else:
            jobs = [_run_job(rec, force=force) for rec in scripts]
        jobs.sort(key=lambda j: str(j.get("script_id") or ""))
        ok = sum(1 for j in jobs if j.get("status") == "ok")
        return {"status": "success", "jobs": jobs, "ok": ok, "count": len(jobs)}
    finally:
        try:
            lock.release()
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
