# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later

# Makefile for pyne (Pine Script Python toolchain) development

.PHONY: help install test lint fmt build run clean \
	docker-build docker-build-cli docker-build-all docker-buildx docker-push-ghcr docker-run \
	docker-up docker-up-full docker-prod docker-down docker-logs docker-smoke \
	docker-cli \
	test-lsp test-backend test-cli typecheck build-check build-cli build-package \
	build-vscode package \
	corpus-flow corpus-flow-set05 corpus-recompile \
	deploy-vps deploy-vps-build

help:
	@echo "pyne — Pine Script™ Python toolchain"
	@echo ""
	@echo "  install          Install Python package (editable + LSP extra)"
	@echo "  test             Run pytest (tests/)"
	@echo "  test-cli         CLI unit tests (tests/test_cli.py)"
	@echo "  test-lsp         LSP unit + e2e tests"
	@echo "  test-backend     Backend / Pro API tests"
	@echo "  lint             ruff check"
	@echo "  fmt              ruff format"
	@echo "  package          Build sdist + wheel (python -m build)"
	@echo "  build            Nuitka LSP binary"
	@echo "  build-cli        Nuitka CLI binary (pyne / pynescript)"
	@echo "  build-check      Fast import check (no compile)"
	@echo "  build-vscode     Package VS Code extension"
	@echo "  run              Flask Pro API (:5002)"
	@echo "  run-lsp          Language server (stdio)"
	@echo "  docker-build     buildx bake production API image (load)"
	@echo "  docker-build-cli buildx bake CLI image (load)"
	@echo "  docker-build-all buildx bake api + api-dev + lsp + cli"
	@echo "  docker-buildx    multi-platform release bake (amd64+arm64)"
	@echo "  docker-push-ghcr trigger GHCR workflow (api+cli multi-arch)"
	@echo "  docker-cli       run CLI in container (ARGS=... e.g. check x.pine)"
	@echo "  docker-up        compose up API (dev target, port 5002)"
	@echo "  docker-up-full   compose up with redis profile (not lsp)"
	@echo "  docker-prod      compose prod overlay (gunicorn, no source mounts)"
	@echo "  docker-down      compose down"
	@echo "  docker-logs      follow API logs"
	@echo "  docker-smoke     health-check curl against :5002"
	@echo "  docker-run       alias for docker-up"
	@echo "  clean            Clean build artifacts"
	@echo "  corpus-flow      Animated full corpus flow (SETS=set05 MODE=auto)"
	@echo "  corpus-flow-set05  shorthand for set05 full pipeline"
	@echo "  corpus-recompile   re-run prior OK scripts (FROM=… LIMIT=0)"
	@echo ""
	@echo "  deploy-vps       rsync API + AXIS dist to VPS (ed25519 key)"
	@echo "  deploy-vps-build bun build AXIS then deploy-vps"
	@echo ""
	@echo "AXIS charting UI lives in the sister repo:"
	@echo "  https://github.com/jango-blockchained/axis"
	@echo "  (local: ../axis  or  /home/jango/Git/axis)"

install:
	pip install -e ".[lsp,pro]"

install-lsp:
	pip install -e ".[lsp]"

install-pro:
	pip install -e ".[pro]"
	pip install -r backend/requirements.txt

test:
	python -m pytest tests/ -v --tb=short

test-cli:
	python -m pytest tests/test_cli.py -v --tb=short

test-lsp:
	python -m pytest tests/test_langserver.py tests/test_lsp_features.py -v

test-backend:
	python -m pytest tests/test_backend.py -v

lint:
	ruff check src/ tests/ backend/

fmt:
	ruff format src/ tests/ backend/

