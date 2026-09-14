"""Хендлери бота. Поки лише /start-заглушка; онбординг (RegisterTeacher,
кнопка web_app) — крок 5 плану."""

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

router = Router()


@router.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer("Zoshyt: скаффолд працює. Онбординг з'явиться далі.")
