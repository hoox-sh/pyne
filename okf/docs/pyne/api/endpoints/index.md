# docs/pyne/api/endpoints

# Concepts

- [Backtest Endpoint](backtest.md) - POST /backtest/quick — usage-tracked strategy metrics, equity curve, and optional mock OHLCV.
- [Data plane](data-plane.md) - POST /run takes its bars in the request. That is fine for a one-shot evaluate, but a live chart re-sends the entire history on every tick and asks the exchange for bars the…
- [POST `/optimize`](optimize.md) - /optimize searches Pine input. values for a strategy() script. It loops the package Runtime (same interpret path as /run) with different overrides, scores closed trades, and…
- [Preview Endpoints](preview.md) - Pro chart and indicator thumbnail routes under /preview with usage tracking.
- [POST /run](run.md) - Free evaluate endpoints: single-script /run and multi-script /run/batch over shared OHLCV.
- [Hosted runner](runner.md) - Optional Flask/container script registry + bar-close scheduler (PYNERUNNER). Off by default.
- [Live sessions](sessions.md) - POST /session and friends — O(1) forming-bar ticks, O(delta) appends, and response windowing on /run.
- [GET /stats](stats.md) - Public process-wide runtime statistics — engine, compile, prewarm, deltas, sessions, datafeed and HTTP counters.
