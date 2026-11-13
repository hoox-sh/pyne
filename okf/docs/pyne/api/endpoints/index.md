# docs/pyne/api/endpoints

# Concepts

- [Backtest Endpoint](backtest.md) - POST /backtest/quick — usage-tracked strategy metrics, equity curve, and optional mock OHLCV.
- [Data plane](data-plane.md) - Engine-owned OHLCV series store and data-bound live sessions — /data/series and /data/session.
- [POST /optimize](optimize.md) - Strategy hyperparameter search — N interpret Runtime runs with input. overrides, TPE/random/grid, holdout or walk-forward.
- [Preview Endpoints](preview.md) - Pro chart and indicator thumbnail routes under /preview with usage tracking.
- [POST /run](run.md) - Free evaluate endpoints: single-script /run and multi-script /run/batch over shared OHLCV.
- [Hosted runner](runner.md) - Optional Flask/container script registry + bar-close scheduler (PYNERUNNER). Off by default.
- [Live sessions](sessions.md) - POST /session and friends — O(1) forming-bar ticks, O(delta) appends, and response windowing on /run.
- [GET /stats](stats.md) - Public process-wide runtime statistics — engine, compile, prewarm, deltas, sessions, datafeed and HTTP counters.
