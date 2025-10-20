"""User model."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    tg_id = Column(Integer, unique=True, nullable=False, index=True)
    tz = Column(String(length=64), nullable=False, default="Europe/Moscow")
    locale = Column(String(length=8), nullable=False, default="ru")
    notify_level = Column(String(length=16), nullable=False, default="normal")
    sleep_window = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), default=dt.datetime.utcnow)
