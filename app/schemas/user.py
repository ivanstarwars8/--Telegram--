"""User schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from .base import ORMModel


class UserRegister(BaseModel):
    tg_id: int
    tz: str
    locale: Literal["ru", "en"] = "ru"


class UserResponse(ORMModel):
    id: int
    tg_id: int
    tz: str
    locale: str
    notify_level: str
    created_at: datetime


class SettingsUpdate(BaseModel):
    tz: Optional[str] = None
    notify_level: Optional[Literal["light", "normal", "hard"]] = None
    sleep_window: Optional[dict] = Field(default=None)
