# pynescript_runtime.py — runs Pine Script in the browser via Pyodide.
# Loaded by the Pyodide engine in `src/engines/pyodide.js` after the
# pynescript wheel is installed via micropip.
#
# Mirrors the Flask backend's `Runtime().run()` (backend/runtime.py +
# backend/evaluator.py + backend/series.py).  Exposes:
#
#   run_script(script: str, bars: list[dict]) -> str  (JSON)
#
# Returns a JSON string with `status`, `plots`, `series`, `events`, `error`,
# `meta` (mode, count, ms, script_id, run_id).

from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections import deque


# --- Lightweight port of backend/series.py ---------------------------------


class PineSeries:
    """Pine Script series — a scalar that supports [n] historical indexing."""

    __hash__ = None  # type: ignore

    def __init__(self, initial_value=None, history_length: int = 1000):
        self.history = deque([initial_value], maxlen=history_length)
        self.current = initial_value

    def update(self, new_value):
        self.current = new_value
        self.history.appendleft(new_value)

    def __getitem__(self, index: int):
        if index < 0:
            raise ValueError("Pine Script does not support negative indexing")
        if index >= len(self.history):
            return None
        return self.history[index]

    def __len__(self):
        return len(self.history)

    def __repr__(self) -> str:
        return f"PineSeries(current={self.current}, len={len(self.history)})"


# --- Lightweight port of backend/evaluator.py -----------------------------


def _patch_evaluator():
    """Monkey-patch NodeLiteralEvaluator so the pynescript runtime can
    accept our custom PineSeries (and the Bar accessor) as series/list
    arguments.  The base class uses ``isinstance(value, list)`` which is
    too strict for our wrapper."""
    from pynescript.ast.evaluator.builtins.arrays import ArrayBuiltinsMixin
    from pynescript.ast.evaluator.builtins.strings import StringBuiltinsMixin
    from pynescript.ast.evaluator.builtins.technical_submodules.core import TechnicalHelpers

    if getattr(ArrayBuiltinsMixin, "_patched_for_browser", False):
        return

    def _expect_list(self, value, message):
        if isinstance(value, list):
            return value
        if hasattr(value, "history") and hasattr(value, "current"):
            return list(value.history)
        if hasattr(value, "__iter__") and hasattr(value, "__len__"):
            return list(value)
        self._error(f"{message}. Got: {type(value).__name__}")

    def _expect_int(self, value, message):
        if isinstance(value, dict) and "default" in value:
            return int(value["default"])
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        self._error(f"{message}. Got: {type(value).__name__}")

    def _expect_number(self, value, message):
        if isinstance(value, dict) and "default" in value:
            return float(value["default"])
        try:
            return float(value)
        except (TypeError, ValueError):
            self._error(f"{message}. Got: {type(value).__name__}")

    def _expect_series(self, args, length):
        if len(args) != length:
            self._error(f"ta.* function requires {length} argument(s), got {len(args)}")
        series = self._expect_list(args[0], "First argument must be a list (series)")
        period = self._expect_int(args[1], "Second argument must be an integer (period)")
        return series, period

    ArrayBuiltinsMixin._expect_list = _expect_list
    StringBuiltinsMixin._expect_int = _expect_int
    TechnicalHelpers._expect_number = _expect_number
    TechnicalHelpers._expect_series = _expect_series
    ArrayBuiltinsMixin._patched_for_browser = True

    # --- Fix _call_builtin: merge kwargs into args for handlers that don't accept kwargs ---
    from pynescript.ast.evaluator.builtins.base import BuiltinDispatchMixin

    _orig_call_builtin = BuiltinDispatchMixin._call_builtin

    def _patched_call_builtin(self, name, args, kwargs=None):
        dispatch = self._builtin_dispatch
        if dispatch is None:
            dispatch = self._build_builtin_map()
            self._builtin_dispatch = dispatch
        handler = dispatch.get(name)
        if handler is None:
            msg = (
                f"Unknown built-in function: '{name}'. "
                f"Available modules: math, str, array, ta, input, request, line, box, label, table, strategy. "
                f"Use 'ta.<name>' for technical analysis, 'math.<name>' for math functions."
            )
            raise ValueError(msg)
        if kwargs:
            import inspect

            try:
                sig = inspect.signature(handler)
                params = list(sig.parameters.values())
                # Check if handler accepts **kwargs or a second positional param
                has_var_keyword = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params)
                has_var_positional = any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params)
                # Count positional params (excluding 'self')
                pos_params = [
                    p
                    for p in params
                    if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
                ]
                # self is bound, so we have len(pos_params) - 1 positional slots after self
                usable_slots = len(pos_params) - 1  # -1 for self
                if has_var_keyword or has_var_positional:
                    return handler(args, kwargs)
                # Merge named kwargs into positional args
                merged = list(args)
                kwarg_names = {k for k in kwargs}
                for p in pos_params[1:]:  # skip self
                    if p.name in kwarg_names and len(merged) <= usable_slots:
                        idx = pos_params.index(p) - 1
                        if idx >= len(merged):
                            merged.extend([None] * (idx - len(merged)))
                        merged[idx] = kwargs.pop(p.name)
                        if not kwargs:
                            break
                if kwargs:
                    return handler(merged, kwargs)
                return handler(merged)
            except (ValueError, TypeError):
                return handler(args, kwargs)
        return handler(args)

    BuiltinDispatchMixin._call_builtin = _patched_call_builtin


