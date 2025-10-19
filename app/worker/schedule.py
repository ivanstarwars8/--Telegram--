"""Celery beat schedule for timezone aware jobs."""
from __future__ import annotations

from celery.schedules import crontab

from app.celery_app import celery_app
from app.worker import tasks

celery_app.conf.beat_schedule = {
    "recompute-metrics": {
        "task": "app.worker.tasks.recompute_metrics",
        "schedule": crontab(minute=0, hour="*/1"),
    },
    "dispatch-timeboxed": {
        "task": "app.worker.tasks.dispatch_timeboxed_notifications",
        "schedule": crontab(minute="*/5"),
    },
}
