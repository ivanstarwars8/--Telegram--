"""All bot handlers in a single module."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, Text
from aiogram.types import CallbackQuery, Message

from app.core.config import settings
from bot.keyboards import (
    focus_session_keyboard,
    plan_choice_keyboard,
    plan_switch_policy_keyboard,
    plan_switch_reason_keyboard,
    plan_switch_target_keyboard,
)
from bot.services import api_client
from bot.services.api_client import BackendError
from bot.services.errors import notify_backend_error

router = Router()


# --- helpers ---------------------------------------------------------------------


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
    return (f"Следующая: {task['title']} ({task['planned_duration']} мин).", task)


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


# --- start & plan flows ----------------------------------------------------------


@router.message(Command("start"))
async def start(message: Message) -> None:
    try:
        await api_client.api_post(
            "/user/register",
            tg_id=message.from_user.id,
            json={"tg_id": message.from_user.id, "tz": settings.timezone_default, "locale": "ru"},
        )
    except BackendError as exc:
        await notify_backend_error(message, exc)
        return
    await message.answer("Выбери план на сегодня", reply_markup=plan_choice_keyboard())


@router.message(Command("plan"))
async def show_plan(message: Message) -> None:
    try:
        snapshot = await api_client.api_get("/day/today", message.from_user.id)
    except BackendError as exc:
        await notify_backend_error(message, exc)
        return
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
    try:
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
            await callback.message.answer("Загляни в /templates, чтобы собрать свой пресет и выбрать его утром.")
        elif action == "switch":
            await callback.message.answer("На какой план переходим?", reply_markup=plan_switch_target_keyboard())
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
    except BackendError as exc:
        await notify_backend_error(callback, exc)
        return
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
    try:
        await api_client.api_post(
            "/day/switch_plan",
            tg_id=message.from_user.id,
            json={"to_level": level, "reason": reason, "policy": policy},
        )
    except BackendError as exc:
        await notify_backend_error(message, exc)
        return
    await message.answer("План переключен", reply_markup=focus_session_keyboard())


# --- task flows ------------------------------------------------------------------


@router.message(Command("today"))
async def today(message: Message) -> None:
    try:
        text = await _fetch_today(message.from_user.id)
    except BackendError as exc:
        await notify_backend_error(message, exc)
        return
    await message.answer(text, reply_markup=focus_session_keyboard())


@router.message(Command("next"))
async def next_task(message: Message) -> None:
    try:
        text, _ = await _fetch_next_task_text(message.from_user.id)
    except BackendError as exc:
        await notify_backend_error(message, exc)
        return
    await message.answer(text, reply_markup=focus_session_keyboard())


@router.message(Command("done"))
async def done(message: Message) -> None:
    try:
        text = await _transition_next_task(message.from_user.id, "done")
    except BackendError as exc:
        await notify_backend_error(message, exc)
        return
    await message.answer(text, reply_markup=focus_session_keyboard())


@router.message(Command("skip"))
async def skip(message: Message) -> None:
    try:
        text = await _transition_next_task(message.from_user.id, "skip", reason="user_skip")
    except BackendError as exc:
        await notify_backend_error(message, exc)
        return
    await message.answer(text, reply_markup=focus_session_keyboard())


@router.message(Command("focus"))
async def focus(message: Message) -> None:
    try:
        text, task = await _fetch_next_task_text(message.from_user.id)
    except BackendError as exc:
        await notify_backend_error(message, exc)
        return
    if not task:
        await message.answer(text)
        return
    minutes = 25
    try:
        await api_client.api_post(
            f"/task/{task['id']}/focus",
            message.from_user.id,
            json={"minutes": minutes},
        )
    except BackendError as exc:
        await notify_backend_error(message, exc)
        return
    await message.answer(f"Запустил фокус на {minutes} минут. {text}")


@router.callback_query(Text("task:list"))
async def task_list_callback(callback: CallbackQuery) -> None:
    try:
        text = await _fetch_today(callback.from_user.id)
    except BackendError as exc:
        await notify_backend_error(callback, exc)
        return
    await callback.message.answer(text, reply_markup=focus_session_keyboard())
    await callback.answer()


@router.callback_query(Text("task:next"))
async def task_next_callback(callback: CallbackQuery) -> None:
    try:
        text, _ = await _fetch_next_task_text(callback.from_user.id)
    except BackendError as exc:
        await notify_backend_error(callback, exc)
        return
    await callback.message.answer(text, reply_markup=focus_session_keyboard())
    await callback.answer()


@router.callback_query(Text("task:done"))
async def task_done_callback(callback: CallbackQuery) -> None:
    try:
        text = await _transition_next_task(callback.from_user.id, "done")
    except BackendError as exc:
        await notify_backend_error(callback, exc)
        return
    await callback.message.answer(text, reply_markup=focus_session_keyboard())
    await callback.answer("Зачёл задачу")


@router.callback_query(Text("task:skip"))
async def task_skip_callback(callback: CallbackQuery) -> None:
    try:
        text = await _transition_next_task(callback.from_user.id, "skip", reason="user_skip")
    except BackendError as exc:
        await notify_backend_error(callback, exc)
        return
    await callback.message.answer(text, reply_markup=focus_session_keyboard())
    await callback.answer("Скипнул")


@router.callback_query(Text(startswith="focus:"))
async def focus_callback(callback: CallbackQuery) -> None:
    minutes = int(callback.data.split(":")[1])
    try:
        text, task = await _fetch_next_task_text(callback.from_user.id)
    except BackendError as exc:
        await notify_backend_error(callback, exc)
        return
    if not task:
        await callback.answer("Нет активной задачи", show_alert=True)
        return
    try:
        await api_client.api_post(
            f"/task/{task['id']}/focus",
            callback.from_user.id,
            json={"minutes": minutes},
        )
    except BackendError as exc:
        await notify_backend_error(callback, exc)
        return
    await callback.message.answer(f"Фокус на {minutes} минут. {text}")
    await callback.answer()


# --- stats & misc -----------------------------------------------------------------


@router.message(Command("stats"))
async def stats(message: Message) -> None:
    try:
        data = await api_client.api_get("/stats/summary", message.from_user.id, params={"range": "weekly"})
    except BackendError as exc:
        await notify_backend_error(message, exc)
        return
    streak = data["streak"]
    reliability = data["reliability"]
    stability = data["stability"]
    focus_value = data["focus_avg"]
    await message.answer(
        "Серия утренних выборов: {streak}\nНадёжность: {reliability}\n"
        "Стабильность: {stability}\nФокус в среднем: {focus} мин".format(
            streak=streak, reliability=reliability, stability=stability, focus=focus_value
        )
    )


@router.message(Command("templates"))
async def templates(message: Message) -> None:
    try:
        templates = await api_client.api_get("/templates", message.from_user.id)
    except BackendError as exc:
        await notify_backend_error(message, exc)
        return
    text = "\n".join(f"{t['level']}: {t['name']}" for t in templates)
    await message.answer(text or "Шаблонов нет. Добавь через /settings")


@router.message(Command("settings"))
async def settings_cmd(message: Message) -> None:
    await message.answer("Настройки скоро будут доступны из меню. Пока держи курс.")


@router.message(Command("sleep"))
async def sleep_cmd(message: Message) -> None:
    await message.answer("Фиксация сна доступна через /sleep_start HH:MM и /sleep_end HH:MM (TODO)")


@router.message(Command("help"))
async def help_cmd(message: Message) -> None:
    await message.answer(
        "/plan — активный план\n/today — список задач\n/next — следующая задача\n/done — выполнить\n/skip — пропустить\n/stats — аналитика"
    )
