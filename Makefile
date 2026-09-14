# Словник команд проєкту. Ті самі команди — локально і в CI.
#   make up     — Postgres у контейнері
#   make check  — ruff + mypy + import-linter + pytest
#   make dev    — api (uvicorn --reload) + bot + vite разом

.PHONY: up check lint typecheck imports test dev

up:
	docker compose up -d postgres

check: lint typecheck imports test

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

typecheck:
	uv run mypy

imports:
	uv run lint-imports

test:
	uv run pytest -q

# Три процеси у фоні + wait; Ctrl+C зупиняє всі.
dev:
	uv run uvicorn zoshyt.api.app:create_app --factory --reload --port 8000 & \
	uv run python -m zoshyt.bot & \
	pnpm -C miniapp dev & \
	wait
