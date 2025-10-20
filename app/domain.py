"""Compact domain functions for plans, tasks, stats and settings."""
from __future__ import annotations

import datetime as dt
import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DailyMetrics, Day, DayTask, FocusSession, PlanTemplate, SleepLog, TemplateTask, User
from app.schemas.plan import (
    DaySnapshot,
    DayTaskResponse,
    PlanSelectionPayload,
    PlanSwitchPayload,
    PlanTemplatePayload,
    TaskTransitionPayload,
)
from app.schemas.sleep import SleepLogPayload
from app.schemas.stats import StatsRange, StatsResponse
from app.schemas.user import SettingsUpdate, UserRegister
from app.utils.math import safe_div

logger = structlog.get_logger(__name__)


# --- User helpers -----------------------------------------------------------------


async def register_user(session: AsyncSession, payload: UserRegister) -> User:
    user = await session.scalar(select(User).where(User.tg_id == payload.tg_id))
    if user:
        logger.info("user.register.exists", user_id=user.id)
        return user

    user = User(tg_id=payload.tg_id, tz=payload.tz, locale=payload.locale)
    session.add(user)
    await session.flush()
    logger.info("user.register.created", user_id=user.id)
    return user


async def update_settings(session: AsyncSession, user: User, payload: SettingsUpdate) -> User:
    if payload.tz:
        user.tz = payload.tz
    if payload.notify_level:
        user.notify_level = payload.notify_level
    if payload.sleep_window is not None:
        user.sleep_window = payload.sleep_window
    await session.flush()
    logger.info("user.settings.updated", user_id=user.id)
    return user


# --- Templates --------------------------------------------------------------------


async def ensure_default_templates(session: AsyncSession, user: User) -> None:
    existing = await session.scalars(select(PlanTemplate).where(PlanTemplate.user_id == user.id))
    if existing.first():
        return
    defaults = [("План A — максимум", "A"), ("План B — стандарт", "B"), ("План C — минимум", "C")]
    for name, level in defaults:
        template = PlanTemplate(user_id=user.id, name=name, level=level, rules={"switch_policy_default": "carry_all"})
        session.add(template)
        await session.flush()
        template.tasks = [
            TemplateTask(
                template_id=template.id,
                title=f"Фокус-блок {i + 1}",
                type="focus",
                priority=10 - i,
                duration_min=50,
                stream="F",
            )
            for i in range({"A": 3, "B": 2, "C": 1}[level])
        ]
    logger.info("plan.templates.default_created", user_id=user.id)


async def upsert_template(session: AsyncSession, user: User, payload: PlanTemplatePayload) -> PlanTemplate:
    if payload.level == "custom":
        template = await session.scalar(
            select(PlanTemplate).where(PlanTemplate.user_id == user.id, PlanTemplate.name == payload.name)
        )
    else:
        template = await session.scalar(
            select(PlanTemplate).where(PlanTemplate.user_id == user.id, PlanTemplate.level == payload.level)
        )

    if not template:
        template = PlanTemplate(user_id=user.id, name=payload.name, level=payload.level)
        session.add(template)
        await session.flush()

    template.rules = payload.rules
    await session.execute(delete(TemplateTask).where(TemplateTask.template_id == template.id))
    await session.flush()
    for task in payload.tasks:
        session.add(
            TemplateTask(
                template_id=template.id,
                title=task.title,
                type=task.type,
                priority=task.priority,
                duration_min=task.duration_min,
                stream=task.stream,
                tags=task.tags,
                active=1,
            )
        )
    logger.info("plan.template.upserted", template_id=template.id, user_id=user.id)
    return template


async def list_templates(session: AsyncSession, user: User) -> list[PlanTemplate]:
    result = await session.scalars(select(PlanTemplate).where(PlanTemplate.user_id == user.id))
    return result.all()


# --- Daily plan management --------------------------------------------------------


async def select_plan(session: AsyncSession, user: User, payload: PlanSelectionPayload) -> Day:
    today = dt.date.today()
    day = await session.scalar(select(Day).where(Day.user_id == user.id, Day.date == today))
    if not day:
        day = Day(user_id=user.id, date=today)
        session.add(day)
        await session.flush()

    template = await _resolve_template(session, user, payload)
    day.selected_template_id = template.id
    day.active_plan_level = template.level
    day.switched_times = []

    await _reset_day_tasks(session, day, template)
    logger.info("plan.day.selected", user_id=user.id, day_id=day.id, template_id=template.id)
    return day


