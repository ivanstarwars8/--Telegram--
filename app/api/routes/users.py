"""User endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.user import SettingsUpdate, UserRegister, UserResponse
from app.services.plan_service import ensure_default_templates
from app.services.user_service import register_user, update_settings

router = APIRouter(prefix="/user", tags=["user"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegister, session: AsyncSession = Depends(get_db)) -> User:
    user = await register_user(session, payload)
    await ensure_default_templates(session, user)
    await session.commit()
    await session.refresh(user)
    return user


@router.post("/settings", response_model=UserResponse)
async def update_user_settings(
    payload: SettingsUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> User:
    updated = await update_settings(session, user, payload)
    await session.commit()
    await session.refresh(updated)
    return updated
