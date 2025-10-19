"""FastAPI entrypoint."""
from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import day, sleep, stats, tasks, templates, users
from app.core.config import settings
from app.core.logging import setup_logging

setup_logging()

app = FastAPI(title=settings.app_name)

app.include_router(users.router)
app.include_router(day.router)
app.include_router(tasks.router)
app.include_router(stats.router)
app.include_router(templates.router)
app.include_router(sleep.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
