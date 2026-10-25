"""Клавиатуры для раздела расписания студентов."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_schedule_view_keyboard(week_type: str = "current") -> InlineKeyboardMarkup:
    """Генерация Inline-кнопок для переключения между текущей и следующей неделей."""
    if week_type == "current":
        toggle_btn = InlineKeyboardButton(
            text="🔜 Следующая неделя",
            callback_data="sched_view:next",
        )
    else:
        toggle_btn = InlineKeyboardButton(
            text="🔙 Текущая неделя",
            callback_data="sched_view:current",
        )

    refresh_btn = InlineKeyboardButton(
        text="🔄 Обновить",
        callback_data=f"sched_refresh:{week_type}",
    )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [toggle_btn, refresh_btn],
        ]
    )
