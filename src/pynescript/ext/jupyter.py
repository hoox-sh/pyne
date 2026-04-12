# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# This software is the proprietary information of jango-blockchained.
# Use is subject to license terms.

"""Jupyter Integration for PyneScript.

This module provides Jupyter notebook support for PyneScript:
- IPython magic commands (%pinescript)
- Data helpers for working with Pine Script in notebooks
- Display helpers for visualizing results

Usage in Jupyter:
    from pynescript.ext.jupyter import load_ipython_extension
    load_ipython_extension(ipython)
"""

from __future__ import annotations

import random

from typing import Any, cast

from pynescript.ast import parse
from pynescript.ast import unparse
from pynescript.ast.linter import lint_script


def load_ipython_extension(ipython: Any) -> None:
    """Load PyneScript magic commands in Jupyter.

    Args:
        ipython: IPython instance
    """
    try:
        from IPython.core.magic import register_cell_magic
    except ImportError:
        msg = "IPython is required for Jupyter integration"
        raise ImportError(msg)  # noqa: B904

    @register_cell_magic
    def pinescript(line: str, cell: str) -> None:  # noqa: ARG001
        """Run Pine Script code and display results.

        Usage:
            %%pinescript
            //@version=5
            indicator("My Indicator")
            plot(ta.sma(close, 14))
        """
        warnings = lint_script(cell)
        if warnings:
            print("Lint warnings:")  # noqa: T201
            for w in warnings:
                print(f"  {w}")  # noqa: T201
            print()  # noqa: T201

        try:
            ast = parse(cell)
            result = unparse(ast)
            print("Parsed successfully!")  # noqa: T201
            print("---")  # noqa: T201
            print(result)  # noqa: T201
        except Exception as e:
            print(f"Error: {e}")  # noqa: T201

    ipython.user_ns.update(
        {
            "pine_parse": parse,
            "pine_unparse": unparse,
            "pine_lint": lint_script,
        }
    )


def create_sample_data(
    length: int = 100,
    start_price: float = 100.0,
    volatility: float = 0.02,
    trend: float = 0.0,
) -> dict[str, list[float]]:
    """Create sample OHLCV data for testing Pine Script indicators.

    Args:
        length: Number of bars to generate
        start_price: Starting price
        volatility: Price volatility (0.02 = 2%)
        trend: Price trend per bar

    Returns:
        Dictionary with 'open', 'high', 'low', 'close', 'volume' keys

    Example:
        >>> data = create_sample_data(100, 100, 0.02)
        >>> data['close'][:5]
        [100.0, 101.23, 99.87, 102.15, 101.02]
    """
    close = [start_price]
    for _ in range(length - 1):
        change = random.gauss(trend, volatility) * close[-1]
        close.append(close[-1] + change)

    opens = close[:-1]
    opens.insert(0, start_price)

    highs = [max(o, c) * (1 + random.uniform(0, volatility)) for o, c in zip(opens, close, strict=False)]
    lows = [min(o, c) * (1 - random.uniform(0, volatility)) for o, c in zip(opens, close, strict=False)]

    volumes = [int(random.gauss(1000000, 200000)) for _ in range(length)]

    return {
        "open": opens,
        "high": highs,
        "low": lows,
        "close": close,
        "volume": [float(v) for v in volumes],
    }


def evaluate_indicator(
    code: str,
    data: dict[str, list[float]],
) -> dict[str, Any]:
    """Evaluate a Pine Script indicator with sample data.

    Args:
        code: Pine Script indicator code
        data: OHLCV data dictionary

    Returns:
        Dictionary of indicator results

    Example:
        >>> data = create_sample_data(100)
        >>> code = '''//@version=5
        ... indicator("SMA")
        ... plot(ta.sma(close, 14))
        ... '''
        >>> result = evaluate_indicator(code, data)
    """
    from pynescript.ast.evaluator import NodeLiteralEvaluator

    context = {
        "close": data["close"],
        "open": data["open"],
        "high": data["high"],
        "low": data["low"],
        "volume": data["volume"],
    }
    evaluator = NodeLiteralEvaluator(context=context)

    try:
        ast = parse(code)
        evaluator.visit(ast)
    except Exception as e:
        return {"error": str(e)}

    return cast(dict[str, Any], evaluator.context)


def display_indicator_table(
    data: dict[str, list[float]],
    columns: list[str] | None = None,
    rows: int = 20,
) -> Any:
    """Display indicator data as a table in Jupyter.

    Args:
        data: Dictionary of column name to values
        columns: Which columns to display (default: all)
        rows: Number of rows to show

    Returns:
        IPython display object
    """
    try:
        import pandas as pd

        df = pd.DataFrame(data)
        if columns:
            df = df[columns]
        return df.head(rows)
    except ImportError:
        print("pandas required for table display. Install with: pip install pandas")  # noqa: T201
        return None


__all__ = [
    "create_sample_data",
    "display_indicator_table",
    "evaluate_indicator",
    "load_ipython_extension",
]
