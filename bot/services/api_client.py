"""HTTP client for interacting with backend API."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings


@asynccontextmanager
async def get_client() -> httpx.AsyncClient:
    async with httpx.AsyncClient(base_url=settings.api_base_url, timeout=10.0) as client:
        yield client


async def api_get(path: str, tg_id: int, params: Optional[dict[str, Any]] = None) -> Dict[str, Any]:
    async with get_client() as client:
        response = await client.get(path, params=params, headers={"X-Telegram-Id": str(tg_id)})
        response.raise_for_status()
        return response.json()


async def api_post(path: str, tg_id: int, json: Optional[dict[str, Any]] = None) -> Dict[str, Any]:
    async with get_client() as client:
        response = await client.post(path, json=json, headers={"X-Telegram-Id": str(tg_id)})
        response.raise_for_status()
        return response.json()
