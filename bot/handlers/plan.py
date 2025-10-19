"""Plan selection handlers."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, Text
from aiogram.types import CallbackQuery, Message

from bot.keyboards.common import (
    focus_session_keyboard,
    plan_choice_keyboard,
    plan_switch_policy_keyboard,
    plan_switch_reason_keyboard,
    plan_switch_target_keyboard,
)
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


@router.callback_query(Text(startswith="plan:"))
async def plan_callback(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")
    action = parts[1]

    if action in {"A", "B", "C"}:
        await api_client.api_post(
            "/day/select_plan",
            tg_id=callback.from_user.id,
            json={"level": action},
        )
        next_task = await api_client.api_get("/task/next", callback.from_user.id)
        if next_task:
            text = (
                f"План {action} активирован. Первая задача: {next_task['title']}"
                f" ({next_task['planned_duration']} мин)."
            )
        else:
            text = "План выбран. Свободных задач нет — настрой шаблон в /templates."
        await callback.message.answer(text, reply_markup=focus_session_keyboard())
    elif action == "custom":
        await callback.message.answer(
            "Загляни в /templates, чтобы собрать свой пресет и выбрать его утром."
        )
    elif action == "switch":
        await callback.message.answer(
            "На какой план переходим?",
            reply_markup=plan_switch_target_keyboard(),
        )
    elif action == "switch_to" and len(parts) >= 3:
        level = parts[2]
        await callback.message.edit_text(
            f"Причина свитча на {level}?",
            reply_markup=plan_switch_reason_keyboard(level),
        )
    elif action == "switch_reason" and len(parts) >= 4:
        level = parts[2]
        reason = parts[3]
        await callback.message.edit_text(
            "Выбери политику переноса",
            reply_markup=plan_switch_policy_keyboard(level, reason),
        )
    elif action == "switch_policy" and len(parts) >= 5:
        level = parts[2]
        reason = parts[3]
        policy = parts[4]
        await api_client.api_post(
            "/day/switch_plan",
            tg_id=callback.from_user.id,
            json={"to_level": level, "reason": reason, "policy": policy},
        )
        snapshot = await api_client.api_get("/day/today", callback.from_user.id)
        pending = [t for t in snapshot.get("tasks", []) if t["status"] in {"todo", "doing"}]
        if pending:
            headline = f"Свитч на {level} зафиксирован. Дальше → {pending[0]['title']}"
        else:
            headline = "Свитч оформлен. Остаток дня пустой — можешь подбросить задачи в /templates."
        await callback.message.answer(headline, reply_markup=focus_session_keyboard())
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
