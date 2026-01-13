from __future__ import annotations

from pynescript.ast.helper import parse

from .evaluator import CustomEvaluator
from .series import PineSeries


class Runtime:
    def __init__(self):
        pass

    def run(self, source_code: str, ohlcv_data: list[dict]):
        """
        Execute the script over the provided OHLCV data.

        Args:
            source_code: Pine Script source to run.
            ohlcv_data: List of dicts with 'open', 'high', 'low', 'close', 'time'.

        Returns:
            dict with 'series': list of plotted values for each bar.
        """
        # Parse once
        try:
            tree = parse(source_code, mode="exec")
        except Exception as e:
            return {"error": f"Parse Error: {e!s}"}

        # Initialize Series
        open_series = PineSeries()
        high_series = PineSeries()
        low_series = PineSeries()
        close_series = PineSeries()

        # Context initialization
        context = {
            "open": open_series,
            "high": high_series,
            "low": low_series,
            "close": close_series,
        }

        evaluator = CustomEvaluator(context=context)

        results = []

        for bar in ohlcv_data:
            # Update series state
            open_series.update(bar.get("open"))
            high_series.update(bar.get("high"))
            low_series.update(bar.get("low"))
            close_series.update(bar.get("close"))

            # Reset plot capture for this bar
            evaluator.reset_plots()

            # Execute script
            try:
                evaluator.visit(tree)
            except Exception as e:
                # In a real engine we might handle runtime errors more gracefully
                # e.g. propagate 'na' or halt
                return {"error": f"Runtime Error at bar {bar.get('time')}: {e!s}"}

            # Collect outputs from this bar
            # For simplicity, we assume one plot() call for now and return that value.
            # If there are multiple plots, we'd need a more structured response.
            bar_result = {}
            for i, plot in enumerate(evaluator.plot_outputs):
                bar_result[f"plot_{i}"] = plot["value"]

            results.append(bar_result)

        # Post-process results into structure expected by frontend
        # Front end expects: array of values for the overlay series.
        # Let's simplify and just return the first plot series found.

        final_series = []
        if results and "plot_0" in results[0]:
            final_series = [r.get("plot_0") for r in results]

        return {"plots": final_series, "count": len(results)}
