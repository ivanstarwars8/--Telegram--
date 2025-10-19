"""Service layer for user operations."""
from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import SettingsUpdate, UserRegister

logger = structlog.get_logger(__name__)


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
