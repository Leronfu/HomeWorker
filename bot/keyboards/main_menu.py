"""Клавиатуры для открытия и навигации Telegram Mini App."""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from bot import config


def get_webapp_inline_keyboard(text: str = "📱 Открыть HomeWorker Mini App") -> InlineKeyboardMarkup:
    """Генерация инлайн-кнопки прямого открытия Telegram Mini App."""
    url = config.WEB_APP_URL or "http://localhost:8080"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=text,
                    web_app=WebAppInfo(url=url),
                )
            ]
        ]
    )


def get_main_menu_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Генерация постоянной Reply-клавиатуры Telegram с кнопкой Web App."""
    url = config.WEB_APP_URL or "http://localhost:8080"
    keyboard = [
        [
            KeyboardButton(
                text="📱 Открыть приложение",
                web_app=WebAppInfo(url=url),
            )
        ],
        [
            KeyboardButton(text="ℹ️ Помощь и статус бота"),
        ],
    ]

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        is_persistent=True,
    )
