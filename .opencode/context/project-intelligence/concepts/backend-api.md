<!-- Context: project-intelligence/concepts/backend-api | Priority: high | Version: 1.0 | Updated: 2026-07-05 -->

# Pro API Backend (Flask)

`backend/` is the **closed-source-style** Pro API server: chart previews, indicator
charts, and quick backtests. Deployed to Google Cloud Run (see `cloudbuild.yaml`).

## Layout

- `backend/app.py` — Flask app factory, middleware wiring, gunicorn entry.
- `backend/runtime.py` — `Runtime` (sandboxed execution).
- `backend/evaluator.py` — Script evaluator glue.
- `backend/series.py` — Time-series / OHLC helpers.
- `backend/api/preview.py` — Blueprints: `preview_bp`, `backtest_bp`.
- `backend/api/__init__.py` — Blueprint registry.
- `backend/middleware/auth.py` — `require_api_key` decorator, `get_key_store`.
- `backend/middleware/__init__.py` — Middleware exports.
- `backend/services/chart_renderer.py` — Chart PNG rendering.
- `backend/services/backtest.py` — Equity-curve / Sharpe / PnL.
- `backend/requirements.txt` — Backend-only Python deps.

## Endpoints (from README)

| Endpoint | Method | Tier | Purpose |
| --- | --- | --- | --- |
| `/run` | POST | Free | Execute Pine Script |
| `/preview/chart` | POST | Pro | Chart thumbnail |
| `/preview/indicator` | POST | Pro | SMA/EMA/RSI/MACD chart |
| `/backtest/quick` | POST | Pro | Backtest with equity curve |

## Run Locally

```bash
pip install -e ".[lsp]"
pip install -r backend/requirements.txt   # flask, flask-cors, numpy, matplotlib
make run                                  # → python -m backend.app
# or:
make docker-run                           # docker compose up api --build
```

## Container

`Dockerfile.api` is a multi-stage build that ends in:
```bash
gunicorn --bind :8080 --workers 2 --threads 4 --timeout 60 backend.app:app
```
Port 8080, user `appuser`, `FLASK_ENV=production`.

## Deploy

`cloudbuild.yaml` builds the image, pushes to `gcr.io/$PROJECT_ID/pynescript/...`,
and deploys to Cloud Run `us-central1`. Substitution `_METADATA_KEY` feeds the LSP
build step (see `build-pipeline.md`).

## 📂 Codebase References

- **Implementation**: `backend/app.py` — Flask app.
- **Implementation**: `backend/api/preview.py` — endpoint blueprints.
- **Implementation**: `backend/services/` — chart + backtest engines.
- **Reference**: `Dockerfile.api` — production container.
- **Reference**: `cloudbuild.yaml` — Cloud Build pipeline.
