"""/start command handler."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.core.config import settings
from bot.keyboards.common import plan_choice_keyboard
from bot.services import api_client

router = Router()


@router.message(Command("start"))
async def start(message: Message) -> None:
    await api_client.api_post(
        "/user/register",
        tg_id=message.from_user.id,
        json={"tg_id": message.from_user.id, "tz": settings.timezone_default, "locale": "ru"},
    )
    await message.answer(
        "Выбери план на сегодня",
        reply_markup=plan_choice_keyboard(),
    )
