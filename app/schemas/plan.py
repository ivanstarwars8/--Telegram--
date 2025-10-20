"""Plan related schemas."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from .base import ORMModel


class TemplateTaskPayload(BaseModel):
    title: str
    type: Literal["focus", "routine", "quick"]
    priority: int = 5
    duration_min: int = 0
    stream: Optional[str] = None
    tags: Optional[list[str]] = None


class PlanTemplatePayload(BaseModel):
    name: str
    level: Literal["A", "B", "C", "custom"]
    rules: dict = Field(default_factory=dict)
    tasks: list[TemplateTaskPayload]


class PlanSelectionPayload(BaseModel):
    level: Literal["A", "B", "C", "custom"]
    custom_id: Optional[int] = None


class PlanSwitchPayload(BaseModel):
    to_level: Literal["A", "B", "C", "custom"]
    reason: Literal["force_majeure", "energy", "external", "other"]
    policy: Literal["carry_all", "compress_50", "cancel_routine"]
    custom_id: Optional[int] = None


class DayTaskResponse(ORMModel):
    id: int
    title: str
    planned_duration: int
    status: str
    order_index: int
    skip_reason: Optional[str]


class DaySnapshot(ORMModel):
    date: date
    active_plan_level: Optional[str]
    tasks: list[DayTaskResponse]
    switches: list[dict]
    metrics: dict


class FocusSessionStart(BaseModel):
    minutes: int = Field(..., ge=5, le=180)


class TaskTransitionPayload(BaseModel):
    status: Literal["start", "done", "skip"]
    reason: Optional[str] = None
