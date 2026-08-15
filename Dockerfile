# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later

# syntax=docker/dockerfile:1.7
# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# Multi-stage, multi-target image for PYNE (pynescript).
#
# Targets (buildx / compose):
#   api      — production Pro API (gunicorn, non-root)  [default for Cloud Run]
#   api-dev  — development Pro API (Flask, HOST=0.0.0.0)
#   lsp      — language server (stdio; ENTRYPOINT pyne-lsp)
#   cli      — pyne Click CLI (parse/lint/format/compile/run; ENTRYPOINT)
#
# Examples:
#   docker buildx bake api
#   docker buildx bake cli
#   docker buildx bake lsp
#   docker build --target api -t pynescript-api:latest .
#   docker build --target cli -t pynescript-cli:latest .
#   docker build --target lsp -t pynescript-lsp:latest .
#   docker run --rm -v "$PWD:/work" -w /work pynescript-cli check script.pine
#   docker run --rm -i pynescript-lsp
#   docker compose up --build api
#
# Secrets: never bake CRYPTO_KEY / ADMIN_TOKEN / API keys into ENV or LABEL.
# Build tools (build-essential) exist only in *builder stages*, not final images.

ARG PYTHON_VERSION=3.12

# ---------------------------------------------------------------------------
# base-os: minimal Python + non-root user (shared foundation; no API libs)
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS base-os

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /data /data/compile-cache /data/cache /work \
    && chown -R appuser:appuser /data /work

# ---------------------------------------------------------------------------
# Base: API/LSP OS packages + long-running service env defaults
# ---------------------------------------------------------------------------
FROM base-os AS base

ENV MPLBACKEND=Agg \
    PORT=8080 \
    HOST=0.0.0.0 \
    API_KEY_STORE=/data/api_keys.json \
    PYNE_COMPILE_DISK_CACHE=1 \
    PYNE_COMPILE_CACHE_DIR=/data/compile-cache \
    PYNE_COMPILE_PREWARM=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        libfreetype6 \
        libpng16-16 \
    && rm -rf /var/lib/apt/lists/*

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
# CLI builder: package + compile/data extras (no Flask / matplotlib stack)
# build-essential stays in this stage only — final `cli` image never sees it.
# ---------------------------------------------------------------------------
FROM base-os AS cli-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE NOTICE ./
COPY src ./src

# Core CLI + Numba compile path + optional market data (ccxt)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --prefix=/install ".[compile,data]"

# ---------------------------------------------------------------------------
# Runtime base: copy installed prefix, drop privileges (API / LSP)
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

ARG PYNESCRIPT_VERSION=0.3.0
ARG GIT_SHA=unknown
LABEL org.opencontainers.image.title="pynescript" \
      org.opencontainers.image.description="PYNE Pro API — Pine Script parse/eval/preview" \
      org.opencontainers.image.version="${PYNESCRIPT_VERSION}" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.licenses="AGPL-3.0-or-later" \
      org.opencontainers.image.source="https://github.com/hoox-sh/pyne"

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
# LSP builder: package + [lsp] only (no Flask / matplotlib / API deps)
# ---------------------------------------------------------------------------
FROM base-os AS lsp-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE NOTICE ./
COPY src ./src

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --prefix=/install ".[lsp]"

# ---------------------------------------------------------------------------
# Target: lsp (language server over stdio — GHCR ghcr.io/hoox-sh/pyne/lsp)
# ---------------------------------------------------------------------------
FROM base-os AS lsp

COPY --from=lsp-builder /install /usr/local
COPY --from=lsp-builder /app/src /app/src

RUN mkdir -p /work \
    && chown -R appuser:appuser /app /work

ENV PYTHONPATH=/app/src

USER appuser
WORKDIR /work

ARG PYNESCRIPT_VERSION=0.3.0
ARG GIT_SHA=unknown
LABEL org.opencontainers.image.title="pynescript-lsp" \
      org.opencontainers.image.description="PYNE language server (stdio) — pyne-lsp" \
      org.opencontainers.image.version="${PYNESCRIPT_VERSION}" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.licenses="AGPL-3.0-or-later" \
      org.opencontainers.image.source="https://github.com/hoox-sh/pyne"

# No HTTP healthcheck — stdio LSP. -i required for docker run / VS Code.
ENTRYPOINT ["pyne-lsp"]

# ---------------------------------------------------------------------------
# Target: cli (pyne Click console — parse / lint / format / compile / run)
#
# Final stage is based on base-os (not base): no curl, freetype, png, or API
# env defaults. build-essential is only in cli-builder. Non-root appuser.
# No HEALTHCHECK: process is ephemeral (compose run / docker run one-shot).
# ---------------------------------------------------------------------------
FROM base-os AS cli

# Runtime shared lib for OpenMP (numba/numpy manylinux wheels may link it)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=cli-builder /install /usr/local
COPY --from=cli-builder /app/src /app/src
COPY docker/entrypoint-cli.sh /usr/local/bin/entrypoint-cli.sh

RUN chmod +x /usr/local/bin/entrypoint-cli.sh \
    && chown -R appuser:appuser /app /data /work

# Prefer bind-mounted sources (compose) over site-packages when present.
# Compile cache on /data (volume). No API secrets / PORT / HOST / API_KEY_STORE.
ENV PYTHONPATH=/app/src \
    PYNE_COMPILE_DISK_CACHE=1 \
    PYNE_COMPILE_CACHE_DIR=/data/compile-cache \
    XDG_CACHE_HOME=/data/cache

USER appuser

ARG PYNESCRIPT_VERSION=0.3.0
ARG GIT_SHA=unknown
# OCI labels only — never put secrets, tokens, or build credentials here.
LABEL org.opencontainers.image.title="pynescript-cli" \
      org.opencontainers.image.description="PYNE CLI — parse, lint, format, compile, and run Pine Script" \
      org.opencontainers.image.version="${PYNESCRIPT_VERSION}" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.licenses="AGPL-3.0-or-later" \
      org.opencontainers.image.source="https://github.com/hoox-sh/pyne"

WORKDIR /work

# Ephemeral one-shot CLI — no long-running daemon, no HTTP listener, therefore
# no HEALTHCHECK (a probe would always be meaningless for `docker run … check`).
ENTRYPOINT ["/usr/local/bin/entrypoint-cli.sh"]
CMD ["--help"]
