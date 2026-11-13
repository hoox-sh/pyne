---
type: "Code Module"
title: "src/pynescript/runtime"
description: "Bar-loop Runtime host — public package surface for multi-bar evaluation."
resource: "src/pynescript/runtime"
tags: [code, pynescript, runtime]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-11-13T13:46:36Z
sources:
  - id: tree
    resource: "src/pynescript/runtime"
    title: "src/pynescript/runtime"
    author: process:git
okf_lock: generated
---

# Files

- `__init__.py`
- `axb1.py` — Axb1Opcode, Header, TipMask, ValueKind, assert_price_scale, encode_append_bar, encode_append_bars, encode_close_verify, encode_envelope, encode_error, encode_heartbeat, encode_json_blob
- `evaluator.py` — CustomEvaluator
- `host.py` — Barstate, Chart, Chartinfo, InterpretSession, LazyCalendarContext, Runtime, Syminfo, Timeframe
- `series.py` — PineSeries, apply_bar_sample, env_series_max, estimate_series_bytes, make_pine_series, parse_max_bars_back_from_source, pineseries_history_length, resolve_series_cap, series_cap_enabled, series_cap_limit, series_ring_enabled, trim_series_lists

# Packages

`NASDAQ:AAPL`
