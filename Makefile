# Makefile for Chronus Quantum iGPU

.PHONY: test test-cover lint format build clean install install-devmode import claims run ga-test help install-dev

# Default target
help:
	@echo "Chronus Quantum iGPU v36.0 Development Tasks"
	@echo "=========================================="
	@echo "make test            Run the test suite"
	@echo "make test-cover      Run tests with coverage report"
	@echo "make lint            Run code linting (ruff)"
	@echo "make format          Auto-format code (black)"
	@echo "make build           Build the package"
	@echo "make clean           Clean build artifacts"
	@echo "make import          Verify the GA foundation imports"
	@echo "make claims          Verify the GA executable claims manifest"
	@echo "make run             Run the experimental GA API"
	@echo "make ga-test         Run the GA foundation tests"
	@echo "make install-devmode Install development dependencies"

# Install the repository and development dependencies.
install: install-devmode

# Install development dependencies (pyproject.toml is the single source of truth)
install-devmode:
	pip install -e '.[dev]'

# Import-safe GA foundation. FastAPI is loaded only when create_app is called.
import:
	python scripts/ci/check_ga_import.py

# Verify every implemented GA claim against its named executable check.
claims:
	python -m ga.claims verify --manifest docs/claims.yaml

# Run the experimental GA API factory.
run:
	python -m ga.cli

# Run only the evidence-safe GA foundation tests.
ga-test:
	python -m ga.claims verify --manifest docs/claims.yaml
	pytest -q tests/ga

# Run tests
test:
	pytest tests/ -v

# Run tests with coverage
test-cover:
	pytest tests/ --cov=src/chronus --cov-report=html --cov-report=term-missing -v

# Lint code
lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

# Format code
format:
	ruff format src/ tests/
	ruff check --fix src/ tests/

# Build package
build:
	rm -rf dist build *.egg-info
	python -m pip install --upgrade build
	python -m build

# Clean build artifacts
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

# Install in development mode
install-dev:
	pip install -e .
