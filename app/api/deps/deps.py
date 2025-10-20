"""FastAPI dependencies."""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.user import User


async def get_db() -> AsyncSession:
    async with get_session() as session:
        yield session


async def get_current_user(
    session: AsyncSession = Depends(get_db),
    x_telegram_id: int = Header(..., alias="X-Telegram-Id"),
) -> User:
    user = await session.scalar(select(User).where(User.tg_id == x_telegram_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    return user
