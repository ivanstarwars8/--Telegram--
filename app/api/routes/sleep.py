"""Sleep endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.sleep import SleepLogPayload
from app.services.sleep_service import log_sleep

router = APIRouter(prefix="/sleep", tags=["sleep"])


@router.post("/log")
async def log(
    payload: SleepLogPayload,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    entry = await log_sleep(session, user.id, payload)
    await session.commit()
    return {"id": entry.id}