# sdist + wheel. Twine is optional so CI/local packaging works without it.
package:
	@python -c "import build" 2>/dev/null || (echo "error: need 'build' (pip install build)" >&2; exit 1)
	python -m build
	@if python -c "import twine" 2>/dev/null; then \
		python -m twine check dist/*; \
	else \
		echo "twine not installed — skipped check (pip install twine)"; \
	fi

build:
	python scripts/build/compile.py --target lsp --jobs=4

build-cli:
	python scripts/build/compile.py --target cli --jobs=4

# Fast import-only check (no Nuitka). Targets match compile.py --target choices.
build-check:
	python scripts/build/compile.py --target all --check

build-vscode:
	cd vscode-extension && npm install && npm run package

run:
	python -m backend.app

run-lsp:
	python -m pynescript.langserver

# VPS demo (namecheap): key auth via ~/.ssh/id_ed25519 by default
deploy-vps:
	./scripts/deploy_vps.sh

deploy-vps-build:
	AXIS_BUILD=1 ./scripts/deploy_vps.sh

# Animated corpus pipeline: parse → re-run fails → runtime → report
# Override: make corpus-flow SETS=set05 WORKERS=6 MODE=auto
SETS ?= set05
WORKERS ?= 4
MODE ?= auto
BARS ?= 50
corpus-flow:
	python scripts/showcase.py --sets $(SETS) --workers $(WORKERS) \
		--runtime-mode $(MODE) --bars $(BARS) --resume

corpus-flow-set05:
	python scripts/showcase.py --sets set05 --workers $(WORKERS) \
		--runtime-mode $(MODE) --bars $(BARS) --timeout 12 --runtime-timeout 10 \
		--recompile-timeout 8 --resume

# Re-run only scripts that already OK'd under a prior runtime CSV (warm compile path).
# Example: make corpus-recompile SETS=set05 FROM=.cache/corpus_flow_set05_runtime_auto.csv
FROM ?= .cache/corpus_flow_set05_runtime_auto.csv
LIMIT ?= 0
corpus-recompile:
	python scripts/showcase.py --sets $(SETS) --workers $(WORKERS) \
		--phases recompile,report --recompile-mode compile \
		--recompile-from $(FROM) --recompile-timeout 8 --bars $(BARS) \
		$(if $(filter-out 0,$(LIMIT)),--recompile-limit $(LIMIT),)

# Docker / buildx -----------------------------------------------------------
# Prefer a dedicated builder for multi-platform: docker buildx create --use --name pynescript
GIT_SHA ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo unknown)
PYNESCRIPT_VERSION ?= $(shell sed -n 's/^__version__ = "\(.*\)"/\1/p' src/pynescript/__about__.py 2>/dev/null || echo 0.2.0)
BAKE_ARGS = --set "*.args.GIT_SHA=$(GIT_SHA)" --set "*.args.PYNESCRIPT_VERSION=$(PYNESCRIPT_VERSION)"

docker-build:
	docker buildx bake api $(BAKE_ARGS)

docker-build-cli:
	docker buildx bake cli $(BAKE_ARGS)

docker-build-all:
	docker buildx bake all $(BAKE_ARGS)

docker-buildx:
	docker buildx bake release $(BAKE_ARGS)

# Trigger GitHub Actions GHCR push (api + cli multi-arch). Requires gh auth.
docker-push-ghcr:
	gh workflow run ghcr.yml -R hoox-sh/pyne
	@echo "Watch: gh run watch -R hoox-sh/pyne"
	@echo "Images: ghcr.io/hoox-sh/pyne/api  ghcr.io/hoox-sh/pyne/cli"

docker-up:
	GIT_SHA=$(GIT_SHA) PYNESCRIPT_VERSION=$(PYNESCRIPT_VERSION) docker compose up --build -d api

docker-run: docker-up

# Ephemeral CLI container.
# Example: make docker-cli ARGS='check examples/rsi_strategy.pine'
# $(ARGS) is intentionally unquoted after Make expansion so the shell word-splits
# multi-arg values; nested quotes inside ARGS are still honored by the shell.
ARGS ?= --help
docker-cli:
	GIT_SHA=$(GIT_SHA) PYNESCRIPT_VERSION=$(PYNESCRIPT_VERSION) \
		docker compose --profile cli run --rm cli $(ARGS)

# Redis only — LSP/CLI are ephemeral; start with `docker compose run --rm lsp|cli`
docker-up-full:
	GIT_SHA=$(GIT_SHA) PYNESCRIPT_VERSION=$(PYNESCRIPT_VERSION) \
		docker compose --profile redis up --build -d

docker-prod:
	@test -n "$${ADMIN_TOKEN:-}" || (echo "Set ADMIN_TOKEN for production compose" >&2; exit 1)
	GIT_SHA=$(GIT_SHA) PYNESCRIPT_VERSION=$(PYNESCRIPT_VERSION) \
		docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d api

docker-down:
	docker compose --profile redis --profile lsp --profile cli down

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
