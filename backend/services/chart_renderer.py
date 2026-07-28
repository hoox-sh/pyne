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

"""Chart rendering service for generating PNG thumbnails."""

from __future__ import annotations

from typing import Any, cast

import base64
import io

import matplotlib


matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def render_line_chart(
    values: list[float | None],
    dates: list[str] | None = None,
    title: str = "Chart",
    color: str = "#2196F3",
    height: int = 300,
    width: int = 600,
    show_volume: bool = False,
    ohlcv: dict[str, list] | None = None,
) -> str:
    """Render a line chart and return as base64-encoded PNG.

    Args:
        values: List of y-values (can contain None for missing data)
        dates: Optional list of date labels
        title: Chart title
        color: Line color (hex)
        height: Image height in pixels
        width: Image width in pixels
        show_volume: Whether to show volume bars below
        ohlcv: Optional OHLCV data dict with keys: open, high, low, close, volume

    Returns:
        Base64-encoded PNG string
    """
    if not values or all(v is None for v in values):
        return _render_empty_chart(title, width, height)

    clean_values = [float(v) if v is not None else np.nan for v in values]
    x = np.arange(len(clean_values))
    y = np.array(clean_values)

    fig_height = 3.5 if show_volume else 3.0
    fig, ax = plt.subplots(figsize=(width / 100, fig_height), dpi=100)
    fig.patch.set_facecolor("#1E1E1E")
    ax.set_facecolor("#252526")

    ax.plot(x, y, color=color, linewidth=1.5, label=title)
    ax.fill_between(x, y, alpha=0.15, color=color)

    ax.set_title(title, color="#CCCCCC", fontsize=11, pad=8)
    ax.tick_params(colors="#888888", labelsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#444444")
    ax.spines["bottom"].set_color("#444444")
    ax.grid(True, alpha=0.2, color="#444444")
    ax.yaxis.set_major_formatter(matplotlib.ticker.StrMethodFormatter("{x:.2f}"))

    if dates and len(dates) > 0:
        step = max(1, len(dates) // 6)
        tick_positions = list(range(0, len(dates), step))
        tick_labels = [dates[i] for i in tick_positions]
        ax.set_xticks(tick_positions)
        ax.set_xticklabels(tick_labels, rotation=30, ha="right", fontsize=7, color="#888888")

    if show_volume and ohlcv and "volume" in ohlcv:
        ax2 = ax.twinx()
        volumes = [float(v) if v else 0 for v in ohlcv.get("volume", [])]
        ax2.bar(x, volumes, alpha=0.3, color="#666666", width=0.8)
        ax2.set_ylabel("Volume", color="#888888", fontsize=8)
        ax2.tick_params(colors="#888888", labelsize=7)
        ax2.spines["right"].set_color("#444444")

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", facecolor=fig.get_facecolor(), dpi=100, bbox_inches="tight")
    plt.close(fig)

    buf.seek(0)
    png_b64 = base64.b64encode(buf.read()).decode("utf-8")
    return png_b64


def render_equity_curve(
    equity_curve: list[float],
    dates: list[str] | None = None,
    height: int = 300,
    width: int = 600,
) -> str:
    """Render an equity curve chart.

    Args:
        equity_curve: List of portfolio values over time
        dates: Optional date labels
        height: Image height in pixels
        width: Image width in pixels

    Returns:
        Base64-encoded PNG string
    """
    if not equity_curve or all(v is None for v in equity_curve):
        return _render_empty_chart("Equity Curve", width, height)

    values = [float(v) if v is not None else np.nan for v in equity_curve]
    x = np.arange(len(values))
    y = np.array(values)

    fig, ax = plt.subplots(figsize=(width / 100, 3.0), dpi=100)
    fig.patch.set_facecolor("#1E1E1E")
    ax.set_facecolor("#252526")

    positive = y >= 0
    ax.fill_between(x, 0, y, where=cast(Any, positive), color="#4CAF50", alpha=0.3, label="Profit")
    ax.fill_between(x, 0, y, where=cast(Any, ~positive), color="#F44336", alpha=0.3, label="Loss")
    ax.plot(x, y, color="#2196F3", linewidth=1.5)

    ax.set_title("Equity Curve", color="#CCCCCC", fontsize=11, pad=8)
    ax.tick_params(colors="#888888", labelsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#444444")
    ax.spines["bottom"].set_color("#444444")
    ax.grid(True, alpha=0.2, color="#444444")
    ax.axhline(y=values[0], color="#666666", linestyle="--", linewidth=0.8, alpha=0.5)

    if dates and len(dates) > 0:
        step = max(1, len(dates) // 6)
        tick_positions = list(range(0, len(dates), step))
        tick_labels = [dates[i] for i in tick_positions]
        ax.set_xticks(tick_positions)
        ax.set_xticklabels(tick_labels, rotation=30, ha="right", fontsize=7, color="#888888")

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", facecolor=fig.get_facecolor(), dpi=100, bbox_inches="tight")
    plt.close(fig)

    buf.seek(0)
    png_b64 = base64.b64encode(buf.read()).decode("utf-8")
    return png_b64


def render_ohlcv_chart(
    ohlcv: dict[str, list],
    title: str = "Price Chart",
    height: int = 300,
    width: int = 600,
) -> str:
    """Render an OHLCV candlestick chart.

    Args:
        ohlcv: Dict with open, high, low, close, volume lists
        title: Chart title
        height: Image height in pixels
        width: Image width in pixels

    Returns:
        Base64-encoded PNG string
    """
    if not ohlcv:
        return _render_empty_chart(title, width, height)

    open_prices = ohlcv.get("open", [])
    high_prices = ohlcv.get("high", [])
    low_prices = ohlcv.get("low", [])
    close_prices = ohlcv.get("close", [])
    volumes = ohlcv.get("volume", [])

    n = len(close_prices)
    if n == 0:
        return _render_empty_chart(title, width, height)

    x = np.arange(n)

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(width / 100, 3.5), dpi=100, gridspec_kw={"height_ratios": [3, 1]}, sharex=True
    )
    fig.patch.set_facecolor("#1E1E1E")

    for ax in (ax1, ax2):
        ax.set_facecolor("#252526")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#444444")
        ax.spines["bottom"].set_color("#444444")
        ax.tick_params(colors="#888888", labelsize=7)
        ax.grid(True, alpha=0.2, color="#444444")

    candle_width = 0.6
    colors = ["#4CAF50" if close_prices[i] >= open_prices[i] else "#F44336" for i in range(n)]

    for i in range(n):
        color = colors[i]
        ax1.plot([i, i], [low_prices[i], high_prices[i]], color=color, linewidth=0.8)
        body_bottom = min(open_prices[i], close_prices[i])
        body_height = abs(close_prices[i] - open_prices[i]) + 1e-9
        ax1.add_patch(
            plt.Rectangle((i - candle_width / 2, body_bottom), candle_width, body_height, color=color, linewidth=0.5)
        )

    ax1.set_ylabel("Price", color="#888888", fontsize=8)
    ax1.set_title(title, color="#CCCCCC", fontsize=11, pad=8)

    ax2.bar(x, volumes, color="#666666", alpha=0.5, width=0.8)
    ax2.set_ylabel("Volume", color="#888888", fontsize=8)

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", facecolor=fig.get_facecolor(), dpi=100, bbox_inches="tight")
    plt.close(fig)

    buf.seek(0)
    png_b64 = base64.b64encode(buf.read()).decode("utf-8")
    return png_b64


def _render_empty_chart(title: str, width: int, height: int) -> str:
    fig, ax = plt.subplots(figsize=(width / 100, 2.5), dpi=100)
    fig.patch.set_facecolor("#1E1E1E")
    ax.set_facecolor("#252526")
    ax.set_title(title, color="#888888", fontsize=11, pad=20)
    ax.text(
        0.5, 0.5, "No data available", color="#666666", ha="center", va="center", transform=ax.transAxes, fontsize=12
    )
    ax.axis("off")
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", facecolor=fig.get_facecolor(), dpi=100, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")
