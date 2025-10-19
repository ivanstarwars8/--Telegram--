"""Sleep tracking service."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan import DailyMetrics
from app.models.sleep import SleepLog
from app.schemas.sleep import SleepLogPayload


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