class CustomEvaluator:
    """Wraps NodeLiteralEvaluator to capture plot commands and strategy events."""

    def __init__(self, context=None, data_feed=None, data_provider=None):
        from pynescript.ast.evaluator import NodeLiteralEvaluator
        from pynescript.ast.evaluator.builtins.strategy import StrategyState

        _patch_evaluator()

        # Wrap (not subclass) to avoid multiple-inheritance surprises.
        self._inner = NodeLiteralEvaluator(context=context, data_feed=data_feed, data_provider=data_provider)
        self.plot_outputs: list[dict] = []
        self._strategy_state = StrategyState()
        self._var_declarations = set()

        # Monkey-patch the inner evaluator's _builtin_plot so plot() calls
        # land in our buffer.  The base class dispatches "plot" to
        # self._builtin_plot, so we rebind the method on the instance.
        inner = self._inner
        plot_outputs = self.plot_outputs
        original_plot = inner._builtin_plot

        def _capture_plot(args, kwargs=None):
            result = original_plot(args, kwargs)
            if args:
                v = args[0]
                # v can be a PineSeries (has .current), a list/deque, or a raw value
                if hasattr(v, "current"):
                    v = v.current
                elif isinstance(v, (list, tuple)) and v:
                    # List result (e.g. from ta.sma): last element is most recent
                    v = v[-1]
                # Extract title from positional args (args[1] is the title string in Pine plot())
                merged = dict(kwargs) if kwargs else {}
                if len(args) > 1 and "title" not in merged:
                    merged["title"] = args[1]
                plot_outputs.append(
                    {
                        "type": "plot",
                        "value": v,
                        "kwargs": merged,
                        "bar_index": _PLOT_BAR_INDEX[0],
                    }
                )
            return result

        inner._builtin_plot = _capture_plot
        # Invalidate dispatch cache so the rebuilt map picks up _capture_plot
        inner._builtin_dispatch = None

    def __getattr__(self, name):
        if name in ("_inner", "plot_outputs", "_strategy_state", "_var_declarations"):
            raise AttributeError(name)
        return getattr(self._inner, name)

    def _builtin_plot(self, args, kwargs=None):
        if not args:
            return None
        value = args[0]
        if hasattr(value, "current"):
            value = value.current
        self.plot_outputs.append({"type": "plot", "value": value, "kwargs": kwargs or {}})
        return None

    def reset_plots(self):
        self.plot_outputs.clear()

    def reset_var_declarations(self):
        self._var_declarations = set()

    def reset_events(self):
        self._strategy_state._events = []


# Per-bar index tracker used by the plot-capture closure
_PLOT_BAR_INDEX = [0]


# --- Helpers for the run loop ---------------------------------------------


