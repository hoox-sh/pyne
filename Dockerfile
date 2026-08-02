# syntax=docker/dockerfile:1.7
# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Multi-stage, multi-target image for PYNE (pynescript).
#
# Targets (buildx / compose):
#   api      — production Pro API (gunicorn, non-root)  [default for Cloud Run]
#   api-dev  — development Pro API (Flask, HOST=0.0.0.0)
#   lsp      — language server (stdio; use with compose profile lsp)
#
# Examples:
#   docker buildx bake api
#   docker build --target api -t pynescript-api:latest .
#   docker compose up --build api

ARG PYTHON_VERSION=3.12

# ---------------------------------------------------------------------------
# Base: shared OS packages
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MPLBACKEND=Agg \
    PORT=8080 \
    HOST=0.0.0.0 \
    API_KEY_STORE=/data/api_keys.json \
    PYNE_COMPILE_DISK_CACHE=1 \
    PYNE_COMPILE_CACHE_DIR=/data/compile-cache \
    PYNE_COMPILE_PREWARM=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        libfreetype6 \
        libpng16-16 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /data /data/compile-cache \
    && chown -R appuser:appuser /data

# ---------------------------------------------------------------------------
# Builder: install Python deps + package into /install prefix
# ---------------------------------------------------------------------------
FROM base AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Metadata first for layer caching of dependency installs
COPY pyproject.toml README.md LICENSE NOTICE ./
COPY backend/requirements.txt ./backend/requirements.txt

# Backend runtime deps (Flask, gunicorn, numpy, matplotlib, …)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --prefix=/install -r backend/requirements.txt

# Application sources
COPY src ./src
COPY backend ./backend

# Install pynescript (core + LSP extras used by api-dev / lsp targets)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --prefix=/install ".[lsp]"

# ---------------------------------------------------------------------------
# Runtime base: copy installed prefix, drop privileges
# ---------------------------------------------------------------------------
FROM base AS runtime

COPY --from=builder /install /usr/local
COPY --from=builder /app/src /app/src
COPY --from=builder /app/backend /app/backend
COPY docker/entrypoint-api.sh /usr/local/bin/entrypoint-api.sh

RUN chmod +x /usr/local/bin/entrypoint-api.sh \
    && chown -R appuser:appuser /app /data

# Prefer bind-mounted sources (compose) over site-packages when present:
#   /app/src → pynescript package, /app → backend package
ENV PYTHONPATH=/app/src:/app

USER appuser

ARG PYNESCRIPT_VERSION=0.2.0
ARG GIT_SHA=unknown
LABEL org.opencontainers.image.title="pynescript" \
      org.opencontainers.image.description="PYNE Pro API — Pine Script parse/eval/preview" \
      org.opencontainers.image.version="${PYNESCRIPT_VERSION}" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.licenses="AGPL-3.0-or-later" \
      org.opencontainers.image.source="https://github.com/jango-blockchained/pyne"

EXPOSE 8080

# ---------------------------------------------------------------------------
# Target: api (production)
# ---------------------------------------------------------------------------
FROM runtime AS api

ENV FLASK_ENV=production

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT:-8080}/" || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint-api.sh"]

# ---------------------------------------------------------------------------
# Target: api-dev (local compose; source mounts expected)
# ---------------------------------------------------------------------------
FROM runtime AS api-dev

ENV FLASK_ENV=development \
    FLASK_DEBUG=1 \
    HOST=0.0.0.0 \
    PORT=8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT:-8080}/" || exit 1

# Flask dev server must bind 0.0.0.0 for published ports to work
CMD ["python", "-m", "backend.app"]

# ---------------------------------------------------------------------------
# Target: lsp (language server over stdio)
# ---------------------------------------------------------------------------
FROM runtime AS lsp

ENV FLASK_ENV=production

# No HTTP healthcheck — stdio LSP
CMD ["python", "-m", "pynescript.langserver"]
