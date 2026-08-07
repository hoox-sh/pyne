#!/bin/sh
# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Ephemeral CLI entrypoint for the `cli` image target.
#
# Ensures the compile-cache directory exists on /data (best-effort), then
# exec's the pynescript Click console. No long-running process and no HTTP
# listener — the image intentionally has no HEALTHCHECK.

set -eu

CACHE_DIR="${PYNE_COMPILE_CACHE_DIR:-/data/compile-cache}"
if [ "${PYNE_COMPILE_DISK_CACHE:-1}" != "0" ]; then
  mkdir -p "${CACHE_DIR}" 2>/dev/null || true
fi

# Optional XDG cache (pip/ccxt/numba side paths) when set to a volume path.
if [ -n "${XDG_CACHE_HOME:-}" ]; then
  mkdir -p "${XDG_CACHE_HOME}" 2>/dev/null || true
fi

exec pynescript "$@"
