# Makefile for Chronus

.PHONY: test test-cover lint format build clean install install-devmode import claims run ga-test frontend-install frontend-build frontend-dev up down help

help:
	@echo "Chronus | HYBA Data"
	@echo "==================="
	@echo "make install          Install Python development dependencies"
	@echo "make test             Run the Python test suite"
	@echo "make lint             Check Python formatting and lint"
	@echo "make build            Build the Python packages"
	@echo "make frontend-install Install frontend dependencies"
	@echo "make frontend-build   Build the Next.js preview"
	@echo "make frontend-dev     Start the Next.js preview"
	@echo "make up               Build and start the local Docker stack"
	@echo "make down             Stop the local Docker stack"
	@echo "make import           Verify the GA foundation imports"
	@echo "make claims           Verify the executable claims manifest"
	@echo "make ga-test          Run the evidence-safe GA foundation tests"

install: install-devmode

install-devmode:
	pip install -e '.[dev]'

frontend-install:
	pnpm --dir frontend install --frozen-lockfile

frontend-build:
	pnpm --dir frontend build

frontend-dev:
	pnpm --dir frontend dev

up:
	docker compose up --build

down:
	docker compose down

import:
	python scripts/ci/check_ga_import.py

claims:
	python -m ga.claims verify --manifest docs/claims.yaml

run:
	python -m ga.cli

ga-test:
	python -m ga.claims verify --manifest docs/claims.yaml
	pytest -q tests/ga

test:
	pytest tests/ -v

test-cover:
	pytest tests/ --cov=src/chronus --cov-report=html --cov-report=term-missing -v

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

format:
	ruff format src/ tests/
	ruff check --fix src/ tests/

build:
	rm -rf dist build *.egg-info
	python -m pip install --upgrade build
	python -m build

clean:
	rm -rf dist build *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true
	find . -type d -name *.pyc -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name .pytest_cache -delete 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name .mypy_cache -delete 2>/dev/null || true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true

install-dev:
	pip install -e .
