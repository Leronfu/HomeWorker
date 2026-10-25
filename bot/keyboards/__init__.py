"""Клавиатуры (Reply и Inline) бота."""

from bot.keyboards.admin_kb import (
    get_admin_confirm_clear_week_keyboard,
    get_admin_confirm_rollover_keyboard,
    get_admin_edit_day_keyboard,
    get_admin_main_keyboard,
    get_admin_schedule_days_keyboard,
    get_admin_schedule_menu_keyboard,
)
from bot.keyboards.main_menu import get_main_menu_keyboard
from bot.keyboards.schedule_kb import get_schedule_view_keyboard

__all__ = [
    "get_main_menu_keyboard",
    "get_schedule_view_keyboard",
    "get_admin_main_keyboard",
    "get_admin_schedule_menu_keyboard",
    "get_admin_schedule_days_keyboard",
    "get_admin_edit_day_keyboard",
    "get_admin_confirm_rollover_keyboard",
    "get_admin_confirm_clear_week_keyboard",
]
