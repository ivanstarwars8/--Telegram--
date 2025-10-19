"""Task flow handlers with inline UX."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, Text
from aiogram.types import CallbackQuery, Message

from bot.keyboards.common import focus_session_keyboard
from bot.services import api_client

router = Router()


async def _fetch_today(tg_id: int) -> str:
    snapshot = await api_client.api_get("/day/today", tg_id)
    if not snapshot["tasks"]:
        return "На сегодня задач нет."
    lines = [
        f"{task['order_index'] + 1}. {task['title']} — {task['status']}"
        + (f" ({task['skip_reason']})" if task.get("skip_reason") else "")
        for task in snapshot["tasks"]
    ]
    return "\n".join(lines)


async def _fetch_next_task_text(tg_id: int) -> tuple[str, dict | None]:
    task = await api_client.api_get("/task/next", tg_id)
    if not task:
        return "Все задачи закрыты. Переберись в /templates и добавь ядро на завтра.", None
    return (
        f"Следующая: {task['title']} ({task['planned_duration']} мин).",
        task,
    )


@router.message(Command("today"))
async def today(message: Message) -> None:
    text = await _fetch_today(message.from_user.id)
    await message.answer(text, reply_markup=focus_session_keyboard())


@router.message(Command("next"))
async def next_task(message: Message) -> None:
    text, _ = await _fetch_next_task_text(message.from_user.id)
    await message.answer(text, reply_markup=focus_session_keyboard())


async def _transition_next_task(tg_id: int, status: str, reason: str | None = None) -> str:
    task = await api_client.api_get("/task/next", tg_id)
    if not task:
        return "Нет активной задачи."
    payload: dict[str, str] = {"status": status}
    if reason:
        payload["reason"] = reason
    await api_client.api_post(f"/task/{task['id']}/transition", tg_id, json=payload)
    text, _ = await _fetch_next_task_text(tg_id)
    return f"Готово. {text}"


@router.message(Command("done"))
async def done(message: Message) -> None:
    text = await _transition_next_task(message.from_user.id, "done")
    await message.answer(text, reply_markup=focus_session_keyboard())


@router.message(Command("skip"))
async def skip(message: Message) -> None:
    text = await _transition_next_task(message.from_user.id, "skip", reason="user_skip")
    await message.answer(text, reply_markup=focus_session_keyboard())


@router.message(Command("focus"))
async def focus(message: Message) -> None:
    text, task = await _fetch_next_task_text(message.from_user.id)
    if not task:
        await message.answer(text)
        return
    minutes = 25
    await api_client.api_post(
        f"/task/{task['id']}/focus",
        message.from_user.id,
        json={"minutes": minutes},
    )
    await message.answer(f"Запустил фокус на {minutes} минут. {text}")


@router.callback_query(Text("task:list"))
async def task_list_callback(callback: CallbackQuery) -> None:
    text = await _fetch_today(callback.from_user.id)
    await callback.message.answer(text, reply_markup=focus_session_keyboard())
    await callback.answer()


@router.callback_query(Text("task:next"))
async def task_next_callback(callback: CallbackQuery) -> None:
    text, _ = await _fetch_next_task_text(callback.from_user.id)
    await callback.message.answer(text, reply_markup=focus_session_keyboard())
    await callback.answer()


@router.callback_query(Text("task:done"))
async def task_done_callback(callback: CallbackQuery) -> None:
    text = await _transition_next_task(callback.from_user.id, "done")
    await callback.message.answer(text, reply_markup=focus_session_keyboard())
    await callback.answer("Зачёл задачу")


@router.callback_query(Text("task:skip"))
async def task_skip_callback(callback: CallbackQuery) -> None:
    text = await _transition_next_task(callback.from_user.id, "skip", reason="user_skip")
    await callback.message.answer(text, reply_markup=focus_session_keyboard())
    await callback.answer("Скипнул")


@router.callback_query(Text(startswith="focus:"))
async def focus_callback(callback: CallbackQuery) -> None:
    minutes = int(callback.data.split(":")[1])
    text, task = await _fetch_next_task_text(callback.from_user.id)
    if not task:
        await callback.answer("Нет активной задачи", show_alert=True)
        return
    await api_client.api_post(
        f"/task/{task['id']}/focus",
        callback.from_user.id,
        json={"minutes": minutes},
    )
    await callback.message.answer(f"Фокус на {minutes} минут. {text}")
    await callback.answer()
