# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later

# Makefile for pyne (Pine Script Python toolchain) development

.PHONY: help install test lint fmt build run clean \
	docker-build docker-build-all docker-buildx docker-run docker-up docker-up-full \
	docker-prod docker-down docker-logs docker-smoke \
	test-lsp test-backend typecheck build-check build-vscode

help:
	@echo "pyne — Pine Script™ Python toolchain"
	@echo ""
	@echo "  install          Install Python package (editable + LSP extra)"
	@echo "  test             Run pytest (tests/)"
	@echo "  test-lsp         LSP unit + e2e tests"
	@echo "  test-backend     Backend / Pro API tests"
	@echo "  lint             ruff check"
	@echo "  fmt              ruff format"
	@echo "  build            Nuitka LSP binary"
	@echo "  build-check      Fast import check (no compile)"
	@echo "  build-vscode     Package VS Code extension"
	@echo "  run              Flask Pro API (:5002)"
	@echo "  run-lsp          Language server (stdio)"
	@echo "  docker-build     buildx bake production API image (load)"
	@echo "  docker-build-all buildx bake api + api-dev + lsp"
	@echo "  docker-buildx    multi-platform release bake (amd64+arm64)"
	@echo "  docker-up        compose up API (dev target, port 5002)"
	@echo "  docker-up-full   compose up with redis profile (not lsp)"
	@echo "  docker-prod      compose prod overlay (gunicorn, no source mounts)"
	@echo "  docker-down      compose down"
	@echo "  docker-logs      follow API logs"
	@echo "  docker-smoke     health-check curl against :5002"
	@echo "  docker-run       alias for docker-up"
	@echo "  clean            Clean build artifacts"
	@echo ""
	@echo "AXIS charting UI lives in the sister repo:"
	@echo "  https://github.com/jango-blockchained/axis"
	@echo "  (local: ../axis  or  /home/jango/Git/axis)"

install:
	pip install -e ".[lsp]"

install-lsp:
	pip install -e ".[lsp]"

test:
	python -m pytest tests/ -v --tb=short

test-lsp:
	python -m pytest tests/test_langserver.py tests/test_lsp_features.py -v

test-backend:
	python -m pytest tests/test_backend.py -v

lint:
	ruff check src/ tests/ backend/

fmt:
	ruff format src/ tests/ backend/

build:
	python scripts/build/compile.py --jobs=4

build-check:
	python scripts/build/compile.py --check

build-vscode:
	cd vscode-extension && npm install && npm run compile && npx vsce package --allow-missing-repository

run:
	python -m backend.app

run-lsp:
	python -m pynescript.langserver

# Docker / buildx -----------------------------------------------------------
# Prefer a dedicated builder for multi-platform: docker buildx create --use --name pynescript
GIT_SHA ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo unknown)
PYNESCRIPT_VERSION ?= $(shell sed -n 's/^__version__ = "\(.*\)"/\1/p' src/pynescript/__about__.py 2>/dev/null || echo 0.2.0)
BAKE_ARGS = --set "*.args.GIT_SHA=$(GIT_SHA)" --set "*.args.PYNESCRIPT_VERSION=$(PYNESCRIPT_VERSION)"

docker-build:
	docker buildx bake api $(BAKE_ARGS)

docker-build-all:
	docker buildx bake all $(BAKE_ARGS)

docker-buildx:
	docker buildx bake release $(BAKE_ARGS)

docker-up:
	GIT_SHA=$(GIT_SHA) PYNESCRIPT_VERSION=$(PYNESCRIPT_VERSION) docker compose up --build -d api

docker-run: docker-up

# Redis only — LSP is stdio and must be started with `docker compose run --rm lsp`
docker-up-full:
	GIT_SHA=$(GIT_SHA) PYNESCRIPT_VERSION=$(PYNESCRIPT_VERSION) \
		docker compose --profile redis up --build -d

docker-prod:
	@test -n "$${ADMIN_TOKEN:-}" || (echo "Set ADMIN_TOKEN for production compose" >&2; exit 1)
	GIT_SHA=$(GIT_SHA) PYNESCRIPT_VERSION=$(PYNESCRIPT_VERSION) \
		docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d api

docker-down:
	docker compose --profile redis --profile lsp down

docker-logs:
	docker compose logs -f api

docker-smoke:
	@echo "Waiting for API on http://127.0.0.1:$${API_PORT:-5002}/ ..."
	@ok=0; \
	for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do \
		if curl -fsS "http://127.0.0.1:$${API_PORT:-5002}/" >/dev/null 2>&1; then ok=1; break; fi; \
		sleep 2; \
	done; \
	if [ "$$ok" != "1" ]; then echo "API did not become healthy" >&2; exit 1; fi; \
	curl -fsS "http://127.0.0.1:$${API_PORT:-5002}/" | head -c 400; echo; \
	echo "docker-smoke: ok"

clean:
	rm -rf dist/
	rm -rf vscode-extension/out/
	rm -rf vscode-extension/node_modules/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
