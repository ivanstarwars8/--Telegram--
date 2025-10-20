"""Statistics schemas."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel

from .base import DaySummary


class StatsRange(BaseModel):
    range: Literal["daily", "weekly", "monthly"] = "daily"


class StatsResponse(BaseModel):
    summaries: list[DaySummary]
    streak: int
    reliability: float
    stability: float
    focus_avg: float
