"""Business logic for plan selection and switching."""
from __future__ import annotations

import datetime as dt

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan import DailyMetrics, Day, DayTask, FocusSession, PlanTemplate, TemplateTask
from app.models.user import User
from app.schemas.plan import (
    DaySnapshot,
    DayTaskResponse,
    PlanSelectionPayload,
    PlanSwitchPayload,
    PlanTemplatePayload,
    TaskTransitionPayload,
)

logger = structlog.get_logger(__name__)


async def ensure_default_templates(session: AsyncSession, user: User) -> None:
    existing = await session.scalars(select(PlanTemplate).where(PlanTemplate.user_id == user.id))
    if existing.first():
        return
    defaults = [
        ("План A — максимум", "A"),
        ("План B — стандарт", "B"),
        ("План C — минимум", "C"),
    ]
    for name, level in defaults:
        template = PlanTemplate(user_id=user.id, name=name, level=level, rules={"switch_policy_default": "carry_all"})
        session.add(template)
        await session.flush()
        template.tasks = [
            TemplateTask(
                template_id=template.id,
                title=f"Фокус-блок {i+1}",
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
    elif payload.status == "skip":
        task.status = "skip"
        task.skip_reason = payload.reason
    await session.flush()
    logger.info("task.transition", task_id=task.id, status=task.status)
    return task


async def log_focus_session(session: AsyncSession, user: User, task_id: int | None, minutes: int) -> FocusSession:
    today = dt.date.today()
    day = await session.scalar(select(Day).where(Day.user_id == user.id, Day.date == today))
    if not day:
        raise ValueError("Day not initialised")
    focus = FocusSession(user_id=user.id, day_id=day.id, task_id=task_id, minutes=minutes)
    session.add(focus)
    metrics = await session.scalar(select(DailyMetrics).where(DailyMetrics.user_id == user.id, DailyMetrics.date == today))
    if not metrics:
        metrics = DailyMetrics(user_id=user.id, date=today)
        session.add(metrics)
    metrics.focus_minutes += minutes
    await session.flush()
    logger.info("focus.session.logged", user_id=user.id, minutes=minutes)
    return focus


async def _resolve_template(session: AsyncSession, user: User, payload: PlanSelectionPayload) -> PlanTemplate:
    if payload.level == "custom":
        if not payload.custom_id:
            raise ValueError("custom_id required")
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
    template_tasks = (await session.scalars(select(TemplateTask).where(TemplateTask.template_id == template.id))).all()
    for index, template_task in enumerate(template_tasks):
        session.add(
            DayTask(
                day_id=day.id,
                template_task_id=template_task.id,
                title=template_task.title,
                planned_duration=template_task.duration_min,
                order_index=index,
            )
        )
    await session.flush()


async def _apply_policy(session: AsyncSession, day: Day, template: PlanTemplate, policy: str) -> None:
    await _reset_day_tasks(session, day, template)
    tasks = (await session.scalars(select(DayTask).where(DayTask.day_id == day.id))).all()
    for task in tasks:
        if policy == "compress_50":
            task.planned_duration = max(5, task.planned_duration // 2)
        elif policy == "cancel_routine" and "рутина" in task.title.lower():
            await session.delete(task)
    await session.flush()
