"""Statistics aggregation service."""
from __future__ import annotations

import datetime as dt
from typing import Iterable

try:  # pragma: no cover - optional during unit tests without deps
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.models.plan import DailyMetrics, Day
except ModuleNotFoundError:  # pragma: no cover
    func = select = None  # type: ignore
    AsyncSession = object  # type: ignore
    DailyMetrics = Day = object  # type: ignore

from app.schemas.base import DaySummary
from app.schemas.stats import StatsRange, StatsResponse
from app.utils.math import safe_div


async def fetch_stats(session: AsyncSession, user_id: int, payload: StatsRange) -> StatsResponse:
    if select is None or func is None:  # pragma: no cover
        raise RuntimeError("SQLAlchemy is required for fetch_stats")

    today = dt.date.today()
    if payload.range == "daily":
        start = today
    elif payload.range == "weekly":
        start = today - dt.timedelta(days=6)
    else:
        start = today - dt.timedelta(days=29)

    metrics_stmt = (
        select(DailyMetrics)
        .where(DailyMetrics.user_id == user_id, DailyMetrics.date >= start, DailyMetrics.date <= today)
        .order_by(DailyMetrics.date)
    )
    metrics_rows = (await session.scalars(metrics_stmt)).all()

    summaries = [
        DaySummary(
            date=row.date,
            active_plan_level=await _active_plan(session, user_id, row.date),
            done_percent=safe_div(row.done_count, row.done_count + row.skip_count),
            focus_minutes=row.focus_minutes,
            switches=row.switches,
        )
        for row in metrics_rows
    ]

    streak = await _streak(session, user_id, today)
    reliability = float(
        safe_div(sum(row.done_count for row in metrics_rows), sum(row.done_count + row.skip_count for row in metrics_rows))
    )
    stability = float(
        safe_div(
            sum(1 for row in metrics_rows if row.switches == 0),
            len(metrics_rows) if metrics_rows else 1,
        )
    )
    focus_avg = float(safe_div(sum(row.focus_minutes for row in metrics_rows), len(metrics_rows) or 1))

    return StatsResponse(
        summaries=summaries,
        streak=streak,
        reliability=reliability,
        stability=stability,
        focus_avg=focus_avg,
    )


async def _active_plan(session: AsyncSession, user_id: int, day: dt.date) -> str | None:
    if select is None:  # pragma: no cover
        raise RuntimeError("SQLAlchemy is required for _active_plan")
    row = await session.scalar(select(Day.active_plan_level).where(Day.user_id == user_id, Day.date == day))
    return row


async def _streak(session: AsyncSession, user_id: int, today: dt.date) -> int:
    if select is None:  # pragma: no cover
        raise RuntimeError("SQLAlchemy is required for _streak")
    streak = 0
    pointer = today
    while True:
        day = await session.scalar(select(Day).where(Day.user_id == user_id, Day.date == pointer))
        if not day or not day.selected_template_id:
            break
        streak += 1
        pointer -= dt.timedelta(days=1)
    return streak
