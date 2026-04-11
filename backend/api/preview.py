# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

"""Preview API endpoints for Pro features (chart thumbnails, backtests)."""

from __future__ import annotations

import time
from flask import Blueprint, g, jsonify, request

from backend.middleware.auth import require_api_key, track_usage
from backend.services.backtest import generate_mock_ohlcv, run_quick_backtest
from backend.services.chart_renderer import render_line_chart, render_ohlcv_chart

preview_bp = Blueprint("preview", __name__, url_prefix="/preview")
backtest_bp = Blueprint("backtest", __name__, url_prefix="/backtest")


@preview_bp.route("/chart", methods=["POST"])
@track_usage
def chart_preview():
    """Generate a chart thumbnail from script + data.

    Request body:
    {
        "script": "//@version=5\nstrategy('My Strategy')...",
        "data": {"close": [100, 101, 102, ...], ...},
        "options": {
            "type": "line" | "ohlcv",
            "color": "#2196F3",
            "show_volume": true,
            "width": 600,
            "height": 300,
        }
    }

    Response:
    {
        "status": "success",
        "chart": "base64_encoded_png...",
        "meta": {
            "type": "line",
            "bars": 252,
            "last_value": 150.25,
        }
    }
    """
    data = request.get_json() or {}

    script = data.get("script", "")
    ohlcv = data.get("data", {})
    opts = data.get("options", {})

    if not ohlcv:
        return jsonify(
            {
                "status": "error",
                "code": "NO_DATA",
                "message": "No data provided. Include 'data' with OHLCV arrays.",
            }
        ), 400

    chart_type = opts.get("type", "line")
    color = opts.get("color", "#2196F3")
    width = min(opts.get("width", 600), 1200)
    height = min(opts.get("height", 300), 600)
    show_volume = opts.get("show_volume", False)

    close = ohlcv.get("close", [])
    if not close:
        return jsonify(
            {
                "status": "error",
                "code": "NO_CLOSE_DATA",
                "message": "No 'close' data provided in 'data' object.",
            }
        ), 400

    try:
        if chart_type == "ohlcv":
            chart_b64 = render_ohlcv_chart(ohlcv, title="Price Chart", height=height, width=width)
        else:
            chart_b64 = render_line_chart(
                close,
                title="Chart Preview",
                color=color,
                height=height,
                width=width,
                show_volume=show_volume,
                ohlcv=ohlcv if show_volume else None,
            )

        return jsonify(
            {
                "status": "success",
                "chart": chart_b64,
                "meta": {
                    "type": chart_type,
                    "bars": len(close),
                    "last_value": close[-1],
                    "first_value": close[0],
                    "change": round(close[-1] - close[0], 2),
                    "change_pct": round((close[-1] / close[0] - 1) * 100, 2) if close[0] != 0 else 0,
                    "rendered_at": int(time.time()),
                },
                "tier_info": g.api_key.get_tier_info(),
            }
        )

    except Exception as e:
        return jsonify(
            {
                "status": "error",
                "code": "RENDER_ERROR",
                "message": f"Failed to render chart: {e}",
            }
        ), 500


@preview_bp.route("/indicator", methods=["POST"])
@track_usage
def indicator_preview():
    """Generate a chart for a specific indicator expression.

    Request body:
    {
        "expression": "ta.sma(close, 14)",
        "data": {"close": [100, 101, 102, ...]},
        "options": {...}
    }
    """
    data = request.get_json() or {}

    expression = data.get("expression", "")
    ohlcv = data.get("data", {})
    opts = data.get("options", {})

    if not ohlcv:
        return jsonify(
            {
                "status": "error",
                "code": "NO_DATA",
                "message": "No data provided.",
            }
        ), 400

    close = ohlcv.get("close", [])
    if not close:
        return jsonify(
            {
                "status": "error",
                "code": "NO_CLOSE_DATA",
                "message": "No 'close' data provided.",
            }
        ), 400

    try:
        values = _compute_indicator(expression, close)
    except Exception:
        values = close

    chart_b64 = render_line_chart(
        values,
        title=f"{expression}",
        color=opts.get("color", "#FF9800"),
        width=min(opts.get("width", 600), 1200),
        height=min(opts.get("height", 300), 600),
    )

    return jsonify(
        {
            "status": "success",
            "chart": chart_b64,
            "meta": {
                "expression": expression,
                "bars": len(values),
                "last_value": values[-1] if values else None,
                "rendered_at": int(time.time()),
            },
            "tier_info": g.api_key.get_tier_info(),
        }
    )


