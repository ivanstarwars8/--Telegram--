"""Statistics endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.stats import StatsRange, StatsResponse
from app.services.stats_service import fetch_stats

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/summary", response_model=StatsResponse)
async def summary(
    query: StatsRange = Depends(),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> StatsResponse:
    return await fetch_stats(session, user.id, query)
