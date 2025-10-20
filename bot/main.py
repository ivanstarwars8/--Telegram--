"""Aiogram entrypoint."""
from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

from app.core.config import settings
from bot import handlers


async def main() -> None:
    bot = Bot(token=settings.telegram_bot_token, parse_mode=ParseMode.HTML)
    dp = Dispatcher()
    dp.include_router(handlers.router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
