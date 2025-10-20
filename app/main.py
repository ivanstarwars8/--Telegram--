"""FastAPI entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app.api import routes as api_routes
from app.core.config import settings
from app.core.logging import setup_logging
from app.db.base import Base
from app.db.session import engine

setup_logging()

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.auto_create_schema:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        logger.info("api.schema.ensure")
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.include_router(api_routes.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
