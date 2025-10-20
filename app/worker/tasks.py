"""Celery tasks for notifications and analytics."""
from __future__ import annotations

import asyncio
import datetime as dt
from zoneinfo import ZoneInfo

import structlog
from aiogram import Bot
from aiogram.enums import ParseMode
from celery import shared_task
from sqlalchemy import select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.plan import DailyMetrics, Day, EventAudit
from app.models.user import User
from app.domain import get_day_snapshot
from bot.keyboards import focus_session_keyboard, plan_choice_keyboard

logger = structlog.get_logger(__name__)


async def _send_message(tg_id: int, text: str, reply_markup=None) -> None:
    bot = Bot(token=settings.telegram_bot_token, parse_mode=ParseMode.HTML)
    try:
        await bot.send_message(chat_id=tg_id, text=text, reply_markup=reply_markup)
    finally:
        await bot.session.close()


async def _log_event(session, user_id: int, event_type: str, local_date: dt.date) -> None:
    session.add(EventAudit(user_id=user_id, type=event_type, payload={"date": str(local_date)}))
    await session.flush()


async def _recent_event(session, user_id: int, event_type: str) -> EventAudit | None:
    result = await session.execute(
        select(EventAudit)
        .where(EventAudit.user_id == user_id, EventAudit.type == event_type)
        .order_by(EventAudit.ts.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _should_fire(
    session,
    user_id: int,
    event_type: str,
    local_date: dt.date,
    now_utc: dt.datetime,
    threshold_minutes: int,
) -> bool:
    event = await _recent_event(session, user_id, event_type)
    if not event:
        return True
    if event.payload.get("date") != str(local_date):
        return True
    delta = now_utc - event.ts
    return delta >= dt.timedelta(minutes=threshold_minutes)


async def _notify_plan_selection(user: User, local_date: dt.date, followup: bool = False) -> None:
    text = "Пора выбрать план: A/B/C или свой пресет." if followup else "Утро. Фиксируем курс: выбери план на сегодня."
    await _send_message(user.tg_id, text, reply_markup=plan_choice_keyboard())


async def _notify_midday(user: User, summary: str) -> None:
    await _send_message(user.tg_id, summary, reply_markup=focus_session_keyboard())


async def _notify_evening(user: User, summary: str) -> None:
    await _send_message(user.tg_id, summary, reply_markup=focus_session_keyboard())


@shared_task
def ping_plan_selection(user_id: int) -> None:
    async def _run() -> None:
        async with AsyncSessionLocal() as session:
            user = await session.get(User, user_id)
            if not user:
                return
            await _notify_plan_selection(user, dt.date.today())
            await _log_event(session, user.id, "plan_prompt", dt.date.today())
            await session.commit()

    asyncio.run(_run())


@shared_task
def send_evening_digest(user_id: int) -> None:
    async def _run() -> None:
        async with AsyncSessionLocal() as session:
            user = await session.get(User, user_id)
            if not user:
                return
            snapshot = await get_day_snapshot(session, user)
            done = sum(1 for task in snapshot.tasks if task.status == "done")
            total = len(snapshot.tasks)
            focus_minutes = snapshot.metrics.get("focus_minutes", 0)
            summary = (
                "Итог дня:\n"
                f"• План: {snapshot.active_plan_level or 'не выбран'}\n"
                f"• Done: {done}/{total}\n"
                f"• Фокус: {focus_minutes} мин\n"
                "Оцени день от 1 до 10 и запиши заметку, если нужно."
            )
            await _notify_evening(user, summary)
            await _log_event(session, user.id, "evening_digest", dt.date.today())
            await session.commit()

    asyncio.run(_run())


@shared_task
def recompute_metrics() -> None:
    async def _run() -> None:
        async with AsyncSessionLocal() as session:
            users = (await session.scalars(select(User.id))).all()
            today = dt.date.today()
            for user_id in users:
                metrics = await session.scalar(
                    select(DailyMetrics).where(DailyMetrics.user_id == user_id, DailyMetrics.date == today)
                )
                if not metrics:
                    metrics = DailyMetrics(user_id=user_id, date=today)
                    session.add(metrics)
            await session.commit()

    asyncio.run(_run())


@shared_task
def dispatch_timeboxed_notifications() -> None:
    async def _run() -> None:
        now_utc = dt.datetime.now(dt.timezone.utc)
        async with AsyncSessionLocal() as session:
            users = (await session.scalars(select(User))).all()
            for user in users:
                tz = ZoneInfo(user.tz or settings.timezone_default)
                local_dt = now_utc.astimezone(tz)
                local_date = local_dt.date()
                local_time = local_dt.time()

                day = await session.scalar(
                    select(Day).where(Day.user_id == user.id, Day.date == local_date)
                )
                plan_selected = bool(day and day.active_plan_level)

                if local_time >= dt.time(7, 30) and local_time < dt.time(9, 0) and not plan_selected:
                    if await _should_fire(session, user.id, "plan_prompt", local_date, now_utc, 60):
                        await _notify_plan_selection(user, local_date)
                        await _log_event(session, user.id, "plan_prompt", local_date)

                if (dt.time(10, 0) <= local_time < dt.time(12, 0)) and not plan_selected:
                    if await _should_fire(session, user.id, "plan_followup", local_date, now_utc, 30):
                        await _notify_plan_selection(user, local_date, followup=True)
                        await _log_event(session, user.id, "plan_followup", local_date)

                if plan_selected and dt.time(12, 0) <= local_time < dt.time(12, 15):
                    if await _should_fire(session, user.id, "midday_check", local_date, now_utc, 720):
                        snapshot = await get_day_snapshot(session, user)
                        done = sum(1 for task in snapshot.tasks if task.status == "done")
                        total = len(snapshot.tasks)
                        summary = (
                            "Полдень. Пробей прогресс:\n"
                            f"• Выполнено {done}/{total}\n"
                            f"• Фокус минут: {snapshot.metrics.get('focus_minutes', 0)}\n"
                            "Если отстал — переключи поток или возьми паузу."
                        )
                        await _notify_midday(user, summary)
                        await _log_event(session, user.id, "midday_check", local_date)

                if plan_selected and dt.time(17, 0) <= local_time < dt.time(17, 15):
                    if await _should_fire(session, user.id, "afternoon_check", local_date, now_utc, 720):
                        snapshot = await get_day_snapshot(session, user)
                        remaining = [task for task in snapshot.tasks if task.status in {"todo", "doing"}]
                        summary = (
                            "Финишный рывок:\n"
                            f"Осталось {len(remaining)} задач. Возьми следующую /next и дожми ядро."
                        )
                        await _notify_midday(user, summary)
                        await _log_event(session, user.id, "afternoon_check", local_date)

                if dt.time(21, 30) <= local_time < dt.time(22, 0):
                    if await _should_fire(session, user.id, "evening_digest", local_date, now_utc, 720):
                        snapshot = await get_day_snapshot(session, user)
                        done = sum(1 for task in snapshot.tasks if task.status == "done")
                        total = len(snapshot.tasks)
                        quality = snapshot.metrics.get("quality_score")
                        summary = (
                            "Подведём итог:\n"
                            f"• План: {snapshot.active_plan_level or 'не выбран'}\n"
                            f"• Done: {done}/{total}\n"
                            f"• Фокус: {snapshot.metrics.get('focus_minutes', 0)} мин\n"
                            + (f"• Оценка: {quality}\n" if quality else "")
                            + "Поставь оценку (1-10) и наметь курс на завтра."
                        )
                        await _notify_evening(user, summary)
                        await _log_event(session, user.id, "evening_digest", local_date)

            await session.commit()

    asyncio.run(_run())
