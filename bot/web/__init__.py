"""Модуль веб-сервера и REST API для Telegram Mini App."""

from bot.web.auth import generate_mock_init_data, validate_telegram_init_data
from bot.web.server import create_web_app, start_web_server

__all__ = [
    "validate_telegram_init_data",
    "generate_mock_init_data",
    "create_web_app",
    "start_web_server",
]
