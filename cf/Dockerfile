# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Cloudflare Workers Containers image for the production Pro API.
# Built from the repo-root `api` target:
#   docker build --platform linux/amd64 --target api -t pyne-api:cf ..
#   docker build -f cf/Dockerfile -t pyne-api:cf-runtime ..
#
# syntax=docker/dockerfile:1.7

FROM pyne-api:cf

ENV HOST=0.0.0.0 \
    PORT=8080 \
    FLASK_ENV=production \
    FLASK_DEBUG=0 \
    PYNE_COMPILE_PREWARM=0 \
    GUNICORN_WORKERS=1 \
    GUNICORN_THREADS=4 \
    GUNICORN_TIMEOUT=60 \
    FREE_TIER_LIMITS=1 \
    STORE_BACKEND=sqlite \
    PYTHONPATH=/app/src:/app
