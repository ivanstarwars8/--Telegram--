"""Stats handler."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.services import api_client

router = Router()


@router.message(Command("stats"))
async def stats(message: Message) -> None:
    data = await api_client.api_get("/stats/summary", message.from_user.id, params={"range": "weekly"})
    streak = data["streak"]
    reliability = data["reliability"]
    stability = data["stability"]
    focus = data["focus_avg"]
    await message.answer(
        f"Серия утренних выборов: {streak}\nНадёжность: {reliability}\nСтабильность: {stability}\nФокус в среднем: {focus} мин"
    )
