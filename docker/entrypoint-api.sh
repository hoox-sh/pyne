#!/bin/sh
# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Production entrypoint for the Pro API (gunicorn).
# Worker/thread/timeout counts are env-tunable without rebuilding the image.
#
# WebSocket (/ws/run, /ws/live, /datafeed/watch) note:
#   These routes use flask-sock, which performs the HTTP→WS upgrade itself by
#   hijacking gunicorn's transport (`gunicorn.socket`). The default is
#   therefore `gthread --threads N` — one thread per live WS connection.
#   Do NOT select geventwebsocket.gunicorn.workers.GeventWebSocketWorker:
#   that worker's handler upgrades the socket on its own (`wsgi.websocket`)
#   and then flask-sock hijacks the same socket and re-frames it, so clients
#   receive an HTTP error body where a WS frame belongs — *after* a successful
#   101 (Chromium reports "Invalid frame header"). `sync` cannot upgrade at
#   all, so AXIS falls back to REST there. Select via GUNICORN_WORKER_CLASS;
#   --threads only applies to gthread. Raise GUNICORN_TIMEOUT for large
#   compile-mode runs (default 120s).
#
# Warm compile (H2):
#   PYNE_COMPILE_DISK_CACHE=1 (default) + PYNE_COMPILE_CACHE_DIR=/data/compile-cache
#   PYNE_COMPILE_PREWARM=1 → once-per-worker builtin warm on first /run (and
#   optional POST /compile/prewarm from readiness probes).

set -eu

PORT="${PORT:-8080}"
# Default 1, deliberately. The live-session routes (/session, …/append, …/tick)
# keep parsed script + series + TA state in process so a re-tick is O(1); that
# state is per-process, so a second worker would 404 on ~half of all follow-up
# calls. gthread still serves many concurrent connections (threads below).
# Override only if session state has moved to an external store.
WORKERS="${GUNICORN_WORKERS:-1}"
# One thread per live WS connection (plus REST), so the default is generous.
THREADS="${GUNICORN_THREADS:-100}"
# flask-sock owns the upgrade: gthread exposes gunicorn.socket, which
# simple-websocket hijacks. See the WebSocket note at the top of this file
# for why the gevent-websocket worker must not be used here.
WORKER_CLASS="${GUNICORN_WORKER_CLASS:-gthread}"
WORKER_CONNECTIONS="${GUNICORN_WORKER_CONNECTIONS:-1000}"
TIMEOUT="${GUNICORN_TIMEOUT:-120}"
BIND="${GUNICORN_BIND:-0.0.0.0:${PORT}}"
# datafeed compose service sets this to backend.datafeed_app:app
APP="${GUNICORN_APP:-backend.app:app}"
# Worker recycling bounds per-worker memory growth across requests
# (Numba / caches). 0 disables. Mirrors the VPS systemd unit.
# Live WS connections delay recycle; 500 was recycling the worker under AXIS
# tick load and forcing a journal rebuild. 0 disables. Memory is still bounded
# by the compose mem_limit.
MAX_REQUESTS="${GUNICORN_MAX_REQUESTS:-5000}"
MAX_REQUESTS_JITTER="${GUNICORN_MAX_REQUESTS_JITTER:-200}"

# Ensure IR / Numba disk cache directory exists on the data volume (best-effort).
CACHE_DIR="${PYNE_COMPILE_CACHE_DIR:-/data/compile-cache}"
if [ "${PYNE_COMPILE_DISK_CACHE:-1}" != "0" ]; then
  mkdir -p "${CACHE_DIR}" 2>/dev/null || true
fi
if [ "${PYNE_RUNNER:-0}" != "0" ]; then
  mkdir -p "$(dirname "${PYNE_RUNNER_DB:-/data/runner.db}")" 2>/dev/null || true
fi

case "${WORKER_CLASS}" in
  sync|gthread)
    # gthread upgrades through flask-sock (gunicorn.socket); sync cannot
    # upgrade, so AXIS falls back to REST on that worker class.
    exec gunicorn \
      --bind "${BIND}" \
      --workers "${WORKERS}" \
      --worker-class "${WORKER_CLASS}" \
      --threads "${THREADS}" \
      --timeout "${TIMEOUT}" \
      --max-requests "${MAX_REQUESTS}" \
      --max-requests-jitter "${MAX_REQUESTS_JITTER}" \
      --access-logfile "-" \
      --error-logfile "-" \
      "${APP}"
    ;;
  *)
    # Async workers (gevent/eventlet): --threads does not apply. flask-sock
    # needs a plain socket to hijack — the gevent-websocket worker breaks
    # framing (see the WebSocket note at the top of this file).
    # Long-lived WS connections delay --max-requests recycling gracefully.
    exec gunicorn \
      --bind "${BIND}" \
      --workers "${WORKERS}" \
      --worker-class "${WORKER_CLASS}" \
      --worker-connections "${WORKER_CONNECTIONS}" \
      --timeout "${TIMEOUT}" \
      --max-requests "${MAX_REQUESTS}" \
      --max-requests-jitter "${MAX_REQUESTS_JITTER}" \
      --access-logfile "-" \
      --error-logfile "-" \
      "${APP}"
    ;;
esac
