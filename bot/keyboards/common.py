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


def plan_switch_target_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="На план A", callback_data="plan:switch_to:A"),
            InlineKeyboardButton(text="На план B", callback_data="plan:switch_to:B"),
        ],
        [InlineKeyboardButton(text="На план C", callback_data="plan:switch_to:C")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def plan_switch_reason_keyboard(level: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="Форс-мажор", callback_data=f"plan:switch_reason:{level}:force_majeure")],
        [InlineKeyboardButton(text="Энергия", callback_data=f"plan:switch_reason:{level}:energy")],
        [InlineKeyboardButton(text="Внешние дела", callback_data=f"plan:switch_reason:{level}:external")],
        [InlineKeyboardButton(text="Другое", callback_data=f"plan:switch_reason:{level}:other")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def plan_switch_policy_keyboard(level: str, reason: str) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text="Перенести всё",
                callback_data=f"plan:switch_policy:{level}:{reason}:carry_all",
            )
        ],
        [
            InlineKeyboardButton(
                text="Сжать до 50%",
                callback_data=f"plan:switch_policy:{level}:{reason}:compress_50",
            )
        ],
        [
            InlineKeyboardButton(
                text="Отменить рутину",
                callback_data=f"plan:switch_policy:{level}:{reason}:cancel_routine",
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def focus_session_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="Старт 25", callback_data="focus:25"),
            InlineKeyboardButton(text="Старт 50", callback_data="focus:50"),
            InlineKeyboardButton(text="Старт 90", callback_data="focus:90"),
        ],
        [
            InlineKeyboardButton(text="Готово", callback_data="task:done"),
            InlineKeyboardButton(text="Пропуск", callback_data="task:skip"),
        ],
        [
            InlineKeyboardButton(text="Следующая", callback_data="task:next"),
            InlineKeyboardButton(text="Список", callback_data="task:list"),
        ],
        [InlineKeyboardButton(text="Сменить план", callback_data="plan:switch")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
