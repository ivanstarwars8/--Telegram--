"""Task flow handlers."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.keyboards.common import focus_session_keyboard
from bot.services import api_client

router = Router()


@router.message(Command("today"))
async def today(message: Message) -> None:
    snapshot = await api_client.api_get("/day/today", message.from_user.id)
    lines = [f"{task['order_index']+1}. {task['title']} — {task['status']}" for task in snapshot["tasks"]]
    await message.answer("\n".join(lines) or "Нет задач", reply_markup=focus_session_keyboard())


@router.message(Command("next"))
async def next_task(message: Message) -> None:
    task = await api_client.api_get("/task/next", message.from_user.id)
    if task:
        await message.answer(
            f"Следующая задача: {task['title']} ({task['planned_duration']} мин)",
            reply_markup=focus_session_keyboard(),
        )
    else:
        await message.answer("Все задачи закрыты. Отдохни")


@router.message(Command("done"))
async def done(message: Message) -> None:
    task = await api_client.api_get("/task/next", message.from_user.id)
    if not task:
        await message.answer("Нет активной задачи")
        return
    await api_client.api_post(f"/task/{task['id']}/transition", message.from_user.id, json={"status": "done"})
    await message.answer("Отметил как выполненную")


@router.message(Command("skip"))
async def skip(message: Message) -> None:
    task = await api_client.api_get("/task/next", message.from_user.id)
    if not task:
        await message.answer("Нет активной задачи")
        return
    await api_client.api_post(
        f"/task/{task['id']}/transition",
        message.from_user.id,
        json={"status": "skip", "reason": "user_skip"},
    )
    await message.answer("Скипнул. Двигаемся дальше")


@router.message(Command("focus"))
async def focus(message: Message) -> None:
    task = await api_client.api_get("/task/next", message.from_user.id)
    if not task:
        await message.answer("Нет задач для фокуса")
        return
    minutes = 25
    await api_client.api_post(
        f"/task/{task['id']}/focus",
        message.from_user.id,
        json={"minutes": minutes},
    )
    await message.answer(f"Стартую фокус на {minutes} минут. Таймер держи сам.")
