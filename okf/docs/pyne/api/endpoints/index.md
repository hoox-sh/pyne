# docs/pyne/api/endpoints

# Concepts

* [Backtest Endpoint](backtest.md) - POST /backtest/quick — usage-tracked strategy metrics, equity curve, and optional mock OHLCV.
* [POST /optimize](optimize.md) - Strategy hyperparameter search — N interpret Runtime runs with input. overrides, TPE/random/grid, holdout or walk-forward.
* [Preview Endpoints](preview.md) - Pro chart and indicator thumbnail routes under /preview with usage tracking.
* [POST /run](run.md) - Free evaluate endpoints: single-script /run and multi-script /run/batch over shared OHLCV.
* [Hosted runner](runner.md) - Optional Flask/VPS/container script registry + bar-close scheduler (PYNERUNNER). Off by default.
