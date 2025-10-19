"""Day operations."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.plan import DaySnapshot, PlanSelectionPayload, PlanSwitchPayload
from app.services.plan_service import get_day_snapshot, select_plan, switch_plan

router = APIRouter(prefix="/day", tags=["day"])


@router.get("/today", response_model=DaySnapshot)
async def today(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)) -> DaySnapshot:
    return await get_day_snapshot(session, user)


@router.post("/select_plan", response_model=DaySnapshot)
async def select_day_plan(
    payload: PlanSelectionPayload,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> DaySnapshot:
    await select_plan(session, user, payload)
    await session.commit()
    return await get_day_snapshot(session, user)


@router.post("/switch_plan", response_model=DaySnapshot)
async def switch_day_plan(
    payload: PlanSwitchPayload,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> DaySnapshot:
    await switch_plan(session, user, payload)
    await session.commit()
    return await get_day_snapshot(session, user)
