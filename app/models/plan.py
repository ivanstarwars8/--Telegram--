"""Models for plan templates and day plans."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import Column, Date, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db.base import Base


class PlanTemplate(Base):
    __tablename__ = "plan_templates"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(128), nullable=False)
    level = Column(String(16), nullable=False)
    rules = Column(JSONB, nullable=False, default=dict)

    tasks = relationship("TemplateTask", back_populates="template", cascade="all, delete-orphan")


class TemplateTask(Base):
    __tablename__ = "template_tasks"

    id = Column(Integer, primary_key=True)
    template_id = Column(Integer, ForeignKey("plan_templates.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    type = Column(String(32), nullable=False)
    priority = Column(Integer, nullable=False, default=5)
    duration_min = Column(Integer, nullable=False, default=0)
    stream = Column(String(16), nullable=True)
    tags = Column(JSONB, nullable=True)
    active = Column(Integer, nullable=False, default=1)

    template = relationship("PlanTemplate", back_populates="tasks")


class Day(Base):
    __tablename__ = "days"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    selected_template_id = Column(Integer, ForeignKey("plan_templates.id"), nullable=True)
    active_plan_level = Column(String(16), nullable=True)
    switched_times = Column(JSONB, nullable=True)
    daily_note = Column(Text, nullable=True)

    template = relationship("PlanTemplate")


class DayTask(Base):
    __tablename__ = "day_tasks"

    id = Column(Integer, primary_key=True)
    day_id = Column(Integer, ForeignKey("days.id", ondelete="CASCADE"), nullable=False)
    template_task_id = Column(Integer, ForeignKey("template_tasks.id"), nullable=True)
    title = Column(String(255), nullable=False)
    planned_duration = Column(Integer, nullable=False, default=0)
    status = Column(String(16), nullable=False, default="todo")
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    skip_reason = Column(String(64), nullable=True)
    order_index = Column(Integer, nullable=False, default=0)


class FocusSession(Base):
    __tablename__ = "focus_sessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    day_id = Column(Integer, ForeignKey("days.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(Integer, ForeignKey("day_tasks.id", ondelete="SET NULL"), nullable=True)
    minutes = Column(Integer, nullable=False)
    started_at = Column(DateTime(timezone=True), default=dt.datetime.utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)


class DailyMetrics(Base):
    __tablename__ = "metrics_daily"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    done_count = Column(Integer, default=0)
    skip_count = Column(Integer, default=0)
    focus_minutes = Column(Integer, default=0)
    switches = Column(Integer, default=0)
    quality_score = Column(Integer, nullable=True)
    sleep_hours = Column(Integer, nullable=True)


class EventAudit(Base):
    __tablename__ = "events_audit"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type = Column(String(64), nullable=False)
    payload = Column(JSONB, nullable=False, default=dict)
    ts = Column(DateTime(timezone=True), default=dt.datetime.utcnow, nullable=False)
