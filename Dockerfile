# Один multi-stage образ (ADR-0010): збірка Mini App → Python-залежності →
# фінальний slim з пакетом і miniapp/dist. Два сервіси з одного образу:
# api (CMD за замовчуванням), bot (command: python -m zoshyt.bot),
# migrate (command: alembic upgrade head) — див. docker-compose.prod.yml.

# ---- Stage 1: збірка Mini App -------------------------------------------
FROM node:22-slim AS miniapp
RUN corepack enable
WORKDIR /build
COPY miniapp/package.json miniapp/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY miniapp/ ./
RUN pnpm build

# ---- Stage 2: Python-залежності (uv --frozen = строго за uv.lock) --------
FROM python:3.12-slim AS python
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv
WORKDIR /app
# Спершу лише маніфести: шар із залежностями кешується, поки не змінився uv.lock.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src/ src/
# README.md потрібен збирачу пакета (readme = "README.md" у pyproject).
COPY alembic.ini README.md ./
RUN uv sync --frozen --no-dev

# ---- Stage 3: фінальний образ — без uv, node і dev-залежностей ------------
FROM python:3.12-slim
WORKDIR /app
COPY --from=python /app/.venv /app/.venv
COPY --from=python /app/src /app/src
COPY --from=python /app/alembic.ini /app/alembic.ini
# Сюди дивиться MINIAPP_DIST у zoshyt/api/app.py (шлях відносно WORKDIR).
COPY --from=miniapp /build/dist /app/miniapp/dist
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
RUN useradd --system --no-create-home app && chown -R app:app /app
USER app
EXPOSE 8000
CMD ["uvicorn", "zoshyt.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
