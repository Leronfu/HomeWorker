"""Клавиатуры для Панели старосты (административной панели) и управления расписанием."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from bot.utils.schedule_helpers import WEEKDAY_SHORT


def get_admin_main_keyboard() -> InlineKeyboardMarkup:
    """Главное меню панели старосты."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📅 Управление расписанием",
                    callback_data="admin_sched_menu",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📚 Управление домашними заданиями",
                    callback_data="admin_hw_menu",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Закрыть панель",
                    callback_data="admin_close",
                )
            ],
        ]
    )


def get_admin_schedule_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню выбора режима управления расписанием."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📌 Редактировать текущую неделю",
                    callback_data="admin_sched_week:current",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔜 Редактировать следующую неделю",
                    callback_data="admin_sched_week:next",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⚡ Перенести следующую неделю в текущую",
                    callback_data="admin_sched_rollover_confirm",
                )
            ],
            [
                InlineKeyboardButton(
                    text="« Назад в панель старосты",
                    callback_data="admin_main_back",
                )
            ],
        ]
    )


def get_admin_schedule_days_keyboard(week_type: str) -> InlineKeyboardMarkup:
    """Клавиатура со списком дней недели (Пн-Сб) для редактирования."""
    buttons = [
        [
            InlineKeyboardButton(
                text=f"1️⃣ {WEEKDAY_SHORT[1]} (Понедельник)",
                callback_data=f"admin_sched_edit_day:{week_type}:1",
            ),
            InlineKeyboardButton(
                text=f"2️⃣ {WEEKDAY_SHORT[2]} (Вторник)",
                callback_data=f"admin_sched_edit_day:{week_type}:2",
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"3️⃣ {WEEKDAY_SHORT[3]} (Среда)",
                callback_data=f"admin_sched_edit_day:{week_type}:3",
            ),
            InlineKeyboardButton(
                text=f"4️⃣ {WEEKDAY_SHORT[4]} (Четверг)",
                callback_data=f"admin_sched_edit_day:{week_type}:4",
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"5️⃣ {WEEKDAY_SHORT[5]} (Пятница)",
                callback_data=f"admin_sched_edit_day:{week_type}:5",
            ),
            InlineKeyboardButton(
                text=f"6️⃣ {WEEKDAY_SHORT[6]} (Суббота)",
                callback_data=f"admin_sched_edit_day:{week_type}:6",
            ),
        ],
        [
            InlineKeyboardButton(
                text="👁 Предпросмотр недели",
                callback_data=f"admin_sched_preview:{week_type}",
            ),
            InlineKeyboardButton(
                text="🗑 Очистить неделю",
                callback_data=f"admin_sched_clear_week_confirm:{week_type}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="« Назад к выбору недели",
                callback_data="admin_sched_menu",
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_edit_day_keyboard(week_type: str, day_of_week: int) -> InlineKeyboardMarkup:
    """Клавиатура во время ввода текста для конкретного дня."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗑 Очистить этот день",
                    callback_data=f"admin_sched_clear_day:{week_type}:{day_of_week}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=f"admin_sched_cancel_edit:{week_type}",
                )
            ],
        ]
    )


def get_admin_confirm_rollover_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура подтверждения ручного переноса недели."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, перенести расписание",
                    callback_data="admin_sched_rollover_do",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="admin_sched_menu",
                )
            ],
        ]
    )


def get_admin_confirm_clear_week_keyboard(week_type: str) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения очистки всей недели."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, очистить все дни",
                    callback_data=f"admin_sched_clear_week_do:{week_type}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=f"admin_sched_week:{week_type}",
                )
            ],
        ]
    )
