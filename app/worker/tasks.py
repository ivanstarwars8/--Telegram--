"""Celery tasks for notifications and analytics."""
from __future__ import annotations

import asyncio
import datetime as dt

import structlog
from celery import shared_task
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.plan import DailyMetrics
from app.models.user import User

logger = structlog.get_logger(__name__)


@shared_task
def ping_plan_selection(user_id: int) -> None:
    logger.info("tasks.ping_plan_selection", user_id=user_id)


@shared_task
def send_evening_digest(user_id: int) -> None:
    logger.info("tasks.send_evening_digest", user_id=user_id)


@shared_task
def recompute_metrics() -> None:
    async def _run() -> None:
        async with AsyncSessionLocal() as session:
            users = (await session.scalars(select(User.id))).all()
            today = dt.date.today()
            for user_id in users:
                metrics = await session.scalar(
                    select(DailyMetrics).where(DailyMetrics.user_id == user_id, DailyMetrics.date == today)
                )
                if not metrics:
                    metrics = DailyMetrics(user_id=user_id, date=today)
                    session.add(metrics)
            await session.commit()

    asyncio.run(_run())