def _compute_indicator(expression: str, close: list) -> list[float | None]:
    parts = expression.strip().lower()
    if parts.startswith("ta.sma("):
        period = int(parts.split(",")[-1].rstrip(")").strip())
        return _sma(close, period)
    elif parts.startswith("ta.ema("):
        period = int(parts.split(",")[-1].rstrip(")").strip())
        return _ema(close, period)
    elif parts.startswith("ta.rsi("):
        period = int(parts.split(",")[-1].rstrip(")").strip())
        return _rsi(close, period)
    elif parts.startswith("ta.macd("):
        return _macd(close)
    return close


def _sma(data: list, period: int) -> list[float | None]:
    result = [None] * len(data)
    for i in range(period - 1, len(data)):
        result[i] = sum(data[i - period + 1 : i + 1]) / period
    return result


def _ema(data: list, period: int) -> list[float | None]:
    result = [None] * len(data)
    if len(data) < period:
        return result
    multiplier = 2 / (period + 1)
    result[period - 1] = sum(data[:period]) / period
    for i in range(period, len(data)):
        result[i] = (data[i] - result[i - 1]) * multiplier + result[i - 1]
    return result


def _rsi(data: list, period: int) -> list[float | None]:
    result = [None] * len(data)
    if len(data) < period + 1:
        return result
    gains = [max(data[i] - data[i - 1], 0) for i in range(1, len(data))]
    losses = [max(data[i - 1] - data[i], 0) for i in range(1, len(data))]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(data)):
        if avg_loss == 0:
            result[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i] = 100 - (100 / (1 + rs))
        if i < len(data) - 1:
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    return result


def _macd(data: list, fast: int = 12, slow: int = 26, signal: int = 9) -> list[float | None]:
    ema_fast = _ema(data, fast)
    ema_slow = _ema(data, slow)
    macd_line = [None] * len(data)
    for i in range(len(data)):
        if ema_fast[i] is not None and ema_slow[i] is not None:
            macd_line[i] = ema_fast[i] - ema_slow[i]
    signal_line = _ema([x if x is not None else 0 for x in macd_line], signal)
    histogram = [None] * len(data)
    for i in range(len(data)):
        if macd_line[i] is not None and signal_line[i] is not None:
            histogram[i] = macd_line[i] - signal_line[i]
    return histogram


@backtest_bp.route("/quick", methods=["POST"])
@track_usage
def quick_backtest():
    """Run a quick backtest on a strategy script.

    Request body:
    {
        "script": "//@version=5\nstrategy('My Strategy', overlay=true)...",
        "data": {"open": [...], "high": [...], "low": [...], "close": [...], "volume": [...]},
        "initial_capital": 10000.0,
        "mock_data": true,
        "mock_bars": 252,
    }

    Response:
    {
        "status": "success",
        "result": {
            "equity_curve": [...],
            "trades": [...],
            "summary": {
                "total_pnl": 1234.56,
                "sharpe_ratio": 1.8,
                "max_drawdown": 5.2,
                "win_rate": 65.0,
                ...
            },
            "equity_chart": "base64_encoded_png...",
        }
    }
    """
    data = request.get_json() or {}

    script = data.get("script", "")
    ohlcv = data.get("data", {})
    initial_capital = float(data.get("initial_capital", 10000.0))
    use_mock = data.get("mock_data", False)
    mock_bars = int(data.get("mock_bars", 252))

    if not script:
        return jsonify(
            {
                "status": "error",
                "code": "NO_SCRIPT",
                "message": "No 'script' provided.",
            }
        ), 400

    if not ohlcv and not use_mock:
        return jsonify(
            {
                "status": "error",
                "code": "NO_DATA",
                "message": "No 'data' provided. Set 'mock_data': true for a mock backtest.",
            }
        ), 400

    try:
        if use_mock or not ohlcv.get("close"):
            ohlcv = generate_mock_ohlcv(n_bars=mock_bars)

        result = run_quick_backtest(script, ohlcv, initial_capital)

        return jsonify(
            {
                "status": "success",
                "result": result,
                "tier_info": g.api_key.get_tier_info(),
                "meta": {
                    "bars": len(ohlcv.get("close", [])),
                    "initial_capital": initial_capital,
                    "completed_at": int(time.time()),
                },
            }
        )

    except Exception as e:
        return jsonify(
            {
                "status": "error",
                "code": "BACKTEST_ERROR",
                "message": f"Backtest failed: {e}",
            }
        ), 500
