"""Процес бота: python -m zoshyt.bot. Long polling (ADR-0004), один процес на токен."""

import asyncio

import structlog
from aiogram import Bot, Dispatcher

from zoshyt.bot.handlers import router
from zoshyt.config import get_settings
from zoshyt.log import configure_logging


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.app_env)
    log = structlog.get_logger()

    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    dp.include_router(router)

    log.info("bot.starting", app_env=settings.app_env)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
