---
type: "Code Module"
title: "src/pynescript/util"
description: "Utility helpers for market data, corpus cleanup, and host math."
resource: "src/pynescript/util"
tags: [code, pynescript, util]
status: stable
generated:
  by: process:axis-okf/1
  at: 2026-10-26T09:58:21Z
sources:
  - id: tree
    resource: "src/pynescript/util"
    title: "src/pynescript/util"
    author: process:git
okf_lock: generated
---

# Files

* `__init__.py`
* `corpus_cli.py` — corpus_group, list_cmd, run_cmd
* `corpus_runtime.py` — CorpusProgress, CorpusRunResult, collect_files, corpus_rel_path, discover_sets, format_summary, is_expected_fail, resolve_cache_dir, resolve_data_root, run_corpus
* `corpus_sanitize.py` — sanitize_corpus_source
* `data.py` — AlphaVantageProvider, CCXTProvider, ChartOHLCVProvider, DataProvider, DataProviderError, MockDataProvider, YahooFinanceProvider, geo_block_message, get_provider, normalize_ccxt_symbol, resolve_request_sources, tune_ccxt_public_urls
* `datafeed.py` — CCXTProDataFeed, CompositeDataFeed, DataFeed, DataFeedBroker, DataFeedError, MockDataFeed, Order, get_datafeed, poll_forming_ohlcv
* `itertools.py` — grouper
* `pine_convert.py` — convert_pine, convert_to_v6, convert_v3_to_v4, convert_v4_to_v5, convert_v5_to_v6, convert_v6_to_v5, detect_version
* `rich_theme.py` — console, has_rich, rich_theme, use_rich
* `runner_cli.py` — api_request, delete_cmd, deploy_cmd, disable_cmd, enable_cmd, jobs_cmd, list_cmd, runner_group, show_cmd, tick_cmd
* `time_parts.py` — UtcParts, apply_utc_parts_to_context, utc_parts_from_ms

# Packages

`Copy code`