async def switch_plan(session: AsyncSession, user: User, payload: PlanSwitchPayload) -> Day:
    today = dt.date.today()
    day = await session.scalar(select(Day).where(Day.user_id == user.id, Day.date == today))
    if not day or not day.selected_template_id:
        raise ValueError("Plan not selected")

    new_template = await _resolve_template(
        session,
        user,
        PlanSelectionPayload(level=payload.to_level, custom_id=payload.custom_id),
    )
    switches = day.switched_times or []
    switches.append(
        {
            "to": payload.to_level,
            "at": dt.datetime.utcnow().isoformat(),
            "reason": payload.reason,
            "policy": payload.policy,
        }
    )
    day.switched_times = switches
    day.active_plan_level = new_template.level

    await _apply_policy(session, day, new_template, payload.policy)
    logger.info("plan.day.switched", user_id=user.id, day_id=day.id, to_level=new_template.level)
    return day


async def get_day_snapshot(session: AsyncSession, user: User) -> DaySnapshot:
    today = dt.date.today()
    day = await session.scalar(select(Day).where(Day.user_id == user.id, Day.date == today))
    if not day:
        return DaySnapshot(date=today, active_plan_level=None, tasks=[], switches=[], metrics={})

    tasks_result = await session.scalars(select(DayTask).where(DayTask.day_id == day.id).order_by(DayTask.order_index))
    task_items = [
        DayTaskResponse(
            id=item.id,
            title=item.title,
            planned_duration=item.planned_duration,
            status=item.status,
            order_index=item.order_index,
            skip_reason=item.skip_reason,
        )
        for item in tasks_result.all()
    ]
    metrics = await session.scalar(select(DailyMetrics).where(DailyMetrics.user_id == user.id, DailyMetrics.date == today))
    metrics_payload = {
        "focus_minutes": metrics.focus_minutes if metrics else 0,
        "done": metrics.done_count if metrics else 0,
        "skip": metrics.skip_count if metrics else 0,
        "quality_score": metrics.quality_score if metrics else None,
    }
    return DaySnapshot(
        date=today,
        active_plan_level=day.active_plan_level,
        tasks=task_items,
        switches=day.switched_times or [],
        metrics=metrics_payload,
    )


# --- Task execution ---------------------------------------------------------------


async def get_next_task(session: AsyncSession, user: User) -> DayTask | None:
    today = dt.date.today()
    day = await session.scalar(select(Day).where(Day.user_id == user.id, Day.date == today))
    if not day:
        return None
    return await session.scalar(
        select(DayTask)
        .where(DayTask.day_id == day.id, DayTask.status.in_(["todo", "doing"]))
        .order_by(DayTask.order_index)
    )


async def transition_task(session: AsyncSession, user: User, task_id: int, payload: TaskTransitionPayload) -> DayTask:
    task = await session.get(DayTask, task_id)
    if not task:
        raise ValueError("Task not found")
    if payload.status == "start":
        task.status = "doing"
        task.started_at = dt.datetime.utcnow()
    elif payload.status == "done":
        task.status = "done"
        task.completed_at = dt.datetime.utcnow()
        await _update_metrics(session, task.day_id, done_delta=1)
    elif payload.status == "skip":
        task.status = "skip"
        task.skip_reason = payload.reason
        await _update_metrics(session, task.day_id, skip_delta=1)
    else:
        raise ValueError("Unsupported transition")
    await session.flush()
    logger.info("plan.task.transition", task_id=task.id, status=task.status)
    return task


async def log_focus_session(session: AsyncSession, user: User, task_id: int, minutes: int) -> FocusSession:
    task = await session.get(DayTask, task_id)
    if not task:
        raise ValueError("Task not found")
    session_obj = FocusSession(user_id=user.id, day_id=task.day_id, task_id=task_id, minutes=minutes)
    session.add(session_obj)
    await _update_metrics(session, task.day_id, focus_delta=minutes)
    await session.flush()
    logger.info("plan.focus.logged", task_id=task_id, minutes=minutes)
    return session_obj


# --- Sleep & stats ----------------------------------------------------------------


