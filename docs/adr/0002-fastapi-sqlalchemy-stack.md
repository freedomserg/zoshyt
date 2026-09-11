# ADR-0002 — Бекенд-стек: FastAPI + SQLAlchemy 2 (async) + Alembic; Postgres 17

Статус: accepted (2026-09)

## Контекст
Бекенд пише [К], що вчиться Python. Потрібен мінімальний сучасний стек
з хорошою типізацією. FastAPI і aiogram обидва async — змішування
sync/async режимів ускладнило б навчання і код.

## Рішення
- FastAPI + uvicorn (UVICORN_WORKERS=1 у проді).
- SQLAlchemy 2.x у async-режимі, драйвер asyncpg. Async — усюди.
- Alembic для міграцій (async-шаблон env.py через run_sync).
- Postgres 17: пін major-тегу `postgres:17` в усіх compose і CI.
- pydantic-settings для конфігурації; structlog для логів
  (stdout; JSON у prod); APScheduler — у процесі бота.

## Альтернативи (відкинуті)
- Django: admin/ORM/templates не потрібні (Mini App — SPA), більше
  магії для новачка.
- Sync SQLAlchemy (psycopg + to_thread у боті): змішаний режим гірший
  за один async.
- Postgres 16 (нічим не кращий) / 18 (жодна потреба не вимагає).

## Наслідки
- Усі IO-функції async; тести — pytest-asyncio.
- Alembic-операції — через async-двигун (run_sync).

## Для Claude Code
Нові залежності — лише через ADR. Версії пакетів звіряти на день
старту (`uv add`), не брати з пам'яті.
