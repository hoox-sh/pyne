---
type: "Code Module"
title: "src/pynescript/ast/evaluator/builtins"
description: "Pine Script evaluator builtins package (dispatch aggregate)."
resource: "src/pynescript/ast/evaluator/builtins"
tags: [ast, code, evaluator, pynescript]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-09-24T03:40:25Z
sources:
  - id: tree
    resource: "src/pynescript/ast/evaluator/builtins"
    title: "src/pynescript/ast/evaluator/builtins"
    author: process:git
okf_lock: generated
---

# Files

* `__init__.py` — BuiltinEvaluator
* `alerts.py` — AlertCondition, AlertEvent, AlertsMixin, export_alerts_from_evaluator, normalize_alert_freq
* `arrays.py` — ArrayBuiltinsMixin
* `base.py` — BuiltinDispatchMixin, pine_expect_int, pine_period_or_none
* `color.py` — Color, color_b, color_from_gradient, color_g, color_new, color_r, color_rgb, color_t, register_color_functions
* `declarations.py` — ScriptDeclaration, indicator, library, register_script_declaration_functions, strategy
* `drawing.py` — Box, ChartPoint, DrawingBuiltinsMixin, DrawingRegistry, Label, Line, LineFill, Polyline, Table, TableCell
* `input.py` — InputBuiltinsMixin
* `logging.py` — Logger, format_log_message, get_logger, log_error, log_info, log_warning, register_logging_functions, runtime_error
* `map.py` — Map
* `map_evaluator.py` — MapBuiltinsMixin
* `matrix.py` — Matrix
* `matrix_evaluator.py` — MatrixBuiltinsMixin
* `numeric.py` — NumericBuiltinsMixin
* `plot_params.py` — extract_wire_meta, param_index, resolve_arg
* `plotting.py` — Plot, PlotRegistry, PlotStyle, PlottingFunctionsMixin, materialize_visual_series_from_drawings, merge_visual_series_from_drawings, uniquify_series_title
* `request.py` — Footprint, FootprintBuiltinsMixin, HtfOffsetExpr, HtfSimpleTaExpr, RequestBuiltinsMixin, VolumeRow, match_htf_offset_ast, match_htf_simple_ta_ast
* `strategy.py` — OpenTrade, Order, StrategyBuiltinsMixin, StrategyCashAmount, StrategyState, Trade
* `strategy_constants.py` — StrategyConstantsMixin
* `strings.py` — StringBuiltinsMixin
* `technical.py` — TechnicalAnalysisMixin
* `ticker.py` — TickerInfo, extract_prefix, extract_ticker, register_ticker_functions, split_symbol, ticker_heikinashi, ticker_inherit, ticker_kagi, ticker_linebreak, ticker_modify, ticker_new, ticker_pointfigure
* `timeframe.py` — register_timeframe_functions, timeframe_bucket_id, timeframe_bucket_ms, timeframe_calendar_id, timeframe_change, timeframe_from_seconds, timeframe_in_seconds, timeframe_is_calendar_tf, timeframe_period_changed, timeframes_equivalent
* `utility.py` — UtilityFunctionsMixin

# Nested

* [src/pynescript/ast/evaluator/builtins/technical_submodules](/code/src/pynescript/ast/evaluator/builtins/technical_submodules.md)
