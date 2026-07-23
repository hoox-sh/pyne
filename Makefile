# Copyright (C) 2025 jango-blockchained. All Rights Reserved.
#
# Makefile for Pynescript development

.PHONY: help install test lint fmt build run clean docker-build docker-run run-frontend worker-install worker-dev worker-deploy worker-typecheck pages-deploy

help:
	@echo "Pynescript Development Commands"
	@echo ""
	@echo "  install          Install dependencies"
	@echo "  install-lsp      Install LSP dependencies"
	@echo "  test             Run all tests"
	@echo "  test-lsp         Run LSP tests only"
	@echo "  test-backend     Run backend tests only"
	@echo "  lint             Run linting"
	@echo "  build            Build LSP binary (requires nuitka)"
	@echo "  build-vscode     Package VS Code extension"
	@echo "  run              Run the API server"
	@echo "  run-lsp          Run the LSP server"
	@echo "  run-frontend     Serve the SuperChart Lite PWA (HTTP, port 8081)"
	@echo "  worker-install   Install Cloudflare Worker npm deps"
	@echo "  worker-dev       Run wrangler dev for the Worker (port 8787)"
	@echo "  worker-typecheck Typecheck the Worker (tsc --noEmit)"
	@echo "  worker-deploy    Deploy the Worker to Cloudflare"
	@echo "  pages-deploy     Deploy the PWA to Cloudflare Pages"
	@echo "  docker-build      Build API Docker image"
	@echo "  docker-run        Run API in Docker"
	@echo "  clean            Clean build artifacts"

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

run-frontend:
	@echo "Serving SuperChart Lite on http://localhost:8081"
	@echo "(requires the backend on :5002 for /run — start with 'make run' in another terminal)"
	python -m http.server 8081 --directory frontend

worker-install:
	cd frontend/worker && npm install

worker-dev:
	cd frontend/worker && npm run dev

worker-typecheck:
	cd frontend/worker && npm run typecheck

worker-deploy:
	cd frontend/worker && npm run deploy

pages-deploy:
	cd frontend && npx --yes wrangler pages deploy . --project-name=pynescript-superchart

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
