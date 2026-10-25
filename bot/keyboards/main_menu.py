"""Клавиатура Главного меню."""

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def get_main_menu_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Генерация клавиатуры Главного меню.
    
    Для студентов доступны кнопки:
    - 📅 Расписание
    - 📚 Домашнее задание
    - 🎤 Доклады
    
    Для администраторов (старосты) дополнительно доступна:
    - ⚙️ Панель старосты
    """
    keyboard = [
        [
            KeyboardButton(text="📅 Расписание"),
            KeyboardButton(text="📚 Домашнее задание"),
        ],
        [
            KeyboardButton(text="🎤 Доклады"),
        ],
    ]

    if is_admin:
        keyboard.append([KeyboardButton(text="⚙️ Панель старосты")])

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        is_persistent=True,
    )
