"""Async engine і фабрика сесій (ADR-0002: async усюди, драйвер asyncpg).

Engine створюється ліниво і один раз (lru_cache), не на імпорті модуля —
щоб імпорт zoshyt.db не вимагав DB_URL (тести, mypy, alembic).
"""

from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from zoshyt.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(get_settings().db_url)


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False: після commit об'єкти лишаються читабельними
    # без нового запиту — стандартна практика для async-сесій.
    return async_sessionmaker(get_engine(), expire_on_commit=False)
