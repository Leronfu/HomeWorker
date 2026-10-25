"""Клавиатуры (Reply и Inline) бота."""

from bot.keyboards.admin_kb import (
    get_admin_confirm_clear_week_keyboard,
    get_admin_confirm_rollover_keyboard,
    get_admin_edit_day_keyboard,
    get_admin_main_keyboard,
    get_admin_schedule_days_keyboard,
    get_admin_schedule_menu_keyboard,
)
from bot.keyboards.homework_kb import (
    get_admin_confirm_delete_hw_keyboard,
    get_admin_homework_detail_keyboard,
    get_admin_homework_list_keyboard,
    get_admin_homework_menu_keyboard,
    get_cancel_hw_keyboard,
    get_student_homework_keyboard,
    get_subjects_keyboard,
)
from bot.keyboards.reports_kb import (
    get_admin_batch_detail_keyboard,
    get_admin_batches_list_keyboard,
    get_admin_confirm_delete_batch_keyboard,
    get_admin_reports_menu_keyboard,
    get_cancel_reports_keyboard,
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
    "get_subjects_keyboard",
    "get_student_homework_keyboard",
    "get_admin_homework_menu_keyboard",
    "get_admin_homework_list_keyboard",
    "get_admin_homework_detail_keyboard",
    "get_admin_confirm_delete_hw_keyboard",
    "get_cancel_hw_keyboard",
    "get_admin_reports_menu_keyboard",
    "get_admin_batches_list_keyboard",
    "get_admin_batch_detail_keyboard",
    "get_admin_confirm_delete_batch_keyboard",
    "get_cancel_reports_keyboard",
]
