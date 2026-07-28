# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later

# Makefile for Pynescript development

.PHONY: help install test lint fmt build run clean docker-build docker-run run-frontend run-axis worker-install worker-dev worker-deploy worker-typecheck pages-deploy test-frontend typecheck

help:
	@echo "Pynescript Development Commands (Bun-first)"
	@echo ""
	@echo "  install          Install Python deps"
	@echo "  install-bun      Install root + worker Bun deps"
	@echo "  test             Run all tests (Python + Bun)"
	@echo "  test-frontend    Run AXIS unit + worker tests (frontend/)"
	@echo "  test-lsp         Run LSP tests only"
	@echo "  test-backend     Run backend tests only"
	@echo "  lint             Run linting"
	@echo "  typecheck        Typecheck all TS (root + worker)"
	@echo "  build            Build LSP binary (requires nuitka)"
	@echo "  build-vscode     Package VS Code extension"
	@echo "  run              Run the API server"
	@echo "  run-lsp          Run the LSP server"
	@echo "  run-axis         AXIS product path: Vite dev (Solid, port 3000)"
	@echo "  run-frontend     Legacy static shell only (Bun server.ts, port 8081)"
	@echo "  worker-install   Install Cloudflare Worker Bun deps"
	@echo "  worker-dev       Run wrangler dev for the Worker (port 8787)"
	@echo "  worker-typecheck Typecheck the Worker (tsc --noEmit)"
	@echo "  worker-deploy    Deploy the Worker to Cloudflare"
	@echo "  pages-deploy     Build AXIS dist/ and deploy to Cloudflare Pages"
	@echo "  docker-build      Build API Docker image"
	@echo "  docker-run        Run API in Docker"
	@echo "  clean            Clean build artifacts"

install:
	pip install -e ".[lsp]"

install-bun:
	bun install
	cd frontend/worker && bun install

install-lsp:
	pip install -e ".[lsp]"

test: test-frontend
	python -m pytest tests/ -v --tb=short

test-frontend:
	cd frontend && bun run test

test-lsp:
	python -m pytest tests/test_langserver.py tests/test_lsp_features.py -v

test-backend:
	python -m pytest tests/test_backend.py -v

lint:
	ruff check src/ tests/ backend/

fmt:
	ruff format src/ tests/ backend/

typecheck:
	bunx tsc -p tsconfig.json
	cd frontend/worker && bunx tsc --noEmit

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

run-axis:
	@echo "AXIS (Solid + Vite) on http://127.0.0.1:3000"
	@echo "(proxies /run → :5002 — start with 'make run' in another terminal)"
	cd frontend && bun run dev

run-frontend:
	@echo "Legacy static shell on http://127.0.0.1:8081 (not the AXIS product path)"
	@echo "Prefer: make run-axis  or  cd frontend && bun run dev"
	@echo "(requires the backend on :5002 for /run — start with 'make run' in another terminal)"
	bun run frontend/server.ts

worker-install:
	cd frontend/worker && bun install

worker-dev:
	cd frontend/worker && bun run dev

worker-typecheck:
	cd frontend/worker && bun run typecheck

worker-deploy:
	cd frontend/worker && bun run deploy

pages-deploy:
	cd frontend && bun run build && bunx --yes wrangler pages deploy dist --project-name=pynescript-superchart

docker-build:
	docker build -f Dockerfile.api -t pynescript-api .

docker-run:
	docker compose up api --build

clean:
	rm -rf dist/
	rm -rf vscode-extension/out/
	rm -rf vscode-extension/node_modules/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
