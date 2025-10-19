"""Plan selection handlers."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.keyboards.common import focus_session_keyboard, plan_choice_keyboard
from bot.services import api_client

router = Router()


@router.message(Command("plan"))
async def show_plan(message: Message) -> None:
    snapshot = await api_client.api_get("/day/today", message.from_user.id)
    if snapshot["active_plan_level"]:
        await message.answer(
            f"Активный план: {snapshot['active_plan_level']}\nЗадачи: {len(snapshot['tasks'])}",
            reply_markup=focus_session_keyboard(),
        )
    else:
        await message.answer("План не выбран", reply_markup=plan_choice_keyboard())


@router.callback_query(lambda c: c.data and c.data.startswith("plan:"))
async def plan_callback(callback: CallbackQuery) -> None:
    _, action = callback.data.split(":", 1)
    if action in {"A", "B", "C"}:
        await api_client.api_post(
            "/day/select_plan",
            tg_id=callback.from_user.id,
            json={"level": action},
        )
        await callback.message.answer("План выбран. Стартуем первую задачу?", reply_markup=focus_session_keyboard())
    elif action == "switch":
        await callback.message.answer("Выбери причину переключения: /switch energy|external|force|other")
    else:
        await callback.message.answer("Шаблоны доступны командой /templates")
    await callback.answer()


@router.message(Command("switch"))
async def switch_plan(message: Message) -> None:
    parts = message.text.split()[1:] if message.text else []
    if len(parts) < 2:
        await message.answer("Используй: /switch <A|B|C> <reason> [policy]")
        return
    level = parts[0].upper()
    reason = parts[1]
    policy = parts[2] if len(parts) > 2 else "carry_all"
    await api_client.api_post(
        "/day/switch_plan",
        tg_id=message.from_user.id,
        json={"to_level": level, "reason": reason, "policy": policy},
    )
    await message.answer("План переключен", reply_markup=focus_session_keyboard())
