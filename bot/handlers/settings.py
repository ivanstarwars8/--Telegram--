"""Settings and templates commands."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.services import api_client

router = Router()


@router.message(Command("settings"))
async def settings(message: Message) -> None:
    await message.answer("Настройки скоро будут доступны из меню. Пока держи курс.")


@router.message(Command("templates"))
async def templates(message: Message) -> None:
    templates = await api_client.api_get("/templates", message.from_user.id)
    text = "\n".join(f"{t['level']}: {t['name']}" for t in templates)
    await message.answer(text or "Шаблонов нет. Добавь через /settings")


@router.message(Command("sleep"))
async def sleep(message: Message) -> None:
    await message.answer("Фиксация сна доступна через /sleep_start HH:MM и /sleep_end HH:MM (TODO)")


@router.message(Command("help"))
async def help_(message: Message) -> None:
    await message.answer(
        "/plan — активный план\n/today — список задач\n/next — следующая задача\n/done — выполнить\n/skip — пропустить\n/stats — аналитика"
    )
