"""Logging configuration leveraging structlog."""
from __future__ import annotations

import logging
from typing import Any, Dict

import structlog

from .config import settings


def setup_logging() -> None:
    """Configure structlog with JSON output."""
    timestamper = structlog.processors.TimeStamper(fmt="iso")

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            timestamper,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(level=logging.INFO)

    structlog.get_logger(__name__).info("logging.initialised", environment=settings.environment)
