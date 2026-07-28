# Copyright (C) 2024-2026 jango_blockchained
# SPDX-License-Identifier: AGPL-3.0-or-later

# Makefile for pyne (Pine Script Python toolchain) development

.PHONY: help install test lint fmt build run clean docker-build docker-run test-lsp test-backend typecheck build-check build-vscode

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
	@echo "  docker-build     Build API Docker image"
	@echo "  docker-run       Run API via docker compose"
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
