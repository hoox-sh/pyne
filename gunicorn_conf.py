# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Gunicorn config for the pynescript Pro API.
#
# This config defines ONLY the post_fork hook; bind/workers/threads/timeout are
# passed on the gunicorn command line (see docker/entrypoint-api.sh) so there is
# no conflict between config-file and CLI settings.
#
# post_fork runs in each worker after fork, which is the correct place to pay
# the one-time Numba JIT + ANTLR cold cost so the first user request never
# stalls on warm-up.

from __future__ import annotations

import logging


def post_fork(server, worker):
    """Eagerly warm Numba builtins + parser in each worker after fork.

    Eliminates first-request JIT stall (Numba ~hundreds of ms) and the cold
    ANTLR ATN parse (~0.7 s). Respects ``PYNE_COMPILE_PREWARM`` (default on).
    Safe to call per-worker: the engine guards against double-warm and missing
    Numba. Logs at debug so failed prewarm never blocks worker boot.
    """
    log = logging.getLogger("gunicorn.conf.post_fork")
    try:
        from pynescript.ast.helper import prewarm_parser
        from pynescript.compiler.engine import prewarm_enabled
        from pynescript.compiler.engine import prewarm_numba_builtins
    except Exception as exc:  # pragma: no cover - dependency missing
        log.debug("post_fork prewarm imports failed: %s", exc)
        return
    if not prewarm_enabled():
        log.debug("post_fork prewarm disabled (PYNE_COMPILE_PREWARM=0)")
        return
    try:
        prewarm_parser()
        log.debug("post_fork: parser prewarm complete")
    except Exception as exc:  # pragma: no cover - never blocks boot
        log.debug("post_fork: parser prewarm failed: %s", exc)
    try:
        prewarm_numba_builtins()
        log.debug("post_fork: numba builtin prewarm complete")
    except Exception as exc:  # pragma: no cover - never blocks boot
        log.debug("post_fork: numba builtin prewarm failed: %s", exc)