class _Namespace:
    """Tiny attribute holder so Pine scripts can read `syminfo.ticker` etc."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


# --- The run loop --------------------------------------------------------


def _run_interpret(script: str, bars: list[dict]) -> dict:
    # Build series
    open_series = PineSeries()
    high_series = PineSeries()
    low_series = PineSeries()
    close_series = PineSeries()
    volume_series = PineSeries()

    context: dict = {
        "open": open_series,
        "high": high_series,
        "low": low_series,
        "close": close_series,
        "volume": volume_series,
        "bar_index": 0,
        "time": 0,
        "syminfo": _Namespace(
            ticker="BTCUSDT",
            currency="USD",
            prefix="",
            mintick=0.01,
            pointvalue=1.0,
            description="Synthetic",
            timezone="UTC",
            type="stock",
            session="regular",
        ),
        "timeframe": _Namespace(
            period="D", multiplier=1, isdaily=True, isintraday=False, isweekly=False, ismonthly=False
        ),
        "barstate": _Namespace(isconfirmed=True, isrealtime=False, isnew=True, islastconfirmedbar=True),
        "chart": _Namespace(isfullscreen=False, leftvisiblebars=0, rightvisiblebars=0),
    }

    evaluator = CustomEvaluator(context=context)

    script_id = hashlib.sha256(script.encode("utf-8")).hexdigest()[:16]
    run_id = uuid.uuid4().hex[:12]
    t0 = time.perf_counter()
    all_events: list[dict] = []
    all_plots: list[dict] = []

    for bar_index, bar in enumerate(bars):
        # Update series state
        open_series.update(bar.get("open"))
        high_series.update(bar.get("high"))
        low_series.update(bar.get("low"))
        close_series.update(bar.get("close"))
        volume_series.update(bar.get("volume", 0.0))

        # Update per-bar counters
        context["bar_index"] = bar_index
        context["time"] = bar.get("time", 0)

        # Reset plot + event buffers
        evaluator.reset_plots()
        evaluator.reset_events()
        # Track which bar's plot we're capturing (the per-bar buffer
        # gets reset, so we mark each entry with the current bar index).
        _PLOT_BAR_INDEX[0] = bar_index

        try:
            evaluator.evaluate_script(script)
        except Exception as e:
            return {
                "status": "error",
                "plots": [],
                "series": {},
                "events": all_events,
                "error": f"Runtime error at bar {bar_index}: {e!s}",
                "meta": {"ms": (time.perf_counter() - t0) * 1000, "mode": "interpret"},
            }

        # Capture plots emitted on this bar
        for p in evaluator.plot_outputs:
            p["bar_index"] = bar_index
            p["time"] = bar.get("time", 0)
        all_plots.extend(evaluator.plot_outputs)

        # Drain strategy events
        for ev in evaluator._strategy_state.drain_events():
            d = ev.to_dict() if hasattr(ev, "to_dict") else {"type": str(ev)}
            d.setdefault("time", bar.get("time", 0))
            d.setdefault("price", bar.get("close", 0.0))
            d["script_id"] = script_id
            d["run_id"] = run_id
            all_events.append(d)

    # Build plot series aligned with bars
    series: dict[str, list] = {}
    for p in all_plots:
        # Group by name (defaults to "plot")
        kwargs = p.get("kwargs") or {}
        name = str(kwargs.get("title") or kwargs.get("name") or "plot")
        arr = series.setdefault(name, [None] * len(bars))
        bi = p.get("bar_index", -1)
        if 0 <= bi < len(bars):
            v = p.get("value")
            if v is not None and not (isinstance(v, float) and v != v):
                arr[bi] = float(v)

    plots_main = series.get(next(iter(series), ""), [b.get("close") for b in bars])

    # Build an equity curve from events
    equity = 100_000.0
    equity_curve: list[dict] = []
    in_pos = False
    entry_price = 0.0
    for ev in sorted(all_events, key=lambda e: e.get("time", 0)):
        kind = (ev.get("type", "") or ev.get("event", "")).lower()
        price = ev.get("price")
        if price is None:
            continue
        if "entry" in kind:
            in_pos = True
            entry_price = price
        elif "close" in kind or "exit" in kind:
            if in_pos:
                equity *= 1 + (price - entry_price) / max(entry_price, 1e-9)
                in_pos = False
        equity_curve.append({"time": ev["time"], "value": equity})

    return {
        "status": "success",
        "plots": plots_main,
        "series": series,
        "events": all_events,
        "equity_curve": equity_curve,
        "meta": {
            "mode": "interpret",
            "count": len(bars),
            "ms": (time.perf_counter() - t0) * 1000,
            "script_id": script_id,
            "run_id": run_id,
        },
    }


def run_script(script: str, bars: list[dict]) -> str:
    """Top-level entry.  Always returns a JSON string for the JS side."""
    try:
        out = _run_interpret(script, bars)
        return json.dumps(out, default=str)
    except Exception as e:
        return json.dumps(
            {
                "status": "error",
                "plots": [],
                "series": {},
                "events": [],
                "error": f"{type(e).__name__}: {e}",
                "meta": {"mode": "interpret"},
            }
        )
