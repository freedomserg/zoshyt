# ADR-0010 — Розкладка репозиторію: monorepo, один Python-пакет, два процеси

Статус: accepted (2026-09)

## Контекст
Один домен, одна БД, двоє людей ([С] інфра/ревʼю, [К] journal/api/bot)
плюс Claude Code і Claude Design. Перші тижні схема подій крутитиметься —
межі мають тримати churn всередині journal.

## Рішення
Monorepo `zoshyt`, один Python-пакет, два процеси з одного образу:

    pyproject.toml, uv.lock, .python-version
    src/zoshyt/
      journal/   ядро: події, команди/запити, EventStore (Protocol +
                 Postgres-реалізація). Володіє events і проєкціями.
      auth/      verify_init_data(bot_token) | DevAuth (AUTH_MODE=dev)
                 | майбутній MagicLinkAuth. Віддає TeacherId.
      api/       FastAPI: роутери 5 екранів, /health, StaticFiles
                 для miniapp/dist. Тонкий шар над journal.
      bot/       aiogram: /start, web_app-кнопка, нагадування,
                 APScheduler-джоби. Тонкий шар над journal.
      db/        engine, session, моделі, alembic/ (async-шаблон).
      notify/    Notifier(send_to_parent) + Telegram-реалізація.
      config.py  pydantic-settings з env.
    miniapp/     React + Vite + TS; react-router;
                 @telegram-apps/sdk-react; api/client.ts + api/auth.ts;
                 нуль state-бібліотек до появи болю.
    docs/adr/, design/handoff/, CLAUDE.md, README.md, Makefile,
    Dockerfile, docker-compose.yml, docker-compose.prod.yml,
    .github/workflows/{ci,release}.yml, .env.example

Граф імпортів (enforcement — import-linter у make check):

    journal <- api, bot, notify    (journal не знає нікого)
    auth    <- api, bot
    db      <- journal, api, bot
    api !-> bot, bot !-> api       (спільне — лише через journal)

Інструменти (фіксуються в pyproject): ruff (lint+format), mypy strict,
pytest + pytest-asyncio + httpx, import-linter, pre-commit.
Залежності: fastapi, uvicorn, sqlalchemy 2.x, asyncpg, alembic,
pydantic-settings, aiogram 3.x, apscheduler, structlog.
miniapp: vite, react, typescript, react-router,
@telegram-apps/sdk-react, eslint + prettier; vitest — лише за появи
логіки, вартої тесту.

Docker: один multi-stage Dockerfile (node → pnpm build miniapp;
python:3.12-slim + uv --frozen + miniapp/dist). Два сервіси з одного
образу: api (uvicorn), bot (python -m zoshyt.bot); migrate — one-shot
перед api. Тег = GITHUB_SHA; :latest — зручність, не джерело правди.

Тести БД: compose-Postgres локально, service container (postgres:17)
у CI. База zoshyt_test, alembic upgrade у session-fixture, truncate
між тестами.

## Альтернативи (відкинуті)
- Окремі пакети api/bot: два pyproject/lock, дублювання моделей —
  один домен різати нема по чому. Процеси розділяємо, код — ні.
- Окреме репо miniapp: подвійна PR-перевірка, ADR відірвані від коду.
- Next/Remix: SPA за Caddy, SSR не потрібен.
- Окремий сервіс планувальника: APScheduler живе в процесі бота.
- testcontainers-python: повільніше і складніше за compose для [К].

## Наслідки
- Churn схеми подій не витікає: api/bot ходять лише через
  команди/запити journal.
- Один образ = один тег = один відкат.

## Для Claude Code
Скаффолд за цією розкладкою. Критерії приймання:
1) make check зелений на порожніх пакетах;
2) docker build проходить; docker run … uvicorn віддає /health;
3) uv run alembic upgrade head проходить на порожньому versions/;
4) контракти import-linter описані в pyproject і реально валять
   збірку при порушенні;
5) pnpm -C miniapp build збирає порожній каркас.
Порожні пакети — з __init__.py і docstring призначення. Нових
залежностей поза списком не додавати без ADR.
