"""Compact API router covering all endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.deps import get_current_user, get_db
from app.domain import (
    ensure_default_templates,
    fetch_stats,
    get_day_snapshot,
    get_next_task,
    list_templates,
    log_focus_session,
    log_sleep,
    register_user,
    select_plan,
    switch_plan,
    transition_task,
    update_settings,
    upsert_template,
)
from app.models.user import User
from app.schemas.plan import (
    DaySnapshot,
    FocusSessionStart,
    PlanSelectionPayload,
    PlanSwitchPayload,
    PlanTemplatePayload,
    TaskTransitionPayload,
)
from app.schemas.sleep import SleepLogPayload
from app.schemas.stats import StatsRange, StatsResponse
from app.schemas.user import SettingsUpdate, UserRegister

router = APIRouter()


@router.post("/user/register", status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegister, session: AsyncSession = Depends(get_db)):
    user = await register_user(session, payload)
    await ensure_default_templates(session, user)
    await session.commit()
    return {"user_id": user.id}


@router.post("/settings/update")
async def settings_update(
    payload: SettingsUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    updated = await update_settings(session, user, payload)
    await session.commit()
    return {"tz": updated.tz, "notify_level": updated.notify_level, "sleep_window": updated.sleep_window}


@router.get("/day/today", response_model=DaySnapshot)
async def today(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    return await get_day_snapshot(session, user)


@router.post("/day/select_plan")
async def select(
    payload: PlanSelectionPayload,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        day = await select_plan(session, user, payload)
        await session.commit()
        return {"day_id": day.id, "active_plan_level": day.active_plan_level}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/day/switch_plan")
async def switch(
    payload: PlanSwitchPayload,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        day = await switch_plan(session, user, payload)
        await session.commit()
        return {"active_plan_level": day.active_plan_level, "switches": day.switched_times}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/task/next")
async def next_task(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    task = await get_next_task(session, user)
    return {"id": task.id, "title": task.title, "planned_duration": task.planned_duration} if task else None


@router.post("/task/{task_id}/transition")
async def transition(
    payload: TaskTransitionPayload,
    task_id: int = Path(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    try:
        task = await transition_task(session, user, task_id, payload)
        await session.commit()
        return {"task_id": task.id, "status": task.status}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/task/{task_id}/focus")
async def focus(
    payload: FocusSessionStart,
    task_id: int = Path(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    session_obj = await log_focus_session(session, user, task_id, payload.minutes)
    await session.commit()
    return {"id": session_obj.id, "minutes": session_obj.minutes}


@router.get("/templates")
async def templates(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    templates = await list_templates(session, user)
    return [
        {
            "id": template.id,
            "name": template.name,
            "level": template.level,
            "tasks": [
                {
                    "id": task.id,
                    "title": task.title,
                    "duration_min": task.duration_min,
                    "type": task.type,
                }
                for task in template.tasks
            ],
        }
        for template in templates
    ]


@router.post("/templates/upsert")
async def templates_upsert(
    payload: PlanTemplatePayload,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    template = await upsert_template(session, user, payload)
    await session.commit()
    return {"id": template.id, "level": template.level}


@router.post("/sleep/log", status_code=status.HTTP_201_CREATED)
async def sleep_log(
    payload: SleepLogPayload,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    entry = await log_sleep(session, user.id, payload)
    await session.commit()
    return {"id": entry.id}


@router.get("/stats/summary", response_model=StatsResponse)
async def stats_summary(
    range_: str = Query("daily", alias="range"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    payload = StatsRange(range=range_)
    return await fetch_stats(session, user.id, payload)
