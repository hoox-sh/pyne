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
#
# Warm compile (H2):
#   PYNE_COMPILE_DISK_CACHE=1 (default) + PYNE_COMPILE_CACHE_DIR=/data/compile-cache
#   PYNE_COMPILE_PREWARM=1 → once-per-worker builtin warm on first /run (and
#   optional POST /compile/prewarm from readiness probes).

set -eu

PORT="${PORT:-8080}"
WORKERS="${GUNICORN_WORKERS:-2}"
THREADS="${GUNICORN_THREADS:-4}"
TIMEOUT="${GUNICORN_TIMEOUT:-120}"
BIND="${GUNICORN_BIND:-0.0.0.0:${PORT}}"

# Ensure IR / Numba disk cache directory exists on the data volume (best-effort).
CACHE_DIR="${PYNE_COMPILE_CACHE_DIR:-/data/compile-cache}"
if [ "${PYNE_COMPILE_DISK_CACHE:-1}" != "0" ]; then
  mkdir -p "${CACHE_DIR}" 2>/dev/null || true
fi

exec gunicorn \
  --bind "${BIND}" \
  --workers "${WORKERS}" \
  --threads "${THREADS}" \
  --timeout "${TIMEOUT}" \
  --access-logfile "-" \
  --error-logfile "-" \
  backend.app:app