async def log_sleep(session: AsyncSession, user_id: int, payload: SleepLogPayload) -> SleepLog:
    entry = SleepLog(user_id=user_id, start_at=payload.start_at, end_at=payload.end_at)
    session.add(entry)

    hours = int((payload.end_at - payload.start_at).total_seconds() // 3600)
    metrics = await session.scalar(select(DailyMetrics).where(DailyMetrics.user_id == user_id, DailyMetrics.date == payload.end_at.date()))
    if not metrics:
        metrics = DailyMetrics(user_id=user_id, date=payload.end_at.date())
        session.add(metrics)
    metrics.sleep_hours = hours
    await session.flush()
    return entry


async def fetch_stats(session: AsyncSession, user_id: int, payload: StatsRange) -> StatsResponse:
    today = dt.date.today()
    if payload.range == "daily":
        start = today
    elif payload.range == "weekly":
        start = today - dt.timedelta(days=6)
    else:
        start = today - dt.timedelta(days=29)

    metrics_stmt = (
        select(DailyMetrics)
        .where(DailyMetrics.user_id == user_id, DailyMetrics.date >= start, DailyMetrics.date <= today)
        .order_by(DailyMetrics.date)
    )
    metrics_rows = (await session.scalars(metrics_stmt)).all()

    summaries = [
        {
            "date": row.date,
            "active_plan_level": await _active_plan(session, user_id, row.date),
            "done_percent": safe_div(row.done_count, row.done_count + row.skip_count),
            "focus_minutes": row.focus_minutes,
            "switches": row.switches,
        }
        for row in metrics_rows
    ]

    streak = await _streak(session, user_id, today)
    reliability = float(
        safe_div(sum(row.done_count for row in metrics_rows), sum(row.done_count + row.skip_count for row in metrics_rows))
    )
    stability = float(
        safe_div(
            sum(1 for row in metrics_rows if row.switches == 0),
            len(metrics_rows) if metrics_rows else 1,
        )
    )
    focus_avg = float(safe_div(sum(row.focus_minutes for row in metrics_rows), len(metrics_rows) or 1))

    return StatsResponse(
        summaries=summaries,
        streak=streak,
        reliability=reliability,
        stability=stability,
        focus_avg=focus_avg,
    )


# --- Internals --------------------------------------------------------------------


async def _resolve_template(session: AsyncSession, user: User, payload: PlanSelectionPayload) -> PlanTemplate:
    if payload.level == "custom" and payload.custom_id:
        template = await session.get(PlanTemplate, payload.custom_id)
    else:
        template = await session.scalar(
            select(PlanTemplate).where(PlanTemplate.user_id == user.id, PlanTemplate.level == payload.level)
        )
    if not template:
        raise ValueError("Template not found")
    return template


async def _reset_day_tasks(session: AsyncSession, day: Day, template: PlanTemplate) -> None:
    await session.execute(delete(DayTask).where(DayTask.day_id == day.id))
    await session.flush()
    tasks = await _load_template_tasks(session, template)
    for order, item in enumerate(tasks):
        session.add(
            DayTask(
                day_id=day.id,
                template_task_id=item.id,
                title=item.title,
                planned_duration=item.duration_min,
                status="todo",
                order_index=order,
                stream=item.stream,
            )
        )
    await _update_metrics(session, day.id, reset=True)


async def _apply_policy(session: AsyncSession, day: Day, template: PlanTemplate, policy: str) -> None:
    await session.execute(delete(DayTask).where(DayTask.day_id == day.id))
    await session.flush()
    tasks = await _load_template_tasks(session, template)
    order = 0
    for template_task in tasks:
        if policy == "cancel_routine" and template_task.type == "routine":
            continue
        duration = template_task.duration_min
        if policy == "compress_50":
            duration = max(5, duration // 2)
        session.add(
            DayTask(
                day_id=day.id,
                template_task_id=template_task.id,
                title=template_task.title,
                planned_duration=duration,
                status="todo",
                order_index=order,
                stream=template_task.stream,
            )
        )
        order += 1
    await _update_metrics(session, day.id, reset=True)


async def _update_metrics(
    session: AsyncSession,
    day_id: int,
    *,
    reset: bool = False,
    done_delta: int = 0,
    skip_delta: int = 0,
    focus_delta: int = 0,
) -> None:
    day = await session.get(Day, day_id)
    if not day:
        return
    metrics = await session.scalar(select(DailyMetrics).where(DailyMetrics.user_id == day.user_id, DailyMetrics.date == day.date))
    if not metrics:
        metrics = DailyMetrics(user_id=day.user_id, date=day.date)
        session.add(metrics)
    if reset:
        metrics.done_count = 0
        metrics.skip_count = 0
        metrics.focus_minutes = 0
    metrics.done_count += done_delta
    metrics.skip_count += skip_delta
    metrics.focus_minutes += focus_delta
    if done_delta or skip_delta or focus_delta or reset:
        await session.flush()


async def _active_plan(session: AsyncSession, user_id: int, day: dt.date) -> str | None:
    return await session.scalar(select(Day.active_plan_level).where(Day.user_id == user_id, Day.date == day))


async def _streak(session: AsyncSession, user_id: int, today: dt.date) -> int:
    streak = 0
    pointer = today
    while True:
        day = await session.scalar(select(Day).where(Day.user_id == user_id, Day.date == pointer))
        if not day or not day.selected_template_id:
            break
        streak += 1
        pointer -= dt.timedelta(days=1)
    return streak


async def _load_template_tasks(session: AsyncSession, template: PlanTemplate) -> list[TemplateTask]:
    result = await session.scalars(
        select(TemplateTask).where(TemplateTask.template_id == template.id).order_by(TemplateTask.id)
    )
    return result.all()
