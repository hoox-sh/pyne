#!/bin/sh
# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Production entrypoint for the Pro API (gunicorn).
# Worker/thread/timeout counts are env-tunable without rebuilding the image.
#
# WebSocket (/ws/run) note:
#   Default gthread/sync workers do NOT speak WebSocket. AXIS will fall back
#   to POST /run. For native WS, run a compatible stack (e.g. geventwebsocket)
#   or keep preferWs=false in AXIS settings. Raise GUNICORN_TIMEOUT for large
#   compile-mode runs (default 120s).

set -eu

PORT="${PORT:-8080}"
WORKERS="${GUNICORN_WORKERS:-2}"
THREADS="${GUNICORN_THREADS:-4}"
TIMEOUT="${GUNICORN_TIMEOUT:-120}"
BIND="${GUNICORN_BIND:-0.0.0.0:${PORT}}"

exec gunicorn \
  --bind "${BIND}" \
  --workers "${WORKERS}" \
  --threads "${THREADS}" \
  --timeout "${TIMEOUT}" \
  --access-logfile "-" \
  --error-logfile "-" \
  backend.app:app
