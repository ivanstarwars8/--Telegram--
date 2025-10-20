"""Base schemas with Pydantic config."""
from __future__ import annotations

from datetime import datetime, date
from typing import Optional

from pydantic import BaseModel


class ORMModel(BaseModel):
    class Config:
        orm_mode = True


class DaySummary(ORMModel):
    date: date
    active_plan_level: Optional[str]
    done_percent: float
    focus_minutes: int
    switches: int
