# Developer entrypoints. Every CI step is a make target so CI == local.
SHELL := /bin/bash
export UV_SYSTEM_CERTS ?= 1
PY_PKGS := -p compback_core -p compback_vault -p compback_extract -p compback_rating \
           -p compback_ml -p compback_disputes -p compback_api -p compback_worker

.PHONY: install lint format typecheck test test-fast migrate migrate-check audit web-check check

install:
	uv sync --frozen
	cd apps/web && pnpm install --frozen-lockfile

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff format .
	uv run ruff check . --fix

typecheck:
	uv run mypy $(PY_PKGS)

test:
	uv run pytest --cov --cov-report=term-missing:skip-covered

test-fast:
	uv run pytest -x -q

migrate:
	uv run alembic upgrade head

# Upgrade -> downgrade -> upgrade on a scratch DB and fail if models drift from migrations.
migrate-check:
	uv run python -m compback_core.tools.migration_check

audit:
	mkdir -p .data
	uv export --frozen --no-emit-workspace --no-hashes --quiet -o .data/requirements-audit.txt
	uv run pip-audit -r .data/requirements-audit.txt --disable-pip --no-deps --strict --progress-spinner off

web-check:
	cd apps/web && pnpm lint && pnpm typecheck && pnpm test

check: lint typecheck test migrate-check
