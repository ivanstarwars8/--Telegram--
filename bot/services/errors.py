"""Utilities for surfacing backend errors to Telegram users."""
from __future__ import annotations

from typing import Union

from aiogram.types import CallbackQuery, Message

from .api_client import BackendError

MessageLike = Union[Message, CallbackQuery]


async def notify_backend_error(target: MessageLike, exc: BackendError) -> None:
    """Send a user-friendly notification about backend issues."""

    text = exc.user_message
    if isinstance(target, CallbackQuery):
        if target.message:
            await target.message.answer(text)
        await target.answer(text, show_alert=True)
    else:
        await target.answer(text)
