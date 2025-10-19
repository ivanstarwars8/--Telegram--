"""Inline keyboards."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def plan_choice_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="План A", callback_data="plan:A")],
        [InlineKeyboardButton(text="План B", callback_data="plan:B")],
        [InlineKeyboardButton(text="План C", callback_data="plan:C")],
        [InlineKeyboardButton(text="Другой", callback_data="plan:custom")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def focus_session_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="Старт 25", callback_data="focus:25")],
        [InlineKeyboardButton(text="Старт 50", callback_data="focus:50")],
        [InlineKeyboardButton(text="Старт 90", callback_data="focus:90")],
        [InlineKeyboardButton(text="Готово", callback_data="task:done")],
        [InlineKeyboardButton(text="Пропуск", callback_data="task:skip")],
        [InlineKeyboardButton(text="Сменить план", callback_data="plan:switch")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
