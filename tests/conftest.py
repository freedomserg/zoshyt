"""Тестова БД (ADR-0010): база zoshyt_test у compose-Postgres / service container.

- URL-и виводяться з DB_URL / DB_MIGRATE_URL заміною імені бази — без нових змінних.
- Міграції накочуються один раз на сесію під zoshyt_migrate.
- Між тестами — TRUNCATE під zoshyt_migrate (app цього права не має).
  Це лише тестова база; у справжньому журналі events ніхто нічого не чистить.
- Тести ходять у БД під zoshyt_app — тією ж роллю, що api і bot.

Потрібен живий Postgres: `make up`.
"""

from collections.abc import AsyncIterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import URL, make_url, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from zoshyt.config import get_settings

TEST_DATABASE = "zoshyt_test"


def _test_url(url: str) -> URL:
    return make_url(url).set(database=TEST_DATABASE)


@pytest.fixture(scope="session")
def migrated_db() -> None:
    """alembic upgrade head на zoshyt_test. Синхронна фікстура: env.py сам
    робить asyncio.run(), а всередині вже запущеного event loop це неможливо."""
    cfg = Config("alembic.ini")
    cfg.attributes["db_url"] = _test_url(get_settings().db_migrate_url).render_as_string(
        hide_password=False
    )
    command.upgrade(cfg, "head")


# Engine на кожен тест і без пулу: pytest-asyncio дає кожному тесту свій
# event loop, а з'єднання asyncpg прив'язане до loop, у якому створене.
@pytest.fixture
async def migrate_engine(migrated_db: None) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(_test_url(get_settings().db_migrate_url), poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest.fixture
async def app_engine(migrate_engine: AsyncEngine) -> AsyncIterator[AsyncEngine]:
    """Engine під zoshyt_app на чистій базі."""
    async with migrate_engine.begin() as conn:
        await conn.execute(
            text("TRUNCATE events, school_members, teachers, schools RESTART IDENTITY")
        )
    engine = create_async_engine(_test_url(get_settings().db_url), poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(app_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with AsyncSession(app_engine, expire_on_commit=False) as s:
        yield s
