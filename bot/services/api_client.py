"""HTTP client for interacting with backend API."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)


class BackendError(RuntimeError):
    """Raised when backend API requests fail."""

    def __init__(self, message: str, *, user_message: str | None = None) -> None:
        super().__init__(message)
        self.user_message = user_message or "Сервис временно недоступен, попробуй позже."


@asynccontextmanager
async def get_client() -> httpx.AsyncClient:
    async with httpx.AsyncClient(base_url=settings.api_base_url, timeout=10.0) as client:
        yield client


async def _request(
    method: str,
    path: str,
    tg_id: int,
    *,
    params: Optional[dict[str, Any]] = None,
    json: Optional[dict[str, Any]] = None,
) -> Dict[str, Any]:
    headers = {"X-Telegram-Id": str(tg_id)}
    try:
        async with get_client() as client:
            response = await client.request(method, path, params=params, json=json, headers=headers)
            response.raise_for_status()
            return response.json() if response.content else {}
    except httpx.HTTPStatusError as exc:  # pragma: no cover - network edge cases
        detail: str | None = None
        try:
            payload = exc.response.json()
            if isinstance(payload, dict):
                raw_detail = payload.get("detail")
                detail = raw_detail if isinstance(raw_detail, str) else None
        except Exception:  # noqa: BLE001
            detail = exc.response.text if exc.response is not None else None
        logger.warning(
            "bot.api.http_status_error",
            path=path,
            status=exc.response.status_code if exc.response else None,
            detail=detail,
        )
        user_message = detail or "Ядро вернуло ошибку. Попробуй позже."
        raise BackendError(f"HTTP {exc.response.status_code} for {path}", user_message=user_message) from exc
    except httpx.HTTPError as exc:  # pragma: no cover - network edge cases
        logger.error("bot.api.http_error", path=path, error=str(exc))
        raise BackendError("Не могу достучаться до ядра. Попробуй позже.") from exc


async def api_get(path: str, tg_id: int, params: Optional[dict[str, Any]] = None) -> Dict[str, Any]:
    return await _request("GET", path, tg_id, params=params)


async def api_post(path: str, tg_id: int, json: Optional[dict[str, Any]] = None) -> Dict[str, Any]:
    return await _request("POST", path, tg_id, json=json)
