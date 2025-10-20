"""Celery application."""
from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery("focusops")
celery_app.conf.update(settings.celery_config)
celery_app.autodiscover_tasks(["app.worker"])
